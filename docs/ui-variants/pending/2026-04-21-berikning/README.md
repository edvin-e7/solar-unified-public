# Berikning — API gates with dry-run

**Page:** Berikning
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Three stacked sections reading top-down like a control panel: (1) **API-grindar** — 6 source cards with a dot + label state (forest "Tillåten" / stone "Pausad") and per-call cost underneath; active gates get a 2px forest left accent, paused ones stone. No filled pills. (2) **Kostnad föregående 24h** — 4 tabular metric cells in a single rule-bordered row, total rendered in amber for emphasis. (3) **Kör berikning nu** — split two-column: left card with azure left-accent listing queue size / active sources / eta / cost estimate / budget share, with `Dry-run` secondary and an azure primary `Kör berikning · 61 prospekt`. Right column is a monospace dry-run plan with forest-green cost totals and amber numerals.

## Tradeoffs

- **Gains:** one-screen mental model of "what will run, what will it cost, and can I preview before spending". Dry-run output in a code-looking pane sets expectations that this is honest, deterministic plumbing.
- **Costs:** gate card grid (3×2) is dense; below 1024px the third column wraps and cards become too tall.
- **Risks:** treating the gate cards as toggles without a visible switch control may confuse — the state chip is the toggle. Needs a clearer affordance for clickability in prod.

## Files touched

- `docs/ui-variants/pending/2026-04-21-berikning/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None.
