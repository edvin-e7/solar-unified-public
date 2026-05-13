# Dashboard — Information-dense (Almanac Terminal)

**Page:** Dashboard
**Status:** pending
**Generated:** 2026-04-21 by claude

## What's different

Bloomberg-terminal density rendered in paper/ink. The whole viewport becomes one scannable grid: 12 KPI tiles, a 14-day sparkline strip, a live event ticker, a compact agent health matrix, and a top-10 prospect mini-table. No hero, no whitespace luxury — every pixel pulls weight. Typography is mono-forward for numbers (JetBrains Mono via `--font-mono`, `.tabular`), display serif reserved for section markers. Designed for the user who keeps the Dashboard open all day and glances at it like a trading screen.

## Tradeoffs

- **Gains:** more info visible without scrolling, fast eye-movement scanning, reinforces the "instrument panel" mental model
- **Costs:** higher cognitive load on first landing, demands good data hygiene (empty cells look bad), less forgiving on small laptop displays
- **Risks:** density can tip into noise if any single tile mis-renders; needs discipline on accent usage — amber only for truly actionable deltas

## Files touched

- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/dashboard/KpiGrid.tsx` (new, 12-cell grid)
- `frontend/src/components/dashboard/SparklineStrip.tsx` (new)
- `frontend/src/components/dashboard/EventTicker.tsx` (new)
- `frontend/src/components/dashboard/AgentMatrix.tsx` (new)

## New tokens (if any)

None. Uses existing `--ink`, `--paper`, `--paper-tint`, `--rule`, `--amber`, `--forest`, `--barn`, `--stone`, `--leaf`. Azure NOT used on content (stays nav-only).
