# Bulk-pipeline demo — runbook för första betal-leverans

T2.13 av Tier-2 quality-plan. Mål: kör solar-unified pipeline mot en
verklig Stockholm-kommun → 200+ prospects som CSV → första demo-batch
för solar-leads-byrå.

## Förutsättningar

- `make install` körd, deps installerade
- `DETECTION_BACKEND=embed` (gratis lokal, MobileNet+head)
- ELLER `DETECTION_BACKEND=moondream` (gratis lokal LLM, kräver `ollama pull moondream`)
- **EJ** `ALLOW_GOOGLE_SOLAR_API=1` (betalt — opt-in)
- ArcGIS + Nominatim (gratis, default)

## Demo-target: Sollentuna kommun

Sollentuna valdes för pilot:
- Pendlingsavstånd till Stockholm centrum
- 60% villor + 40% radhus = bra solar-prospekt-mix
- Tillräckligt stor (76k invånare) för 200+ prospects men inte överväldigande
- Inga befintliga solar-projekt jag känner till — lokala installatörer kan ha intresse

## Steg-för-steg

### 1. Förbered adress-seed-list (1h, semi-manuell)

Skapa `backend/scripts/fixtures/sollentuna-addresses.txt` med 300-500
adresser från Sollentuna kommun. Två källor:

**Option A — Hitta.se manuell scrape (semi-manuell):**
```bash
# Sök Hitta.se "kommun:Sollentuna typ:villa"
# Klistra in i fil, ca 50 adresser per gata
```

**Option B — OSM extract (auto, rekommenderas):**
```bash
# Hämta Sollentuna OSM-bbox → extrahera way:building=house addresses
# (kräver overpass-turbo eller osmium-tool, gratis open data)
overpass-turbo.eu →
  [out:json][timeout:25];
  area["name"="Sollentuna"]["admin_level"="7"]->.s;
  (way["building"~"house|detached|residential"](area.s);)->.b;
  .b out center;
# Convert till adresser via Nominatim reverse-geocode (gratis, ~1 req/sec)
```

**Option C — Lantmäteriet open-data (mest officiellt):**
- lantmateriet.se → "Belägenhetsadresser" som GeoJSON-shapefile
- Open data, gratis efter konto-registrering
- Filtrera på kommun=Sollentuna → exportera till txt

Mål-output:
```
Bygdevägen 1, Sollentuna
Bygdevägen 3, Sollentuna
Bygdevägen 5, Sollentuna
... (300-500 rows)
```

### 2. Bulk-scan-kör (2-4h, mostly automatiskt)

```bash
cd ~/solar-unified
make dev   # uvicorn :8000 igång i terminal A

# Terminal B: bulk-scan via API
python3 backend/scripts/bulk_scan_addresses.py \
  --input backend/scripts/fixtures/sollentuna-addresses.txt \
  --backend embed
```

**Förväntat:**
- ~5s per address (geocode + satellit-fetch + detection)
- 300 addresses = ~25 min
- Skriver till `prospects.db` per address
- Lite RAM (Moondream ~2 GB om backend=moondream)

### 3. Verifiera resultat

```bash
python3 -c "
import sqlite3
conn = sqlite3.connect('backend/data/prospects.db')
print('Total:', conn.execute('SELECT count(*) FROM prospects').fetchone()[0])
print('With score:', conn.execute('SELECT count(*) FROM prospects WHERE score IS NOT NULL').fetchone()[0])
print('Score buckets:')
for bucket in [(0.0, 0.3), (0.3, 0.5), (0.5, 0.7), (0.7, 0.9), (0.9, 1.01)]:
    c = conn.execute('SELECT count(*) FROM prospects WHERE score >= ? AND score < ?',
                     bucket).fetchone()[0]
    print(f'  {bucket[0]:.1f}-{bucket[1]:.1f}: {c}')
"
```

Mål: 60-80% av addresses får score, varav 30-40% score >= 0.5 (kvalificerade prospects).

### 4. Generera demo-CSV-paket

