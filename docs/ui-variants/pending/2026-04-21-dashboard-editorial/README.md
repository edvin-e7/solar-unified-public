# Dashboard — Editorial (Almanac Frontispiece)

**Page:** Dashboard
**Status:** pending
**Generated:** 2026-04-21 by claude

## What's different

Pushes the Solar Almanac aesthetic to its logical conclusion: the Dashboard reads like the front page of a weekly broadsheet. One enormous display numeral ("1,247 prospekt") sets the register, a single pull-quote from PatternAgent dominates the fold, and supporting KPIs run as a thin statistical ribbon beneath the dateline. Generous margins, hairline rules, drop cap, small caps metadata — the page earns its whitespace. Reading order is top-to-bottom like prose, not left-to-right like a dashboard.

## Tradeoffs

- **Gains:** unmistakable brand identity, lowest cognitive entry cost (one number, one idea), the agent insight finally gets treated as content not chrome
- **Costs:** lower info density — fewer KPIs visible at a glance, power users will scroll more, requires a well-chosen pull-quote (cached insight must be genuinely good)
- **Risks:** if PatternAgent returns a weak insight the whole page feels empty; needs graceful degradation to a secondary quote or hide the block entirely

## Files touched

- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/dashboard/FrontispieceHero.tsx` (new — display numeral + dateline)
- `frontend/src/components/dashboard/PullQuote.tsx` (new — reusable for other pages)
- `frontend/src/components/dashboard/StatRibbon.tsx` (new — thin rule-divided strip)

## New tokens (if any)

None. Leans heavily on `--font-display`, `.display`, `.caps`, `.rule`, `--amber` for the drop cap, `--ink-60` for metadata.
