"""Adversarial matrix for services/scanner.py.

Per spec: backend/specs/scanner.md. Each test maps to a numbered invariant
(I1-I8) or a documented edge case.

Geocode, satellite, and gemini are all stubbed; no network, no disk-bound
LLM, no real model files.

Run: python3 -m pytest backend/specs/test_scanner.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any
from unittest.mock import AsyncMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import scanner

# --- Test fixtures ----------------------------------------------------------

GOOD_ANALYSIS: dict[str, Any] = {
    "has_panels": True,
    "confidence": 0.82,
    "panel_count_estimate": 12,
    "roof_orientation": "S",
    "roof_area_m2_estimate": 50,
    "shading_risk": "low",
    "reasoning": "Tydligt synliga svarta paneler på söderläge.",
}


@pytest.fixture
def mock_pipeline(monkeypatch: pytest.MonkeyPatch, tmp_path: Path):
    """Stub geocode + satellite + gemini and redirect IMAGES_DIR to tmp."""
    monkeypatch.setattr(scanner, "IMAGES_DIR", tmp_path / "images")
    (tmp_path / "images").mkdir(parents=True, exist_ok=True)

    geocode_mock = AsyncMock(return_value=(59.33, 18.07))
    monkeypatch.setattr(scanner.geocode_mod, "geocode", geocode_mock)

    sat_mock = AsyncMock(return_value=b"\xff\xd8\xff\x00fake-jpeg-bytes")
    monkeypatch.setattr(scanner.satellite, "fetch_satellite_image", sat_mock)

    gemini_mock = AsyncMock(return_value=dict(GOOD_ANALYSIS))
    monkeypatch.setattr(scanner.gemini, "generate_json", gemini_mock)

    # Default: legacy path (no DETECTION_BACKEND).
    monkeypatch.delenv("DETECTION_BACKEND", raising=False)

    return {
        "geocode": geocode_mock,
        "satellite": sat_mock,
        "gemini": gemini_mock,
        "tmp": tmp_path,
    }


# --- I1: geocode error propagates, no image written -------------------------

def test_scan_address_propagates_value_error_from_geocode(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(scanner, "IMAGES_DIR", tmp_path / "images")
    (tmp_path / "images").mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(
        scanner.geocode_mod,
        "geocode",
        AsyncMock(side_effect=ValueError("Could not geocode: nope")),
    )
    sat_mock = AsyncMock()
    monkeypatch.setattr(scanner.satellite, "fetch_satellite_image", sat_mock)

    with pytest.raises(ValueError, match="Could not geocode"):
        asyncio.run(scanner.scan_address("not a real place"))

    sat_mock.assert_not_called()
    assert list((tmp_path / "images").iterdir()) == []


def test_scan_address_calls_geocode_exactly_once(mock_pipeline) -> None:
    asyncio.run(scanner.scan_address("Kungsgatan 1, Stockholm"))
    assert mock_pipeline["geocode"].await_count == 1


# --- I2: image written before LLM call --------------------------------------

def test_scan_location_writes_image_before_llm_call(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(scanner, "IMAGES_DIR", tmp_path / "images")
    (tmp_path / "images").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(
        scanner.satellite,
        "fetch_satellite_image",
        AsyncMock(return_value=b"\xff\xd8\xff\x00bytes"),
    )

    files_at_llm_time: list[Path] = []

    async def gemini_check(*args: Any, **kwargs: Any) -> dict:
        files_at_llm_time.extend((tmp_path / "images").iterdir())
        return dict(GOOD_ANALYSIS)

    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(side_effect=gemini_check))
    monkeypatch.delenv("DETECTION_BACKEND", raising=False)

    asyncio.run(scanner.scan_location(59.33, 18.07, label="test"))
    assert len(files_at_llm_time) == 1, "image must exist on disk by the time LLM is called"


# --- I3: has_panels collapse on inconsistent verdict ------------------------

def test_low_confidence_collapses_has_panels(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    """LLM says has_panels=True with confidence=0.2 — must collapse to False."""
    bad = dict(GOOD_ANALYSIS)
    bad.update({"has_panels": True, "confidence": 0.2})
    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(return_value=bad))

    out = asyncio.run(scanner.scan_address("Storgatan 1"))
    assert out["has_panels"] is False
    assert out["confidence"] == 0.2


def test_zero_panel_count_collapses_has_panels(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    bad = dict(GOOD_ANALYSIS)
    bad.update({"has_panels": True, "confidence": 0.9, "panel_count_estimate": 0})
    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(return_value=bad))

    out = asyncio.run(scanner.scan_address("Storgatan 1"))
    assert out["has_panels"] is False


def test_consistent_positive_verdict_preserved(mock_pipeline) -> None:
    out = asyncio.run(scanner.scan_address("Storgatan 1"))
    assert out["has_panels"] is True
    assert out["confidence"] == 0.82
    assert out["panel_count_estimate"] == 12


# --- I4: numeric clamping ---------------------------------------------------

def test_negative_roof_area_clamps_to_zero(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    bad = dict(GOOD_ANALYSIS)
    bad["roof_area_m2_estimate"] = -50
    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(return_value=bad))

    out = asyncio.run(scanner.scan_address("X"))
    assert out["roof_area_m2_estimate"] == 0


def test_confidence_clamped_to_unit_interval(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    bad = dict(GOOD_ANALYSIS)
    bad["confidence"] = 1.7  # LLM hallucinates >1
    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(return_value=bad))

    out = asyncio.run(scanner.scan_address("X"))
    assert out["confidence"] == 1.0


def test_none_numeric_fields_default_to_zero(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    """LLM JSON is allowed to be sparse/null on numeric fields."""
    bad = {"has_panels": False, "confidence": None, "panel_count_estimate": None,
           "roof_area_m2_estimate": None}
    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(return_value=bad))

    out = asyncio.run(scanner.scan_address("X"))
    assert out["confidence"] == 0.0
    assert out["panel_count_estimate"] == 0
    assert out["roof_area_m2_estimate"] == 0


def test_non_numeric_string_field_does_not_crash(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    """LLM occasionally returns 'unknown' where a number was asked for."""
    bad = dict(GOOD_ANALYSIS)
    bad["roof_area_m2_estimate"] = "lots"
    monkeypatch.setattr(scanner.gemini, "generate_json", AsyncMock(return_value=bad))

    out = asyncio.run(scanner.scan_address("X"))
    assert out["roof_area_m2_estimate"] == 0


# --- I5: timestamps are ISO-8601 UTC ---------------------------------------

def test_scanned_at_is_iso_utc(mock_pipeline) -> None:
    out = asyncio.run(scanner.scan_address("X"))
    ts = out["scanned_at"]
    # ISO 8601 with timezone offset; UTC is +00:00.
    assert "T" in ts and ts.endswith("+00:00")


# --- I8: image_path is relative to backend/data ----------------------------

def test_image_path_is_relative_not_absolute(mock_pipeline) -> None:
    out = asyncio.run(scanner.scan_address("Storgatan 1"))
    p = out["image_path"]
    assert not p.startswith("/"), "image_path must not leak absolute deployment root"
    assert p.startswith("images/"), f"expected images/<file>.jpg, got {p!r}"


# --- LLM failure surfaced as RuntimeError ----------------------------------

def test_gemini_failure_becomes_runtime_error(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    monkeypatch.setattr(
        scanner.gemini,
        "generate_json",
        AsyncMock(side_effect=RuntimeError("upstream 503")),
    )
    with pytest.raises(RuntimeError, match="Gemini detection failed"):
        asyncio.run(scanner.scan_address("X"))


# --- Dispatcher path triggered by DETECTION_BACKEND -------------------------

def test_detection_backend_set_routes_to_dispatcher(
    monkeypatch: pytest.MonkeyPatch, mock_pipeline
) -> None:
    """When DETECTION_BACKEND is non-empty, scanner uses the ML dispatcher.

    We stub `_scan_via_dispatcher` directly to avoid pulling the
    detection_escalate / detection_label_log import chain into the test.
    """
    sentinel: dict[str, Any] = {
        "address": "X",
        "lat": 59.33,
        "lng": 18.07,
        "image_path": "images/x.jpg",
        "has_panels": True,
        "confidence": 0.91,
        "panel_count_estimate": 8,
        "roof_orientation": "unknown",
        "roof_area_m2_estimate": 40,
        "shading_risk": "unknown",
        "reasoning": "backend=embed inference_ms=42",
        "scanned_at": "2026-05-04T00:00:00+00:00",
    }
    dispatcher_mock = AsyncMock(return_value=sentinel)
    monkeypatch.setattr(scanner, "_scan_via_dispatcher", dispatcher_mock)
    monkeypatch.setenv("DETECTION_BACKEND", "embed")

    out = asyncio.run(scanner.scan_address("X"))
    assert dispatcher_mock.await_count == 1
    assert out["reasoning"].startswith("backend=embed")
    # Legacy path's gemini call must NOT have fired.
    mock_pipeline["gemini"].assert_not_called()


# --- Unicode preservation ---------------------------------------------------

def test_swedish_characters_preserved_in_address(mock_pipeline) -> None:
    out = asyncio.run(scanner.scan_address("Götaplatsen, Göteborg"))
    assert "Götaplatsen" in out["address"]
    assert "Göteborg" in out["address"]


# --- _save_image: filename sanitation --------------------------------------

def test_save_image_sanitizes_label(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    monkeypatch.setattr(scanner, "IMAGES_DIR", tmp_path)
    out = scanner._save_image(b"data", "Kungsgatan 1, Stockholm/../etc/passwd")
    assert out.parent == tmp_path, "must not escape IMAGES_DIR via path separators"
    assert ".." not in out.name
    assert "/" not in out.name


def test_save_image_truncates_long_label(
    monkeypatch: pytest.MonkeyPatch, tmp_path: Path
) -> None:
    monkeypatch.setattr(scanner, "IMAGES_DIR", tmp_path)
    out = scanner._save_image(b"x", "A" * 500)
    # 80 char cap on the sanitized label + suffix.
    assert len(out.stem.split("_")[0]) <= 80


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
