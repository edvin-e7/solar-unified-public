# Manual QA Checklist

Run this checklist end-to-end before any commit that touches UI or API.
Expected time: ~15 minutes. Log the run in `QA_RUN_LOG.md` when done.

**Pre-run setup:**

```bash
cd backend && .venv/bin/uvicorn main:app --reload --port 8000 &
cd frontend && npx vite --port 5173 &
```

Open http://localhost:5173. Have at least 3 test prospects in the DB.

---

## Dashboard (`/`)

### T-01 KPI tiles render
- Pre: ≥1 prospect exists
- Steps: navigate to `/`
- Expected: 4 tiles show numeric values (totalt, konvertering, berikad, snittscore). No `NaN`, no empty strings.
- Actual: [ ] pass  [ ] fail — notes: ________

### T-02 Daily bars render
- Pre: prospects added over last 14 days
- Steps: scroll to "Senaste 14 dagarna"
- Expected: bar chart with ≥1 visible bar, hover shows `{day}: {n}`
- Actual: [ ] pass  [ ] fail — notes: ________

### T-03 Agent activity feed
- Pre: backend running
- Steps: scroll to "Agentaktivitet"
- Expected: ≥5 agents listed with name + idle/active dot. No HTTP 500 in console.
- Actual: [ ] pass  [ ] fail — notes: ________

### T-04 Pull-quote insight (error path)
- Pre: ALLOW_EXTERNAL_LLM=0 OR no GEMINI_API_KEY
- Steps: reload `/`
- Expected: page loads without error; pull-quote block absent or shows "—"; no red console error.
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Prospekt (`/prospekt`)

### T-10 Add prospect via paste (golden)
- Pre: BulkInput reachable
- Steps: paste "Teststigen 1, Stockholm" → press add
- Expected: row appears in table with status "new"; table count increments
- Actual: [ ] pass  [ ] fail — notes: ________

### T-11 Import CSV (edge)
- Pre: valid 3-row CSV file
- Steps: BulkInput → import CSV → select file
- Expected: all 3 rows appear; toast confirms count
- Actual: [ ] pass  [ ] fail — notes: ________

### T-12 List loads
- Steps: navigate to `/prospekt`
- Expected: table populates within 2s; row count matches `GET /api/prospects` JSON length
- Actual: [ ] pass  [ ] fail — notes: ________

### T-13 Row selection → detail tab
- Steps: click any row
- Expected: right panel "Info" tab shows address, owner, kWh
- Actual: [ ] pass  [ ] fail — notes: ________

### T-14 Bulk status change
- Steps: check 2 rows → click "Intresserad" in bulk bar
- Expected: both rows' status column flips; left status-edge color turns green
- Actual: [ ] pass  [ ] fail — notes: ________

### T-15 Bulk delete (confirm dialog)
- Steps: check 1 row → click "Ta bort" → confirm
- Expected: row disappears; count decrements
- Actual: [ ] pass  [ ] fail — notes: ________

### T-16 Bulk enrich (error path)
- Pre: network disconnected
- Steps: check 1 row → click "Berika"
- Expected: toast shows error; row unchanged; no uncaught error in console
- Actual: [ ] pass  [ ] fail — notes: ________

### T-17 Status hotkey (scoped)
- Steps: select a row on Prospekt, press `2`
- Expected: row flips to "interested"
- Counter-test: navigate to `/installningar`, focus the page (not an input), press `2` → nothing happens
- Actual: [ ] pass  [ ] fail — notes: ________

### T-18 J/K navigation
- Steps: focus page (not input), press `j` 3 times
- Expected: selected row moves down 3 positions; detail panel updates
- Actual: [ ] pass  [ ] fail — notes: ________

### T-19 Tab switching
- Steps: click Info / Anteckningar / Dokument
- Expected: active tab has `--azure` underline; Dokument shows "Phase 20" placeholder
- Actual: [ ] pass  [ ] fail — notes: ________

### T-20 Export CSV
- Steps: click "Exportera CSV"
- Expected: browser downloads `prospects-*.csv`; file opens in spreadsheet with expected columns
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Sök (`/sok`)

### T-21 Filter by address (golden)
- Pre: prospects containing "stockholm" exist
- Steps: enter `stockholm` in address field → click Sök
- Expected: results list shows only matching rows; count matches `GET /api/prospects?q=stockholm`
- Actual: [ ] pass  [ ] fail — notes: ________

### T-22 Save + apply search
- Steps: run a filter → click "Spara sökning" → enter name "test" → clear fields → click saved chip "test"
- Expected: fields refill with saved values
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Detektion (`/detektion`)

