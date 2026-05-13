# scanner — unified detection pipeline

`backend/services/scanner.py`

## Public API

```python
async def scan_address(address: str) -> ScanResult
async def scan_location(lat: float, lng: float, *, label: str = "", address: str | None = None) -> ScanResult
```

Backend selection is driven by the `DETECTION_BACKEND` env var. See `CLAUDE.md` "Detection backend selection".

## Invariants

I1. `scan_address` calls `geocode` exactly once. A `ValueError` from geocode propagates as a `ValueError`, not a partial `ScanResult`.

I2. `scan_location` always writes an image file before any LLM call. Image bytes never round-trip through the LLM unless persisted.

I3. `ScanResult.has_panels == True` implies `confidence >= 0.5` AND `panel_count_estimate >= 1`. Inconsistent verdicts collapse to `has_panels=False` (mirrors `detection_gemini` / `detection_moondream` invariant I4).

I4. `roof_area_m2_estimate >= 0` always. Negative or `None` upstream values clamp to `0`.

I5. `scanned_at` is ISO-8601 UTC. Local timezones never leak.

I6. `DETECTION_BACKEND=auto` order: `ml → embed → moondream → gemini`. The first `is_available()` true wins. If none is available, raise — do not silently no-op.

I7. Per-call latency is bounded by upstream timeouts (geocode, satellite, detection). Scanner does not add an unbounded wait.

I8. `image_path` is a path **relative to** `backend/data/`, never absolute. Avoids leaking the deployment root into prospect records.

## Adversarial test matrix

> **TODO** — see `specs/test_scanner.py`. Required cases:
> - `geocode` raises `ValueError` (city not found) → propagates, no image written
> - satellite returns < 1 KB / corrupt JPEG → raises before LLM call
> - LLM returns malformed JSON → caught, fallback ScanResult with `confidence=0`, `has_panels=False`
> - `DETECTION_BACKEND=ml` but model file missing → clear error, no fallback
> - `DETECTION_BACKEND=auto` with all backends unavailable → raises, doesn't return zeroed result
> - Concurrent `scan_address` of the same address → atomic image write (no half-files)
> - Address contains non-ASCII (åäö) → preserved through pipeline
