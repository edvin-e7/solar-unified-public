# Agenter — leaderboard with journal tail

**Page:** Agenter
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Agent operations as a single ranked board instead of a dashboard of tiles. 10 agents (coordinator, piifilter, verification, scoring, detection, quality, pitch, pattern, data_gatherer, ui_design) listed by composite score with columns for 24h runs, success-rate (thin bar + %), average cost (tabular kr), last-run timestamp (mono). Live-status uses a colored dot with a pulsing ring on "aktiv" agents (CSS keyframe only, no JS). Below the board, a journal tail of the last 15 entries in a monospace log — each line is `time | agent | [level] | message`, with `ok` / `warn` / `err` level tags in forest / leaf / barn. Amber `<mark>` highlights the one datum worth catching per line.

## Tradeoffs

- **Gains:** one ordering axis ("who is pulling their weight") instead of ten tiles. Monospace log at the bottom reads like a real system and is scannable. Color-coded level tags keep the list calm.
- **Costs:** a board with 10 agents is fine; at 30+ we'll need collapse/group. Pulse animation is subtle but could be annoying for accessibility — reduce-motion needed in prod.
- **Risks:** composite rank formula isn't surfaced — users may wonder why coordinator is #1 at zero cost. Needs a "how ranked" tooltip.

## Files touched

- `docs/ui-variants/pending/2026-04-21-agenter/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None.