```bash
# Pilot-paket (50 prospects, 1500 kr i pricing)
curl -s "http://localhost:8000/api/prospects/export/csv?status=qualified&limit=50" \
  > deliverables/sollentuna-pilot-2026-05-12.csv

# Standard-paket (200 prospects, 3500 kr)
curl -s "http://localhost:8000/api/prospects/export/csv?status=qualified&limit=200" \
  > deliverables/sollentuna-standard-2026-05-12.csv

# Premium-tier sample (top score >= 0.7)
curl -s "http://localhost:8000/api/prospects/export/csv?status=qualified&min_score=0.7&limit=500" \
  > deliverables/sollentuna-premium-2026-05-12.csv

# GDPR-light anonymized sample (för cold-pitch-attachment)
curl -s "http://localhost:8000/api/prospects/export/csv?exclude_owner_names=true&limit=20" \
  > deliverables/sollentuna-anon-sample.csv
```

### 5. QA-walkthrough innan första leverans

För varje CSV:
- [ ] Header korrekt (rätt antal cols beroende på GDPR-mode)
- [ ] Sortering: top-row har högst score
- [ ] Adresser ser legitima ut (inte tomma, inte "undefined", inte "null")
- [ ] Score-distribution är realistisk (inte alla 0 eller 1)
- [ ] Open file in Excel/Numbers — formatting ren

### 6. Markera prospects som "qualified" innan export

Default-status på nya prospects = "new". För att export ska
filtrera de bra ones via `?status=qualified`, måste Edvin markera dem:

```sql
-- Auto-flagga som qualified om score >= 0.5
UPDATE prospects SET status = 'qualified'
WHERE score >= 0.5 AND status = 'new';
```

ELLER lägga till `--auto-qualify` flagga till bulk-scan-skriptet.

## Pricing-koppling

Per `~/freelance-launch/solar-leads-bureau/pricing-and-offer.md`:
- Pilot (50 prospects): **1500 kr** — för första 3 kunder, rep-byggande
- Standard (200): **3500 kr** — efter 1 lyckad pilot
- Premium (500 + custom-scoring): **8000 kr/mån** abonnemang
- Premium Plus (1000+, custom-API): **15000-25000 kr/mån**

## Tids-investering Edvin

- Adress-seed (steg 1): 1h om OSM/Lantmäteriet, 3h om Hitta-manual
- Pipeline-körning (steg 2): 25 min × 1 (interactive)
- Verify + export (steg 3-4): 30 min
- QA (steg 5): 20 min
- **Total: 2-4h** för första demo-batch klar

## Säljbar-output-volym för 300 input addresses

Realistic:
- 250-280 av 300 får score (geocoding-failures, satellit-misses)
- Av dessa: ~120 score >= 0.5 (qualified bucket)
- Av dessa: ~50 score >= 0.7 (Premium-tier)
- Återstår räcker för 1 Standard (200) eller 2 Pilots (50×2)

## Risker

1. **Hitta-rate-limit** vid kontakt-enrichment — vänja sig vid Cloudflare-challenge.
   Fix: Electron-renderer för manuell solve, ej API-bara.
2. **Moondream-detection-noise** — 2-3 false positives per 100 = OK, Edvin bör spot-check.
3. **GDPR** — innan leverans behöver Edvin ha PUB-avtal-template + skriva
   personuppgiftspolicy. Se solar-leads-bureau/lead-export-design.md.

## Nästa steg efter demo

1. Skicka demo-CSV till 3 installatörer per `installator-targets.md` Tier 1
2. Sales-pitch: "Här är 50 prospects från Sollentuna kommun, gratis att titta
   på, 1500 kr om du vill ha 50 mer + namn/telefon"
3. Vid första betalning: F-skatt eller Frilans Finans-konto behövs.

---

**Status 2026-05-12:** Runbook skriven, ej körd än. prospects.db är fortfarande
9-row dev-fixture. Endast Edvin kan köra detta lokalt (kräver Mac med
deps installerade + ev. ollama för Moondream).

Säg "kör solar bulk-demo" när du är klar att köra.
