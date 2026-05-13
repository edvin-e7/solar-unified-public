> **Migrated 2026-04-21 from edvins-solprojekt-sandbox.** Desktop/Electron patterns, address format rules, Swedish API ceiling notes. Reference only — canonical coding rules live in the root CLAUDE.md.

# Solprojekt — agent memory

Canonical context file for Claude Code and Gemini CLI. Everything both agents need lives here.

## What this is

A **solar prospecting tool for Swedish field sales**. Edvin pastes a list of Swedish addresses, the app runs each through Google's Solar API, ranks rooftops by yearly kWh, and tracks call status + notes. A Gemini-generated one-liner gives the rep a ringöppnare (cold-call opener) on demand.

Stack: Vite + React 19 + TypeScript + Tailwind v4 + vite-plugin-pwa. Everything client-side, localStorage-persisted, no backend.

## Entry points

- `src/App.tsx` — bulk input, ranked table, row expansion, CSV export, satellite + Street View thumbnails
- `src/hooks/useProspects.ts` — localStorage CRM state (`solprojekt:prospects:v1`); exposes `addMany`, `seed`, `setInsights`, `update`, `remove`, `clear`
- `src/services/solar.ts` — geocode + Google Solar API + SEK savings calc
- `src/services/gemini.ts` — Gemini pitch generator (Swedish, one sentence; `gemini-2.5-flash`)
- `electron/main.cjs` — Electron main process (loads `dist/index.html`, devtools detached for bug-test build)
- `public/prospects-seed.json` — gitignored prospect data parsed from `~/Desktop/Edvin prospektering/Edvin Prospekterings lista.ods`. Includes color-decoded statuses (green→interested, yellow/blue/cyan→callback, red→rejected, white→new). Re-generate with the python script in this file's git history (look for `analyze_colors_*` or run a fresh extract from the .ods).
- `docs/swedish-apis.md` — full reference for Swedish property/satellite/electricity APIs (Lantmäteriet, TIC, Metria, Copernicus, Nordpool, etc.). Imported from `edvin-solar-master`. Use this for future "where do I get X data from in Sweden" questions.
- `docs/PRD.md` — Product Requirements Document. All 13 functional requirements with status, data model, external deps, gaps. Read before implementing new features.
- `docs/README.md` — index for `docs/` and `docs/legacy/`. Explains what the legacy plans from `edvin-solar-master` describe and which parts map onto Solprojekt.
- `docs/legacy/*.md` — plans and review docs from the Python prospecting tool. **Reference only**, not a to-do list. Solprojekt is a subset of the scope described there.

## Commands

```bash
npm install --legacy-peer-deps   # vite-plugin-pwa peer dep requires this
npm run dev                      # http://localhost:5173
npm run build                    # tsc -b && vite build → dist/
npm run lint
npm run electron:dev             # run as desktop app against current build
npm run electron:build           # package Windows .exe to release/Solprojekt-win32-x64/
```

The packaged .exe is ~220 MB standalone + unpacked folder ~419 MB. Portable, no installer. Launches with devtools detached for bug testing. Node_modules currently bundled inside the asar — not optimal, shave ~200 MB by extending the `--ignore` pattern in `electron:build` script if size matters.

## Secrets

`.env` (gitignored, already present locally):

```
# Backend / scripts read these:
GOOGLE_MAPS_API_KEY=...
GEMINI_API_KEY=...

# Frontend dev server reads these (duplicate the same values). VITE_-prefixed
# vars are the ONLY ones exposed to client code. Production builds ignore them
# entirely — Electron users paste their keys into the Settings modal and they
# land in userData/secrets.json.
VITE_GOOGLE_MAPS_API_KEY=...
VITE_GEMINI_API_KEY=...
VITE_ELECTRICITY_RATE=2          # SEK/kWh, default 2
```

Vite's `envPrefix` is `['VITE_']`. Non-VITE env vars NEVER reach the browser —
`loadFromEnv()` in `src/services/keys.ts` early-returns outside DEV mode so
Rollup tree-shakes the key lookups out of the production bundle.

**Security debt:** the API keys were committed in the pre-consolidation `HANDOFF.md`. Rotate them in Google Cloud Console before sharing this repo publicly.

## Style

- TS strict, function components + hooks only
- Named exports; default export only in `App.tsx`
- Tailwind for all styling; no CSS modules
- Custom hooks use **lazy `useState` initializers** — never `useState([]) + useEffect(load, [])` (violates `react-hooks/set-state-in-effect`, which bit us in an earlier session)
- Swedish UI strings, English code identifiers and comments
- Prettier + ESLint are the source of truth

