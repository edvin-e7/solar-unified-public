"""OSM Overpass — fetch existing solar PV installations tagged in OpenStreetMap.

Tagging reference: https://wiki.openstreetmap.org/wiki/Tag:generator:source%3Dsolar
Matches buildings/nodes/ways carrying `generator:source=solar` (rooftop PV + farms).
"""

from __future__ import annotations

from dataclasses import dataclass
from math import cos, radians

import httpx

OVERPASS_URL = "https://overpass-api.de/api/interpreter"


@dataclass(slots=True)
class SolarSite:
    lat: float
    lng: float
    address: str | None  # built from OSM addr:* tags if present, else None (caller may reverse-geocode)
    osm_type: str  # "node" | "way" | "relation"
    osm_id: int
    capacity_kw: float | None
    method: str | None  # "photovoltaic" | "thermal" | ...


def _radius_to_bbox(lat: float, lng: float, radius_m: int) -> tuple[float, float, float, float]:
    lat_delta = radius_m / 111_320.0
    lng_delta = radius_m / (111_320.0 * max(cos(radians(lat)), 0.01))
    return (lat - lat_delta, lng - lng_delta, lat + lat_delta, lng + lng_delta)


def _build_query(south: float, west: float, north: float, east: float) -> str:
    bbox = f"({south},{west},{north},{east})"
    return (
        f"[out:json][timeout:90];\n"
        f"(\n"
        f'  node["generator:source"="solar"]{bbox};\n'
        f'  way["generator:source"="solar"]{bbox};\n'
        f'  node["power"="generator"]["generator:source"="solar"]{bbox};\n'
        f'  way["power"="generator"]["generator:source"="solar"]{bbox};\n'
        f"  way[\"building\"][\"roof:solar\"]{bbox};\n"
        f"  way[\"building\"][\"roof:material\"=\"solar_panels\"]{bbox};\n"
        f");\n"
        f"out tags center;"
    )


def _address_from_tags(tags: dict[str, str]) -> str | None:
    street = (tags.get("addr:street") or "").strip()
    house = (tags.get("addr:housenumber") or "").strip()
    if not street:
        return None
    postcode = (tags.get("addr:postcode") or "").strip()
    city = (tags.get("addr:city") or "").strip() or "Sverige"
    lead = f"{street} {house}".strip()
    return " ".join(f"{lead}, {postcode} {city}".split()).replace(" ,", ",").strip()


def _capacity_kw(tags: dict[str, str]) -> float | None:
    raw = tags.get("generator:output:electricity") or tags.get("plant:output:electricity")
    if not raw:
        return None
    s = raw.strip().lower().replace(" ", "")
    try:
        if s.endswith("mw"):
            return float(s[:-2]) * 1000
        if s.endswith("kw"):
            return float(s[:-2])
        if s.endswith("w"):
            return float(s[:-1]) / 1000
        return float(s)
    except ValueError:
        return None


async def fetch_solar_in_bbox(
    south: float,
    west: float,
    north: float,
    east: float,
    *,
    limit: int = 5000,
    timeout: float = 120.0,
) -> list[SolarSite]:
    query = _build_query(south, west, north, east)
    async with httpx.AsyncClient(timeout=timeout) as client:
        res = await client.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "solar-unified/0.1 (edvin.pierre03@gmail.com)"},
        )
    if res.status_code != 200:
        raise RuntimeError(f"Overpass HTTP {res.status_code}: {res.text[:200]}")

    sites: list[SolarSite] = []
    seen: set[tuple[str, int]] = set()
    for el in res.json().get("elements", []):
        key = (el.get("type", ""), int(el.get("id", 0)))
        if key in seen:
            continue
        seen.add(key)
        tags = el.get("tags") or {}
        lat = el.get("lat") or (el.get("center") or {}).get("lat")
        lng = el.get("lon") or (el.get("center") or {}).get("lon")
        if lat is None or lng is None:
            continue
        sites.append(
            SolarSite(
                lat=float(lat),
                lng=float(lng),
                address=_address_from_tags(tags),
                osm_type=key[0],
                osm_id=key[1],
                capacity_kw=_capacity_kw(tags),
                method=tags.get("generator:method"),
            )
        )
        if len(sites) >= limit:
            break
    return sites


async def fetch_solar_around(
    lat: float, lng: float, radius_m: int, *, limit: int = 5000
) -> list[SolarSite]:
    south, west, north, east = _radius_to_bbox(lat, lng, radius_m)
    return await fetch_solar_in_bbox(south, west, north, east, limit=limit)
