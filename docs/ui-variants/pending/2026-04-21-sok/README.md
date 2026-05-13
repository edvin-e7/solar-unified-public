# Sök — semantic search with hero

**Page:** Sok
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Dedicated Search page with a large editorial hero — 18px input, serif h2, `/` shortcut hint, token-style suggestion chips. Saved searches rail on the left (sticky, sort by frequency), result previews on the right in a two-column card grid. Query shown in the demo is `takvinkel > 30` returning 12 cards; the copy/layout also documents the empty-state behaviour (shows "senast tillagda" + "fortsätt där du slutade" when query is blank). Search expressions like `score ≥ 8.0`, `status:intresserad`, `area > 120` are first-class — no hidden filter drawer.

## Tradeoffs

- **Gains:** query language feels powerful without being "advanced search" modal. Saved searches become the spine of repeat work. Hero gives the page presence so it doesn't feel like a utility sub-route.
- **Costs:** two-column card grid + 280px rail needs ≥1200px breathing room; below that the rail should collapse above results.
- **Risks:** expression grammar (`takvinkel > 30`) must be documented clearly or it looks like free-text that happens to work sometimes. Needs a parse-error affordance.

## Files touched

- `docs/ui-variants/pending/2026-04-21-sok/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None.
