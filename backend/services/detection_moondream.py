"""Moondream vision-LLM detection backend (free, local, via Ollama).

Drop-in replacement for ``services.detection_gemini`` that hits a local
Ollama daemon instead of Google's paid API. Works on CPU, uses
~1.5 GB of disk for the model, costs nothing per call.

Setup (one time):
    1. Install Ollama:  curl -fsSL https://ollama.com/install.sh | sh
       (Or download from https://ollama.com for Mac / Windows.)
    2. Pull the model: ``ollama pull moondream``
    3. ``ollama serve`` runs as a daemon by default and listens on
       OLLAMA_HOST (defaults to http://localhost:11434).

Why Moondream and not Llama 3.2 Vision / LLaVA?
- ~1.5 GB model vs 8+ GB. Real consumer hardware can run it.
- Purpose-built for visual question answering — fast, accurate on
  the binary "are there panels here?" question we actually ask.
- MIT-licensed open weights. No API key, no rate limit, no spend.

Public surface mirrors ``services.detection_gemini``:
    is_available() -> bool
    detect(image_bytes, *, lat, zoom=20) -> dict (DetectionResult shape)
"""

from __future__ import annotations

import asyncio
import base64
import json
import logging
import os
import re
import time

import httpx

log = logging.getLogger(__name__)

THRESHOLD = 0.5
DEFAULT_HOST = "http://localhost:11434"
DEFAULT_MODEL = "moondream"
DEFAULT_TIMEOUT_S = 60  # CPU inference is slower than a paid API
DEFAULT_AVAIL_TIMEOUT_S = 1.5  # availability check must be snappy

def _load_prompt() -> str:
    from prompts_loader import load, render

    return render(load("detection_moondream"), {})


def _host() -> str:
    return (os.getenv("OLLAMA_HOST") or DEFAULT_HOST).rstrip("/")


def _model_name() -> str:
    return (os.getenv("MOONDREAM_MODEL") or DEFAULT_MODEL).strip()


def _timeout_s() -> float:
    raw = os.getenv("MOONDREAM_TIMEOUT_S")
    if not raw:
        return float(DEFAULT_TIMEOUT_S)
    try:
        return max(1.0, float(raw))
    except ValueError:
        return float(DEFAULT_TIMEOUT_S)


def is_available() -> bool:
    """True iff Ollama is reachable AND the configured model is pulled.

    Synchronous + short-timeout: this is called from the dispatcher's auto
    path and must never hang. A missing daemon, missing model, or network
    blip all return False — never raise.
    """
    url = f"{_host()}/api/tags"
    try:
        r = httpx.get(url, timeout=DEFAULT_AVAIL_TIMEOUT_S)
        if r.status_code != 200:
            return False
        models = r.json().get("models", [])
    except Exception:  # noqa: BLE001 — broad on purpose: this is a health probe
        return False
    wanted = _model_name()
    # Ollama tags are stored as "moondream:latest" — match on the bare name too.
    return any(
        m.get("name") == wanted or m.get("name", "").split(":", 1)[0] == wanted
        for m in models
    )


def _extract_json(text: str) -> dict:
    text = text.strip()
    fence = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if fence:
        return json.loads(fence.group(1))
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        return json.loads(brace.group(0))
    raise RuntimeError(f"Moondream returned non-JSON: {text[:200]!r}")


def _parse_response(text: str, *, started_at: float) -> dict:
    text = (text or "").strip()
    if not text:
        raise RuntimeError("Moondream returned empty response")
    try:
        data = json.loads(text)
    except json.JSONDecodeError:
        data = _extract_json(text)

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
        # Mirror detection_gemini invariant I4: panel_area_m2 must be > 0
        # when has_panels=True. Withhold the positive verdict otherwise.
        has_panels = False

    return {
        "has_panels": has_panels,
        "confidence": confidence,
        "panel_area_m2": panel_area_m2,
        "roof_area_m2": panel_area_m2,
        "inference_ms": int((time.perf_counter() - started_at) * 1000),
        "backend": "moondream",
    }


async def _generate(image_b64: str) -> str:
    payload = {
        "model": _model_name(),
        "prompt": _load_prompt(),
        "images": [image_b64],
        "stream": False,
        "format": "json",
        "options": {"temperature": 0.1},
    }
    url = f"{_host()}/api/generate"
    async with httpx.AsyncClient(timeout=_timeout_s()) as client:
        r = await client.post(url, json=payload)
        r.raise_for_status()
        body = r.json()
    return (body.get("response") or "").strip()


async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict:
    """Run Moondream via local Ollama. Raises RuntimeError if unreachable."""
    t0 = time.perf_counter()
    image_b64 = base64.b64encode(image_bytes).decode("ascii")
    try:
        text = await _generate(image_b64)
    except httpx.HTTPError as e:
        raise RuntimeError(
            f"Moondream/Ollama call failed: {type(e).__name__}: {e}. "
            f"Is `ollama serve` running at {_host()} and `{_model_name()}` pulled?"
        ) from e
    return _parse_response(text, started_at=t0)


def detect_sync(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict:
    """Sync wrapper — convenience for scripts and tests."""
    return asyncio.run(detect(image_bytes, lat=lat, zoom=zoom))
