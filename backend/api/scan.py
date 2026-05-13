"""Scan endpoints — real geocode + satellite + Gemini detection."""

from __future__ import annotations

from agents.coordinator import get_coordinator
from fastapi import APIRouter, Form, HTTPException, UploadFile
from pydantic import BaseModel, Field
from services import geocode as geocode_mod
from services import overpass, scanner

from api.prospects import db as prospect_db
from api.prospects import record_scan_result

router = APIRouter()


class ScanRequest(BaseModel):
    address: str | None = None
    lat: float | None = None
    lng: float | None = None
    label: str = ""


class BatchScanRequest(BaseModel):
    locations: list[ScanRequest] = Field(default_factory=list)
    addresses: list[str] | None = None

    def resolved_locations(self) -> list[ScanRequest]:
        if self.addresses:
            return [*self.locations, *(ScanRequest(address=a) for a in self.addresses)]
        return self.locations


class AreaScanRequest(BaseModel):
    municipality: str | None = None
    lat: float | None = None
    lng: float | None = None
    bbox: tuple[float, float, float, float] | None = None  # (south, west, north, east)
    radius_m: int = Field(2000, gt=0, le=20000)
    building_limit: int = Field(200, gt=0, le=2000)
    enqueue: bool = False  # create prospects from findings (no auto-scan)


@router.post("")
async def scan(req: ScanRequest) -> dict:
    try:
        if req.address:
            result = await scanner.scan_address(req.address)
        elif req.lat is not None and req.lng is not None:
            result = await scanner.scan_location(req.lat, req.lng, label=req.label)
        else:
            raise HTTPException(422, "Provide address or lat+lng")
    except ValueError as e:
        raise HTTPException(422, str(e))
    except RuntimeError as e:
        raise HTTPException(502, f"Upstream service unavailable: {e}")

    scanner.save_history([result])
    record_scan_result(result)
    return dict(result)


@router.post("/batch")
async def scan_batch(req: BatchScanRequest) -> dict:
    locations = req.resolved_locations()
    if not locations:
        raise HTTPException(422, "Provide at least one location (locations[] or addresses[])")
    results: list[dict] = []
    errors: list[dict] = []
    for loc in locations:
        try:
            if loc.address:
                results.append(dict(await scanner.scan_address(loc.address)))
            elif loc.lat is not None and loc.lng is not None:
                results.append(dict(await scanner.scan_location(loc.lat, loc.lng, label=loc.label)))
        except Exception as e:  # noqa: BLE001 -- per-item fail-soft into errors[]
            from error_logger import log_error
            log_error(
                "api-scan-batch-item",
                e,
                context={"input": loc.model_dump()},
            )
            errors.append({"input": loc.model_dump(), "error": str(e)})
    if results:
        scanner.save_history(results)  # type: ignore[arg-type]
        for r in results:
            record_scan_result(r)
    return {"results": results, "errors": errors, "count": len(results)}


@router.post("/area")
async def scan_area(req: AreaScanRequest) -> dict:
    """Fetch residential buildings in an area via Overpass (OpenStreetMap).

    Accepts one of: bbox | (lat, lng) + radius_m | municipality name (geocoded to center + radius).

    Does NOT auto-scan detected buildings — that would blow quota. If `enqueue=True`,
    unseen addresses are inserted as prospects so they're ready for paneldetektion.
    """
    # Resolve center / bbox
    if req.bbox is not None:
        south, west, north, east = req.bbox
        center_desc = f"bbox({south:.4f},{west:.4f},{north:.4f},{east:.4f})"
    else:
        if req.lat is not None and req.lng is not None:
            lat, lng = req.lat, req.lng
        elif req.municipality:
            try:
                lat, lng = await geocode_mod.geocode(req.municipality)
            except ValueError as e:
                raise HTTPException(422, f"Could not geocode municipality: {e}")
        else:
            raise HTTPException(422, "Provide bbox, lat+lng, or municipality")
        south, west, north, east = None, None, None, None
        center_desc = f"{req.municipality or f'{lat:.4f},{lng:.4f}'} r={req.radius_m}m"

    try:
        if req.bbox is not None:
            houses = await overpass.fetch_houses_in_bbox(
                south, west, north, east, limit=req.building_limit
            )
        else:
            houses = await overpass.fetch_houses_around(
                lat, lng, req.radius_m, limit=req.building_limit
            )
    except RuntimeError as e:
        raise HTTPException(502, f"Overpass upstream error: {e}")

    created = 0
    if req.enqueue and houses:
        with prospect_db() as conn:
            existing = {
                r[0].strip().lower()
                for r in conn.execute("SELECT address FROM prospects")
            }
            for h in houses:
                if h.address.lower() in existing:
                    continue
                conn.execute(
                    "INSERT INTO prospects (address, lat, lng, status) VALUES (?, ?, ?, 'new')",
                    (h.address, h.lat, h.lng),
                )
                existing.add(h.address.lower())
                created += 1

    return {
        "area": center_desc,
        "radius_m": req.radius_m,
        "found": len(houses),
        "enqueued": created if req.enqueue else None,
        "buildings": [{"address": h.address, "lat": h.lat, "lng": h.lng} for h in houses[:100]],
        "truncated": len(houses) > 100,
    }


@router.post("/detect")
async def detect_image(image: UploadFile, address: str = Form("")) -> dict:
    """Manual upload for detection — routes through DetectionAgent."""
    image_bytes = await image.read()
    if not image_bytes:
        raise HTTPException(422, "Empty image")
    try:
        result = await get_coordinator().detection.run(
            address=address or "(unspecified)",
            image_bytes=image_bytes,
        )
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return result
