"""Solar potential — Google Solar API with PVGIS fallback for Sweden.

edvins-solprojekt hits Google Solar directly from the browser; edvin-solar has PVGIS
fallback server-side. Unifying here means the frontend always gets an answer.
"""

from __future__ import annotations

import os

import httpx
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()

GOOGLE_KEY = os.getenv("GOOGLE_MAPS_API_KEY", "")
ALLOW_GOOGLE_SOLAR_API = os.getenv("ALLOW_GOOGLE_SOLAR_API", "0") == "1"


class PotentialRequest(BaseModel):
    lat: float
    lng: float
    rate_sek_per_kwh: float = 2.0


@router.post("/potential")
async def potential(req: PotentialRequest) -> dict:
    google = await _google_solar(req.lat, req.lng)
    if google:
        kwh = google["maxArrayAnnualEnergyKwh"]
        return {
            "source": "google",
            "annual_kwh": kwh,
            "annual_sek": round(kwh * req.rate_sek_per_kwh),
            "max_panels": google.get("maxArrayPanelsCount"),
            "roof_area_m2": google.get("maxArrayAreaMeters2"),
        }

    pvgis = await _pvgis(req.lat, req.lng)
    if pvgis:
        return {
            "source": "pvgis",
            "annual_kwh": pvgis,
            "annual_sek": round(pvgis * req.rate_sek_per_kwh),
            "max_panels": None,
            "roof_area_m2": None,
        }

    raise HTTPException(404, "No solar data available for this location")


async def _google_solar(lat: float, lng: float) -> dict | None:
    if not ALLOW_GOOGLE_SOLAR_API or not GOOGLE_KEY:
        return None
    url = "https://solar.googleapis.com/v1/buildingInsights:findClosest"
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params={"location.latitude": lat, "location.longitude": lng, "key": GOOGLE_KEY})
    if r.status_code != 200:
        return None
    data = r.json()
    solar = data.get("solarPotential") or {}
    if "maxArrayAnnualEnergyKwh" not in solar:
        return None
    return solar


async def _pvgis(lat: float, lng: float) -> float | None:
    # Sensible 5 kWp south-facing tilt for Swedish latitudes.
    url = "https://re.jrc.ec.europa.eu/api/v5_2/PVcalc"
    params = {"lat": lat, "lon": lng, "peakpower": 5, "loss": 14, "outputformat": "json"}
    async with httpx.AsyncClient(timeout=15) as client:
        r = await client.get(url, params=params)
    if r.status_code != 200:
        return None
    try:
        return float(r.json()["outputs"]["totals"]["fixed"]["E_y"])
    except (KeyError, ValueError, TypeError):
        return None
