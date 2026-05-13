"""Issue ledger — persistent, cross-session bug + fix-attempt tracker.

The problem this solves: every session was re-trying the same failed fix for
the same bug because nothing remembered what had already been tried. The
52x "Enrichment stub returning empty dict" loop is the canonical example —
the improvement suggester kept proposing a fix that CoVe kept rejecting at
50% confidence, session after session.

The ledger is the structured memory that breaks that loop.

Model
=====
- **Issue**: a bug / pattern, identified by a stable `key` (hash of
  error_type + target). Carries: title, first_seen, last_seen, occurrences,
  status (open | in_progress | resolved | wontfix), tags, attempts.
- **Attempt**: one recorded fix attempt on an issue. Carries: ts, hypothesis,
  change_summary, outcome (success | failed | rejected_by_cove | blocked),
  evidence (journal/prompts-log refs), rationale_for_next.

Workflow (for any session, human or agent)
==========================================
1. Before proposing a fix, call `find_issue(error_type, target)` — if an open
   issue exists with prior attempts, READ them first. Do not repeat a rejected
   hypothesis unless the precondition that made it fail has changed.
2. Open or reopen the issue via `open_issue()`. Get back its key.
3. Log each concrete fix attempt via `log_attempt()` — hypothesis, what you
   changed, what happened. Required fields, not optional.
4. On verified success, call `resolve_issue()` with the resolution summary and
   evidence. Future sessions see `status="resolved"` and skip.
5. If an issue recurs after "resolved", `reopen_issue()` — the old attempts
   stay visible so we don't retry them blindly.

Storage
=======
JSON file at `prompts/learned/issue_ledger.json` — append-friendly, grep-able,
survives git (intentionally committed so the knowledge is shared).
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import threading
from datetime import UTC, datetime
from typing import Any, Literal

from learning_journal import LEARNED_DIR
from services.structured_log import cleanup_stale_tmp, write_json_atomic

log = logging.getLogger(__name__)

LEDGER_PATH = LEARNED_DIR / "issue_ledger.json"
_LOCK = threading.Lock()

IssueStatus = Literal["open", "in_progress", "resolved", "wontfix"]
AttemptOutcome = Literal[
    "success", "passed", "failed", "rejected_by_cove", "rejected_by_design", "blocked", "partial"
]

# Purge any stale .tmp left by a crashed prior write before first read.
cleanup_stale_tmp(LEDGER_PATH)


def _now() -> str:
    return datetime.now(UTC).isoformat()


def _issue_key(error_type: str, target: str) -> str:
    """Stable identifier — same (error_type, target) always maps to same key."""
    raw = f"{error_type.strip().lower()}|{target.strip().lower()}"
    return hashlib.sha1(raw.encode("utf-8")).hexdigest()[:12]


def _load() -> dict[str, Any]:
    if not LEDGER_PATH.exists():
        return {"version": 1, "issues": {}}
    try:
        return json.loads(LEDGER_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        log.error("issue_ledger unreadable, starting fresh: %s", exc)
        return {"version": 1, "issues": {}}


def _save(data: dict[str, Any]) -> None:
    write_json_atomic(LEDGER_PATH, data)


def find_issue(error_type: str, target: str) -> dict[str, Any] | None:
    """Return the issue for this (error_type, target), or None. Call this BEFORE fixing."""
    key = _issue_key(error_type, target)
    with _LOCK:
        data = _load()
        return data["issues"].get(key)


def all_open() -> list[dict[str, Any]]:
    """All currently-open issues, oldest first. For session-start review."""
    with _LOCK:
        data = _load()
        issues = [i for i in data["issues"].values() if i["status"] in ("open", "in_progress")]
        return sorted(issues, key=lambda i: i["first_seen"])


def recent(limit: int = 20) -> list[dict[str, Any]]:
    """Most-recently-touched issues across all statuses."""
    with _LOCK:
        data = _load()
        issues = list(data["issues"].values())
        return sorted(issues, key=lambda i: i["last_seen"], reverse=True)[:limit]


def open_issue(
    *,
    error_type: str,
    target: str,
    title: str,
    tags: list[str] | None = None,
    evidence: dict[str, Any] | None = None,
) -> str:
    """Open (or touch) an issue. Returns the stable key.

    Idempotent — calling with the same (error_type, target) updates last_seen
    and increments occurrences instead of duplicating.
    """
    key = _issue_key(error_type, target)
    now = _now()
    with _LOCK:
        data = _load()
        existing = data["issues"].get(key)
        if existing:
            existing["last_seen"] = now
            existing["occurrences"] = existing.get("occurrences", 1) + 1
            if existing["status"] == "resolved":
                existing["status"] = "open"
                existing["reopened_at"] = now
        else:
            data["issues"][key] = {
                "key": key,
                "error_type": error_type,
                "target": target,
                "title": title,
                "tags": tags or [],
                "first_seen": now,
                "last_seen": now,
                "occurrences": 1,
                "status": "open",
                "attempts": [],
                "resolution": None,
                "evidence": evidence or {},
            }
        _save(data)
    return key


def log_attempt(
    *,
    key: str,
    hypothesis: str,
    change_summary: str,
    outcome: AttemptOutcome,
    rationale_for_next: str | None = None,
    evidence: dict[str, Any] | None = None,
    author: str = "claude",
) -> None:
    """Record a concrete fix attempt. REQUIRED before considering the issue touched."""
    now = _now()
    with _LOCK:
        data = _load()
        issue = data["issues"].get(key)
        if not issue:
            log.warning("log_attempt: unknown issue key %s", key)
            return
        issue["attempts"].append(
            {
                "ts": now,
                "author": author,
                "hypothesis": hypothesis,
                "change_summary": change_summary,
                "outcome": outcome,
                "rationale_for_next": rationale_for_next,
                "evidence": evidence or {},
            }
        )
        issue["last_seen"] = now
        if outcome == "success":
            issue["status"] = "resolved"
            issue["resolution"] = {"ts": now, "summary": change_summary, "evidence": evidence or {}}
        elif issue["status"] == "open":
            issue["status"] = "in_progress"
        _save(data)


def resolve_issue(
    *,
    key: str,
    resolution_summary: str,
    evidence: dict[str, Any] | None = None,
) -> None:
    """Mark an issue resolved. Use this for the final success log — it's explicit."""
    now = _now()
    with _LOCK:
        data = _load()
        issue = data["issues"].get(key)
        if not issue:
            log.warning("resolve_issue: unknown issue key %s", key)
            return
        issue["status"] = "resolved"
        issue["last_seen"] = now
        issue["resolution"] = {"ts": now, "summary": resolution_summary, "evidence": evidence or {}}
        _save(data)


