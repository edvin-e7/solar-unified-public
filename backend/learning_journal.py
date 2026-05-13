"""Self-teaching journal — append-only log of phase outcomes + auto-generated lessons.

Every completed phase (success OR error) calls `record()`. The journal writes to
`prompts/learned/journal.jsonl` and regenerates `prompts/learned/summary.md` —
a Markdown digest Claude reads on the next development session.

This is how the system teaches itself: failed patterns become don'ts, successful
patterns become reusable prompts in `prompts/learned/`.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Literal

_log = logging.getLogger(__name__)
if not _log.handlers:
    _handler = logging.StreamHandler(sys.stderr)
    _handler.setFormatter(logging.Formatter("%(asctime)s [%(levelname)s] %(name)s: %(message)s"))
    _log.addHandler(_handler)
    _log.setLevel(logging.INFO)

# CLAUDE.md rule 6: failed/error outcomes MUST have metadata.error_type. If a
# caller forgets, we WARN once + default to this sentinel so pattern_detector
# and antipattern-grouping in run_autonomous_cycle still partition cleanly.
_UNSPECIFIED_ERROR_TYPE = "unspecified"
_FAILED_OUTCOMES = frozenset({"failed", "error"})

LEARNED_DIR = Path(__file__).parent / "prompts" / "learned"
LEARNED_DIR.mkdir(parents=True, exist_ok=True)
JOURNAL = LEARNED_DIR / "journal.jsonl"
SUMMARY = LEARNED_DIR / "summary.md"


Outcome = Literal["passed", "failed", "error", "no_op"]


# Fas 1.d — PII filter applied to every record() before write. Pattern
# language: Swedish phone formats (070-1234567, +46 70 123 45 67, 0701234567)
# and email addresses. Names are NOT auto-redacted (too noisy); use
# redact_lines() for those. The filter is intentionally conservative —
# false positives on phone-shaped numeric data (e.g. order ids) are
# preferable to PII leaks per CLAUDE.md rule 10.
_PHONE_RE = re.compile(
    r"(?<!\d)(?:\+46[\s-]?|0)\d[\d\s-]{6,12}\d(?!\d)"
)
_EMAIL_RE = re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b")


def _sanitize_pii(text: str | None) -> str | None:
    if not text:
        return text
    out = _EMAIL_RE.sub("<EMAIL_REDACTED>", text)
    out = _PHONE_RE.sub("<PHONE_REDACTED>", out)
    return out


def _sanitize_value(value: Any) -> Any:
    if isinstance(value, str):
        return _sanitize_pii(value)
    if isinstance(value, dict):
        return {k: _sanitize_value(v) for k, v in value.items()}
    if isinstance(value, list):
        return [_sanitize_value(v) for v in value]
    return value


def record(
    phase: str,
    outcome: Outcome,
    lesson: str,
    *,
    files: list[str] | None = None,
    error: str | None = None,
    metadata: dict[str, Any] | None = None,
) -> None:
    # Deferred import avoids circular dependency (structured_log → no deps here,
    # but error_logger → learning_journal → structured_log is cleanest as lazy).
    from services.structured_log import append_jsonl_sync

    # CLAUDE.md rule 6 enforcement — failed/error MUST include metadata.error_type
    # for pattern_detector + autonomous-cycle antipattern grouping. If a caller
    # forgets, log a WARN and default to "unspecified" so the field is never
    # empty. Fixes docs/BUGS.md Bug 8 (15 consecutive 2026-04-21 entries with
    # empty err= rendered the journal unusable for diagnosis).
    metadata = dict(metadata or {})
    if outcome in _FAILED_OUTCOMES:
        et = metadata.get("error_type")
        if et is None or (isinstance(et, str) and not et.strip()):
            _log.warning(
                "journal.record(phase=%s, outcome=%s) missing metadata.error_type — "
                "defaulting to %r. Callers should pass a real error_type per CLAUDE.md rule 6.",
                phase,
                outcome,
                _UNSPECIFIED_ERROR_TYPE,
            )
            metadata["error_type"] = _UNSPECIFIED_ERROR_TYPE

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "phase": phase,
        "outcome": outcome,
        "lesson": _sanitize_pii(lesson),
        "files": files or [],
        "error": _sanitize_pii(error),
        "metadata": _sanitize_value(metadata),
    }
    append_jsonl_sync(JOURNAL, entry)
    _regenerate_summary()


def _regenerate_summary() -> None:
    if not JOURNAL.exists():
        return
    entries: list[dict[str, Any]] = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                entries.append(json.loads(line))
            except json.JSONDecodeError:
                continue

    passed = [e for e in entries if e["outcome"] == "passed"]
    failed = [e for e in entries if e["outcome"] in ("failed", "error")]

    lines = [
        "---",
        "name: learned/summary",
        "version: auto",
        "audience: claude",
        "description: Rolling digest of what works and what doesn't in this codebase.",
        "---",
        "",
        f"# Lessons journal ({len(entries)} entries · updated {datetime.now(UTC).isoformat()})",
        "",
        "## ✅ Patterns that worked",
        "",
    ]
    for e in passed[-20:]:
        lines.append(f"- **{e['phase']}** — {e['lesson']}")
    lines += ["", "## ⚠ Patterns that failed — don't repeat", ""]
    for e in failed[-20:]:
        suffix = f" _(error: {e['error']})_" if e.get("error") else ""
        lines.append(f"- **{e['phase']}** — {e['lesson']}{suffix}")

    SUMMARY.write_text("\n".join(lines) + "\n", encoding="utf-8")


def entries() -> list[dict[str, Any]]:
    if not JOURNAL.exists():
        return []
    result = []
    for line in JOURNAL.read_text(encoding="utf-8").splitlines():
        if line.strip():
            try:
                result.append(json.loads(line))
            except json.JSONDecodeError:
                continue
    return result


def redact_lines(replacements: dict[str, str]) -> dict[str, int]:
    """Redact PII (or any literal substring) across the journal in place.

    Surgical substring replacement on the raw JSONL — preserves entry order,
    timestamps, and surrounding context (e.g. a verifier's critique still
    reads correctly with `<NAME_REDACTED>` replacing the leaked name). The
    file is rewritten atomically via a temp file + replace.

    This is the *only* sanctioned way to mutate journal.jsonl after the
    fact; the PreToolUse hook in .claude/settings.json blocks Edit/Write,
    which is correct for Claude's editing surface — programmatic redaction
    via this function is intentional. CLAUDE.md rule 10 (PII is first-class)
    overrides strict append-only when a leak has already happened.

    Args:
        replacements: literal `pattern → replacement` substring map. Empty
            patterns are rejected. Patterns are matched on raw bytes after
            decoding the file as UTF-8 — no regex, no normalization.

    Returns:
        Per-pattern replacement counts.
    """
    if not replacements:
        return {}
    if any(not p for p in replacements):
        raise ValueError("redact_lines: empty pattern not allowed")
    if not JOURNAL.exists():
        return dict.fromkeys(replacements, 0)

    raw = JOURNAL.read_text(encoding="utf-8")
    counts: dict[str, int] = {}
    for pattern, replacement in replacements.items():
        counts[pattern] = raw.count(pattern)
        raw = raw.replace(pattern, replacement)

    tmp = JOURNAL.with_suffix(JOURNAL.suffix + ".redact-tmp")
    tmp.write_text(raw, encoding="utf-8")
    tmp.replace(JOURNAL)

    # Audit trail must NOT reproduce the patterns it just removed (that
    # would re-introduce the PII the caller just paid to delete). Hash
    # each pattern; caller still has the originals if they need to
    # re-run; journal stays clean.
    hashed = {hashlib.sha256(p.encode("utf-8")).hexdigest()[:12]: counts[p] for p in replacements}
    record(
        phase="journal-redaction",
        outcome="passed",
        lesson=f"Redacted {sum(counts.values())} PII substring(s) across {sum(1 for v in counts.values() if v)} pattern(s)",
        metadata={"replacements_by_hash": hashed, "patterns": len(replacements)},
    )
    return counts