### T-23 Single detection (golden)
- Pre: ALLOW_EXTERNAL_LLM=1, valid address
- Steps: paste "Strandvägen 5, Stockholm" → Kör detektion
- Expected: result card appears within 30s with JSON payload
- Known deviation: expected to fail until `/api/detect` contract is aligned — frontend sends `{"address": ...}` but backend expects `{"image": ...}`, producing a 422 in the result log. Track as open bug.
- Actual: [ ] pass  [ ] fail — notes: ________

### T-24 Multiple detections (edge)
- Steps: paste 3 addresses → run
- Expected: 3 result cards in reverse chronological order
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Karta (`/karta`)

### T-25 Pins render colored (golden)
- Pre: prospects with lat/lng exist
- Steps: navigate to `/karta`
- Expected: map loads, pins visible, each colored by status (stone/forest/amber/barn)
- Actual: [ ] pass  [ ] fail — notes: ________

### T-26 Pin click → drawer
- Steps: click a pin
- Expected: right drawer opens to that prospect's Info tab
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Agenter (`/agenter`)

### T-27 Live status refresh
- Steps: open `/agenter`, wait 6s
- Expected: `last_run` timestamps update (if any agent recently ran) within 5s polling interval
- Actual: [ ] pass  [ ] fail — notes: ________

### T-28 Leaderboard renders
- Steps: scroll to leaderboard
- Expected: list shows agents with score + wins, OR "Ingen data än" if journal empty
- Actual: [ ] pass  [ ] fail — notes: ________

### T-29 Journal tail renders
- Steps: scroll to journal
- Expected: recent entries, each with outcome chip (green/red). **Regression check: page loads without HTTP 500 from `/api/execute/status`.**
- Actual: [ ] pass  [ ] fail — notes: ________

### T-30 Run learning cycle (error path)
- Pre: ALLOW_EXTERNAL_LLM=0
- Steps: click "Kör inlärningscykel"
- Expected: toast shows error; UI doesn't hang; page still usable
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Berikning (`/berikning`)

### T-31 Gate chips match /api/settings/flags
- Steps: compare chip state to `curl http://localhost:8000/api/settings/flags`
- Expected: identical booleans
- Actual: [ ] pass  [ ] fail — notes: ________

### T-32 Enrich with paid APIs disabled
- Pre: ALLOW_GOOGLE_SOLAR_API=0
- Steps: select 1 prospect without lat/lng → Berika
- Expected: log shows Nominatim geocode attempt + PVGIS solar fetch (no Google Solar call); no paid-API traffic in network tab
- Actual: [ ] pass  [ ] fail — notes: ________

### T-33 Enrich with nothing selected (edge)
- Steps: click Berika with 0 selected
- Expected: button disabled; no network request
- Actual: [ ] pass  [ ] fail — notes: ________

---

## Inställningar (`/installningar`)

### T-34 Theme toggle
- Steps: click theme toggle
- Expected: page switches light ↔ dark; setting persists on reload (localStorage)
- Actual: [ ] pass  [ ] fail — notes: ________

### T-35 Flag chips show live state
- Steps: change `.env` `ALLOW_EXTERNAL_LLM=0` → restart backend → reload page
- Expected: LLM chip now shows "AV"
- Actual: [ ] pass  [ ] fail — notes: ________

### T-36 Hotkey reference complete
- Steps: read shortcut table
- Expected: all keys (J, K, 1, 2, 3, 4) listed with Swedish descriptions
- Actual: [ ] pass  [ ] fail — notes: ________

### T-37 CSV import (duplicate)
- Already T-11 — skip here or revisit if Settings uses different component

### T-38 CSV export (duplicate)
- Already T-20 — skip here

---

## Cross-cutting

### T-40 Offline banner
- Steps: stop backend → observe top bar
- Expected: badge flips to "offline" (barn/red) within 5s; pages still render stale data; no uncaught promise rejections
- Actual: [ ] pass  [ ] fail — notes: ________

### T-41 Sidebar nav completeness
- Steps: click every sidebar item in order
- Expected: all 8 pages load without error; active state (azure left-border) follows selection
- Actual: [ ] pass  [ ] fail — notes: ________

### T-42 Keyboard tab order
- Steps: from Sidebar, press Tab repeatedly
- Expected: focus moves down nav items in document order, then into main content
- Actual: [ ] pass  [ ] fail — notes: ________

### T-43 Bundle size
- Steps: `cd frontend && npx vite build | grep assets/index`
- Expected: main entry chunk < 400 KB; no single chunk > 500 KB
- Known deviation: Leaflet/Map chunk (~1 MB) exceeds the 500 KB guard. Pre-existing, tracked separately.
- Actual: [ ] pass  [ ] fail — notes: ________

### T-44 Console clean on cold load
- Steps: hard-reload each page, open DevTools console
- Expected: no `Error`, no `Warning`, no `Failed to fetch` red entries (except T-04 expected insight skip)
- Actual: [ ] pass  [ ] fail — notes: ________
