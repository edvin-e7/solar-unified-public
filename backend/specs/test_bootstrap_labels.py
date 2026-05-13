"""Smoke + invariant tests for bootstrap_labels.py.

The full pipeline (geocode → satellite → teacher → label) needs network
+ a running Ollama daemon. These tests stub everything so the script's
core logic — idempotency, image-path stability, confidence floor,
paid-teacher refusal — is verified without external dependencies.
"""

from __future__ import annotations

import asyncio
import importlib.util
import json
import sys
from pathlib import Path
from unittest import mock

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "bootstrap_labels.py"
spec = importlib.util.spec_from_file_location("bootstrap_labels", SCRIPT_PATH)
bootstrap_labels = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec is not None and spec.loader is not None
spec.loader.exec_module(bootstrap_labels)  # type: ignore[union-attr]


@pytest.fixture
def isolated_data(tmp_path: Path, monkeypatch) -> Path:
    """Redirect script's DATA_DIR / LABELS_JSONL / IMAGES_DIR into tmp_path."""
    data = tmp_path / "data"
    images = data / "images" / "bootstrap"
    labels = data / "detection" / "labels.jsonl"
    images.mkdir(parents=True, exist_ok=True)
    labels.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(bootstrap_labels, "DATA_DIR", data)
    monkeypatch.setattr(bootstrap_labels, "IMAGES_DIR", images)
    monkeypatch.setattr(bootstrap_labels, "LABELS_JSONL", labels)
    return tmp_path


def test_image_filename_stable_per_coord() -> None:
    a = bootstrap_labels._image_filename("Storgatan 1, Stockholm", 59.3293, 18.0686)
    b = bootstrap_labels._image_filename("Storgatan 1, Stockholm", 59.3293, 18.0686)
    assert a == b, "same coords must produce same filename for idempotent re-runs"

    c = bootstrap_labels._image_filename("Storgatan 1, Stockholm", 59.3294, 18.0686)
    assert a != c, "different coords must produce different filenames"


def test_image_filename_safe_chars() -> None:
    fname = bootstrap_labels._image_filename("Åäö/foo bar #1", 59.0, 18.0)
    assert "/" not in fname
    assert " " not in fname
    assert fname.endswith(".jpg")


def test_already_labelled_reads_existing(isolated_data: Path) -> None:
    bootstrap_labels.LABELS_JSONL.write_text(
        json.dumps({"image_path": "images/bootstrap/foo.jpg", "has_panels_truth": True}) + "\n"
        + json.dumps({"image_path": "images/bootstrap/bar.jpg", "has_panels_truth": False}) + "\n",
        encoding="utf-8",
    )
    seen = bootstrap_labels._already_labelled()
    assert seen == {"images/bootstrap/foo.jpg", "images/bootstrap/bar.jpg"}


def test_already_labelled_tolerates_corruption(isolated_data: Path) -> None:
    bootstrap_labels.LABELS_JSONL.write_text(
        '{"image_path": "good.jpg"}\n'
        + 'not json at all\n'
        + '{"image_path": "good2.jpg"}\n',
        encoding="utf-8",
    )
    seen = bootstrap_labels._already_labelled()
    assert seen == {"good.jpg", "good2.jpg"}


def test_load_addresses_skips_comments_and_blanks(tmp_path: Path) -> None:
    f = tmp_path / "addr.txt"
    f.write_text(
        "# header\n"
        "Storgatan 1, Stockholm\n"
        "\n"
        "Avenyn 5, Göteborg\n"
        "# trailing comment\n",
        encoding="utf-8",
    )
    args = mock.MagicMock(addresses=f, coords=None)
    out = bootstrap_labels._load_addresses(args)
    assert out == [
        ("Storgatan 1, Stockholm", None, None),
        ("Avenyn 5, Göteborg", None, None),
    ]


def test_load_addresses_parses_coords(tmp_path: Path) -> None:
    f = tmp_path / "coords.txt"
    f.write_text("59.3293, 18.0686\nbroken\n55.6, 13.0\n", encoding="utf-8")
    args = mock.MagicMock(addresses=None, coords=f)
    out = bootstrap_labels._load_addresses(args)
    assert len(out) == 2
    assert out[0][1:] == (59.3293, 18.0686)


