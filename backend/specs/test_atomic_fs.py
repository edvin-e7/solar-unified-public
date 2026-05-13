"""Adversarial matrix for services/atomic_fs.py.

Each test maps to a numbered case (A1–A15) in backend/specs/atomic_fs.md.

Run: python3 -m pytest backend/specs/test_atomic_fs.py -v
"""

from __future__ import annotations

import json
import sys
import threading
from pathlib import Path
from unittest.mock import patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import atomic_fs

# ----- A1: normal write to new path -----------------------------------------


def test_a1_normal_bytes_write_to_new_path(tmp_path: Path) -> None:
    target = tmp_path / "new.bin"
    atomic_fs.write_bytes_atomic(target, b"hello")
    assert target.read_bytes() == b"hello"
    assert not (tmp_path / "new.bin.tmp").exists()


def test_a1_normal_text_write_to_new_path(tmp_path: Path) -> None:
    target = tmp_path / "new.txt"
    atomic_fs.write_text_atomic(target, "hello")
    assert target.read_text(encoding="utf-8") == "hello"
    assert not (tmp_path / "new.txt.tmp").exists()


# ----- A2: replace existing file -------------------------------------------


def test_a2_replace_existing_bytes(tmp_path: Path) -> None:
    target = tmp_path / "exists.bin"
    target.write_bytes(b"old content")
    atomic_fs.write_bytes_atomic(target, b"new")
    assert target.read_bytes() == b"new"


def test_a2_replace_existing_text(tmp_path: Path) -> None:
    target = tmp_path / "exists.txt"
    target.write_text("old", encoding="utf-8")
    atomic_fs.write_text_atomic(target, "new")
    assert target.read_text(encoding="utf-8") == "new"


# ----- A3: bytes round-trip including null/0xFF ----------------------------


def test_a3_binary_fidelity_with_null_and_high_bytes(tmp_path: Path) -> None:
    target = tmp_path / "binary.bin"
    data = bytes(range(256))  # every possible byte value
    atomic_fs.write_bytes_atomic(target, data)
    assert target.read_bytes() == data


# ----- A4: UTF-8 with svenska + emoji ---------------------------------------


def test_a4_utf8_svenska_and_emoji(tmp_path: Path) -> None:
    target = tmp_path / "svenska.txt"
    text = "Edvin på Kungsängen 🌞 — Åke Östberg läser CV:n"
    atomic_fs.write_text_atomic(target, text)
    assert target.read_text(encoding="utf-8") == text


# ----- A5: explicit cp1252 encoding ----------------------------------------


def test_a5_explicit_cp1252_encoding(tmp_path: Path) -> None:
    target = tmp_path / "cp1252.txt"
    text = "Åke"  # cp1252-encodable
    atomic_fs.write_text_atomic(target, text, encoding="cp1252")
    assert target.read_text(encoding="cp1252") == text


# ----- A6, A7: empty inputs -------------------------------------------------


def test_a6_empty_bytes(tmp_path: Path) -> None:
    target = tmp_path / "empty.bin"
    atomic_fs.write_bytes_atomic(target, b"")
    assert target.exists()
    assert target.read_bytes() == b""


def test_a7_empty_text(tmp_path: Path) -> None:
    target = tmp_path / "empty.txt"
    atomic_fs.write_text_atomic(target, "")
    assert target.exists()
    assert target.read_text(encoding="utf-8") == ""


# ----- A8: large file -------------------------------------------------------


