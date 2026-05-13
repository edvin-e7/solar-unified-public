"""Lead-byrå orchestration — one-button pipeline for solar-installer deliveries.

Composes existing endpoints into a single sales-ready call:
  1. /api/scan/area (municipality + radius)         — Overpass building harvest
  2. /api/detect/batch (addresses)                  — Moondream detection per building
  3. /api/prospects/export/csv (region filter)      — CSV deliverable

Saves having to script three separate cURL invocations during a live demo.
"""

from __future__ import annotations

import asyncio
import csv
import io
from datetime import UTC, datetime
from typing import Any

from fastapi import APIRouter, HTTPException
from fastapi.responses import StreamingResponse
from pydantic import BaseModel, Field
from services import lead_report, overpass, scanner

from api.prospects import _export_csv_sync, db, record_scan_result

router = APIRouter()


class LeadsSnapshotRequest(BaseModel):
    """One-button lead-snapshot request.

    Either `municipality` (geocoded to center) or `lat`+`lng` required.
    """

    municipality: str | None = None
    lat: float | None = None
    lng: float | None = None
    radius_m: int = Field(2000, gt=0, le=20000)
    building_limit: int = Field(20, gt=0, le=200, description="Max buildings to scan (cost-cap)")
    detect: bool = Field(True, description="Run Moondream detection on harvested buildings")
    skip_existing: bool = Field(True, description="Skip buildings whose address is already in DB")


class LeadsSnapshotResponse(BaseModel):
    """Stats + CSV-export URL for the freshly-built batch."""

    region: str
    radius_m: int
    buildings_found: int
    new_prospects: int
    scanned: int
    scan_errors: int
    csv_path: str
    elapsed_seconds: float


async def _harvest_and_scan(req: LeadsSnapshotRequest) -> tuple[list[dict], int, list[dict]]:
    """Inner pipeline: Overpass → enqueue → optional detect.

    Returns (scan_results, new_prospects_count, scan_errors).
    """
    # Resolve center
    if req.lat is not None and req.lng is not None:
        lat, lng = req.lat, req.lng
    elif req.municipality:
        from services import geocode as geocode_mod
        try:
            lat, lng = await geocode_mod.geocode(req.municipality)
        except ValueError as e:
            raise HTTPException(422, f"Could not geocode municipality: {e}")
    else:
        raise HTTPException(422, "Provide municipality or lat+lng")

    # Overpass harvest
    try:
        houses = await overpass.fetch_houses_around(lat, lng, req.radius_m, limit=req.building_limit)
    except RuntimeError as e:
        raise HTTPException(502, f"Overpass upstream: {e}")

    # Enqueue new prospects (dedupe on address)
    new_count = 0
    queued_addresses: list[str] = []
    with db() as conn:
        existing = {
            r[0].strip().lower()
            for r in conn.execute("SELECT address FROM prospects")
        }
        for h in houses:
            queued_addresses.append(h.address)
            if req.skip_existing and h.address.lower() in existing:
                continue
            conn.execute(
                "INSERT INTO prospects (address, lat, lng, status) VALUES (?, ?, ?, 'new')",
                (h.address, h.lat, h.lng),
            )
            existing.add(h.address.lower())
            new_count += 1

    # Optional detection
    scan_results: list[dict] = []
    scan_errors: list[dict] = []
    if req.detect:
        for addr in queued_addresses:
            try:
                result = dict(await scanner.scan_address(addr))
                scan_results.append(result)
                record_scan_result(result)
            except Exception as exc:  # noqa: BLE001 -- per-item fail-soft
                from error_logger import log_error
                log_error("leads-snapshot-scan", exc, context={"address": addr})
                scan_errors.append({"address": addr, "error": str(exc)})

    return scan_results, new_count, scan_errors


@router.post("/snapshot", response_model=LeadsSnapshotResponse)
async def leads_snapshot(req: LeadsSnapshotRequest) -> dict:
    """One-shot: harvest → enqueue → scan → return CSV-export-URL + stats.

    Designed for sales demos: a single call against a Swedish municipality
    produces a deliverable CSV at a known path. The caller (or sales person)
    then downloads via GET /api/prospects/export/csv?region=… for the actual
    file.
    """
    t0 = datetime.now(UTC)
    scan_results, new_count, scan_errors = await _harvest_and_scan(req)
    elapsed = (datetime.now(UTC) - t0).total_seconds()

    region_label = req.municipality or f"{req.lat:.4f},{req.lng:.4f}"
    csv_url_path = f"/api/prospects/export/csv?region={req.municipality or ''}&status=new"

    return {
        "region": region_label,
        "radius_m": req.radius_m,
        "buildings_found": len(scan_results) + len(scan_errors),
        "new_prospects": new_count,
        "scanned": len(scan_results),
        "scan_errors": len(scan_errors),
        "csv_path": csv_url_path,
        "elapsed_seconds": round(elapsed, 1),
    }


@router.get("/report.pdf")
async def lead_report_pdf(
    region: str,
    installer: str | None = None,
    limit: int = 30,
    min_score: float | None = None,
) -> StreamingResponse:
    """Generate installer-ready PDF lead-report for the given region.

    Query params:
      region    — required, filters prospects on address LIKE %region%
      installer — optional, personalizes the report title
      limit     — max leads to include (default 30, max 200)
      min_score — optional threshold (e.g. 0.5 for "qualified-and-up")

    Response: application/pdf with Content-Disposition attachment.
    """
    if limit < 1 or limit > 200:
        raise HTTPException(422, "limit must be 1-200")
    if min_score is not None and (min_score < 0 or min_score > 1):
        raise HTTPException(422, "min_score must be 0-1")

    # Reuse existing CSV-builder to get the same row-shape, then parse back
    buf = await asyncio.to_thread(
        _export_csv_sync,
        region=region,
        min_score=min_score,
        limit=limit,
        exclude_owner_names=False,
    )
    rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
    # Cast types — CSV gives strings
    typed: list[dict[str, Any]] = []
    for r in rows:
        typed.append({
            "address": r.get("address", ""),
            "score": float(r["score"]) if r.get("score") else None,
            "has_panels": r["has_panels"] == "1" if r.get("has_panels") else None,
            "panel_confidence": float(r["panel_confidence"]) if r.get("panel_confidence") else None,
            "annual_kwh": float(r["annual_kwh"]) if r.get("annual_kwh") else None,
        })

    pdf_bytes = await asyncio.to_thread(
        lead_report.build_lead_report,
        region=region,
        installer_name=installer,
        leads=typed,
    )

    fname = f"solar-leads-{region.replace(' ', '-')}-{datetime.now(UTC):%Y-%m-%d}.pdf"
    return StreamingResponse(
        iter([pdf_bytes]),
        media_type="application/pdf",
        headers={"Content-Disposition": f'attachment; filename="{fname}"'},
    )


@router.get("/snapshot/{municipality}/preview")
async def leads_snapshot_preview(municipality: str, limit: int = 10) -> dict:
    """Preview lead-snapshot output without running detection — for sales-pitch
    'here's what a delivery looks like' visualization.

    Reads existing prospects matching the region, formats as preview-shape.
    """
    # Reuse _export_csv_sync but parse into preview structure
    buf = _export_csv_sync(region=municipality, limit=limit, exclude_owner_names=True)
    rows = list(csv.DictReader(io.StringIO(buf.getvalue())))
    return {
        "region": municipality,
        "preview_count": len(rows),
        "columns": list(rows[0].keys()) if rows else [],
        "rows": rows,
    }
