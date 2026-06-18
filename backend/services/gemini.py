"""Gemini client wrapper — single entry point for text + vision calls.

Keeps the google-genai SDK import in one place so we can swap providers later.
Public `generate`/`generate_json` are async and offload the blocking SDK call
via `asyncio.to_thread`, so agents can `await` them without stalling the event
loop. Sync variants are kept as `_generate_sync`/`_generate_json_sync` for
synchronous call sites (e.g. scripts).
"""

from __future__ import annotations

import asyncio
import base64
import functools
import json
import logging
import os
import random
import re
import time
from typing import Any

import httpx
from prompt_log import record_prompt

try:
    from google import genai
    from google.genai import types
except ImportError:  # pragma: no cover
    genai = None  # type: ignore
    types = None  # type: ignore


_OLLAMA_DEFAULT_TEXT_MODEL = "qwen2.5:1.5b"
_OLLAMA_DEFAULT_VISION_MODEL = "moondream"

_log = logging.getLogger(__name__)


class GeminiQuotaExceeded(RuntimeError):
    """Gemini API quota exhausted (429 RESOURCE_EXHAUSTED).

    Distinguished from generic RuntimeError so schedulers in main.py and
    executors/orchestrator.py can decide to (a) defer to next tick,
    (b) fall back to a local model, or (c) journal + skip — without re-trying
    on every loop iteration. Fixes docs/BUGS.md Bug 3 silent stall on
    Gemini free-tier cap.
    """

    def __init__(self, message: str, *, attempts: int, last_error: Exception | None = None):
        super().__init__(message)
        self.attempts = attempts
        self.last_error = last_error


# Retry policy — exponential backoff with full jitter. Env-tunable.
_RETRY_MAX_ATTEMPTS = int(os.getenv("GEMINI_RETRY_MAX_ATTEMPTS", "3"))
_RETRY_BASE_S = float(os.getenv("GEMINI_RETRY_BASE_S", "1.0"))
_RETRY_MAX_DELAY_S = float(os.getenv("GEMINI_RETRY_MAX_DELAY_S", "16.0"))


def _is_rate_limit_error(exc: BaseException) -> bool:
    """Detect Gemini 429 / RESOURCE_EXHAUSTED across SDK versions.

    google-genai doesn't expose a stable typed quota exception — match on
    message + common attributes. Conservative on purpose: false negatives are
    harmless (we still raise GeminiQuotaExceeded on terminal failure).
    """
    msg = str(exc).lower()
    status = getattr(exc, "status_code", None) or getattr(exc, "code", None)
    if status == 429:
        return True
    if "429" in msg:
        return True
    if "resource_exhausted" in msg or "resource exhausted" in msg:
        return True
    if "quota" in msg and ("exceed" in msg or "limit" in msg):
        return True
    return bool("rate limit" in msg or "rate-limit" in msg or "rate_limit" in msg)


def _backoff_delay_seconds(attempt: int) -> float:
    """Exponential backoff with full jitter. `attempt` is 1-indexed."""
    capped = min(_RETRY_MAX_DELAY_S, _RETRY_BASE_S * (2 ** (attempt - 1)))
    return random.uniform(0, capped)


def _provider() -> str:
    # Default = "ollama" (free, local). Explicit opt-in required for "gemini"
    # via LLM_PROVIDER=gemini + GEMINI_API_KEY + ALLOW_EXTERNAL_LLM=1.
    # Rationale: prevents accidental Gemini billing when an env var slips
    # the safety gate (.env.example documents the trade-offs). Matches the
    # zero-cost-workflow described in CLAUDE.md.
    return os.getenv("LLM_PROVIDER", "ollama").lower()


def _ollama_model(image_bytes: bytes | None) -> str:
    if image_bytes is not None:
        return os.getenv("OLLAMA_VISION_MODEL", _OLLAMA_DEFAULT_VISION_MODEL)
    return os.getenv("OLLAMA_TEXT_MODEL", _OLLAMA_DEFAULT_TEXT_MODEL)


