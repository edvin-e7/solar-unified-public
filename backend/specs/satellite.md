# satellite — ArcGIS World Imagery tile fetcher

`backend/services/satellite.py`

## Public API

```python
async def fetch_satellite_image(lat: float, lng: float, *, zoom: int = 20) -> bytes
```

Free, no API key, fair-use. ArcGIS World Imagery rendered at the given zoom level.

## Invariants

I1. Returned bytes are a valid JPEG — non-empty, starts with `\xff\xd8\xff`. If ArcGIS returns HTML (rate-limit page, error), raise `RuntimeError`, not return the HTML as image bytes.

I2. `zoom` clamped to `[1, 22]`. Higher zoom is silently capped — do not surface ArcGIS-tile-not-found.

I3. SSRF guard: `lat`/`lng` are validated as floats. URL is constructed via tile-coord arithmetic, not string concatenation of user input — no path-traversal on the upstream URL.

I4. Image cache key is `(lat, lng, zoom)` with float quantization to avoid cache misses on near-equal coordinates.

I5. Image is **never** persisted by this module. Persistence is `scanner._save_image`'s job.

## Adversarial test matrix

> **TODO** — required cases:
> - Coords outside `[-90, 90]` / `[-180, 180]` → `ValueError`
> - ArcGIS returns 200 with HTML body (rate-limit) → `RuntimeError`
> - ArcGIS returns 200 with truncated JPEG (< 1 KB) → `RuntimeError`
> - Network timeout → `httpx.TimeoutException`
> - Concurrent fetches of the same tile → no duplicate downloads beyond cache size
