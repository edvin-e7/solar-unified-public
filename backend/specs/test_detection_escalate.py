"""Tests for the active-learning escalation wrapper."""

from __future__ import annotations

import asyncio
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import detection_escalate


@pytest.fixture(autouse=True)
def _reset_dedup():
    detection_escalate.reset_for_tests()
    yield
    detection_escalate.reset_for_tests()


def _embed_result(confidence: float, has_panels: bool = False) -> dict:
    return {
        "has_panels": has_panels,
        "confidence": confidence,
        "panel_area_m2": None,
        "roof_area_m2": None,
        "inference_ms": 30,
        "backend": "embed",
    }


def _teacher_result(confidence: float = 0.95, has_panels: bool = True) -> dict:
    return {
        "has_panels": has_panels,
        "confidence": confidence,
        "panel_area_m2": 14.0 if has_panels else None,
        "roof_area_m2": 14.0 if has_panels else None,
        "inference_ms": 1500,
        "backend": "moondream",
    }


def _patch_label_log(tmp_path: Path, monkeypatch):
    """Redirect detection_label_log paths under tmp_path."""
    from services import detection_label_log

    log_dir = tmp_path / "detection"
    log_dir.mkdir(parents=True)
    monkeypatch.setattr(detection_label_log, "LOG_DIR", log_dir)
    monkeypatch.setattr(detection_label_log, "INFERENCE_LOG", log_dir / "inferences.jsonl")
    monkeypatch.setattr(detection_label_log, "LABEL_LOG", log_dir / "labels.jsonl")


def test_disabled_passes_through(monkeypatch) -> None:
    monkeypatch.delenv("ESCALATE_ON_LOW_CONFIDENCE", raising=False)
    primary = _embed_result(0.5)  # smack in the middle — would escalate if enabled
    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)):
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))
    assert out == primary


def test_non_embed_primary_not_escalated(monkeypatch) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    primary = {**_embed_result(0.5), "backend": "ml"}
    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)):
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))
    assert out["backend"] == "ml"


def test_confident_embed_not_escalated(monkeypatch) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    primary = _embed_result(0.95, has_panels=True)
    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)):
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))
    assert out == primary


def test_borderline_escalates_to_teacher(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    monkeypatch.setenv("ESCALATE_BAND", "0.2")
    monkeypatch.setenv("ESCALATE_TEACHER", "moondream")
    _patch_label_log(tmp_path, monkeypatch)

    primary = _embed_result(0.55)  # inside default band
    teacher = _teacher_result(0.92, True)

    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)), \
         mock.patch("services.detection_moondream.is_available", return_value=True), \
         mock.patch("services.detection_moondream.detect", new=mock.AsyncMock(return_value=teacher)):
        out = asyncio.run(detection_escalate.detect(b"img-bytes", lat=60.0))

    assert out["backend"] == "moondream"
    assert out["escalated_from"] == "embed"
    assert out["primary_confidence"] == 0.55

    from services import detection_label_log
    assert detection_label_log.label_count() == 1
    rows = detection_label_log.LABEL_LOG.read_text(encoding="utf-8").splitlines()
    label = json.loads(rows[0])
    assert label["has_panels_truth"] is True
    assert label["source"] == "escalation:moondream"
    assert "embed conf was 0.55" in label["note"]


def test_teacher_unavailable_returns_primary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    _patch_label_log(tmp_path, monkeypatch)

    primary = _embed_result(0.5)
    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)), \
         mock.patch("services.detection_moondream.is_available", return_value=False):
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))

    assert out == primary
    from services import detection_label_log
    assert detection_label_log.label_count() == 0


def test_teacher_raises_returns_primary(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    _patch_label_log(tmp_path, monkeypatch)

    primary = _embed_result(0.5)
    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)), \
         mock.patch("services.detection_moondream.is_available", return_value=True), \
         mock.patch("services.detection_moondream.detect",
                    new=mock.AsyncMock(side_effect=RuntimeError("ollama down"))):
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))

    assert out == primary, "teacher failure must never break the user request"


def test_dedup_skips_repeat_within_window(monkeypatch, tmp_path: Path) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    monkeypatch.setenv("ESCALATE_MIN_INTERVAL_S", "60")
    _patch_label_log(tmp_path, monkeypatch)

    primary = _embed_result(0.5)
    teacher = _teacher_result(0.9, True)
    teacher_detect = mock.AsyncMock(return_value=teacher)

    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)), \
         mock.patch("services.detection_moondream.is_available", return_value=True), \
         mock.patch("services.detection_moondream.detect", new=teacher_detect):
        first = asyncio.run(detection_escalate.detect(b"same-image", lat=60.0))
        second = asyncio.run(detection_escalate.detect(b"same-image", lat=60.0))

    assert first["backend"] == "moondream"
    assert second["backend"] == "embed", "second call within window must skip teacher"
    assert teacher_detect.await_count == 1


def test_clearly_outside_band_not_escalated(monkeypatch) -> None:
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    monkeypatch.setenv("ESCALATE_BAND", "0.2")
    primary = _embed_result(0.85)  # well outside [0.3, 0.7]

    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)), \
         mock.patch("services.detection_moondream.is_available", return_value=True) as avail:
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))

    assert out == primary
    avail.assert_not_called()


def test_invalid_band_falls_back(monkeypatch) -> None:
    monkeypatch.setenv("ESCALATE_BAND", "garbage")
    assert detection_escalate._band() == detection_escalate.DEFAULT_BAND


def test_teacher_same_as_primary_skips(monkeypatch) -> None:
    """If ESCALATE_TEACHER somehow == primary backend, don't recurse."""
    monkeypatch.setenv("ESCALATE_ON_LOW_CONFIDENCE", "1")
    monkeypatch.setenv("ESCALATE_TEACHER", "embed")
    primary = _embed_result(0.5)

    with mock.patch("services.detection_model.detect", new=mock.AsyncMock(return_value=primary)):
        out = asyncio.run(detection_escalate.detect(b"x", lat=60.0))
    assert out == primary
