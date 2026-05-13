> **Migrated 2026-04-21 from edvins-solprojekt-sandbox.** Product Requirements Document from predecessor variant. 13 functional requirements + gap list. Compare against current state before implementing any listed gap.

# Solprojekt — Product Requirements Document

**Status legend:** ✅ done · 🚧 partial · ❌ missing
**Last updated:** 2026-04-13

## 1. Product

A browser-based prospecting tool for a Swedish solar sales rep. The user pastes or imports addresses, the app pulls rooftop solar data from Google's Solar API, ranks prospects by yearly kWh, and acts as a lightweight CRM (call status, phone, notes) so the rep can work the list.

**Why this exists:** Edvin sells solar panels door-to-door / by phone in Stockholm and Hedemora/Säter. He keeps lead lists in `.ods` / `.xlsx` files with color-coded statuses. He needs a faster way to find the highest-potential rooftops first and not lose track of who he's already called.

**Non-goals:** ML detection of panels from satellite (handled by the separate `edvin-solar-master` Python tool). Backend / multi-user sync. Direct integration with Lantmäteriet (documented in `docs/swedish-apis.md` for future work).

## 2. Target user

- Single user, single device. localStorage persistence, no auth, no sync.
- Swedish UI strings. SEK currency. `sv-SE` number formatting.
- Runs in Chrome/Edge desktop **and** as a packaged Electron .exe for offline / standalone use.

## 3. Functional requirements

### F1. Bulk address input ✅
- Textarea, one address per line. Whitespace + duplicates trimmed.
- Live counter shows how many parseable addresses are pending.
- Submit button disabled when empty or while a run is in progress.
- **Acceptance:** pasting 50 addresses, pressing "Analysera alla", all 50 are processed sequentially with progress `done/total` shown on the button.

### F2. Solar API analysis ✅
- For each address: `geocode` → `buildingInsights:findClosest` → derive `yearlyEnergyKwh`, `maxAreaM2`, `sunHoursPerYear`, `maxPanels`, `panelCapacityWatts`, `imageryYear`.
- Failed addresses (404 = no rooftop data, or any API error) keep the row with `insights: null` and `error: "..."` so the rep can still call them.
- **Acceptance:** an address Google has no rooftop data for renders as a row with the error message in red; an address Google does have data for renders the kWh + savings.

### F3. Ranked prospect table ✅
- Always sorted by `yearlyEnergyKwh` descending. Failed rows fall to the bottom.
- Columns: name (if seeded) / address+region, kWh/yr, SEK savings/yr, panels (sm+), status badge.
- Status badge has distinct color per state (new=neutral, called=blue, interested=green, rejected=red, callback=amber).

### F4. Per-row CRM ✅
- Inline-editable fields when row is expanded: status (dropdown), phone (text), notes (text).
- Edits persist to localStorage immediately.
- `updatedAt` timestamp tracked per row (not yet displayed; see G3).

### F5. Row expand → details ✅
- Click anywhere on a row to expand. Clicking again collapses.
- Expanded view shows: rooftop mini-stats (area, sun hours, panel cap, imagery year), satellite thumbnail, Street View thumbnail, AI-generated cold-call opener (lazy-loaded on first expand), and the CRM editors.
- Thumbnails are clickable → open Google Maps / Street View in a new tab.

### F6. AI cold-call opener (Gemini) ✅
- One Swedish sentence, references the concrete kWh + SEK savings, framed as worth a 2-minute call.
- Lazy-loaded only when row is expanded; cached per `prospect.id` for the session (not persisted across reloads).
- Model: `gemini-2.5-flash` (free-tier compatible). Pro is blocked at 0 quota for free keys.
- **Acceptance:** clicking a row triggers exactly one Gemini call; reopening the same row re-renders the cached pitch with no second call.

### F7. localStorage persistence ✅
- Key: `solprojekt:prospects:v1`. Cap: 500 prospects (configurable in `useProspects.ts`).
- Survives page reload, browser restart, and Electron app restart.
- Hook uses lazy `useState` initializer (project rule — see `solprojekt-reviewer` agent).

