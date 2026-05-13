"""Tests for import_labels.py — CSV ingestion of pre-labelled images."""

from __future__ import annotations

import importlib.util
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[2]
SCRIPT_PATH = REPO_ROOT / "backend" / "scripts" / "import_labels.py"

spec = importlib.util.spec_from_file_location("import_labels", SCRIPT_PATH)
import_labels = importlib.util.module_from_spec(spec)  # type: ignore[arg-type]
assert spec is not None and spec.loader is not None
spec.loader.exec_module(import_labels)  # type: ignore[union-attr]


@pytest.fixture
def isolated(tmp_path: Path, monkeypatch) -> Path:
    data = tmp_path / "data"
    images = data / "images" / "imported"
    labels = data / "detection" / "labels.jsonl"
    images.mkdir(parents=True, exist_ok=True)
    labels.parent.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(import_labels, "DATA_DIR", data)
    monkeypatch.setattr(import_labels, "IMAGES_DIR", images)
    monkeypatch.setattr(import_labels, "LABELS_JSONL", labels)
    return tmp_path


def _make_image(path: Path, contents: bytes = b"\xff\xd8\xff\xd9") -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(contents)
    return path


def _write_csv(path: Path, rows: list[dict]) -> Path:
    cols = ["path", "has_panels", "note"]
    lines = [",".join(cols)]
    for r in rows:
        lines.append(",".join(str(r.get(c, "")) for c in cols))
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return path


def test_parse_bool_true_variants() -> None:
    for v in ("true", "True", "1", "yes", "y", "T"):
        assert import_labels._parse_bool(v, row_num=1) is True


def test_parse_bool_false_variants() -> None:
    for v in ("false", "False", "0", "no", "n", "F"):
        assert import_labels._parse_bool(v, row_num=1) is False


def test_parse_bool_garbage_raises() -> None:
    with pytest.raises(ValueError):
        import_labels._parse_bool("maybe", row_num=5)


def test_stable_filename_same_bytes_same_name(tmp_path: Path) -> None:
    a = _make_image(tmp_path / "a.jpg", b"identical-bytes")
    b = _make_image(tmp_path / "subdir" / "b.jpg", b"identical-bytes")
    assert import_labels._stable_filename(a) == import_labels._stable_filename(b)


def test_stable_filename_different_bytes_different_name(tmp_path: Path) -> None:
    a = _make_image(tmp_path / "a.jpg", b"one")
    b = _make_image(tmp_path / "b.jpg", b"two")
    assert import_labels._stable_filename(a) != import_labels._stable_filename(b)


def test_csv_missing_required_columns_raises(tmp_path: Path, isolated: Path) -> None:
    csv = tmp_path / "bad.csv"
    csv.write_text("foo,bar\n1,2\n", encoding="utf-8")
    with pytest.raises(SystemExit, match="missing required columns"):
        import_labels._read_rows(csv)


def test_end_to_end_writes_labels_and_copies_images(tmp_path: Path, isolated: Path, monkeypatch) -> None:
    img1 = _make_image(tmp_path / "src" / "pos1.jpg", b"image-bytes-1")
    img2 = _make_image(tmp_path / "src" / "neg1.jpg", b"image-bytes-2")

    csv = _write_csv(tmp_path / "labels.csv", [
        {"path": str(img1), "has_panels": "true", "note": "rooftop with array"},
        {"path": str(img2), "has_panels": "false", "note": ""},
    ])

    monkeypatch.setattr(sys, "argv", ["import_labels.py", "--csv", str(csv)])
    rc = import_labels.main()
    assert rc == 0

    rows = import_labels.LABELS_JSONL.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 2
    parsed = [json.loads(r) for r in rows]
    truths = sorted(r["has_panels_truth"] for r in parsed)
    assert truths == [False, True]
    assert all(r["source"] == "imported-csv" for r in parsed)

    # Both images copied with stable hash names.
    copied = list(import_labels.IMAGES_DIR.iterdir())
    assert len(copied) == 2


def test_end_to_end_idempotent(tmp_path: Path, isolated: Path, monkeypatch) -> None:
    img = _make_image(tmp_path / "img.jpg", b"unique-bytes")
    csv = _write_csv(tmp_path / "labels.csv", [
        {"path": str(img), "has_panels": "true", "note": ""},
    ])
    monkeypatch.setattr(sys, "argv", ["import_labels.py", "--csv", str(csv)])

    assert import_labels.main() == 0
    assert import_labels.main() == 0  # second run

    rows = import_labels.LABELS_JSONL.read_text(encoding="utf-8").splitlines()
    assert len(rows) == 1, "second run must not append duplicate label"


def test_dry_run_writes_nothing(tmp_path: Path, isolated: Path, monkeypatch) -> None:
    img = _make_image(tmp_path / "img.jpg", b"x")
    csv = _write_csv(tmp_path / "labels.csv", [
        {"path": str(img), "has_panels": "true", "note": ""},
    ])
    monkeypatch.setattr(sys, "argv", ["import_labels.py", "--csv", str(csv), "--dry-run"])
    assert import_labels.main() == 0
    assert not import_labels.LABELS_JSONL.exists() or \
        import_labels.LABELS_JSONL.read_text() == ""
    assert not list(import_labels.IMAGES_DIR.iterdir())


def test_missing_source_image_skipped(tmp_path: Path, isolated: Path, monkeypatch) -> None:
    csv = _write_csv(tmp_path / "labels.csv", [
        {"path": str(tmp_path / "does-not-exist.jpg"), "has_panels": "true", "note": ""},
    ])
    monkeypatch.setattr(sys, "argv", ["import_labels.py", "--csv", str(csv)])
    rc = import_labels.main()
    assert rc == 0  # not a failure; just nothing imported
    assert not import_labels.LABELS_JSONL.exists() or \
        import_labels.LABELS_JSONL.read_text() == ""
