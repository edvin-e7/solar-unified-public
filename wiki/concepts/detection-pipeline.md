---
name: Detection pipeline
description: geocode → satellite → Gemini → persist — end-to-end scan flow
updated: 2026-04-23
---

# Detection pipeline

Address in, `ScanResult` out, prospect row updated.

## Flow

```
address
  │
  ▼
services/geocode.py::geocode(address)     ─── Nominatim, 1 req/s rate limit
  │ → (lat, lng)
  ▼
services/satellite.py::fetch_satellite_image(lat, lng)  ─── Google Maps static API
  │ → image_bytes (JPEG)
  ▼
_save_image(image_bytes, label)           ─── writes to backend/data/images/
  │ → image_path
  ▼
prompts_loader::render(load("detection"), {address, lessons})
  │ → prompt string
  ▼
services/gemini.py::generate_json(prompt, model="gemini-2.5-flash", image_bytes)
  │ → analysis dict OR RuntimeError (2026-04-23: propagated, not swallowed)
  ▼
ScanResult{
  address, lat, lng, image_path,
  has_panels, confidence, panel_count_estimate,
  roof_orientation, roof_area_m2_estimate, shading_risk,
  reasoning, scanned_at
}
  │
  ▼
api/prospects.py::record_scan_result(result)
  │ → UPDATE prospects SET ... WHERE address=? (or INSERT)
  │ → populates has_panels / panel_confidence / detected_at (NEW U1)
```

## Entry points

- POST `/api/scan {address}` — single
- POST `/api/scan/batch {locations:[...]}` — many
- POST `/api/scan/area {municipality}` — **STUB (U5)**
- POST `/api/scan/detect` — manual image upload, skips geocode+satellite

## Gates

- `ALLOW_EXTERNAL_LLM=1` required — `services/gemini.py::_client` raises RuntimeError if not set. Gate rationale: avoid accidental quota burn in CI.
- `ALLOW_GOOGLE_SOLAR_API=1` is separate gate for `/api/solar/potential`.

## Failure semantics

| Cause | Behavior |
|---|---|
| Geocode miss | `ValueError` → HTTPException(422) |
| Satellite fetch fail | RuntimeError → HTTPException(502) |
| Gemini fail (2026-04-23 onward) | RuntimeError → HTTPException(502), NOT pseudosuccess |
| Batch: any one item fails | error recorded, others continue |

## Journal

Each completed scan emits `learning_journal.record(...)` entry (phase outcome). `/api/execute/status` aggregates: `{last_cycle, total_cycles}`. As of 2026-04-23: `total_cycles=0` — learning loop not yet wired to per-scan events.

## Improvement hooks (TODO)

- Cove verifier (`cove_verifier.py`) — async + sentiment-based secondary check
- Pattern detector (`executors/pattern_detector.py`) — schema-sensitive, see `pattern-detector-schema` memory
- Auto-backfill for 6377 pre-U1 rows (decision pending)