### F8. Import from prospects-seed.json ✅
- Button: **Importera prospektlista** → fetches `/prospects-seed.json` and seeds prospects via `useProspects.seed()`.
- Dedupe by phone number first, address second.
- Imported prospects have `insights: null` until F9 runs them through the Solar API.
- Source: parsed from `~/Desktop/Edvin prospektering/Edvin Prospekterings lista.ods` by a Python script using `odfpy`. Statuses are decoded from cell background colors (green→interested, yellow→callback, blue→callback, cyan→callback, red→rejected, white→new).
- **Current seed:** 598 prospects (494 Stockholm + 104 Hedemora/Säter), 555 with phone numbers, 40 already flagged as interested.

### F9. Run Solar API on un-analyzed ✅
- Button: **Kör Solar API på oanalyserade (N)** → walks all prospects with `insights === null && error === null` and calls `analyzeAddress()` for each, persisting per-row results as they come back.
- Disabled when no rows need analysis or while running.
- **Acceptance:** after importing the seed, clicking this button rolls through ~600 addresses and the table re-sorts as kWh values arrive.

### F10. CSV export ✅
- Button: **Exportera CSV** in the table header.
- Output: UTF-8 with BOM (Excel-friendly), columns: name, address, region, phone, status, kwh_per_year, savings_sek, panels, notes, error.
- Filename: `solprojekt-prospekt-YYYY-MM-DD.csv`.

### F11. Clear all ✅
- Confirmation dialog before wiping.

### F12. Stats summary ✅
- Above the table: total prospects, called, interested, total annual savings (sum SEK).

### F13. Electron desktop build ✅
- `npm run electron:build` produces `release/Solprojekt-win32-x64/Solprojekt.exe` (~220 MB single exe + 419 MB unpacked).
- Devtools open detached on launch (deliberate — this is a bug-test build).
- Loads `dist/index.html` via `loadFile`, which is why `vite.config.ts` has `base: "./"` (relative paths).
- **Known waste:** `node_modules` is bundled inside the asar (electron-packager's `--ignore` regex doesn't filter it). Saves ~200 MB to fix; non-blocking.

### F14. PWA install ✅ (manifest) / 🚧 (icons)
- Web manifest references `/icons/icon-192.png`, `/icons/icon-512.png`, `/icons/icon-maskable.png`. **These files don't exist** — PWA installs but shows a broken icon. See G1.
- Service worker auto-updates via vite-plugin-pwa (`registerType: "autoUpdate"`).

## 4. Data model

```ts
type Prospect = {
  id: string;             // unique
  address: string;        // formatted from geocode, or raw input if no insights
  name: string;           // seeded from import; "" otherwise
  region: string;         // "Stockholm" / "Hedemora/Säter" / ""
  savedAt: number;        // ms
  updatedAt: number;      // ms
  status: "new" | "called" | "interested" | "rejected" | "callback";
  phone: string;          // normalized digits
  notes: string;          // freeform; seeded from spreadsheet's call log
  insights: SolarInsights | null;
  error: string | null;
};
```

`SolarInsights` matches the Google Solar API `solarPotential` subset we use (see `src/services/solar.ts`).

## 5. External dependencies

| Service | Purpose | Key env var | Quota notes |
|---|---|---|---|
| Google Geocoding API | address → lat/lng | `GOOGLE_MAPS_API_KEY` | $200 free credit/mo |
| Google Solar API | rooftop insights | same key | $200 free credit/mo, **patchy Sweden coverage** outside major cities |
| Google Static Maps | satellite thumbnail | same key | shared with above |
| Google Street View Static | street thumbnail | same key | shared with above |
| Gemini API | cold-call opener | `GEMINI_API_KEY` | free tier blocks `gemini-2.5-pro`; we use `gemini-2.5-flash` |

All keys live in `.env` (gitignored). Vite's `envPrefix` extends to `VITE_`, `GOOGLE_`, `GEMINI_`.

## 6. Non-functional requirements

- **Perf:** initial JS bundle <250 KB gzipped (currently ~70 KB gzip). Solar API calls run sequentially to avoid Google rate limiting; expect ~1s/address.
- **Security:** no auth, no PII over the wire except what the user types. API keys are baked into the bundle (acceptable for personal/internal use; rotate before sharing the .exe).
- **Browser support:** modern Chromium (Chrome, Edge, Electron). Not tested in Safari/Firefox.
- **Offline:** PWA shell + last-loaded prospects persist offline. New analyses require connectivity.

