# Prospekt — list view with bulk actions

**Page:** Prospekt
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

First dedicated mock of the Prospekt list page using Solar Almanac tokens. Tests a dense editorial table (17 rows) with a persistent bulk-action toolbar at the top and a right-side preview drawer that becomes active the moment any row is selected. Status is rendered as colored dot + inline Swedish label (`Ny`, `Intresserad`, `Callback`, `Avböjd`) — no filled pills — so the table reads as typography first, state second. Sort affordance lives in the header as a small `↕` / `↓` glyph that tints amber when active.

## Tradeoffs

- **Gains:** bulk ops (change status, enrich, export CSV, delete) stay one tab-stop away, no context switch. Drawer means inspecting a row never loses place in the list. Colored-dot status is lighter typographically than pills and keeps the table calm.
- **Costs:** right drawer eats 360px — narrow laptops (≤1366px) will want the drawer collapsible behind a shortcut.
- **Risks:** the selected-row accent (`box-shadow: inset 2px 0` in amber) reuses the nav accent language; if the user reads that as "active route" we may need a different visual.

## Files touched

- `docs/ui-variants/pending/2026-04-21-prospekt/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None — all colors pulled from existing Solar Almanac palette (paper/ink/amber/forest/leaf/barn/stone/azure). No new variables added.
