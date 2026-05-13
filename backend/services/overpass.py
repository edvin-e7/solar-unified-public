"""OpenStreetMap Overpass integration — fetch residential buildings in a bbox.

Ported from edvins-solprojekt-sandbox MapView.tsx:66-125.
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians

import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"

HOUSE_TYPES = (
    "house",
    "detached",
    "semidetached_house",
    "terrace",
    "bungalow",
    "cabin",
    "residential",
    "yes",
)

_EXCLUDE_USE = {"commercial", "industrial", "retail"}
_EXCLUDE_AMENITY = {"school", "hospital", "place_of_worship"}


@dataclass(slots=True)
class House:
    address: str
    lat: float
    lng: float


def _radius_to_bbox(lat: float, lng: float, radius_m: int) -> tuple[float, float, float, float]:
    """Return (south, west, north, east) for a square bbox around (lat, lng) with given radius."""
    lat_delta = radius_m / 111_320.0
    lng_delta = radius_m / (111_320.0 * max(cos(radians(lat)), 0.01))
    return (lat - lat_delta, lng - lng_delta, lat + lat_delta, lng + lng_delta)


def _build_query(south: float, west: float, north: float, east: float) -> str:
    clauses = []
    for house_type in HOUSE_TYPES:
        clauses.append(
            f'way["building"="{house_type}"]["addr:street"]["addr:housenumber"]'
            f"({south},{west},{north},{east});"
        )
        clauses.append(
            f'node["building"="{house_type}"]["addr:street"]["addr:housenumber"]'
            f"({south},{west},{north},{east});"
        )
    body = "\n  ".join(clauses)
    return f"[out:json][timeout:60];\n(\n  {body}\n);\nout tags center 2000;"


def _format_address(tags: dict[str, str]) -> str | None:
    street = (tags.get("addr:street") or "").strip()
    house = (tags.get("addr:housenumber") or "").strip()
    if not street or not house:
        return None
    if tags.get("addr:flats") or tags.get("building:flats") or tags.get("building:units"):
        return None
    if (tags.get("building:use") or "") in _EXCLUDE_USE:
        return None
    if (tags.get("amenity") or "") in _EXCLUDE_AMENITY:
        return None
    postcode = (tags.get("addr:postcode") or "").strip()
    city = (tags.get("addr:city") or "").strip() or "Sverige"
    return " ".join(f"{street} {house}, {postcode} {city}".split()).replace(" ,", ",").strip()


async def fetch_houses_in_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    *,
    limit: int = 2000,
    timeout: float = 90.0,
) -> list[House]:
    query = _build_query(south, west, north, east)
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "solar-unified/0.1 (edvin.pierre03@gmail.com)"},
        )
    if res.status_code != 200:
        msg = {429: "rate-limited", 504: "timeout", 502: "bad gateway"}.get(
            res.status_code, "error"
        )
        raise RuntimeError(f"Overpass {msg} (HTTP {res.status_code})")
    data = res.json()

    seen: set[str] = set()
    houses: list[House] = []
    for el in data.get("elements", []):
        tags = el.get("tags") or {}
        addr = _format_address(tags)
        if not addr:
            continue
        key = addr.lower()
        if key in seen:
            continue
        seen.add(key)
        lat = el.get("lat") or (el.get("center") or {}).get("lat") or 0.0
        lng = el.get("lon") or (el.get("center") or {}).get("lon") or 0.0
        houses.append(House(address=addr, lat=float(lat), lng=float(lng)))
        if len(houses) >= limit:
            break
    return houses


async def fetch_houses_around(
    lat: float,
    lng: float,
    radius_m: int,
    *,
    limit: int = 2000,
) -> list[House]:
    south, west, north, east = _radius_to_bbox(lat, lng, radius_m)
    return await fetch_houses_in_bbox(south, west, north, east, limit=limit)
