"""Geocoding — Nominatim (free, no key) with permutation fallbacks.

Fix for docs/BUGS.md Bug 2: callers must be able to distinguish "address not
found" (legitimate 404) from "geocoding service errored" (502 / retryable).
The single ValueError raise was indistinguishable.

Public surface:
- ``geocode(address)`` → ``tuple[float, float]`` (raises ``GeocodeNotFound``
  on no-hit, propagates ``httpx.HTTPError`` on upstream failure).
- ``reverse_geocode(lat, lng)`` → ``str | None`` (unchanged).
- ``GeocodeNotFound`` exception class — subclass of ``ValueError`` so
  legacy ``except ValueError`` catch-sites continue to work.
"""

from __future__ import annotations

import logging
import re

import httpx

USER_AGENT = "solar-unified/0.1 (github.com/edvin-e7)"

_log = logging.getLogger(__name__)


class GeocodeNotFound(ValueError):
    """Geocoding completed but found no hit for the address.

    Subclasses ValueError for backwards-compat with ``except ValueError``
    catch-sites in api/scan.py and services/scanner.py. Callers can branch on
    the typed exception to return 404 (not 500) on legitimate no-hit.

    The ``.address`` attribute carries the original query for downstream
    logging / retry-with-different-shape.
    """

    def __init__(self, address: str, *, tried: list[str] | None = None):
        super().__init__(f"Could not geocode: {address}")
        self.address = address
        self.tried = tried or [address]


def _permutations(address: str) -> list[str]:
    """Yield Nominatim-friendly variants of the address, in order of preference.

    Deduplicated, original first. Nominatim's Swedish coverage has known gaps
    on numeric house-numbers and trailing region tokens — these permutations
    surface the same address in shapes Nominatim tends to resolve.
    """
    seen: set[str] = set()
    out: list[str] = []

    def push(s: str) -> None:
        s = s.strip(" ,")
        if s and s not in seen:
            seen.add(s)
            out.append(s)

    push(address)

    # Strip numeric house-number tokens. Conservative regex: an integer
    # optionally followed by a single A-Z letter (e.g. "15A"), as a whole
    # whitespace-bounded token, with optional trailing comma. Avoids stripping
    # postcodes (5-digit), but house numbers (1-4 digit) like "3", "15", "15A"
    # are removed. Surrounding whitespace and stray commas are collapsed.
    no_numbers = re.sub(r"\b\d{1,4}[A-Za-z]?\b,?\s*", " ", address)
    no_numbers = re.sub(r"\s+", " ", no_numbers).strip(" ,")
    push(no_numbers)

    # Comma-separated: try each prefix dropped tail-first ("X, Y, Z" → "X, Y", "X")
    if "," in address:
        parts = [p.strip() for p in address.split(",")]
        for cut in range(len(parts) - 1, 0, -1):
            push(", ".join(parts[:cut]))
        # Try just the city (last token) as last resort — gives a city-center
        # hit so the caller at least gets coordinates in the right region.
        push(parts[-1])

    return out


async def geocode(address: str) -> tuple[float, float]:
    """Geocode a Swedish address. Raises GeocodeNotFound on no-hit.

    Tries the original address first, then permutations (numeric-stripped,
    comma-prefix truncations, city-only). All Nominatim, no paid providers.
    """
    tried: list[str] = []
    async with httpx.AsyncClient(timeout=10, headers={"User-Agent": USER_AGENT}) as client:
        for variant in _permutations(address):
            tried.append(variant)
            hit = await _nominatim(client, variant)
            if hit:
                if variant != address:
                    _log.info(
                        "geocode: hit on permutation %r (original=%r)",
                        variant,
                        address,
                    )
                return hit

    # Log via error_logger so failures are journaled, not silent.
    try:
        from error_logger import log_error  # local import — avoid cycle at module load
        log_error(
            "geocode-not-found",
            GeocodeNotFound(address, tried=tried),
            context={"address": address, "tried": tried, "provider": "nominatim"},
        )
    except Exception:  # noqa: BLE001 -- logger must not block the raise
        _log.warning("geocode: failed to journal not-found for %r (tried %d variants)", address, len(tried))

    raise GeocodeNotFound(address, tried=tried)


async def _nominatim(client: httpx.AsyncClient, q: str) -> tuple[float, float] | None:
    r = await client.get(
        "https://nominatim.openstreetmap.org/search",
        params={
            "q": q,
            "format": "json",
            "limit": 1,
            "countrycodes": "se",
            "accept-language": "sv",
        },
    )
    r.raise_for_status()
    data = r.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


async def reverse_geocode(lat: float, lng: float) -> str | None:
    """Reverse-geocode to a Swedish street-level address. Returns None if outside SE or no street hit."""
    async with httpx.AsyncClient(timeout=15, headers={"User-Agent": USER_AGENT}) as client:
        r = await client.get(
            "https://nominatim.openstreetmap.org/reverse",
            params={
                "lat": f"{lat:.6f}",
                "lon": f"{lng:.6f}",
                "format": "json",
                "zoom": 18,
                "addressdetails": 1,
                "accept-language": "sv",
            },
        )
        r.raise_for_status()
        data = r.json()
    if not data or data.get("address", {}).get("country_code") != "se":
        return None
    a = data["address"]
    road = a.get("road") or a.get("pedestrian") or a.get("footway")
    if not road:
        return None
    house = a.get("house_number")
    street = f"{road} {house}" if house else road
    city = a.get("city") or a.get("town") or a.get("village") or a.get("municipality") or "Sverige"
    postcode = (a.get("postcode") or "").strip()
    tail = f"{postcode} {city}".strip()
    return f"{street}, {tail}".strip().rstrip(",")
