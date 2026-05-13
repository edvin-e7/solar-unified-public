# Inställningar — theme, keys, hotkeys, flags

**Page:** Installningar
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Four editorial sections stacked vertically — Tema, API-nycklar, Kortkommandon, Funktionsflaggor. Theme is a single card with a 3-way segmented toggle (Papper / Kväll / System) using amber bottom-rule to mark the active tab. API keys are a table with masked values (`AIza••••••• 9vK2`) in monospace, per-service status dot, and a copy button on each row — keys never leave the server. Hotkeys are a 2-column dashed-rule grid with real `<kbd>` pills (Ctrl+V paste, J/K vim-nav, S status menu, chord combos G+P, G+K, G+D, G+H, ⌘+K palette, `/` focus-search). Flags are a 4-column matrix (name + env default, description, scope badge, on/off state) covering `ALLOW_GOOGLE_SOLAR_API`, `ALLOW_METRIA`, `ALLOW_MRKOLL`, `PIIFILTER_STRICT`, `COVE_THRESHOLD`, `AUTONOMOUS_CYCLE`, `PITCH_USE_PRO`, `EXPERIMENTAL_MAP_TILES`.

## Tradeoffs

- **Gains:** one page per concern, one scroll. Masked API keys + copy button is the low-friction right thing. Flag table surfaces default values and scope inline so you never need to dig into `.env` to remember what's on.
- **Costs:** long scroll — no anchor nav yet. At ~15 flags a table reads fine; at 40 it'll need search/filter.
- **Risks:** copy button next to masked keys invites "did it copy the full secret?" questions. Needs a visible confirmation state (briefly reveal? toast?) we haven't designed.

## Files touched

- `docs/ui-variants/pending/2026-04-21-installningar/mock.html`
- No `frontend/src/` files modified (mockup-only).

## New tokens (if any)

None.