## 7. Known gaps & TODOs

| ID | Description | Severity | Status | Owner |
|---|---|---|---|---|
| G1 | PWA icons missing (`public/icons/*.png`) | low | open | Gemini CLI |
| G2 | `node_modules` bundled inside Electron asar bloats build by ~200 MB | low | open | Claude |
| G3 | `updatedAt` timestamp not surfaced in UI | low | open | Claude |
| G4 | No "called today" filter / no date-bucketing | medium | open | Claude |
| G5 | No CSV/Excel **import** UI (only seed file) — user must regenerate seed via Python script when source ods changes | medium | open | Claude |
| G6 | Sort is fixed to kWh desc; no column sorting | low | open | Claude |
| G7 | Status colors hardcoded; no way to remap them per user | low | open | Claude |
| G8 | Solar API failures swallow detail beyond message; no retry | medium | open | Claude |
| G9 | Gemini pitch not persisted across reloads | low | open | Claude |
| G10 | Sweden coverage of Google Solar API not measured (anecdotally patchy outside Stockholm/Göteborg/Malmö) | medium | open | Research |
| G11 | API keys committed in pre-consolidation `HANDOFF.md` (now deleted but preserved in git history) — rotate before publishing | high | open | Edvin |
| G12 | Capacitor (Android) + Tauri (Linux/macOS desktop) wrappers — deferred from `edvin-solar-master`'s plan | low | open | Gemini CLI |
| G13 | `MAX=500` cap silently truncated 16% of the imported seed list | high | **fixed** — bumped to 5000 | Claude |
| G14 | `VITE_ELECTRICITY_RATE=0.17` (USD legacy) caused footer + savings calc to use wrong rate | high | **fixed** — `.env` now `=2` (SEK) | Claude |
| G15 | `fmt()` crashed with `Cannot read properties of undefined` when a Prospect's insights object was missing fields, taking down the whole row tree (no error boundary) | high | **fixed** — `fmt(n: number \| undefined \| null)` returns `"—"` | Claude |
| G16 | Unanalyzed seeded prospects rendered as "0 kWh / 0 kr/år / 0 panels" — looked like a real (zero) result | medium | **fixed** — now show "Ej analyserad" / "—" / "Inget takdata" | Claude |
| G17 | Gemini 503 transients silently swallowed — no UI feedback, no retry | medium | **fixed** — `pitchError` state + "Försök igen" button | Claude |
| G18 | No way to look up phone numbers from inside the app | high | **fixed** — 6 external source links per row (mrkoll, hitta.se, eniro, ratsit, birthday.se, Google) with smart pre-filled queries based on phone/name/city | Claude |

## 8. Acceptance test plan (manual)

1. **Boot:** `npm run dev`. App loads at http://localhost:5173 with empty state and zero console errors.
2. **Bulk paste:** Paste 3 known Stockholm addresses, click Analysera alla. All 3 appear in the table sorted by kWh desc with non-zero savings.
3. **Expand:** Click the top row. Verify mini-stats render, satellite + Street View thumbnails load, Gemini pitch appears within ~3s, status/phone/notes editors render.
4. **Edit:** Change status to "interested", type a phone number, type a note. Reload the page. All edits persist.
5. **Import:** Click Importera prospektlista. ~600 prospects appear (mostly status=callback or new). Stats chips update.
6. **Run missing:** Click Kör Solar API på oanalyserade. Progress increments. Some rows get insights, others get errors (expected for rural Sweden).
7. **Export:** Click Exportera CSV. Open in Excel. All rows present with `kwh_per_year` and `savings_sek` columns.
8. **Clear:** Click Rensa allt → confirm. Table empty. Reload — still empty.
9. **Electron .exe:** `npm run electron:build`, double-click `release/Solprojekt-win32-x64/Solprojekt.exe`. App opens in a desktop window with devtools detached. Repeat steps 2–5.

## 9. Out of scope (for v1)

- Multi-user / cloud sync
- Lantmäteriet / TIC / Metria integration (documented in `docs/swedish-apis.md`, not implemented)
- Map view with pinned prospects (table-only for now)
- PDF export (CSV is enough for v1)
- Places Autocomplete on the bulk input
- Integration with the `edvin-solar-master` Python ML pipeline (separate tool, separate process)
