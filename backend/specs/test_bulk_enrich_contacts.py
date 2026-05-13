"""Adversarial matrix for POST /api/prospects/bulk-enrich-contacts.

Per spec: backend/specs/bulk_enrich_contacts.md. Each test maps to a numbered
invariant or edge case in the spec. Must all be green before the endpoint
can ship.

Run: python3 -m pytest backend/specs/test_bulk_enrich_contacts.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path
from unittest.mock import AsyncMock, patch

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from fastapi.testclient import TestClient
from main import app
from services.hitta import HittaBlocked, HittaContact, HittaEmpty, HittaResult

client = TestClient(app)


def _result(*contacts: HittaContact, query: str = "test") -> HittaResult:
    return HittaResult(query=query, contacts=list(contacts), total_hits=len(contacts))


def _exact_contact() -> HittaContact:
    return HittaContact(
        kind="person",
        name="Anna Andersson",
        telephone="070-1234567",
        street_address="Kungsgatan 1",
        postal_code="11143",
        city="Stockholm",
    )


# ---------- Adversarial matrix ----------

def test_empty_ids_422():
    """Test 1: empty ids → 422."""
    r = client.post("/api/prospects/bulk-enrich-contacts", json={"ids": []})
    assert r.status_code == 422


def test_idempotent_skip_skips_hitta(seed_prospect):
    """Test 2: idempotent re-run — already-complete row skips hitta call."""
    pid = seed_prospect(address="Kungsgatan 1, 11143 Stockholm",
                       owner_name="Anna Andersson", phone="070-1234567")
    with patch("services.hitta.lookup_hitta", new=AsyncMock()) as mock:
        r = client.post("/api/prospects/bulk-enrich-contacts", json={"ids": [pid]})
    assert r.status_code == 200
    body = r.json()
    assert body["unchanged"] == 1
    assert body["changed"] == 0
    assert mock.call_count == 0  # idempotency must short-circuit before hitta


def test_hitta_blocked_one_row_continues_batch(seed_prospect):
    """Test 3: HittaBlocked on one row — others still process; error_kind set."""
    pid_a = seed_prospect(address="Kungsgatan 1, 11143 Stockholm")
    pid_b = seed_prospect(address="Drottninggatan 2, 11151 Stockholm")

    async def fake_lookup(address: str) -> HittaResult:
        if "Kungsgatan" in address:
            raise HittaBlocked("cf challenge")
        return _result(HittaContact(
            kind="person", name="Bo Berg", telephone="070-9999999",
            street_address="Drottninggatan 2", postal_code="11151", city="Stockholm",
        ))

    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts",
                       json={"ids": [pid_a, pid_b], "min_score": 0.6})
    body = r.json()
    assert r.status_code == 200
    assert body["changed"] == 1  # pid_b
    kinds = [e["error_kind"] for e in body["errors"]]
    assert "HittaBlocked" in kinds


def test_hitta_empty_counts_as_no_match(seed_prospect):
    """Test 4: HittaEmpty (no addr in DB) → no_match, NOT errors."""
    pid = seed_prospect(address="Nonexistent 999, 99999 Nowhere")
    async def fake_lookup(address: str) -> HittaResult:
        raise HittaEmpty("not found")
    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts", json={"ids": [pid]})
    body = r.json()
    assert body["no_match"] == 1
    assert body["errors"] == []


def test_low_score_no_write(seed_prospect):
    """Test 5: best score < min_score → no_match, DB row UNCHANGED."""
    pid = seed_prospect(address="Kungsgatan 1, 11143 Stockholm")
    # Hitta returns a contact in a totally different city
    async def fake_lookup(address: str) -> HittaResult:
        return _result(HittaContact(
            kind="person", name="Wrong Person", telephone="000",
            street_address="Other Street 5", postal_code="22222", city="Göteborg",
        ))
    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts",
                       json={"ids": [pid], "min_score": 0.6})
    body = r.json()
    assert body["no_match"] == 1
    assert body["changed"] == 0
    # DB invariant: name still null
    from api.prospects import db
    with db() as conn:
        row = conn.execute("SELECT owner_name FROM prospects WHERE id=?", (pid,)).fetchone()
    assert row["owner_name"] is None


def test_high_score_writes_row(seed_prospect):
    """Test 6: score >= min_score → changed += 1, DB row updated."""
    pid = seed_prospect(address="Kungsgatan 1, 11143 Stockholm")
    async def fake_lookup(address: str) -> HittaResult:
        return _result(_exact_contact())
    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts",
                       json={"ids": [pid], "min_score": 0.6})
    body = r.json()
    assert body["changed"] == 1
    from api.prospects import db
    with db() as conn:
        row = conn.execute("SELECT owner_name, owner_phone FROM prospects WHERE id=?", (pid,)).fetchone()
    assert row["owner_name"] == "Anna Andersson"
    assert row["owner_phone"] == "070-1234567"


def test_count_invariant(seed_prospect):
    """Test 7: changed + unchanged + no_match + len(errors) == len(ids), all scenarios."""
    a = seed_prospect(address="Kungsgatan 1, 11143 Stockholm")
    b = seed_prospect(address="Done 1, 11111 Stockholm",
                     owner_name="Done", phone="070-0000000")
    c = seed_prospect(address="Empty 1, 99999 Nowhere")

    async def fake_lookup(address: str) -> HittaResult:
        if "Kungsgatan" in address:
            return _result(_exact_contact())
        if "Empty" in address:
            raise HittaEmpty("none")
        return _result()

    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts",
                       json={"ids": [a, b, c], "min_score": 0.6})
    body = r.json()
    assert body["changed"] + body["unchanged"] + body["no_match"] + len(body["errors"]) == 3


def test_no_pii_in_error_logs(seed_prospect):
    """Test 8: PII never reaches error_logger context."""
    pid = seed_prospect(address="Kungsgatan 1, 11143 Stockholm")
    async def fake_lookup(address: str) -> HittaResult:
        raise RuntimeError("boom Anna Andersson 070-1234567")  # name+phone in error str

    captured: list[dict] = []
    def fake_log(phase, e, context=None):
        captured.append({"phase": phase, "context": context or {}})

    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)), \
         patch("error_logger.log_error", side_effect=fake_log):
        client.post("/api/prospects/bulk-enrich-contacts", json={"ids": [pid]})
    for entry in captured:
        ctx = str(entry["context"])
        assert "Anna" not in ctx and "1234567" not in ctx, \
            "PII leaked into error_logger context"


def test_truncation_max_per_request(seed_prospect):
    """Test 10: > max_per_request → first N processed, rest silently dropped."""
    ids = [seed_prospect(address=f"S{i} 1, 11143 Stockholm") for i in range(5)]
    async def fake_lookup(address: str) -> HittaResult:
        raise HittaEmpty("none")
    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts",
                       json={"ids": ids, "max_per_request": 3})
    body = r.json()
    assert body["changed"] + body["unchanged"] + body["no_match"] + len(body["errors"]) == 3


def test_unicode_address(seed_prospect):
    """Test 12: åäö in address — no mojibake on lookup or DB."""
    pid = seed_prospect(address="Götgatan 1, 83131 Östersund")
    async def fake_lookup(address: str) -> HittaResult:
        # Verify hitta got the correct unicode
        assert "Götgatan" in address
        assert "Östersund" in address
        return _result(HittaContact(
            kind="person", name="Östen Östberg", telephone="070-1110000",
            street_address="Götgatan 1", postal_code="83131", city="Östersund",
        ))
    with patch("services.hitta.lookup_hitta", new=AsyncMock(side_effect=fake_lookup)):
        r = client.post("/api/prospects/bulk-enrich-contacts",
                       json={"ids": [pid], "min_score": 0.6})
    body = r.json()
    assert body["changed"] == 1


# ---------- Fixtures ----------

@pytest.fixture
def seed_prospect(tmp_path, monkeypatch):
    """Insert a temporary prospect row, yield its id factory.

    Uses the live db; cleans up after by deleting inserted rows.
    """
    from api.prospects import db
    inserted: list[int] = []

    def make(*, address: str, owner_name: str | None = None,
             phone: str | None = None, lat: float | None = None,
             lng: float | None = None) -> int:
        with db() as conn:
            cur = conn.execute(
                "INSERT INTO prospects (address, owner_name, owner_phone, lat, lng, status) "
                "VALUES (?, ?, ?, ?, ?, 'NEW')",
                (address, owner_name, phone, lat, lng),
            )
            pid = cur.lastrowid
            inserted.append(pid)
            return pid

    yield make

    with db() as conn:
        if inserted:
            placeholders = ",".join("?" * len(inserted))
            conn.execute(f"DELETE FROM prospects WHERE id IN ({placeholders})", inserted)