def test_paid_teacher_refused_without_flag(isolated_data: Path) -> None:
    args = mock.MagicMock(
        addresses=None, coords=None, teacher="gemini", allow_paid=False,
        min_confidence=0.6, write_borderline=False,
    )
    args.addresses = REPO_ROOT / "backend" / "scripts" / "fixtures" / "eval_set_sample.txt"
    rc = asyncio.run(bootstrap_labels._run(args))
    assert rc == 4, "must refuse paid teachers when --allow-paid not set"


def _stub_teacher(has_panels: bool, confidence: float):
    async def _detect(image_bytes, *, lat, zoom=20):
        return {
            "has_panels": has_panels,
            "confidence": confidence,
            "panel_area_m2": 12.0 if has_panels else None,
            "roof_area_m2": 12.0 if has_panels else None,
            "inference_ms": 100,
            "backend": "stub",
        }
    return _detect


def test_end_to_end_idempotent(isolated_data: Path, tmp_path: Path, monkeypatch) -> None:
    """Run twice over the same address list; second run should add zero rows."""
    addr_file = tmp_path / "addr.txt"
    addr_file.write_text("Test Address 1\nTest Address 2\n", encoding="utf-8")

    fake_geocode = mock.AsyncMock(side_effect=[(59.0, 18.0), (60.0, 17.0)])
    fake_satellite = mock.AsyncMock(return_value=b"\xff\xd8\xff\xd9")  # tiny valid jpeg sentinel

    monkeypatch.setattr(bootstrap_labels, "_resolve_teacher",
                        lambda name: (name, _stub_teacher(True, 0.85)))

    import services.geocode as geo_mod
    import services.satellite as sat_mod
    monkeypatch.setattr(geo_mod, "geocode", fake_geocode)
    monkeypatch.setattr(sat_mod, "fetch_satellite_image", fake_satellite)

    args = mock.MagicMock(
        addresses=addr_file, coords=None, teacher="moondream",
        min_confidence=0.6, write_borderline=False, allow_paid=False,
    )

    rc1 = asyncio.run(bootstrap_labels._run(args))
    assert rc1 == 0
    first = bootstrap_labels.LABELS_JSONL.read_text(encoding="utf-8").splitlines()
    assert len(first) == 2

    # Reset geocode mock so second-run resolves to same coords.
    fake_geocode.side_effect = [(59.0, 18.0), (60.0, 17.0)]
    rc2 = asyncio.run(bootstrap_labels._run(args))
    assert rc2 == 0
    second = bootstrap_labels.LABELS_JSONL.read_text(encoding="utf-8").splitlines()
    assert len(second) == 2, "idempotent re-run must not append duplicate rows"


def test_confidence_floor_filters(isolated_data: Path, tmp_path: Path, monkeypatch) -> None:
    addr_file = tmp_path / "addr.txt"
    addr_file.write_text("Borderline Address\n", encoding="utf-8")

    monkeypatch.setattr(bootstrap_labels, "_resolve_teacher",
                        lambda name: (name, _stub_teacher(True, 0.4)))  # below floor

    import services.geocode as geo_mod
    import services.satellite as sat_mod
    monkeypatch.setattr(geo_mod, "geocode", mock.AsyncMock(return_value=(59.0, 18.0)))
    monkeypatch.setattr(sat_mod, "fetch_satellite_image", mock.AsyncMock(return_value=b"img"))

    args = mock.MagicMock(
        addresses=addr_file, coords=None, teacher="moondream",
        min_confidence=0.6, write_borderline=False, allow_paid=False,
    )
    rc = asyncio.run(bootstrap_labels._run(args))
    assert rc == 0
    # No labels written (confidence below floor) but image should be saved
    # for human review.
    assert not bootstrap_labels.LABELS_JSONL.exists() or \
        bootstrap_labels.LABELS_JSONL.read_text() == ""
    assert any(bootstrap_labels.IMAGES_DIR.iterdir()), "image must be saved even when label dropped"
