# enrich — hitta.se person & business enrichment

`backend/api/enrich.py`

## Public API

```python
POST /person (EnrichRequest) -> EnrichPersonResponse
POST /batch (BatchEnrichRequest) -> dict
```

Enriches addresses with contact data (names, phones) from hitta.se.

## Invariants

I1. **Validation**: Address must be 3-200 characters and not whitespace-only. Empty or whitespace strings raise 422.

I2. **Source**: Data is fetched exclusively from hitta.se (businesses and published individuals).

I3. **Confidence Threshold**: Any contact with an address match score `< 0.2` is discarded. If no contacts exceed this, `/person` returns 404.

I4. **Ranking**: Results are sorted by `match_score` (descending), then by `name` (alphabetical, ascending) to ensure stable output.

I5. **Best Pick**: If `name` is provided in the request, the first contact containing that name (case-insensitive) is selected as "best". Otherwise, the highest-ranked contact is selected.

I6. **Normalization**: Every request normalizes the input address via `services.address_match` for cross-referencing against hitta.se results.

I7. **Batch Limit**: Batch processing is strictly capped at the first 50 addresses in the list.

I8. **Error Mapping**: Upstream `HittaBlocked` (Cloudflare/Rate limit) maps to 502; `HittaEmpty` (no hits) maps to 404.

## Adversarial test matrix

- **Address length** < 3 or > 200 → 422 Unprocessable Entity
- **Whitespace-only address** → 422 Unprocessable Entity
- **Hitta.se blocked/Cloudflare** → 502 Bad Gateway
- **No contacts found** → 404 Not Found
- **Contacts found, but all scores < 0.2** → 404 Not Found
- **Batch > 50 addresses** → Process first 50, ignore remainder
- **Name filter mismatch** → Fallback to highest scored contact if preferred name not found in result set
