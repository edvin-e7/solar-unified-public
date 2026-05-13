# Karta — geographic view with drawer

**Page:** Karta
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Full-bleed map placeholder (no tile service) rendered as a paper-tint rectangle with a 40px repeating grid, center crosshair, and a scale bar. Prospect pins are absolute-positioned status-colored dots; the selected pin wears an amber outline ring. Top-left carries filter chips (`Alla`, `Nya`, `Intresserade`, `Callback`) with counts. Bottom-right has a 2-button zoom control, bottom-left a mono scale indicator. The 380px right drawer shows the full editorial detail card for Sveagatan 12, Falun — mini-roof sketch, score block (amber 36px numeral), tak & solpotential rows, contact, notes, primary azure CTA.

## Tradeoffs

- **Gains:** placeholder grid is honest — no map-tile cost, no "fake satellite" sheen. Paper palette stays intact. Drawer reuses the detail-card shape from Prospekt so users learn it once.
- **Costs:** grid is decorative; a real geographic reading of pin positions is impossible. The moment we integrate tiles the chrome tone shifts cold and the page loses its paper feel — need a dedicated "map surface" decision.
- **Risks:** labels ("Falun", "Borlänge") are pure static text — they'll drift when real coordinates arrive.

## Files touched

- `docs/ui-variants/pending/2026-04-21-karta/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None.
