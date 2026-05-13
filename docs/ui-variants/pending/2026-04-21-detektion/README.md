# Detektion — panel detection results

**Page:** Detektion
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Editorial grid of 9 detection cards, each with a 3:2 paper-tint frame and a CSS-only roof/bounding-box sketch (no real imagery) showing detected panels. Confidence is a thin 3px bar plus percentage — colors shift forest → leaf → barn across high/mid/low tiers. Header is a full-width amber-accented "run bar" that combines the pending queue size, mean confidence, cost, and a blue primary "Kör nu" button with a settings secondary. Card metadata (panels, takvinkel, area, azimut) is tabular-num in a 2×2 grid below each thumbnail.

## Tradeoffs

- **Gains:** visual overview beats a table for this domain — the user is judging roof geometry, not sorting numbers. Confidence bar + % gives dual-channel readability. Run bar puts the action where the work starts.
- **Costs:** fake roof/bbox sketches communicate intent but may mislead if users assume real images; needs a "schematic" label in prod. 3-wide grid forces ≥1200px comfort zone.
- **Risks:** bounding-box is drawn with amber — re-uses the content-accent. If the page later shows multiple overlay layers we'll need distinct colors.

## Files touched

- `docs/ui-variants/pending/2026-04-21-detektion/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None.
