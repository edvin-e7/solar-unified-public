"""Prospect CRUD — SQLite as the single source of truth.

Replaces localStorage (edvins-solprojekt), data/prospect_database.json (edvin-solar),
and history/*.json (solar-app) with one store.
"""

from __future__ import annotations

import asyncio
import csv
import io
import os
import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from datetime import UTC
from pathlib import Path
from typing import Any

from error_logger import log_error
from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel
from services.geocode import geocode

from api.solar import _google_solar, _pvgis

router = APIRouter()


def _update_prospect(conn: sqlite3.Connection, pid: int, updates: dict) -> None:
    """UPDATE one prospect row with the given column→value map. Touches updated_at."""
    cols = ", ".join(f"{k}=?" for k in updates)
    conn.execute(
        f"UPDATE prospects SET {cols}, updated_at=CURRENT_TIMESTAMP WHERE id=?",
        (*updates.values(), pid),
    )
_DEFAULT_DB_PATH = Path(__file__).parent.parent / "data" / "prospects.db"
DB_PATH = Path(os.getenv("PROSPECTS_DB") or _DEFAULT_DB_PATH)
DB_PATH.parent.mkdir(exist_ok=True)


SCHEMA = """
CREATE TABLE IF NOT EXISTS prospects (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    address TEXT NOT NULL,
    lat REAL,
    lng REAL,
    status TEXT DEFAULT 'new',
    score REAL,
    annual_kwh REAL,
    owner_name TEXT,
    owner_age INTEGER,
    owner_phone TEXT,
    notes TEXT,
    has_panels INTEGER,
    panel_confidence REAL,
    detected_at TEXT,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_prospects_status ON prospects(status);
CREATE INDEX IF NOT EXISTS idx_prospects_score ON prospects(score DESC);
"""


_PANEL_COLUMNS = (
    ("has_panels", "INTEGER"),
    ("panel_confidence", "REAL"),
    ("detected_at", "TEXT"),
)


def _migrate(conn: sqlite3.Connection) -> None:
    existing = {r[1] for r in conn.execute("PRAGMA table_info(prospects)")}
    for name, coltype in _PANEL_COLUMNS:
        if name not in existing:
            conn.execute(f"ALTER TABLE prospects ADD COLUMN {name} {coltype}")
    conn.execute("CREATE INDEX IF NOT EXISTS idx_prospects_has_panels ON prospects(has_panels)")


@contextmanager
def db() -> Iterator[sqlite3.Connection]:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    try:
        conn.executescript(SCHEMA)
        _migrate(conn)
        yield conn
        conn.commit()
    finally:
        conn.close()


class Prospect(BaseModel):
    id: int | None = None
    address: str
    lat: float | None = None
    lng: float | None = None
    status: str = "new"
    score: float | None = None
    annual_kwh: float | None = None
    owner_name: str | None = None
    owner_age: int | None = None
    owner_phone: str | None = None
    notes: str | None = None
    has_panels: int | None = None
    panel_confidence: float | None = None
    detected_at: str | None = None


class BatchInput(BaseModel):
    prospects: list[dict]
    sort_by: str = "score"


@router.get("")
async def list_prospects(
    q: str | None = None,
    status: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int = 500,
) -> list[dict]:
    clauses: list[str] = []
    params: list[Any] = []
    if q:
        clauses.append("(LOWER(address) LIKE ? OR LOWER(COALESCE(owner_name,'')) LIKE ?)")
        needle = f"%{q.lower()}%"
        params.extend([needle, needle])
    if status:
        clauses.append("status = ?")
        params.append(status)
    else:
        clauses.append("status != ?")
        params.append("rejected")
    if min_score is not None:
        clauses.append("COALESCE(score, 0) >= ?")
        params.append(min_score)
    if max_score is not None:
        clauses.append("COALESCE(score, 0) <= ?")
        params.append(max_score)
    where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
    query = f"SELECT * FROM prospects {where} ORDER BY score DESC NULLS LAST LIMIT ?"
    params.append(limit)
    with db() as conn:
        return [dict(r) for r in conn.execute(query, params)]


