# geocode — Nominatim wrapper

`backend/services/geocode.py`

## Public API

```python
async def geocode(query: str) -> tuple[float, float]   # (lat, lng)
async def reverse_geocode(lat: float, lng: float) -> str | None
```

Free, rate-limited (~1 req/s). Used by scanner, panels.osm_import, prospects.bulk_geocode.

## Invariants

I1. Nominatim's "max 1 req/s" fair-use limit is enforced by callers via `asyncio.sleep(1.05)`. The module does NOT add its own throttle — callers see what they pay for. Documented in CLAUDE.md.

I2. `geocode` raises `ValueError` for "no result". Never returns `(0.0, 0.0)` or `None` as a sentinel — those are valid coordinates near the Gulf of Guinea.

I3. `reverse_geocode` returns `None` (not raise) for "no result" because callers expect best-effort enrichment.

I4. User-Agent header includes a contact hint per Nominatim policy.

I5. Returned `(lat, lng)` is always inside Sweden's bbox for Swedish queries — flag if a query maps to a different country (potential typo or stale Nominatim cache).

## Adversarial test matrix

> **TODO** — required cases:
> - Empty string → `ValueError`
> - All-whitespace → `ValueError`
> - SQL-injection-shaped query (`'; DROP TABLE`) → URL-encoded, returns ValueError or geocodes harmlessly
> - Query with å/ä/ö → preserved, valid result
> - Network timeout → `httpx.TimeoutException` propagates (caller decides)
> - Nominatim returns 200 with empty array → `ValueError` ("no result"), not `IndexError`
> - Reverse geocode for ocean coords → returns `None`, doesn't crash
