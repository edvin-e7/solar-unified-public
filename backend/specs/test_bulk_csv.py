"""Adversarial matrix for backend/api/prospects.py::_bulk_import_csv_sync.

Spec: backend/specs/bulk_csv.md.

Each test points the prospects module at a fresh in-memory-ish sqlite db
under tmp_path so we don't trample backend/data/prospects.db.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def isolated_prospects(tmp_path, monkeypatch):
    """Point api.prospects at a fresh tmp DB. monkeypatch.setattr is reliable
    even when the module is already imported (env var trick fails after a
    cached import; setattr always wins)."""
    db_path = tmp_path / "prospects.db"
    from api import prospects  # type: ignore

    monkeypatch.setattr(prospects, "DB_PATH", db_path)
    # First db() call creates schema via executescript(SCHEMA) — no manual init needed.
    return prospects


def _payload(text):
    from api.prospects import BulkCsvPayload  # type: ignore

    return BulkCsvPayload(csv_text=text)


def _all_addresses(prospects_module):
    with prospects_module.db() as conn:
        return [r[0] for r in conn.execute("SELECT address FROM prospects ORDER BY id")]


def test_single_line_no_comma_creates_one(isolated_prospects):
    r = isolated_prospects._bulk_import_csv_sync(_payload("Storgatan 12 Falun"))
    assert r == {"created": 1, "skipped": 0, "errors": []}
    assert _all_addresses(isolated_prospects) == ["Storgatan 12 Falun"]


def test_single_line_with_comma_keeps_city(isolated_prospects):
    """The bug-of-record: comma between street and city used to truncate."""
    r = isolated_prospects._bulk_import_csv_sync(_payload("Storgatan 12, Falun"))
    assert r["created"] == 1
    assert _all_addresses(isolated_prospects) == ["Storgatan 12, Falun"]


def test_multi_line_address_per_line_preserves_cities(isolated_prospects):
    text = "Storgatan 12, Falun\nKungsgatan 5, Borlänge\nVasagatan 8, Falun"
    r = isolated_prospects._bulk_import_csv_sync(_payload(text))
    assert r["created"] == 3
    assert _all_addresses(isolated_prospects) == [
        "Storgatan 12, Falun",
        "Kungsgatan 5, Borlänge",
        "Vasagatan 8, Falun",
    ]


def test_blank_lines_skipped(isolated_prospects):
    text = "Storgatan 12, Falun\n\n\nKungsgatan 5, Borlänge\n"
    r = isolated_prospects._bulk_import_csv_sync(_payload(text))
    assert r["created"] == 2
    assert r["skipped"] == 2  # the two blank intermediate lines


def test_header_mode_with_address_column(isolated_prospects):
    text = "address,owner_name,owner_phone\nStorgatan 12 Falun,Anna,070-1111111"
    r = isolated_prospects._bulk_import_csv_sync(_payload(text))
    assert r["created"] == 1
    with isolated_prospects.db() as conn:
        row = conn.execute("SELECT address, owner_name, owner_phone FROM prospects").fetchone()
    assert row[0] == "Storgatan 12 Falun"
    assert row[1] == "Anna"
    assert row[2] == "070-1111111"


def test_header_mode_ignores_unknown_columns(isolated_prospects):
    text = "address,unknown_col,owner_name\nStorgatan 12,xyz,Anna"
    r = isolated_prospects._bulk_import_csv_sync(_payload(text))
    assert r["created"] == 1


def test_crlf_line_endings(isolated_prospects):
    text = "Storgatan 12, Falun\r\nKungsgatan 5, Borlänge"
    r = isolated_prospects._bulk_import_csv_sync(_payload(text))
    assert r["created"] == 2
    addrs = _all_addresses(isolated_prospects)
    # \r should not be left dangling on the first address
    assert all(not a.endswith("\r") for a in addrs)
    assert "Storgatan 12, Falun" in addrs


def test_empty_input_raises_422(isolated_prospects):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        isolated_prospects._bulk_import_csv_sync(_payload(""))
    assert exc.value.status_code == 422


def test_whitespace_only_input_raises_422(isolated_prospects):
    from fastapi import HTTPException

    with pytest.raises(HTTPException) as exc:
        isolated_prospects._bulk_import_csv_sync(_payload("   \n\n\t"))
    assert exc.value.status_code == 422


def test_only_blank_lines_after_strip(isolated_prospects):
    """Input that is non-empty after .strip() but contains only blanks."""
    text = "Storgatan 12 Falun\n\n\n"
    r = isolated_prospects._bulk_import_csv_sync(_payload(text))
    assert r["created"] == 1
    # Trailing blank lines were skipped — no error
    assert r["skipped"] == 0  # they were inside the .strip()ed text, but splitlines() preserves them
