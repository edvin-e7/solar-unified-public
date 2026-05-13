# Spec: POST /api/prospects/bulk-enrich-contacts

**Kontrakt**: kör hitta-baserad kontakt-berikning på en batch prospects, skriv `owner_name` / `phone` när högsta-poängs-träffen är säker nog, hoppa annars över utan att skriva. (`owner_age` kommer endast från mrkoll/birthday — Electron-renderer-pathen — inte detta endpoint.)

## Why

`/bulk-geocode` fyller bara lat/lng + annual_kwh. Panel-detektion via OSM ger 30 panel_owners men noll har owner_name. UI-knappen "Berika" saknar därmed kontakt-fyllnings-pathen. `/api/enrich/person` är 1-i-taget, `/api/enrich/batch` tar adress-strängar (inte prospect-ids) och uppdaterar inte DB. Detta endpoint är den saknade DB-skrivande batch-versionen.

## Request

```json
{ "ids": [int, ...], "min_score": float in [0.0, 1.0], default 0.6, "max_per_request": int default 50 }
```

- `ids` får inte vara tom → 422.
- Längd `> max_per_request` → trunkeras till första N (resten ignoreras tyst, returneras INTE som fel).
- `min_score`: train-och-tier för säker enrichment. Default 0.6 = "samma gata, möjligen annat nummer". 0.8+ = endast exakt matchning.

## Response — 200 OK

```json
{
  "changed": int,        // rader som faktiskt fick name/phone/age skrivna
  "unchanged": int,      // rader som redan var kompletta (idempotency rule 9)
  "no_match": int,       // hitta hittade noll, eller bästa score < min_score
  "errors": [{"id": int, "address": str, "error_kind": str, "error": str}, ...]
}
```

`changed + unchanged + no_match + len(errors) == len(processed_ids)` (invariant).

## Idempotency (CLAUDE.md rule 9)

Om prospect redan har **både** `owner_name` och `phone` → hoppa över utan hitta-call, räkna som `unchanged`. Sparar Cloudflare-budget.

## Error mapping (CLAUDE.md rule 6)

- `HittaBlocked` → errors[i].error_kind = "HittaBlocked", råd-meddelande loggas via `error_logger.log_error("api-prospects-bulk-enrich-contacts-row")`, INGET 502 — batch fortsätter
- `HittaEmpty` → räknas som `no_match` (inte error). Hitta säger "ingen sån adress" → legitimt utfall, inte fel.
- Bästa score < `min_score` → räknas som `no_match`. Inte error.
- Allt annat (httpx.TimeoutException, parser crash) → errors[i] med `error_kind = type(e).__name__`.

## Invariants

1. **Aldrig skriv namn/telefon från låg-confidence träff.** Skrivning sker endast om `best_score >= min_score`. Annars `no_match`-räknat.
2. **Aldrig logga PII i error_logger context.** Endast `id`, `address` (publik). Namn/telefon från träffar går aldrig till loggar.
3. **Idempotent**: samma ids körda två gånger ger `changed=0, unchanged=N` andra gången.
4. **Per-row failures aborterar inte batchen** — alla ids processas, fel samlas.
5. **Hitta-throttling**: max 1 req/sek (samma som geocode) — `await asyncio.sleep(1.1)` mellan rader som faktiskt går till hitta. Idempotent-skip räknas inte mot throttle.
6. **DB-skrivning per rad är atomic** (ett UPDATE-statement, ingen multi-step). Crash mid-batch lämnar databasen i ett läge där skrivna rader är skrivna, oskriva inte.
7. **Returshape stämmer alltid** — varje id hamnar exakt i ett av {changed, unchanged, no_match, errors}, ingen dubbelräkning.

## Out of scope (uttryckligen)

- INTE mrkoll/eniro/birthday — endast hitta. Andra källor kräver Electron renderer (Cloudflare).
- INTE personnummer — bara namn/telefon/ålder från hitta JSON-LD.
- INTE filtrering på `has_panels=1` på server-sidan — caller (frontend / executor) bestämmer urval. Endpoint accepterar valfri prospect.id.

## Adversarial test matrix (i `test_bulk_enrich_contacts.py`)

1. **Empty ids** → 422.
2. **Idempotent re-run** — samma id som redan har name+phone+age → `unchanged += 1`, ingen hitta-call (mock asserterar).
3. **Hitta blocked för en rad** — andra rader fortsätter, errors[].error_kind = "HittaBlocked".
4. **Hitta returnerar tom lista** → no_match += 1, INTE errors.
5. **Bästa score < min_score** (annan stad) → no_match += 1, INTE skriven.
6. **Bästa score >= min_score** (samma gata) → changed += 1, DB-rad uppdaterad.
7. **Räkne-invariant**: changed + unchanged + no_match + len(errors) == len(ids) (för alla scenarios).
8. **PII-läckage**: error_logger context får aldrig innehålla nyckelord "name" eller "phone" från hitta-resultatet (asserterat via patch).
9. **Throttle-disciplin**: 5 ids varav 2 idempotent-skippade → exakt 3 hitta-calls + exakt 2 sleeps (mellan calls 2 och 3, ingen sleep efter sista).
10. **Trunkering**: 100 ids skickade, 50 max → första 50 processas, resten tyst ignorerade (length-check + counter visar 50).
11. **Concurrent-safe DB-skrivning**: två samtidiga batchar mot olika ids ska INTE krascha (sqlite WAL-mode redan på); samma ids → sista vinner men ingen korruption.
12. **Unicode i adress** — "Götgatan 1, Östersund" (åäö) → träffas korrekt mot hitta-resultats normalisering (ingen mojibake).