def reopen_issue(key: str, reason: str) -> None:
    """Reopen a previously-resolved issue. Keeps old attempts visible."""
    now = _now()
    with _LOCK:
        data = _load()
        issue = data["issues"].get(key)
        if not issue:
            log.warning("reopen_issue: unknown issue key %s", key)
            return
        issue["status"] = "open"
        issue["last_seen"] = now
        issue["reopened_at"] = now
        issue["reopen_reason"] = reason
        _save(data)


def prior_attempts(error_type: str, target: str) -> list[dict[str, Any]]:
    """Convenience: every past attempt for this (error_type, target). Call before hypothesizing."""
    issue = find_issue(error_type, target)
    return list(issue["attempts"]) if issue else []


_WORD_RE = re.compile(r"[a-z0-9åäö]+")
_STOPWORDS = frozenset({
    "the", "a", "an", "to", "of", "in", "on", "at", "by", "for", "with",
    "and", "or", "but", "is", "are", "be", "was", "were", "been", "being",
    "use", "using", "used", "add", "adding", "added", "try", "trying",
    "this", "that", "those", "these", "i", "we", "it", "its",
    "och", "eller", "på", "av", "en", "ett", "till", "för", "ska",
    "via", "som", "den", "det", "är", "att", "inte", "ej",
})


