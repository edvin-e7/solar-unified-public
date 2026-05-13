---
name: export_csv
version: 1.0
status: implemented
---

# Spec: `/api/prospects/export/csv` endpoint

Public API: `GET /api/prospects/export/csv` returnerar prospects som CSV-attachment
för lead-byrå-leveranser. Composable filters (alla AND-kombinerade).

## Public API

### Query-parametrar (alla optional)

| Param | Typ | Effekt |
|---|---|---|
| `status` | str | Filter `status = ?` (e.g. "qualified", "new") |
| `region` | str | Filter `address LIKE %?%` (substring-match) |
| `min_score` | float [0,1] | Filter `score >= ?` (kräver score IS NOT NULL) |
| `max_score` | float [0,1] | Filter `score <= ?` (för Premium-tier slicing) |
| `limit` | int >0 | Cap result count |
| `exclude_owner_names` | bool | Om true: utelämna owner_name/age/phone cols (GDPR-light) |

### Response

- Content-Type: `text/csv`
- Filename: `prospects-YYYY-MM-DD.csv` (UTC datum)
- Header row + en rad per prospekt
- Columns: id, address, lat, lng, status, score, annual_kwh, [owner_name, owner_age, owner_phone om ej exkl], notes, has_panels, panel_confidence, detected_at, created_at

### Error codes

| Code | When |
|---|---|
| 422 | min_score/max_score < 0 eller > 1 |
| 422 | limit < 0 |
| 200 | Success även om 0 rader matchar (returnerar bara header) |

## Invariants

I1. **Idempotent**: samma query-params → samma output (deterministisk SQL ORDER BY score DESC NULLS LAST)
I2. **Sorted descending by score**: rader med högst score först, NULL scores sist
I3. **Limit kappar resultatet**: om limit=N, returnerar ≤N rader
I4. **GDPR-mode skippar 3 cols**: när exclude_owner_names=true, header har ej owner_name/owner_age/owner_phone
I5. **Filter komposition är AND**: kombinationer som `status=qualified&min_score=0.6` returnerar bara rader som matchar BÅDA
I6. **Region är case-insensitive substring**: "Stockholm" matchar "Stockholm 1", "stockholmsvägen 12"
I7. **NULL scores filtrerade ut när min/max_score sätts**: SQL `score IS NOT NULL` guarantor
I8. **Empty DB → empty CSV (with header)**: ej throw, returnerar bara header-rad
I9. **Filename inkluderar datum**: för audit-spår av leverans-batchar
I10. **Validation-errors innan SQL**: invalid score/limit → 422 utan att touch DB

## Adversarial matrix (test_export_csv.py — to-be-written)

| Case | Input | Expected |
|---|---|---|
| Empty DB | (no rows) | 200, only header in CSV |
| No filters | (default) | All rows, sorted by score desc, NULLs last |
| status="qualified", 5 rows ej qualified | status=qualified | Bara qualified-rows |
| region="Stockholm" mixed-case | region="STOCKHOLM" | Matchar Stockholm-rows (LIKE %STOCKHOLM% via SQLite default) |
| min_score=0.6, has 0.5 and 0.7 rows | min_score=0.6 | Bara 0.7-row |
| min_score=0.6, has NULL-score rows | min_score=0.6 | NULL-score rows utelämnas |
| min_score=0.7, max_score=0.6 | (intersection empty) | 200, empty CSV (no header logic break) |
| min_score=-0.1 | (invalid) | 422 |
| min_score=1.5 | (invalid) | 422 |
| limit=-1 | (invalid) | 422 |
| limit=0 | (valid as "no limit") | All rows |
| limit=3, 5 rows | limit=3 | Top-3 by score |
| exclude_owner_names=false | (default) | 15 cols including owner_* |
| exclude_owner_names=true | (GDPR-light) | 12 cols, no owner_name/age/phone |
| Filter compose: status+region+score+limit | all set | Intersection of filters, sorted, capped |
| Empty result + filename | (no rows) | Filename still YYYY-MM-DD format |

## Implementation notes

- SQLite `LIKE` är case-insensitive by default — så region-substring matchar utan extra `LOWER()`
- `score DESC NULLS LAST` är SQLite >=3.30 (Edvin's setup OK)
- `_export_csv_sync` är blocking → wrapped i `asyncio.to_thread` för FastAPI async
- CSV writer från `csv` stdlib: hanterar quoting/escape automatiskt

## Säljbar-output-format för solar-leads-byrå

Default output passar Standard-paket per `~/freelance-launch/solar-leads-bureau/pricing-and-offer.md`:
- All 15 cols (med ägardata)
- Premium-paket: använd `?min_score=0.7` för topp-X-leveranser
- GDPR-light demo: använd `?exclude_owner_names=true` för anonym sample

## Migration-not

Tidigare version av `/export/csv` (pre-2026-05-12) tog bara `status` som param.
Bakåtkompatibilitet: alla existerande caller funkar oförändrat (övriga params optional).
