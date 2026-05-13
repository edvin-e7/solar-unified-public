"""
Adversarial test matrix för /api/prospects/export/csv per spec export_csv.md.

Testar invariants I1-I10 plus edge-cases. Använder in-memory SQLite (PROSPECTS_DB env)
för isolering — no taint på Edvins riktiga prospects.db.

Kör:  pytest backend/specs/test_export_csv.py -v
"""

from __future__ import annotations

import csv
import io
import tempfile
from pathlib import Path

import pytest


@pytest.fixture
def isolated_db(monkeypatch):
    """Isolated SQLite DB per test — populates a temp file."""
    tmp = tempfile.NamedTemporaryFile(suffix=".db", delete=False)
    tmp.close()
    monkeypatch.setenv("PROSPECTS_DB", tmp.name)

    # Re-import to pick up new env
    import importlib

    from api import prospects as prospects_mod
    importlib.reload(prospects_mod)

    # Initialize schema
    from api.prospects import SCHEMA, db
    with db() as conn:
        conn.executescript(SCHEMA)

    yield tmp.name

    Path(tmp.name).unlink(missing_ok=True)


def _insert(conn, **kwargs):
    """Insert a prospect row with defaults."""
    defaults = {
        "address": "Test address 1",
        "status": "new",
        "score": None,
        "annual_kwh": None,
        "owner_name": None,
        "owner_age": None,
        "owner_phone": None,
        "notes": None,
        "has_panels": None,
        "panel_confidence": None,
        "detected_at": None,
    }
    defaults.update(kwargs)
    cols = ", ".join(defaults.keys())
    placeholders = ", ".join("?" * len(defaults))
    conn.execute(f"INSERT INTO prospects ({cols}) VALUES ({placeholders})",
                 tuple(defaults.values()))


def _csv_from_buf(buf: io.StringIO) -> list[list[str]]:
    buf.seek(0)
    return list(csv.reader(buf))


# ── I8: Empty DB → header-only CSV ──

def test_empty_db_returns_header_only(isolated_db):
    from api.prospects import _export_csv_sync
    buf = _export_csv_sync()
    rows = _csv_from_buf(buf)
    assert len(rows) == 1  # only header
    assert rows[0][0] == "id"


# ── I2: Sort descending by score, NULLs last ──

def test_sort_desc_score_nulls_last(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        _insert(conn, address="A", score=0.5)
        _insert(conn, address="B", score=0.9)
        _insert(conn, address="C", score=None)
        _insert(conn, address="D", score=0.7)
    buf = _export_csv_sync()
    rows = _csv_from_buf(buf)
    addresses = [r[1] for r in rows[1:]]
    # B=0.9, D=0.7, A=0.5, C=NULL
    assert addresses == ["B", "D", "A", "C"]


# ── I3: Limit caps result ──

def test_limit_caps_result(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        for i in range(5):
            _insert(conn, address=f"addr-{i}", score=0.1 * i)
    buf = _export_csv_sync(limit=3)
    rows = _csv_from_buf(buf)
    assert len(rows) == 4  # header + 3


def test_limit_zero_returns_all(isolated_db):
    """limit=0 disables limit, returns all (per implementation: 'if limit > 0')."""
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        for i in range(5):
            _insert(conn, address=f"addr-{i}", score=0.1 * i)
    buf = _export_csv_sync(limit=0)
    rows = _csv_from_buf(buf)
    assert len(rows) == 6  # header + 5


# ── I4: GDPR-mode skips 3 cols ──

def test_gdpr_mode_omits_owner_cols(isolated_db):
    from api.prospects import _export_csv_sync
    buf_normal = _export_csv_sync()
    buf_gdpr = _export_csv_sync(exclude_owner_names=True)
    rows_normal = _csv_from_buf(buf_normal)
    rows_gdpr = _csv_from_buf(buf_gdpr)
    # Owner-cols stripped from header
    assert "owner_name" in rows_normal[0]
    assert "owner_name" not in rows_gdpr[0]
    assert "owner_age" not in rows_gdpr[0]
    assert "owner_phone" not in rows_gdpr[0]


# ── I5: Filter compose AND ──

def test_filter_compose_status_and_score(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        _insert(conn, address="A", status="qualified", score=0.8)
        _insert(conn, address="B", status="qualified", score=0.4)
        _insert(conn, address="C", status="new", score=0.9)
    buf = _export_csv_sync(status="qualified", min_score=0.6)
    rows = _csv_from_buf(buf)
    addresses = [r[1] for r in rows[1:]]
    assert addresses == ["A"]  # only qualified AND score>=0.6


# ── I6: Region substring match ──

def test_region_substring_matches(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        _insert(conn, address="Sveavägen 10, Stockholm", score=0.5)
        _insert(conn, address="Storgatan 1, Göteborg", score=0.5)
        _insert(conn, address="Östra Hamngatan 5, Solna", score=0.5)
    buf = _export_csv_sync(region="Stockholm")
    rows = _csv_from_buf(buf)
    addresses = [r[1] for r in rows[1:]]
    assert len(addresses) == 1
    assert "Stockholm" in addresses[0]


# ── I7: NULL scores filtered out when min/max_score set ──

def test_null_score_excluded_when_min_score_set(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        _insert(conn, address="A", score=0.7)
        _insert(conn, address="B", score=None)
    buf = _export_csv_sync(min_score=0.5)
    rows = _csv_from_buf(buf)
    addresses = [r[1] for r in rows[1:]]
    assert "A" in addresses
    assert "B" not in addresses


# ── Intersection-empty produces empty result without crash ──

def test_intersection_empty_returns_header_only(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        _insert(conn, address="A", score=0.5)
    # min_score=0.7 + max_score=0.6 → empty
    buf = _export_csv_sync(min_score=0.7, max_score=0.6)
    rows = _csv_from_buf(buf)
    assert len(rows) == 1  # header only


# ── I1: Idempotency — same params → same output ──

def test_idempotent_same_output(isolated_db):
    from api.prospects import _export_csv_sync, db
    with db() as conn:
        for i in range(3):
            _insert(conn, address=f"a-{i}", score=0.1 * i)
    out1 = _export_csv_sync().getvalue()
    out2 = _export_csv_sync().getvalue()
    assert out1 == out2