def _tokenize_hypothesis(text: str) -> set[str]:
    """Lowercase, split on non-word, drop stopwords, drop 1-char tokens."""
    toks = _WORD_RE.findall(text.lower())
    return {t for t in toks if len(t) > 1 and t not in _STOPWORDS}


def _jaccard(a: set[str], b: set[str]) -> float:
    if not a or not b:
        return 0.0
    inter = len(a & b)
    union = len(a | b)
    return inter / union if union else 0.0


def _containment(prior: set[str], new: set[str]) -> float:
    """Fraction of prior's tokens that appear in new. 1.0 = prior ⊆ new.

    Anti-brainrot case this targets: prior hypothesis is short ("add low-light
    section to prompt"), new hypothesis restates the same idea with more words
    ("add section for low-light: image dim focus edges roof lines zoom …").
    Jaccard dilutes to ~0.5 because new has many extra tokens, but containment
    is 1.0 — same idea, more verbose. False-positive risk for very short priors
    is mitigated by requiring prior ≥ 3 meaningful tokens.
    """
    if len(prior) < 3 or not new:
        return 0.0
    return len(prior & new) / len(prior)


def similar_attempts(
    error_type: str,
    target: str,
    hypothesis: str,
    *,
    threshold: float = 0.6,
    include_outcomes: tuple[str, ...] = ("failed", "rejected_by_cove", "rejected_by_design"),
) -> list[dict[str, Any]]:
    """Return prior attempts whose hypothesis is ≥ `threshold` similar to the new one.

    Similarity = max(Jaccard, containment_of_prior_in_new). Containment catches
    "same idea, more words" paraphrases that Jaccard misses. Only rejected/failed
    priors are considered by default — a prior SUCCESS doesn't block a new
    attempt, it's already captured in the resolution.

    Advisory, not enforcement — caller decides whether to proceed.
    """
    new_toks = _tokenize_hypothesis(hypothesis)
    if not new_toks:
        return []
    out: list[dict[str, Any]] = []
    for att in prior_attempts(error_type, target):
        if att.get("outcome") not in include_outcomes:
            continue
        prev_toks = _tokenize_hypothesis(att.get("hypothesis", ""))
        jac = _jaccard(new_toks, prev_toks)
        cont = _containment(prev_toks, new_toks)
        score = max(jac, cont)
        if score >= threshold:
            out.append(
                {
                    **att,
                    "_similarity": round(score, 3),
                    "_jaccard": round(jac, 3),
                    "_containment": round(cont, 3),
                }
            )
    out.sort(key=lambda a: a["_similarity"], reverse=True)
    return out


def has_already_tried(error_type: str, target: str, hypothesis: str) -> bool:
    """Backwards-compat: True if at least one prior rejected attempt has
    Jaccard similarity ≥ 0.6 against `hypothesis`. Prefer `similar_attempts`
    for paraphrase-aware checks; this keeps the boolean short-circuit ergonomic
    for agents that only need a go/no-go signal.
    """
    return bool(similar_attempts(error_type, target, hypothesis))


def summary() -> dict[str, Any]:
    """High-level counts for dashboards / session-start triage."""
    with _LOCK:
        data = _load()
        issues = list(data["issues"].values())
    by_status: dict[str, int] = {}
    for i in issues:
        by_status[i["status"]] = by_status.get(i["status"], 0) + 1
    top_open = sorted(
        [i for i in issues if i["status"] in ("open", "in_progress")],
        key=lambda i: i.get("occurrences", 1),
        reverse=True,
    )[:5]
    return {
        "total": len(issues),
        "by_status": by_status,
        "top_open": [
            {"key": i["key"], "title": i["title"], "occurrences": i.get("occurrences", 1)}
            for i in top_open
        ],
    }