def _resolved_model(base_model: str, image_bytes: bytes | None) -> str:
    """Model name to record in prompt_log — actual provider when routed locally."""
    if _provider() == "ollama":
        return f"ollama:{_ollama_model(image_bytes)}"
    return base_model


@functools.lru_cache(maxsize=1)
def _client() -> Any:
    if os.getenv("ALLOW_EXTERNAL_LLM", "0") != "1":
        raise RuntimeError(
            "External LLM APIs disabled. Set ALLOW_EXTERNAL_LLM=1 in .env to enable "
            "Gemini calls (AI Studio keys are free tier; Google Cloud keys may bill)."
        )
    if genai is None:
        raise RuntimeError("google-genai not installed: pip install google-genai")
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    return genai.Client(api_key=key)


def _ollama_generate_sync(prompt: str, image_bytes: bytes | None) -> str:
    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    payload: dict[str, Any] = {
        "model": _ollama_model(image_bytes),
        "prompt": prompt,
        "stream": False,
    }
    if image_bytes is not None:
        payload["images"] = [base64.b64encode(image_bytes).decode()]
    # 300s — qwen2.5/moondream cold-load on a Chromebook can take ~20-30s
    # before the first token; subsequent calls are <5s. Generous timeout
    # avoids httpx.ReadTimeout on the first call after the model has been
    # idle long enough for Ollama to unload it.
    resp = httpx.post(f"{host}/api/generate", json=payload, timeout=300.0)
    resp.raise_for_status()
    return resp.json().get("response", "") or ""


