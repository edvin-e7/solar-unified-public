"""Public detection entrypoint — dispatches to ML, Embed, Moondream, or Gemini.

Strategy (env-controlled by `DETECTION_BACKEND`):
    "auto" (default): pick the first usable backend in this order
        1. ml        — full YOLOv8-seg ONNX (panel mask + area)
        2. embed     — frozen encoder + numpy head (auto-trained from
                       your prospects DB; fast, deterministic, no GPU)
        3. moondream — local vision LLM via Ollama (free, ~1.5 GB on disk)
        4. gemini    — Gemini Vision LLM (paid; last resort)
    "ml" / "embed" / "moondream" / "gemini" — force that backend; raise
        loudly if the chosen backend is unusable.

The downstream contract is identical for every backend:
    detect(image_bytes, *, lat, zoom=20) -> DetectionResult
where DetectionResult["backend"] reveals which path served the call so
callers can warn about non-deterministic LLM verdicts.
"""

from __future__ import annotations

import os
from typing import Literal, TypedDict

from services import detection_embed, detection_ml, detection_moondream
from services.detection_ml import (  # noqa: F401 -- re-exports for back-compat
    MODEL_INPUT_SIZE,
    MODEL_PATH,
    THRESHOLD,
    reset_session_for_tests,
)


class DetectionResult(TypedDict):
    has_panels: bool
    confidence: float
    panel_area_m2: float | None
    roof_area_m2: float | None
    inference_ms: int
    backend: str  # "ml" | "embed" | "moondream" | "gemini"


Backend = Literal["ml", "embed", "moondream", "gemini"]
_VALID = {"ml", "embed", "moondream", "gemini"}


def select_backend() -> Backend:
    """Pick the backend per env, honouring strict overrides.

    Never raises for valid 'auto' — falls all the way through to "gemini".
    Raises only for an unknown DETECTION_BACKEND value.
    """
    requested = (os.getenv("DETECTION_BACKEND") or "auto").strip().lower()
    if requested in _VALID:
        return requested  # type: ignore[return-value]
    if requested not in {"auto", ""}:
        raise RuntimeError(
            f"DETECTION_BACKEND={requested!r} unknown. "
            "Use 'auto', 'ml', 'embed', 'moondream', or 'gemini'."
        )
    if detection_ml.is_available():
        return "ml"
    if detection_embed.is_available():
        return "embed"
    if detection_moondream.is_available():
        return "moondream"
    return "gemini"


def select_backend_safe() -> tuple[Backend | None, str | None]:
    """Like select_backend, but returns (backend, error) — never raises.

    Used by the /status endpoint so a misconfiguration doesn't 500.
    """
    try:
        return select_backend(), None
    except RuntimeError as e:
        return None, str(e)


async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> DetectionResult:
    """Run detection via the selected backend.

    Raises RuntimeError if the chosen backend is unusable
    (e.g. ML requested but weights missing, Gemini chosen but no API key).
    """
    backend = select_backend()
    if backend == "ml":
        result = await detection_ml.detect(image_bytes, lat=lat, zoom=zoom)
    elif backend == "embed":
        result = await detection_embed.detect(image_bytes, lat=lat, zoom=zoom)
    elif backend == "moondream":
        result = await detection_moondream.detect(image_bytes, lat=lat, zoom=zoom)
    else:
        from services import detection_gemini  # lazy: only import when used
        result = await detection_gemini.detect(image_bytes, lat=lat, zoom=zoom)
    return DetectionResult(**result)  # type: ignore[typeddict-item]
