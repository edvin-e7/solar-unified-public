"""Gemini Vision fallback for solar-panel detection.

Used by ``services.detection_model`` when no faster backend is configured.
NOT deterministic — flagged in DetectionResult["backend"] = "gemini" so the
caller can warn / withhold high-confidence actions.

Robustness features:
- Structured JSON-schema response mode (no regex parsing)
- Configurable model + timeout via env (GEMINI_MODEL, GEMINI_TIMEOUT_S)
- Retry with exponential backoff on transient errors (429, 503, network)
- Cached per-key Client (one HTTP session per worker)
- Loud, actionable error messages

Public surface mirrors ``services.detection_ml``:
    is_available() -> bool
    detect(image_bytes, *, lat, zoom=20) -> dict (DetectionResult shape)
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import random
import re
import threading
import time

log = logging.getLogger(__name__)

THRESHOLD = 0.5
DEFAULT_MODEL = "gemini-2.5-flash"
DEFAULT_TIMEOUT_S = 30
MAX_ATTEMPTS = 3
BASE_BACKOFF_S = 1.0

_client_cache: tuple[str, object] | None = None  # (api_key, client)
_client_lock = threading.Lock()


def _load_prompt() -> str:
    from prompts_loader import load, render

    return render(load("detection_vision"), {})

# JSON schema enforced by Gemini's structured-output mode. Eliminates regex
# fragility — the SDK refuses to return malformed JSON.
_RESPONSE_SCHEMA: dict = {
    "type": "object",
    "properties": {
        "has_panels": {"type": "boolean"},
        "confidence": {"type": "number"},
        "panel_area_m2": {"type": "number", "nullable": True},
        "reasoning": {"type": "string"},
    },
    "required": ["has_panels", "confidence"],
    "propertyOrdering": ["has_panels", "confidence", "panel_area_m2", "reasoning"],
}


def is_available() -> bool:
    """True iff GEMINI_API_KEY is set and google-genai imports cleanly.

    Catches BaseException (not just ImportError) because some sandboxes
    panic at import time via PyO3/cryptography ABI mismatches.
    """
    if not os.getenv("GEMINI_API_KEY"):
        return False
    try:
        from google import genai  # noqa: F401
        return True
    except BaseException:  # noqa: BLE001 -- intentionally broad: pyo3 panics aren't Exception
        return False


def _model_name() -> str:
    return (os.getenv("GEMINI_MODEL") or DEFAULT_MODEL).strip()


def _timeout_s() -> float:
    raw = os.getenv("GEMINI_TIMEOUT_S")
    if not raw:
        return float(DEFAULT_TIMEOUT_S)
    try:
        return max(1.0, float(raw))
    except ValueError:
        return float(DEFAULT_TIMEOUT_S)


def _extract_json(text: str) -> dict:
    """Lenient JSON extraction. Used as a fallback path; structured-mode
    responses parse directly via json.loads(text)."""
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise RuntimeError(f"Gemini returned non-JSON: {text[:200]!r}")


def _parse_response(text: str, *, started_at: float) -> dict:
    """Pure parser: response text → DetectionResult dict. Testable without genai."""
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Gemini returned empty response")
    try:
        data = json.loads(text)  # structured-mode path
    except json.JSONDecodeError:
        data = _extract_json(text)  # legacy / unstructured fallback

    confidence = max(0.0, min(1.0, float(data.get("confidence", 0.0))))
    has_panels = bool(data.get("has_panels", False)) and confidence >= THRESHOLD
    raw_area = data.get("panel_area_m2")
    panel_area_m2: float | None = None
    if has_panels and raw_area is not None:
        try:
            v = float(raw_area)
            panel_area_m2 = v if v > 0 else None
        except (TypeError, ValueError):
            panel_area_m2 = None
    if has_panels and panel_area_m2 is None:
        # Invariant I4: panel_area_m2 must be > 0 when has_panels=True.
        # Gemini returned no number — withhold the positive verdict.
        has_panels = False

    return {
        "has_panels": has_panels,
        "confidence": confidence,
        "panel_area_m2": panel_area_m2,
        "roof_area_m2": panel_area_m2,
        "inference_ms": int((time.perf_counter() - started_at) * 1000),
        "backend": "gemini",
    }


def _build_client(api_key: str):
    """Construct a fresh genai.Client. Tests patch this for isolation."""
    try:
        from google import genai
        from google.genai import types  # noqa: F401 -- proves SDK is intact
    except BaseException as e:  # noqa: BLE001 -- pyo3 panics aren't Exception
        raise RuntimeError(
            f"google-genai unusable: {type(e).__name__}: {e}. "
            "On Linux, this is often a system 'cryptography' ABI mismatch — "
            "reinstall in a clean venv."
        ) from None
    return genai.Client(api_key=api_key)


def _get_client(api_key: str):
    """Return a cached Client, creating one only on first call per api_key."""
    global _client_cache
    if _client_cache is not None and _client_cache[0] == api_key:
        return _client_cache[1]
    with _client_lock:
        if _client_cache is not None and _client_cache[0] == api_key:
            return _client_cache[1]
        client = _build_client(api_key)
        _client_cache = (api_key, client)
        return client


def reset_client_cache_for_tests() -> None:
    global _client_cache
    with _client_lock:
        _client_cache = None


def _is_transient(err: BaseException) -> bool:
    """Should we retry this error? Conservative — only obvious transients."""
    msg = (str(err) or "").lower()
    type_name = type(err).__name__.lower()
    transient_signals = (
        "429", "rate limit", "rate_limit",
        "503", "unavailable",
        "500", "internal server error",
        "504", "deadline", "timeout",
        "connection reset", "connection error",
    )
    if any(sig in msg for sig in transient_signals):
        return True
    return "timeout" in type_name or "deadline" in type_name


def _detect_sync(image_bytes: bytes, *, lat: float, zoom: int) -> dict:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise RuntimeError(
            "Detection unavailable: no ML/embed backend AND GEMINI_API_KEY not set. "
            "Set GEMINI_API_KEY in .env, or install ML weights / train embed head."
        )
    try:
        from google.genai import types
    except BaseException as e:  # noqa: BLE001 -- pyo3 panics aren't Exception
        raise RuntimeError(
            f"google-genai unusable: {type(e).__name__}: {e}"
        ) from None

    client = _get_client(api_key)
    config = types.GenerateContentConfig(
        response_mime_type="application/json",
        # response_json_schema is the dict-friendly field; response_schema
        # expects a Schema pydantic object. Using the JSON variant keeps us
        # forward-compatible across SDK versions.
        response_json_schema=_RESPONSE_SCHEMA,
        temperature=0.1,  # stable verdicts, not creative ones
        http_options=types.HttpOptions(timeout=int(_timeout_s() * 1000)),
    )
    contents = [
        types.Part.from_bytes(data=image_bytes, mime_type="image/jpeg"),
        _load_prompt(),
    ]
    model = _model_name()

    t0 = time.perf_counter()
    return _call_with_retry(client, model, contents, config, started_at=t0)


def _call_with_retry(client, model: str, contents, config, *, started_at: float) -> dict:
    """Run generate_content with bounded retries on transient errors.

    Catches Exception (not BaseException) — KeyboardInterrupt and SystemExit
    propagate so Ctrl-C and worker shutdown are honoured.
    """
    last_err: Exception | None = None
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            response = client.models.generate_content(
                model=model, contents=contents, config=config
            )
            text = (response.text or "").strip()
            if not text:
                # Structured mode + safety block can yield empty text.
                # Surface candidate.finish_reason so we know why.
                reason = "empty"
                cands = getattr(response, "candidates", None) or []
                if cands:
                    reason = str(getattr(cands[0], "finish_reason", "empty"))
                raise RuntimeError(f"Gemini returned empty response (finish_reason={reason})")
            return _parse_response(text, started_at=started_at)
        except Exception as e:  # noqa: BLE001 -- broad on purpose: SDK errors vary
            last_err = e
            if attempt < MAX_ATTEMPTS and _is_transient(e):
                delay = BASE_BACKOFF_S * (2 ** (attempt - 1)) + random.uniform(0, 0.3)
                log.warning(
                    "gemini transient error (attempt %d/%d): %s — retrying in %.1fs",
                    attempt, MAX_ATTEMPTS, e, delay,
                )
                time.sleep(delay)
                continue
            break

    raise RuntimeError(
        f"Gemini detection failed after {MAX_ATTEMPTS} attempts: "
        f"{type(last_err).__name__}: {last_err}"
    ) from last_err


async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict:
    return await asyncio.to_thread(_detect_sync, image_bytes, lat=lat, zoom=zoom)