def _create_prospect_sync(p: Prospect) -> dict:
    with db() as conn:
        cur = conn.execute(
            """INSERT INTO prospects(address, lat, lng, status, score, annual_kwh,
                                      owner_name, owner_age, owner_phone, notes)
               VALUES(?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (p.address, p.lat, p.lng, p.status, p.score, p.annual_kwh,
             p.owner_name, p.owner_age, p.owner_phone, p.notes),
        )
        return {"id": cur.lastrowid, **p.model_dump(exclude={"id"})}


@router.post("")
async def create_prospect(p: Prospect) -> dict:
    return await asyncio.to_thread(_create_prospect_sync, p)


def _update_prospect_sync(prospect_id: int, p: Prospect) -> dict:
    with db() as conn:
        cur = conn.execute(
            """UPDATE prospects SET address=?, lat=?, lng=?, status=?, score=?,
                   annual_kwh=?, owner_name=?, owner_age=?, owner_phone=?, notes=?,
                   updated_at=CURRENT_TIMESTAMP WHERE id=?""",
            (p.address, p.lat, p.lng, p.status, p.score, p.annual_kwh,
             p.owner_name, p.owner_age, p.owner_phone, p.notes, prospect_id),
        )
        if cur.rowcount == 0:
            raise HTTPException(404, "Prospect not found")
        return {"id": prospect_id, **p.model_dump(exclude={"id"})}


@router.put("/{prospect_id}")
async def update_prospect(prospect_id: int, p: Prospect) -> dict:
    return await asyncio.to_thread(_update_prospect_sync, prospect_id, p)


def _delete_prospect_sync(prospect_id: int) -> dict:
    with db() as conn:
        cur = conn.execute("DELETE FROM prospects WHERE id=?", (prospect_id,))
        if cur.rowcount == 0:
            raise HTTPException(404, "Prospect not found")
        return {"ok": True}


@router.delete("/{prospect_id}")
async def delete_prospect(prospect_id: int) -> dict:
    return await asyncio.to_thread(_delete_prospect_sync, prospect_id)


class BulkCsvPayload(BaseModel):
    csv_text: str


def _bulk_import_csv_sync(payload: BulkCsvPayload) -> dict:
    """Bulk import prospects from CSV text.

    Two modes:

    1. **Header mode** — first line contains the literal `address` column
       header. Parsed as CSV; extra columns (`owner_name`, `owner_phone`,
       `notes`) are picked up if present.

    2. **Address-per-line mode** — no `address` header detected. Each
       *line* (split on \\n) is treated as a single address string. Commas
       inside lines are kept verbatim (so `"Storgatan 12, Falun"` stays
       intact instead of being split into `["Storgatan 12", " Falun"]`).
       This is the common paste-from-CRM case and was the origin of the
       silent-data-corruption bug noted in the architecture review.

    Empty lines are skipped, not counted as errors.

    Returns: {"created": N, "skipped": M, "errors": [...]}
    """
    text = payload.csv_text.strip()
    if not text:
        raise HTTPException(422, "Empty CSV input")

    first_line = text.splitlines()[0]
    has_address_header = any(
        c.strip().lower() == "address" for c in next(csv.reader(io.StringIO(first_line)))
    )

    created = 0
    skipped = 0
    errors: list[str] = []

    with db() as conn:
        if has_address_header:
            reader = csv.reader(io.StringIO(text))
            rows = list(reader)
            header = [h.strip().lower() for h in rows[0]]
            for idx, row in enumerate(rows[1:]):
                if not row or not any(c.strip() for c in row):
                    skipped += 1
                    continue
                try:
                    record = dict(zip(header, [c.strip() for c in row], strict=False))
                    address = record.get("address", "").strip()
                    if not address:
                        skipped += 1
                        continue
                    conn.execute(
                        """INSERT INTO prospects(address, owner_name, owner_phone, notes)
                           VALUES(?, ?, ?, ?)""",
                        (
                            address,
                            record.get("owner_name") or None,
                            record.get("owner_phone") or None,
                            record.get("notes") or None,
                        ),
                    )
                    created += 1
                except sqlite3.Error as e:
                    errors.append(f"Row {idx + 2}: {e}")
        else:
            for idx, line in enumerate(text.splitlines()):
                address = line.strip()
                if not address:
                    skipped += 1
                    continue
                try:
                    conn.execute("INSERT INTO prospects(address) VALUES(?)", (address,))
                    created += 1
                except sqlite3.Error as e:
                    errors.append(f"Line {idx + 1}: {e}")

    return {"created": created, "skipped": skipped, "errors": errors[:10]}


@router.post("/bulk-csv")
async def bulk_import_csv(payload: BulkCsvPayload) -> dict:
    """Bulk import prospects from CSV text. See `_bulk_import_csv_sync`."""
    return await asyncio.to_thread(_bulk_import_csv_sync, payload)


class BulkStatusUpdate(BaseModel):
    ids: list[int]
    status: str


def _bulk_update_status_sync(payload: BulkStatusUpdate) -> dict:
    if not payload.ids:
        raise HTTPException(422, "Empty ids list")
    if payload.status not in {"new", "interested", "callback", "rejected"}:
        raise HTTPException(422, f"Invalid status: {payload.status}")

    placeholders = ",".join("?" * len(payload.ids))
    with db() as conn:
        cur = conn.execute(
            f"""UPDATE prospects SET status=?, updated_at=CURRENT_TIMESTAMP
                WHERE id IN ({placeholders})""",
            (payload.status, *payload.ids),
        )
        return {"updated": cur.rowcount}


@router.post("/bulk-status")
async def bulk_update_status(payload: BulkStatusUpdate) -> dict:
    """Update status for multiple prospects at once."""
    return await asyncio.to_thread(_bulk_update_status_sync, payload)


class BulkDelete(BaseModel):
    ids: list[int]


def _bulk_delete_sync(payload: BulkDelete) -> dict:
    if not payload.ids:
        raise HTTPException(422, "Empty ids list")
    placeholders = ",".join("?" * len(payload.ids))
    with db() as conn:
        cur = conn.execute(
            f"DELETE FROM prospects WHERE id IN ({placeholders})", tuple(payload.ids)
        )
        return {"deleted": cur.rowcount}


@router.post("/bulk-delete")
async def bulk_delete(payload: BulkDelete) -> dict:
    """Delete multiple prospects at once."""
    return await asyncio.to_thread(_bulk_delete_sync, payload)


def _stats_sync() -> dict:
    with db() as conn:
        total = conn.execute("SELECT COUNT(*) AS n FROM prospects").fetchone()["n"]
        by_status = {
            r["status"]: r["n"]
            for r in conn.execute(
                "SELECT status, COUNT(*) AS n FROM prospects GROUP BY status"
            )
        }
        avg_score = conn.execute(
            "SELECT AVG(score) AS avg FROM prospects WHERE score IS NOT NULL"
        ).fetchone()["avg"]
        enriched = conn.execute(
            "SELECT COUNT(*) AS n FROM prospects WHERE owner_name IS NOT NULL"
        ).fetchone()["n"]
        daily = [
            dict(r)
            for r in conn.execute(
                """SELECT DATE(created_at) AS day, COUNT(*) AS n
                   FROM prospects
                   WHERE created_at >= DATE('now', '-7 days')
                   GROUP BY DATE(created_at)
                   ORDER BY day"""
            )
        ]

    interested = by_status.get("interested", 0)
    conversion_rate = (interested / total * 100) if total > 0 else 0.0
    enrichment_rate = (enriched / total * 100) if total > 0 else 0.0

    return {
        "total": total,
        "by_status": by_status,
        "avg_score": round(avg_score or 0.0, 2),
        "conversion_rate": round(conversion_rate, 1),
        "enrichment_rate": round(enrichment_rate, 1),
        "daily": daily,
    }


@router.get("/stats")
async def stats() -> dict:
    """Performance dashboard metrics."""
    return await asyncio.to_thread(_stats_sync)


def record_scan_result(result: dict) -> int:
    """Record a scan result into the prospects database.
    Updates existing prospect if address matches, else creates new.
    Persists has_panels / panel_confidence / detected_at for panel-owner catalog.
    """
    address = result["address"]
    has_panels = 1 if result.get("has_panels") else 0
    confidence = float(result.get("confidence", 0) or 0)
    score = confidence * 100 if has_panels else 0
    detected_at = result.get("scanned_at")
    with db() as conn:
        existing = conn.execute("SELECT id FROM prospects WHERE address = ?", (address,)).fetchone()
        if existing:
            conn.execute(
                """UPDATE prospects SET lat=?, lng=?, score=?, notes=?,
                       has_panels=?, panel_confidence=?, detected_at=?,
                       updated_at=CURRENT_TIMESTAMP WHERE id=?""",
                (result["lat"], result["lng"], score, result.get("reasoning"),
                 has_panels, confidence, detected_at, existing["id"]),
            )
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO prospects (address, lat, lng, score, notes,
                   has_panels, panel_confidence, detected_at)
               VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
            (address, result["lat"], result["lng"], score, result.get("reasoning"),
             has_panels, confidence, detected_at),
        )
        return cur.lastrowid


def _export_csv_sync(
    *,
    status: str | None = None,
    region: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int | None = None,
    exclude_owner_names: bool = False,
) -> io.StringIO:
    """Internal CSV-export with rich filters. Used by lead-byrå deliveries.

    Filters compose (AND):
      status="qualified" → only rows where status matches
      region="Stockholm"  → SQL LIKE %region% on address (substring match)
      min_score=0.6       → only rows with score >= 0.6
      max_score=0.95      → only rows with score <= 0.95 (för Premium-tier slicing)
      limit=500           → cap result count (no limit → all matching)
      exclude_owner_names=True → omit owner_name/age/phone cols (GDPR-light)
    """
    buf = io.StringIO()
    writer = csv.writer(buf)

    # Column-set varies by GDPR-mode
    if exclude_owner_names:
        cols = ["id", "address", "lat", "lng", "status", "score", "annual_kwh",
                "notes", "has_panels", "panel_confidence", "detected_at", "created_at"]
    else:
        cols = ["id", "address", "lat", "lng", "status", "score", "annual_kwh",
                "owner_name", "owner_age", "owner_phone", "notes",
                "has_panels", "panel_confidence", "detected_at", "created_at"]
    writer.writerow(cols)

    query = "SELECT * FROM prospects WHERE 1=1"
    args: list = []
    if status:
        query += " AND status = ?"
        args.append(status)
    if region:
        query += " AND address LIKE ?"
        args.append(f"%{region}%")
    if min_score is not None:
        query += " AND score IS NOT NULL AND score >= ?"
        args.append(min_score)
    if max_score is not None:
        query += " AND score IS NOT NULL AND score <= ?"
        args.append(max_score)
    query += " ORDER BY score DESC NULLS LAST"
    if limit is not None and limit > 0:
        query += " LIMIT ?"
        args.append(limit)

    with db() as conn:
        for r in conn.execute(query, tuple(args)):
            writer.writerow([r[c] for c in cols])

    buf.seek(0)
    return buf


@router.get("/export/csv")
async def export_csv(
    status: str | None = None,
    region: str | None = None,
    min_score: float | None = None,
    max_score: float | None = None,
    limit: int | None = None,
    exclude_owner_names: bool = False,
) -> StreamingResponse:
    """Export prospects as CSV. Supports filters for lead-byrå deliveries.

    Query-params (all optional, compose with AND):
      status              — t.ex. "qualified" (filter on status column)
      region              — substring-match på address (för Stockholm-leveranser)
      min_score, max_score — float thresholds, för Premium-tier slicing
      limit               — max rader (för paket-storlek)
      exclude_owner_names — om true: utelämna owner_name/age/phone (GDPR-light)

    Filename inkluderar timestamp för audit-spår av leveranser.
    """
    if min_score is not None and (min_score < 0 or min_score > 1):
        raise HTTPException(422, "min_score must be 0-1")
    if max_score is not None and (max_score < 0 or max_score > 1):
        raise HTTPException(422, "max_score must be 0-1")
    if limit is not None and limit < 0:
        raise HTTPException(422, "limit must be positive")

    buf = await asyncio.to_thread(
        _export_csv_sync,
        status=status, region=region,
        min_score=min_score, max_score=max_score,
        limit=limit, exclude_owner_names=exclude_owner_names,
    )
    from datetime import datetime
    fname = f"prospects-{datetime.now(UTC).strftime('%Y-%m-%d')}.csv"
    headers = {"Content-Disposition": f"attachment; filename={fname}"}
    return StreamingResponse(
        iter([buf.getvalue()]), media_type="text/csv", headers=headers
    )


class BulkGeocode(BaseModel):
    ids: list[int]


@router.post("/bulk-geocode")
async def bulk_geocode(payload: BulkGeocode) -> dict:
    """Fill missing lat/lng + annual_kwh on the given prospects.

    NOT contact enrichment — does not touch owner_name/phone/age. Skips rows that
    already have both lat/lng and annual_kwh set. Per-prospect failures don't abort
    the batch. Nominatim asks clients to keep to ~1 req/sec — we sleep between geocodes.

    Returns {changed: rows we wrote to DB, unchanged: rows that were already complete,
    errors: per-row failures}.
    """
    if not payload.ids:
        raise HTTPException(422, "Empty ids list")

    placeholders = ",".join("?" * len(payload.ids))
    with db() as conn:
        rows = [dict(r) for r in conn.execute(
            f"SELECT * FROM prospects WHERE id IN ({placeholders})", tuple(payload.ids)
        )]

    changed = 0
    errors: list[dict] = []
    needed_geocode = False

    for row in rows:
        pid = row["id"]
        updates: dict = {}

        try:
            if row["lat"] is None or row["lng"] is None:
                if needed_geocode:
                    await asyncio.sleep(1.1)
                lat, lng = await geocode(row["address"])
                updates["lat"], updates["lng"] = lat, lng
                needed_geocode = True
            else:
                lat, lng = row["lat"], row["lng"]

            if row["annual_kwh"] is None:
                solar = await _google_solar(lat, lng)
                if solar:
                    updates["annual_kwh"] = solar["maxArrayAnnualEnergyKwh"]
                else:
                    pvgis = await _pvgis(lat, lng)
                    if pvgis:
                        updates["annual_kwh"] = pvgis

            if updates:
                with db() as conn:
                    _update_prospect(conn, pid, updates)
                changed += 1
        except Exception as e:  # noqa: BLE001 -- per-row fail-soft into errors[]
            log_error("api-prospects-bulk-geocode-row", e,
                      context={"id": pid, "address": row["address"]})
            errors.append({"id": pid, "address": row["address"], "error": str(e)})

    return {"changed": changed, "unchanged": len(rows) - changed - len(errors), "errors": errors}


class BulkEnrichContacts(BaseModel):
    ids: list[int]
    min_score: float = 0.6
    max_per_request: int = 50


@router.post("/bulk-enrich-contacts")
async def bulk_enrich_contacts(payload: BulkEnrichContacts) -> dict:
    """Hitta-based contact (name+phone) enrichment for a batch of prospects.

    See backend/specs/bulk_enrich_contacts.md for the full contract + matrix.

    NOT geocoding — leaves lat/lng/annual_kwh untouched. NOT mrkoll/birthday —
    Electron renderer path. owner_age stays unset (hitta doesn't expose it).
    """
    if not payload.ids:
        raise HTTPException(422, "Empty ids list")

    from services import address_match
    from services import hitta as hitta_svc
    from services.hitta import HittaBlocked, HittaEmpty

    from api.enrich import _pick_best, _score_and_sort

    ids = payload.ids[: payload.max_per_request]
    placeholders = ",".join("?" * len(ids))
    with db() as conn:
        rows = [dict(r) for r in conn.execute(
            f"SELECT id, address, owner_name, owner_phone FROM prospects "
            f"WHERE id IN ({placeholders})", tuple(ids)
        )]

    changed = unchanged = no_match = 0
    errors: list[dict] = []
    needed_lookup = False

    for row in rows:
        pid, addr = row["id"], row["address"]
        if row["owner_name"] and row["owner_phone"]:
            unchanged += 1
            continue
        if needed_lookup:
            await asyncio.sleep(1.1)
        needed_lookup = True
        try:
            result = await hitta_svc.lookup_hitta(addr)
        except HittaEmpty:
            no_match += 1
            continue
        except HittaBlocked as e:
            log_error("api-prospects-bulk-enrich-contacts-row", e,
                      context={"id": pid, "address": addr, "kind": "HittaBlocked"})
            errors.append({"id": pid, "address": addr,
                          "error_kind": "HittaBlocked", "error": str(e)})
            continue
        except Exception as e:  # noqa: BLE001 -- per-row fail-soft after typed HittaEmpty/HittaBlocked
            log_error("api-prospects-bulk-enrich-contacts-row", e,
                      context={"id": pid, "address": addr, "kind": type(e).__name__})
            errors.append({"id": pid, "address": addr,
                          "error_kind": type(e).__name__, "error": str(e)})
            continue

        scored = _score_and_sort(result.contacts, address_match.normalize(addr))
        if not scored or scored[0][1].score < payload.min_score:
            no_match += 1
            continue
        best, _ = _pick_best(scored)
        if not best:
            no_match += 1
            continue
        with db() as conn:
            _update_prospect(conn, pid, {"owner_name": best.name,
                                         "owner_phone": best.telephone})
        changed += 1

    return {"changed": changed, "unchanged": unchanged,
            "no_match": no_match, "errors": errors}


@router.post("/sort")
async def sort_prospects(batch: BatchInput) -> dict:
    """Sort prospects by the specified dimension (score, address, status)."""
    # Defensive coding: handle potentially missing fields without zero-filling
    def get_val(p: dict[str, Any], key: str) -> Any:
        return p.get(key) if p.get(key) is not None else (0 if key == "score" else "")

    if batch.sort_by == "score":
        sorted_list = sorted(batch.prospects, key=lambda p: get_val(p, "score"), reverse=True)
    elif batch.sort_by == "address":
        sorted_list = sorted(batch.prospects, key=lambda p: get_val(p, "address"))
    elif batch.sort_by == "status":
        sorted_list = sorted(batch.prospects, key=lambda p: get_val(p, "status"))
    else:
        sorted_list = batch.prospects

    return {"sorted": sorted_list, "count": len(sorted_list)}


@router.post("/route")
async def route_prospects(batch: BatchInput) -> dict:
    """Route prospects into geographic buckets based on address."""
    buckets: dict[str, list[dict]] = {}
    # Simple keyword routing for Sweden
    regions = {
        "stockholm": ["stockholm", "nacka", "täby", "solna", "huddinge"],
        "gothenburg": ["göteborg", "gothenburg", "mölndal", "partille"],
        "malmo": ["malmö", "malmo", "lund", "vellinge"],
        "uppsala": ["uppsala"],
    }

    for p in batch.prospects:
        addr = p.get("address", "").lower()
        found = False
        for region, kws in regions.items():
            if any(kw in addr for kw in kws):
                buckets.setdefault(region, []).append(p)
                found = True
                break
        if not found:
            buckets.setdefault("other", []).append(p)

    return buckets
