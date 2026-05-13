# Spec: `registry_gate` primitive

**Kontrakt**: a single pure function that asks "do any authoritative public registries already say this address has solar panels?" If yes with high confidence, the caller skips the vision/LLM step entirely. If no or uncertain, the caller falls through to the existing detection pipeline.

## Why

Paid Gemini-vision call today fires for every address, even ones where public registries already have ground-truth. OSM's `generator:source=solar` tag alone contributed 30 confirmed panel_owners to the DB (log 2026-04-23). Registry-first means: never spend a vision call on an address the internet already labeled. Future sources (Skatteverket grönt avdrag, Energimyndigheten, Länsstyrelsen) plug into the same gate without touching scanner.py.

Also: guards against the OSM-proximity trap (issue_ledger `3efbcc9d53c3`). A neighboring building with panels is NOT evidence this building has panels. All address comparison MUST route through `services.address_match`. Proximity alone is insufficient.

## Public API

```python
from dataclasses import dataclass
from typing import Literal

Source = Literal["osm-tag"]  # enumerate more as sources are added

@dataclass(frozen=True, slots=True)
class GateHit:
    has_panels: bool
    confidence: float            # 0.0–1.0; registries with addr-match score 1.0 → 0.9
    source: Source
    evidence: dict               # source-specific (e.g. osm_type, osm_id, capacity_kw, matched_address)

async def check(
    address: str,
    lat: float,
    lng: float,
    *,
    radius_m: int = 200,
) -> GateHit | None:
    """Return GateHit if a registry has a sannolik-confidence match for this address.

    Returns None in every other case: no registry hit, empty input, upstream failure,
    partial match below the sannolik threshold. Caller falls through to vision.
    """
```

## Invariants

1. **Pure composition** — calls only `services.osm_solar.fetch_solar_around` + `services.address_match.score_raw`. No direct HTTP, no file IO, no journal writes. Side-effect-free.
2. **address_match is sole authority** — every address comparison routes through `services.address_match.score_raw`. No parallel normalization, no regex matching, no `str.lower() == str.lower()`. Rule from issue_ledger `3efbcc9d53c3`.
3. **Conservative threshold** — only returns a hit when `address_match.score >= 0.8` ("sannolik" label). Score 0.6 (same-street-different-number) is NOT a hit. Score 0.4/0.2 (same-postal/same-city) are NOT hits.
4. **Proximity-only is never sufficient** — an OSM site with `address=None` (no `addr:*` tags) does NOT produce a hit even if coordinates match exactly. Would cause false positives on multi-unit apartment buildings. Returns None.
5. **None = no signal** — caller MUST fall through to the vision path. Gate never returns a GateHit with `has_panels=False`. If a registry says "no panels" explicitly (a future sub-case), that is still None from this gate.
6. **Deterministic on fixed registry state** — same `(address, lat, lng)` with same OSM data → same answer. No random, no LLM.
7. **Fail-open on upstream error** — Overpass/DNS/HTTP failures do NOT raise. The function returns None and the caller falls through to vision. Rationale: registry outage must never block prospecting.
8. **No PII in evidence** — `evidence` contains only OSM-public fields (osm_type, osm_id, capacity_kw, matched_address, match_score). No names, no phones, no internal identifiers.
9. **Source is enumerated** — `source` is a `Literal` union. Adding a source = spec update + matrix extension. No magic strings.
10. **Best-of-many wins** — if multiple OSM sites fall in the search area, the one with the highest address_match score is chosen. Ties broken by capacity_kw (larger first) then osm_id (smaller first). Deterministic.
11. **Empty-input guard** — empty/whitespace address returns None (no crash). `lat/lng == 0.0` is treated as valid (some addresses geocode near equator for edge cases), but Overpass will just return no results.
12. **Radius bounds** — `radius_m` is clipped to `[0, 10000]`. `0` returns None without a network call. `>10000` clipped silently (no raise).
13. **Confidence mapping** — `address_match.score` → `GateHit.confidence`:
    - score 1.0 (exact) → confidence 0.9 (never 1.0; registry drift + tag quality)
    - score ≥ 0.8 but not 1.0 → confidence 0.8
    - score < 0.8 → no hit
14. **No caller assumptions on evidence keys** — adding fields to `evidence` is non-breaking. Removing or renaming keys is a breaking change requiring spec bump.

## Out of scope

- Journal writes (caller's concern; scanner.py already journals).
- Prompt logging (no LLM call here).
- Additional sources (Skatteverket grönt avdrag, Energimyndigheten) — separate spec addenda.
- Rate-limit / backoff on Overpass — `fetch_solar_around` owns that.
- Caching of OSM responses — add later, not essential for correctness.

## Integration contract

Caller (scanner.py `scan_location`):
```python
from services import registry_gate

async def scan_location(lat, lng, *, label="", address=None):
    addr = address or label or f"{lat:.5f},{lng:.5f}"

    gate = await registry_gate.check(addr, lat, lng)
    if gate:
        image_bytes = await satellite.fetch_satellite_image(lat, lng)
        image_path = _save_image(image_bytes, label or f"{lat:.5f}_{lng:.5f}")
        return ScanResult(
            address=addr, lat=lat, lng=lng,
            image_path=str(image_path.relative_to(IMAGES_DIR.parent)),
            has_panels=gate.has_panels,
            confidence=gate.confidence,
            panel_count_estimate=0,             # registry doesn't tell us count
            roof_orientation="unknown",         # nor orientation
            roof_area_m2_estimate=0,
            shading_risk="unknown",
            reasoning=f"Registry hit ({gate.source}): {gate.evidence.get('matched_address','')}",
            scanned_at=datetime.now(timezone.utc).isoformat(),
        )

    # fall through to Gemini path (unchanged)
    ...
```

**Downstream contract**: the ScanResult schema is unchanged. `panel_count_estimate / roof_orientation / roof_area_m2_estimate / shading_risk` are set to zero/"unknown" when gate hits — future phases (local YOLO segmentation) will fill these, Gemini call no longer needed.

## Future extensions (non-binding)

- Skatteverket grönt avdrag public PDF scrape → `source="skatteverket"`
- Energimyndigheten elcertifikat-produktion address list → `source="energimyndigheten"`
- Own DB of prior-verified panel_owners (cached hits) → `source="internal-cache"`
- Commercial licensing consideration: all planned sources are commercial-redistributable public registries. OSM data is ODbL (attribution + share-alike on derivative DB). Skatteverket + Energimyndigheten are offentliga handlingar (fully reusable).