def test_a8_large_bytes_no_truncation(tmp_path: Path) -> None:
    target = tmp_path / "large.bin"
    data = b"abc" * (10 * 1024 * 1024 // 3)  # ~10 MB
    atomic_fs.write_bytes_atomic(target, data)
    assert target.stat().st_size == len(data)
    assert target.read_bytes() == data


# ----- A9: parent dir missing -----------------------------------------------


def test_a9_parent_missing_raises_filenotfound(tmp_path: Path) -> None:
    target = tmp_path / "nope" / "file.bin"
    with pytest.raises(FileNotFoundError):
        atomic_fs.write_bytes_atomic(target, b"x")
    with pytest.raises(FileNotFoundError):
        atomic_fs.write_text_atomic(target, "x")


# ----- A10: write fails mid-flight ------------------------------------------


def test_a10_crash_mid_write_preserves_original(tmp_path: Path) -> None:
    """Simulate a process that writes the tempfile but dies before replace.

    On disk this manifests as the original `path` content unchanged + a
    `.tmp` file present (or absent, depending on when the crash happened).
    Invariant: reader of `path` sees pre-write content, never partial.
    """
    target = tmp_path / "crash.bin"
    target.write_bytes(b"ORIGINAL")

    # Patch os.replace to raise — simulates kernel killing the process
    # after the tempfile was written but before the rename completed.
    with patch("services.atomic_fs.os.replace", side_effect=OSError("kill -9")):
        with pytest.raises(OSError):
            atomic_fs.write_bytes_atomic(target, b"NEW")

    # Original content intact
    assert target.read_bytes() == b"ORIGINAL"
    # Tempfile may exist (containing NEW); next successful call cleans it up
    # by overwriting. We don't assert on its presence.


# ----- A11: concurrent same-path writers serialised -------------------------


def test_a11_concurrent_writers_serialised(tmp_path: Path) -> None:
    """Two threads write the same path concurrently. The final content is
    one of the two valid payloads — never a mix. The thread-lock prevents
    interleaved writes from corrupting the tempfile."""
    target = tmp_path / "concurrent.bin"
    target.write_bytes(b"INITIAL")

    payload_a = b"A" * 1024
    payload_b = b"B" * 1024

    barrier = threading.Barrier(2)

    def writer(payload: bytes) -> None:
        barrier.wait()
        atomic_fs.write_bytes_atomic(target, payload)

    t1 = threading.Thread(target=writer, args=(payload_a,))
    t2 = threading.Thread(target=writer, args=(payload_b,))
    t1.start()
    t2.start()
    t1.join()
    t2.join()

    final = target.read_bytes()
    assert final in (payload_a, payload_b), "must be one of two valid payloads, not mixed"


# ----- A12: existing .tmp from prior run is overwritten ---------------------


def test_a12_stale_tmp_overwritten(tmp_path: Path) -> None:
    target = tmp_path / "with-stale-tmp.bin"
    stale_tmp = tmp_path / "with-stale-tmp.bin.tmp"
    stale_tmp.write_bytes(b"LEFTOVER FROM PRIOR CRASH")

    atomic_fs.write_bytes_atomic(target, b"NEW")

    assert target.read_bytes() == b"NEW"
    # Tempfile was atomically renamed to target, so .tmp no longer exists
    assert not stale_tmp.exists()


# ----- A13: write_json_atomic re-export matches structured_log -------------


def test_a13_json_atomic_round_trip(tmp_path: Path) -> None:
    target = tmp_path / "data.json"
    data = {"prospects": [{"id": 1, "addr": "Kungsgatan 1"}], "count": 1}
    atomic_fs.write_json_atomic(target, data)
    assert json.loads(target.read_text(encoding="utf-8")) == data


def test_a13_json_atomic_with_list_root(tmp_path: Path) -> None:
    target = tmp_path / "list.json"
    data = [{"a": 1}, {"b": 2}]
    atomic_fs.write_json_atomic(target, data)
    assert json.loads(target.read_text(encoding="utf-8")) == data


# ----- A14: surrogate-pair filename (emoji) ---------------------------------


def test_a14_emoji_in_filename(tmp_path: Path) -> None:
    target = tmp_path / "scan_🌞_solar.jpg"
    atomic_fs.write_bytes_atomic(target, b"jpeg-bytes-here")
    assert target.read_bytes() == b"jpeg-bytes-here"


# ----- A15: permission denied → exception, original intact ------------------


def test_a15_permission_denied_preserves_original(tmp_path: Path) -> None:
    """If the tempfile write fails with PermissionError, original must be
    intact. We simulate this by mocking the tempfile write itself."""
    target = tmp_path / "perm.bin"
    target.write_bytes(b"ORIGINAL")

    with patch("pathlib.Path.write_bytes", side_effect=PermissionError("EACCES")):
        with pytest.raises(PermissionError):
            atomic_fs.write_bytes_atomic(target, b"NEW")

    assert target.read_bytes() == b"ORIGINAL"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
