"""ML solar-panel detection (ONNX path) — YOLOv8 segmentation.

Pure ML implementation. Imported by ``services.detection_model`` and called
when ONNX weights are present. Deterministic, offline-safe, CPU-only.
"""

from __future__ import annotations

import asyncio
import io
import logging
import threading
import time
from pathlib import Path
from typing import TYPE_CHECKING

from services.detection_geom import mask_pixels_to_m2

if TYPE_CHECKING:
    import numpy as np
    import onnxruntime as ort

log = logging.getLogger(__name__)

MODEL_PATH = Path(__file__).resolve().parents[1] / "models" / "yolov8n-solar-seg.onnx"
MODEL_INPUT_SIZE = 640
DEFAULT_TILE_SIZE = 512
THRESHOLD = 0.5
MASK_BINARIZE_THRESHOLD = 0.5

_session: ort.InferenceSession | None = None
_session_lock = threading.Lock()


def is_available() -> bool:
    """True iff weights exist on disk and onnxruntime is importable."""
    if not MODEL_PATH.exists():
        return False
    try:
        import onnxruntime  # noqa: F401
        return True
    except ImportError:
        return False


def _get_session() -> ort.InferenceSession:
    global _session
    if _session is not None:
        return _session
    with _session_lock:
        if _session is not None:
            return _session
        if not MODEL_PATH.exists():
            raise RuntimeError(
                f"ML weights missing at {MODEL_PATH}. "
                "See backend/models/README.md, or unset DETECTION_BACKEND=ml."
            )
        try:
            import onnxruntime as ort
        except ImportError as e:
            raise RuntimeError("onnxruntime not installed") from e
        opts = ort.SessionOptions()
        opts.intra_op_num_threads = 1
        opts.graph_optimization_level = ort.GraphOptimizationLevel.ORT_ENABLE_ALL
        _session = ort.InferenceSession(
            str(MODEL_PATH), sess_options=opts, providers=["CPUExecutionProvider"]
        )
        return _session


def _decode_and_letterbox(image_bytes: bytes) -> np.ndarray:
    if not image_bytes:
        raise RuntimeError("empty image bytes")
    try:
        import numpy as np
        from PIL import Image
    except ImportError as e:
        raise RuntimeError("Pillow + numpy required for ML detection") from e
    try:
        img = Image.open(io.BytesIO(image_bytes)).convert("RGB")
    except Exception as e:
        raise RuntimeError(f"could not decode image: {e}") from e
    w, h = img.size
    scale = MODEL_INPUT_SIZE / max(w, h)
    new_w, new_h = max(1, round(w * scale)), max(1, round(h * scale))
    img_resized = img.resize((new_w, new_h), Image.BILINEAR)
    canvas = Image.new("RGB", (MODEL_INPUT_SIZE, MODEL_INPUT_SIZE), (114, 114, 114))
    canvas.paste(img_resized, ((MODEL_INPUT_SIZE - new_w) // 2, (MODEL_INPUT_SIZE - new_h) // 2))
    arr = np.asarray(canvas, dtype=np.float32) / 255.0
    return arr.transpose(2, 0, 1)[None, ...]


def _postprocess(output0: np.ndarray, output1: np.ndarray) -> tuple[float, int]:
    import numpy as np

    preds = output0[0]
    proto = output1[0]
    if preds.ndim != 2 or preds.shape[0] < 5:
        raise RuntimeError(f"unexpected output0 shape: {output0.shape}")
    num_mask_coeffs = preds.shape[0] - 5
    class_scores = preds[4]
    best_idx = int(np.argmax(class_scores))
    max_conf = float(class_scores[best_idx])
    if max_conf < THRESHOLD:
        return max_conf, 0
    if num_mask_coeffs <= 0 or proto.shape[0] != num_mask_coeffs:
        return max_conf, 0
    coeffs = preds[5:5 + num_mask_coeffs, best_idx]
    mask = (coeffs[:, None, None] * proto).sum(axis=0)
    mask = 1.0 / (1.0 + np.exp(-mask))
    mh, mw = mask.shape
    scale_h, scale_w = MODEL_INPUT_SIZE / mh, MODEL_INPUT_SIZE / mw
    if scale_h != 1 or scale_w != 1:
        ys = (np.arange(MODEL_INPUT_SIZE) / scale_h).astype(np.int64)
        xs = (np.arange(MODEL_INPUT_SIZE) / scale_w).astype(np.int64)
        mask = mask[ys[:, None], xs[None, :]]
    pixel_count = int((mask > MASK_BINARIZE_THRESHOLD).sum())
    return max_conf, pixel_count


def _detect_sync(image_bytes: bytes, *, lat: float, zoom: int) -> dict:
    t0 = time.perf_counter()
    tensor = _decode_and_letterbox(image_bytes)
    sess = _get_session()
    inputs = {sess.get_inputs()[0].name: tensor}
    outputs = sess.run(None, inputs)
    if len(outputs) < 2:
        raise RuntimeError(f"expected 2 outputs from segmentation model, got {len(outputs)}")
    confidence, mask_pixels = _postprocess(outputs[0], outputs[1])
    has_panels = confidence >= THRESHOLD and mask_pixels > 0
    panel_area_m2: float | None = None
    if has_panels:
        panel_area_m2 = mask_pixels_to_m2(
            mask_pixels,
            lat=lat,
            zoom=zoom,
            tile_size_px=DEFAULT_TILE_SIZE,
            model_size_px=MODEL_INPUT_SIZE,
        )
        if panel_area_m2 <= 0:
            panel_area_m2 = None
            has_panels = False
    return {
        "has_panels": has_panels,
        "confidence": max(0.0, min(1.0, confidence)),
        "panel_area_m2": panel_area_m2,
        "roof_area_m2": panel_area_m2,
        "inference_ms": int((time.perf_counter() - t0) * 1000),
        "backend": "ml",
    }


async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict:
    return await asyncio.to_thread(_detect_sync, image_bytes, lat=lat, zoom=zoom)


def reset_session_for_tests() -> None:
    global _session
    with _session_lock:
        _session = None