## Free Swedish people-data scraping (the ceiling)

**Don't re-explore this — it doesn't work for batch.** Tested against:

| Source | Reverse address → resident? | Notes |
|---|---|---|
| mrkoll.se | ✅ via Electron BrowserWindow only | Cloudflare-blocks bulk; per-row works (`Hämta från mrkoll`) |
| hitta.se | ❌ | Per-address page only shows aggregate area stats; per-resident needs paid login |
| eniro.se | ❌ | Anti-bot ("verifiering") page on every reverse-lookup URL pattern |
| birthday.se | ❌ | Robotskydd page (4 KB stub) on every reverse-lookup URL pattern |
| merinfo.se | ❌ | 404 on every URL pattern |
| upplysning.se | ❌ | 404 on every URL pattern |
| ratsit.se | name-only | No address-based search at all |

**What actually works:** the per-row `MrkollScraper` component in `App.tsx` invokes `electron/mrkoll.cjs` via `window.solprojektApi.mrkollLookup`, which loads mrkoll in a hidden Chromium window with a persistent cookie partition, fills the search form, navigates to the result, scrapes name/age/phone/address, and writes diagnostics to `userData/mrkoll-last.{json,html}`. Limit it to ~30 calls per session to avoid Cloudflare account-level bans.

**Paid alternatives for batch enrichment** (not implemented):
- Lantmäteriet Fastighetsregistret API — official property registry, requires application + per-query fees
- TIC Property API — commercial wrapper around Lantmäteriet, simpler to integrate
- ScrapingBee / Bright Data — generic anti-bot proxy services, ~$50/mo for ~10 000 requests

## Address format (hard rule for all agents)

Any address that an agent — Claude, Gemini, the autoscanner, or any future tool — generates, suggests, or pastes into UI/prompts/data files MUST follow Swedish format:

> `Gatunamn 12, 123 45 Stad`

street name + space + house number, comma, optional postcode (`DDD DD`), then city. Use ÅÄÖ correctly. Never anglicize street names, never use US-style "City, ST ZIP". Currency in any output is SEK (`kr`), never USD or EUR. The Gemini prompt in `src/services/gemini.ts` enforces this; new prompts must do the same.

## File ownership (parallel agents)

**Claude owns** — frontend + services:
- `src/**`
- `vite.config.ts`, `index.html`
- `AGENTS.md`, `README.md`

**Gemini owns** — packaging + assets:
- `capacitor.config.ts`, `android/**`
- `src-tauri/**`
- `public/icons/**`
- `package.json` scripts **additions only** (`android:build`, `desktop:build`)

If Gemini needs to change a Claude-owned file, append the request to `AGENTS.md` under `## Cross-agent requests` and stop.

## Task queue

### Active (Claude)
- [ ] PWA icons referenced in `vite.config.ts` manifest still missing — any install surface shows a broken icon. Deferred to Gemini; Claude won't block on this.
- [ ] Places Autocomplete on bulk input (probably won't fit — keep plain textarea)
- [ ] CSV file upload (currently textarea-only)
- [ ] PDF export of the ranked list for handing off to a team

### Active (Gemini)
- [ ] **PWA icons** — generate `public/icons/icon-192.png`, `icon-512.png`, `icon-maskable.png`. Amber sun (`#f59e0b`) on deep-navy (`#0b1020`). Pure-JS rasterization (`sharp` / `@resvg/resvg-js`), no imagemagick.

### Deferred (Gemini)
- [ ] Capacitor Android wrapper — only if Android SDK available
- [ ] Tauri v2 desktop wrapper — only if Rust + webkit2gtk libs available

### Research
- [ ] Google Solar API coverage in Sweden — it's patchy outside major cities. App already handles 404 → error message per row, but test with ≥50 real Swedish addresses across urban/rural before calling this production-ready.
- [ ] Is 2 SEK/kWh a sensible default for 2026? Consider reading nordpool or letting user override per-session.

## Cross-agent requests

*(Empty. When Gemini needs Claude to change a frontend file, or Claude needs Gemini to build an asset, add a bullet here.)*

## Known gotchas

- `vite-plugin-pwa@1.2.0` declares peer `vite@<=7` but we're on `vite@8`. Use `--legacy-peer-deps` for install. Works fine at runtime.
- Gemini CLI free tier has **zero quota on `gemini-2.5-pro`**; project is pinned to `gemini-2.5-flash` in `.gemini/settings.json` and `src/services/gemini.ts`.
- Google Solar API key must have **Solar API enabled** in Google Cloud Console (confirmed for the current key).
