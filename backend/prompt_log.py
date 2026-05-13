"""Prompt log — append-only record of every LLM prompt + response.

Purpose: let us (or the agent itself) review what was asked and what came back.
When a suggestion fails or a detection misfires, the prompt log is the primary
evidence for why. Feed the log back into the improvement loop to find the
actual fix instead of brute-forcing the same prompt.

Shape per line (JSONL):
    {
      "ts": "...",
      "model": "gemini-2.5-flash",
      "phase": "detection" | "cove-verify" | "scoring" | ...,
      "prompt": "...",
      "response": "...",         # or null if error
      "response_kind": "text" | "json" | "error",
      "error": "...",            # if response_kind == "error"
      "latency_ms": 1234,
      "image_attached": true | false,
      "metadata": {...}
    }

Keep the whole prompt — truncation destroys the signal we need for diagnosis.
If size becomes a problem later, rotate by date, not by truncation.
"""

from __future__ import annotations

import hashlib
import json
import logging
import re
from datetime import UTC, datetime
from typing import Any

from learning_journal import LEARNED_DIR
from services.structured_log import append_jsonl_sync

log = logging.getLogger(__name__)

PROMPTS_LOG = LEARNED_DIR / "prompts_log.jsonl"


# --- PII redaction (CLAUDE.md rule 10) ------------------------------------
# Mask Swedish phone numbers, 10-digit personnummer, email-likes, and any
# metadata field named name/phone/address/personnummer/email. Hash is stable
# so downstream dedup still works without plaintext.

# Swedish phone patterns. Two alts:
#   - domestic: starts with 0, total 7-12 digits with separators
#   - international: +46 / 0046 prefix, digit-seq without leading 0
# Residual: free-text NAMES not caught (would need NER). Callers must not
# stuff raw prospect names into prompt/response text — use IDs/hashes instead.
_PHONE_RE = re.compile(
    r"(?:(?:\+46|0046)[\s-]?\d[\d\s-]{5,11}\d|\b0\d[\d\s-]{5,11}\d)\b"
)
_PN_RE = re.compile(r"\b(\d{6,8}[-\s]?\d{4})\b")
_EMAIL_RE = re.compile(r"\b[\w.+-]+@[\w-]+\.[\w.-]+\b")
_PII_KEYS = {"name", "phone", "telephone", "address", "personnummer", "email", "pn"}


def _hash8(s: str) -> str:
    return hashlib.sha1(s.encode("utf-8")).hexdigest()[:8]


def _mask_in_text(s: str) -> str:
    s = _PHONE_RE.sub(lambda m: f"<phone:{_hash8(m.group(0))}>", s)
    s = _PN_RE.sub(lambda m: f"<pn:{_hash8(m.group(0))}>", s)
    s = _EMAIL_RE.sub(lambda m: f"<email:{_hash8(m.group(0))}>", s)
    return s


def _mask_metadata(meta: dict) -> dict:
    out: dict[str, Any] = {}
    for k, v in meta.items():
        if k.lower() in _PII_KEYS and isinstance(v, str) and v:
            out[k] = f"<{k}:{_hash8(v)}>"
        elif isinstance(v, dict):
            out[k] = _mask_metadata(v)
        elif isinstance(v, str):
            out[k] = _mask_in_text(v)
        else:
            out[k] = v
    return out


def _redact_prompt_entry(entry: dict) -> dict:
    """Pure PII-redact for a prompt_log record. Hashes preserve dedup."""
    red = dict(entry)
    if isinstance(red.get("prompt"), str):
        red["prompt"] = _mask_in_text(red["prompt"])
    if isinstance(red.get("response"), str):
        red["response"] = _mask_in_text(red["response"])
    if isinstance(red.get("metadata"), dict):
        red["metadata"] = _mask_metadata(red["metadata"])
    return red


def record_prompt(
    *,
    model: str,
    phase: str,
    prompt: str,
    response: str | None,
    response_kind: str,
    latency_ms: int,
    error: str | None = None,
    image_attached: bool = False,
    metadata: dict[str, Any] | None = None,
) -> None:
    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "model": model,
        "phase": phase,
        "prompt": prompt,
        "response": response,
        "response_kind": response_kind,
        "error": error,
        "latency_ms": latency_ms,
        "image_attached": image_attached,
        "metadata": metadata or {},
    }
    try:
        append_jsonl_sync(PROMPTS_LOG, entry, redact=_redact_prompt_entry)
    except OSError:
        log.exception("prompts_log.jsonl write failed")


def tail(limit: int = 50) -> list[dict[str, Any]]:
    if not PROMPTS_LOG.exists():
        return []
    lines = PROMPTS_LOG.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def errors_only(limit: int = 100) -> list[dict[str, Any]]:
    """Last `limit` prompt-log entries that errored. For debugging failed LLM calls."""
    return [e for e in tail(limit * 4) if e.get("response_kind") == "error"][-limit:]


def by_phase(phase: str, limit: int = 50) -> list[dict[str, Any]]:
    return [e for e in tail(limit * 4) if e.get("phase") == phase][-limit:]