def _generate_sync_no_retry(
    prompt: str, *, model: str = "gemini-2.5-flash", image_bytes: bytes | None = None
) -> str:
    """Single Gemini call, no retry. Visible only to the retry wrapper + tests."""
    if _provider() == "ollama":
        return _ollama_generate_sync(prompt, image_bytes)
    contents: list[Any] = [prompt]
    if image_bytes is not None:
        contents.append(types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"))
    resp = _client().models.generate_content(model=model, contents=contents)
    return resp.text or ""


def _generate_sync(
    prompt: str, *, model: str = "gemini-2.5-flash", image_bytes: bytes | None = None
) -> str:
    """Gemini call with 429-aware retry.

    On non-rate-limit exceptions: raise immediately (auth errors, invalid
    args, network glitches are not improved by retrying).
    On rate-limit exceptions: retry up to GEMINI_RETRY_MAX_ATTEMPTS with
    exponential backoff + full jitter. Final failure → GeminiQuotaExceeded
    so the orchestrator can branch (defer / fall back to Ollama / journal).

    Ollama backend short-circuits the retry — local model has no quota.
    """
    if _provider() == "ollama":
        return _ollama_generate_sync(prompt, image_bytes)

    last_exc: Exception | None = None
    for attempt in range(1, _RETRY_MAX_ATTEMPTS + 1):
        try:
            return _generate_sync_no_retry(prompt, model=model, image_bytes=image_bytes)
        except Exception as exc:
            last_exc = exc
            if not _is_rate_limit_error(exc):
                raise
            if attempt >= _RETRY_MAX_ATTEMPTS:
                break
            delay = _backoff_delay_seconds(attempt)
            _log.warning(
                "Gemini 429 on attempt %d/%d (model=%s) — backing off %.2fs",
                attempt,
                _RETRY_MAX_ATTEMPTS,
                model,
                delay,
            )
            time.sleep(delay)

    raise GeminiQuotaExceeded(
        f"Gemini quota exhausted after {_RETRY_MAX_ATTEMPTS} attempts (model={model}): {last_exc}",
        attempts=_RETRY_MAX_ATTEMPTS,
        last_error=last_exc,
    )


async def generate(
    prompt: str,
    *,
    model: str = "gemini-2.5-flash",
    image_bytes: bytes | None = None,
    phase: str = "generate",
) -> str:
    """Async wrapper around the sync Gemini SDK call.

    Every call is logged to prompts_log.jsonl (prompt + response + latency)
    so failed detections and rejected CoVe gates can be diagnosed from
    primary evidence instead of guessed at.
    """
    t0 = time.monotonic()
    log_model = _resolved_model(model, image_bytes)
    try:
        result = await asyncio.to_thread(
            _generate_sync, prompt, model=model, image_bytes=image_bytes
        )
    except Exception as exc:
        record_prompt(
            model=log_model,
            phase=phase,
            prompt=prompt,
            response=None,
            response_kind="error",
            latency_ms=int((time.monotonic() - t0) * 1000),
            error=f"{type(exc).__name__}: {exc}",
            image_attached=image_bytes is not None,
        )
        raise
    record_prompt(
        model=log_model,
        phase=phase,
        prompt=prompt,
        response=result,
        response_kind="text",
        latency_ms=int((time.monotonic() - t0) * 1000),
        image_attached=image_bytes is not None,
    )
    return result


_FENCE_BLOCK = re.compile(r"```(?:json)?\s*(.*?)\s*```", re.DOTALL)
_DECODER = json.JSONDecoder()


def _extract_json(raw: str) -> Any:
    """Extract JSON from an LLM response, tolerant of common defects.

    Handles: code fences, prose-before-json, json-followed-by-prose (Extra data),
    nested brackets, naked arrays/objects, unicode.

    Raises:
        ValueError: input is empty or whitespace-only (transient — caller degrades).
        json.JSONDecodeError: input has no parseable JSON (caller logs error).

    See backend/specs/gemini_json_parse.md for invariants.
    """
    if raw is None or not str(raw).strip():
        raise ValueError("empty response")

    # 1. Try fenced block first — most reliable when present.
    fence = _FENCE_BLOCK.search(raw)
    if fence:
        candidate = fence.group(1).strip()
        try:
            return json.loads(candidate)
        except json.JSONDecodeError:
            obj, _ = _try_raw_decode(candidate)
            if obj is not None:
                return obj

    payload = raw.strip()

    # 2. Direct parse of the whole stripped payload.
    try:
        return json.loads(payload)
    except json.JSONDecodeError:
        pass  # invariant-ok: PY-SILENT-EXC — direct JSON parse failed; falls through to next parse strategy

    # 3. Locate first `{` or `[` and use raw_decode — handles "Extra data"
    #    by parsing the first valid JSON value and ignoring trailing prose.
    obj, _ = _try_raw_decode(payload)
    if obj is not None:
        return obj

    # 4. No usable JSON — caller decides how to degrade.
    raise json.JSONDecodeError("no parseable JSON in response", payload, 0)


def _try_raw_decode(payload: str) -> tuple[Any, int]:
    """Find first `{` or `[` and raw-decode the prefix from there.

    Returns (parsed_value, end_index) or (None, -1) if nothing parses.
    Uses raw_decode so "Extra data" trailing prose is tolerated.
    """
    start_obj = payload.find("{")
    start_arr = payload.find("[")
    candidates = [s for s in (start_obj, start_arr) if s != -1]
    if not candidates:
        return None, -1
    for start in sorted(candidates):
        try:
            value, end = _DECODER.raw_decode(payload[start:])
            return value, start + end
        except json.JSONDecodeError:
            continue
    return None, -1


def _generate_json_sync(
    prompt: str, *, model: str = "gemini-2.5-flash", image_bytes: bytes | None = None
) -> Any:
    raw = _generate_sync(prompt, model=model, image_bytes=image_bytes)
    return _extract_json(raw)


async def generate_json(
    prompt: str,
    *,
    model: str = "gemini-2.5-flash",
    image_bytes: bytes | None = None,
    phase: str = "generate_json",
) -> Any:
    """Like `generate()` but extracts JSON from the response, tolerant of code fences."""
    raw = await generate(prompt, model=model, image_bytes=image_bytes, phase=phase)
    return _extract_json(raw)
