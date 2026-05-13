"""Append-only JSONL log of detection inferences and user-supplied labels.

Two streams:
- inferences.jsonl: every model call, success or fail (model-of-record)
- labels.jsonl: user-supplied ground truth, used as a training corpus seed

When `labels.jsonl` accumulates ~hundreds of confirmed entries, the file pair
becomes the bootstrap dataset for fine-tuning a real ML model.

Public surface:
    record_inference(image_path, backend, has_panels, confidence, inference_ms, address=None)
    record_label(image_path, has_panels_truth, source="user", note="")
    label_count() -> int
    inference_count() -> int
"""

from __future__ import annotations

import json
import threading
import time
from pathlib import Path

LOG_DIR = Path(__file__).resolve().parents[1] / "data" / "detection"
INFERENCE_LOG = LOG_DIR / "inferences.jsonl"
LABEL_LOG = LOG_DIR / "labels.jsonl"

_lock = threading.Lock()


def _ensure_dir() -> None:
    LOG_DIR.mkdir(parents=True, exist_ok=True)


def _append(path: Path, entry: dict) -> None:
    _ensure_dir()
    line = json.dumps(entry, ensure_ascii=False) + "\n"
    with _lock, path.open("a", encoding="utf-8") as f:
        f.write(line)


def record_inference(
    *,
    image_path: str,
    backend: str,
    has_panels: bool,
    confidence: float,
    inference_ms: int,
    address: str | None = None,
) -> None:
    _append(
        INFERENCE_LOG,
        {
            "ts": time.time(),
            "image_path": image_path,
            "address": address,
            "backend": backend,
            "has_panels": bool(has_panels),
            "confidence": round(float(confidence), 4),
            "inference_ms": int(inference_ms),
        },
    )


def record_label(
    *,
    image_path: str,
    has_panels_truth: bool,
    source: str = "user",
    note: str = "",
) -> None:
    _append(
        LABEL_LOG,
        {
            "ts": time.time(),
            "image_path": image_path,
            "has_panels_truth": bool(has_panels_truth),
            "source": source,
            "note": note[:200],
        },
    )


def _count(path: Path) -> int:
    if not path.exists():
        return 0
    with path.open(encoding="utf-8") as f:
        return sum(1 for _ in f)


def label_count() -> int:
    return _count(LABEL_LOG)


def inference_count() -> int:
    return _count(INFERENCE_LOG)
