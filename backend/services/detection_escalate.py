"""Active-learning wrapper around ``detection_model.detect``.

Idea: the fast embed head serves >95% of traffic at ~25 ms. When it's
genuinely uncertain (confidence in a configurable band around 0.5),
we transparently escalate to a slower but more capable teacher
(Moondream by default), return the teacher's verdict to the caller,
AND record the teacher verdict as a new training label.

That label feeds the next ``auto_train_detection`` run, so the head
learns exactly where it was uncertain. Over time the embed head
converges toward the teacher's accuracy on the user's actual traffic
distribution — without any manual labelling.

Opt-in via env (off by default to keep the dispatcher behaviour clean):
    ESCALATE_ON_LOW_CONFIDENCE=1   # enable
    ESCALATE_BAND=0.2              # half-width of band around 0.5
                                   #   default 0.2 → escalate if 0.3 < c < 0.7
    ESCALATE_TEACHER=moondream     # which backend to escalate to

The teacher is only consulted when:
  1. Escalation is enabled (env flag set).
  2. The primary verdict came from `embed` (no point escalating from
     the teacher to itself, or from `ml` which is already the strongest).
  3. The teacher is currently available (is_available() True).
  4. The image has not been escalated for in the last ESCALATE_MIN_INTERVAL_S
     seconds (per-hash dedup; prevents tight loops on repeat scans).
"""

from __future__ import annotations

import hashlib
import logging
import os
import threading
import time
from collections import OrderedDict

log = logging.getLogger(__name__)

DEFAULT_BAND = 0.2  # band half-width around 0.5
DEFAULT_MIN_INTERVAL_S = 60.0
DEDUP_CACHE_MAX = 4096

# Per-image hash → ts of last escalation. LRU-ish; capped to avoid leaks.
_recent: OrderedDict[str, float] = OrderedDict()
_recent_lock = threading.Lock()


def _enabled() -> bool:
    return os.getenv("ESCALATE_ON_LOW_CONFIDENCE", "0").strip() == "1"


def _band() -> float:
    raw = os.getenv("ESCALATE_BAND")
    if not raw:
        return DEFAULT_BAND
    try:
        v = float(raw)
        return max(0.0, min(0.5, v))
    except ValueError:
        return DEFAULT_BAND


def _teacher_name() -> str:
    return (os.getenv("ESCALATE_TEACHER") or "moondream").strip().lower()


def _min_interval_s() -> float:
    raw = os.getenv("ESCALATE_MIN_INTERVAL_S")
    if not raw:
        return DEFAULT_MIN_INTERVAL_S
    try:
        return max(0.0, float(raw))
    except ValueError:
        return DEFAULT_MIN_INTERVAL_S


def _is_borderline(confidence: float) -> bool:
    band = _band()
    return abs(confidence - 0.5) < band


def _image_hash(image_bytes: bytes) -> str:
    return hashlib.sha1(image_bytes).hexdigest()[:16]


def _seen_recently(h: str) -> bool:
    """True iff we escalated this hash within the dedup window."""
    interval = _min_interval_s()
    if interval <= 0:
        return False
    now = time.time()
    with _recent_lock:
        ts = _recent.get(h)
        if ts is None:
            return False
        if now - ts > interval:
            _recent.pop(h, None)
            return False
        return True


def _remember(h: str) -> None:
    with _recent_lock:
        _recent[h] = time.time()
        _recent.move_to_end(h)
        while len(_recent) > DEDUP_CACHE_MAX:
            _recent.popitem(last=False)


def reset_for_tests() -> None:
    with _recent_lock:
        _recent.clear()


def _save_escalation_image(image_bytes: bytes, h: str) -> str:
    """Save image to backend/data/images/escalation/<h>.jpg, return rel path."""
    from services import detection_label_log

    base = detection_label_log.LOG_DIR.parents[0]  # backend/data
    out_dir = base / "images" / "escalation"
    out_dir.mkdir(parents=True, exist_ok=True)
    path = out_dir / f"{h}.jpg"
    if not path.exists():
        path.write_bytes(image_bytes)
    return str(path.relative_to(base))


async def _resolve_teacher():
    """Return (name, is_available, detect) for the configured teacher.

    Lazy-imported so a misconfigured env doesn't break imports of this
    module from places that don't use escalation.
    """
    name = _teacher_name()
    if name == "moondream":
        from services import detection_moondream as t
    elif name == "ml":
        from services import detection_ml as t
    elif name == "gemini":
        from services import detection_gemini as t
    else:
        raise RuntimeError(
            f"ESCALATE_TEACHER={name!r} unknown. Use moondream / ml / gemini."
        )
    return name, t.is_available, t.detect


async def detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict:
    """Run primary backend, escalate to teacher when borderline.

    Drop-in replacement for ``detection_model.detect`` — same input/output
    shape. When escalation is disabled or not applicable, behaves
    identically to the underlying dispatcher.
    """
    from services import detection_model

    primary = await detection_model.detect(image_bytes, lat=lat, zoom=zoom)

    if not _enabled():
        return primary
    if primary["backend"] != "embed":
        return primary
    if not _is_borderline(primary["confidence"]):
        return primary

    teacher_name = _teacher_name()
    if teacher_name == primary["backend"]:
        return primary

    h = _image_hash(image_bytes)
    if _seen_recently(h):
        log.debug("escalate: dedup-skip image %s", h)
        return primary

    try:
        name, avail, detect_fn = await _resolve_teacher()
    except RuntimeError as e:
        log.warning("escalate: %s — returning primary verdict", e)
        return primary

    if not avail():
        log.info(
            "escalate: teacher %r unavailable; embed conf=%.2f stays as-is",
            name, primary["confidence"],
        )
        return primary

    try:
        teacher_result = await detect_fn(image_bytes, lat=lat, zoom=zoom)
    except Exception as e:  # noqa: BLE001 — escalation must never break the request
        log.warning("escalate: teacher %r raised %s; returning primary", name, e)
        return primary

    _remember(h)

    # Save image + label so next ml-train pass learns from this case.
    try:
        from services import detection_label_log
        rel_path = _save_escalation_image(image_bytes, h)
        detection_label_log.record_label(
            image_path=rel_path,
            has_panels_truth=teacher_result["has_panels"],
            source=f"escalation:{name}",
            note=f"embed conf was {primary['confidence']:.2f}; "
                 f"teacher conf {teacher_result['confidence']:.2f}",
        )
    except Exception as e:  # noqa: BLE001 — labelling is best-effort
        log.warning("escalate: failed to record label: %s", e)

    teacher_result.setdefault("escalated_from", primary["backend"])
    teacher_result.setdefault("primary_confidence", primary["confidence"])
    return teacher_result
