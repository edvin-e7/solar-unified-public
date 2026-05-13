# Legacy components — salvage from `edvins-solprojekt-sandbox`

Migrated 2026-04-21. **Not wired into the app yet.** These are reference implementations kept around for on-demand porting when the corresponding features land in solar-unified. Expect broken imports, dark-slate styling that violates the Solar Almanac tokens, and coupling to Electron-only APIs (`window.solprojektApi`) that do not exist here.

## Files

- **`MrkollScraper.tsx`** — per-row Swedish people-data enrichment button (mrkoll.se + hitta.se). Salvaged because the legacy app proved this is the only free path to reverse-address → resident name/phone lookups (see [`docs/DESKTOP_PATTERNS.md`](../../../../docs/DESKTOP_PATTERNS.md) "Free Swedish people-data scraping" table). Triggers an Electron main-process scraper via `window.solprojektApi.mrkollLookup`. Why kept: reference for the IPC shape + the merge logic (`mergePhones`, address/PN overwrite rules) when solar-unified grows a bulk-enrichment flow.
  - **Before wiring in:** port/implement `hooks/useProspects` (`Prospect`, `SeedItem`), `global.ts` (`PersonEnrichment`, `window.solprojektApi`), `utils/lookupLinks` (`extractCity`), `utils/phone` (`mergePhones`), `services/enrichment` (`enrichPerson`). Retokenize away from `amber-400`/`white/10`/`black/30` onto Solar Almanac tokens. Decide whether solar-unified even runs in Electron — if it's PWA-only, the whole component no-ops.

- **`DocumentDropzone.tsx`** — drag-and-drop ingestion for CSV / JSON / TXT / images / PDF into the seed list, routing files through a backend `ingestDocuments` agent pipeline. Salvaged because the Phase 20 "Dokument" tab needs exactly this UX (drop files → detect/pattern/scoring agents run → prospects seeded). Why kept: complete drag-over state machine, per-file status/hint rendering, UTF-8-aware error handling.
  - **Before wiring in:** port `services/agent.ingestDocuments` (+ `DocIngestFileResult`, `DocIngestResponse`) onto the FastAPI backend, re-model `SeedItem` against solar-unified's Prospect shape, retokenize the slate/amber palette. Ensure the backend rejects files above a sensible size cap; this component does no client-side validation.

- **`Tour.tsx`** — overlay-based onboarding tour driven by `data-tour="<id>"` attributes on target elements. Salvaged because we want a first-run guided tour for new reps. Why kept: the DOM-measurement pattern (useLayoutEffect + getBoundingClientRect, cutout via huge box-shadow, arrow-key + Escape handlers) is a clean, framework-free implementation worth copying rather than re-deriving.
  - **Before wiring in:** swap `bg-slate-900/95` + `text-amber-200` + `border-amber-400/40` for Solar Almanac paper/ink/amber tokens. Define the real step list somewhere (a sibling `tourSteps.ts` or app constants). Wire it behind a user-controllable "Visa rundtur" button — don't auto-open for returning users.

## What needs to change before any of these wire in

1. **Retokenize** — every file here uses the sandbox's dark-slate + amber palette. solar-unified uses the Solar Almanac paper/ink tokens ([`frontend/src/design/tokens.css`](../../design/tokens.css)). Find-and-replace `bg-slate-*`, `text-white`, `border-white/*`, `bg-black/*`, `bg-amber-400` etc.
2. **Resolve imports** — each file has a `TODO` comment listing its broken imports. Either port the underlying module or rewrite the component against solar-unified's equivalents.
3. **Decide runtime surface** — `MrkollScraper` requires Electron; `DocumentDropzone` requires a backend route; `Tour` is framework-agnostic. Confirm the solar-unified shell can host each before porting.
4. **Re-run lint + typecheck** — the sandbox ran Prettier + ESLint with slightly different rules. Expect warnings about `any`, unused vars, and the `react-hooks/set-state-in-effect` rule that `Tour.tsx` disables.
