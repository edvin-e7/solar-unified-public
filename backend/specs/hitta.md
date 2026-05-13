# hitta — Swedish registry reverse-address lookup

`backend/services/hitta.py`

## Public API

```python
async def lookup_hitta(address: str) -> HittaResult

class HittaResult:
    query: str
    contacts: list[HittaContact]
    total_hits: int
    tabs: dict[str, int]
    def best_person(self) -> HittaContact | None
    def best_contact(self) -> HittaContact | None

class HittaContact:
    kind: str  # "business" | "person"
    name: str
    telephone: str | None
    street_address: str | None
    postal_code: str | None
    city: str | None
    url: str | None
    lat: float | None
    lng: float | None
```

Scrapes hitta.se reverse-address lookup via JSON-LD and Next.js state. Primarily for business leads and verifying residential addresses.

## Invariants

I1. **Pure Parsing:** `parse_hitta_html` must never perform network I/O. It must be unit-testable using only string input.

I2. **Schema-First:** Extraction prioritizes `application/ld+json` (Schema.org) and `__NEXT_DATA__` (Next.js) blocks over CSS selectors to maintain stability against DOM refactors.

I3. **Exception Hierarchy:** 
    - `HittaBlocked`: Network failures or non-200 responses (e.g., Cloudflare challenges).
    - `HittaEmpty`: Valid 200 OK response but no contacts could be parsed.

I4. **Data Normalization:** All string fields (name, phone, address) are stripped of whitespace. Empty strings are returned as `None`.

I5. **Type Safety:** `lat`/`lng` coordinates must be validated as floats or `None`. Failure to parse a coordinate string should not crash the scraper.

I6. **User Agent:** Must use a modern browser User-Agent to minimize bot detection.

I7. **Contact Preference:** `best_person()` prioritizes "person" types over "business" types to support lead generation for residential services.

I8. **No Persistence:** This module does not store results. It returns transient data objects for the caller to handle.

## Adversarial test matrix

| Case | Expected Behavior |
| :--- | :--- |
| Empty address query | `HittaEmpty` or `HittaBlocked` (depending on site behavior) |
| Non-200 status code | `HittaBlocked` with status code in message |
| Cloudflare challenge page | `HittaBlocked` |
| 200 OK with no JSON-LD | `HittaEmpty` |
| Malformed JSON-LD block | Skip block, continue parsing other blocks |
| Negative `total_hits` in JSON | Use 0 or clamp to non-negative |
| Coordinates as non-numeric strings | `None` for lat/lng fields |
| Circular JSON in `__NEXT_DATA__` | `json.loads` error handled or raised |
