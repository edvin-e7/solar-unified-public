# Dashboard — Premium (Linear-grade)

**Page:** Dashboard
**Status:** pending
**Generated:** 2026-04-21 by Claude (Opus 4.7)

## What's different

Total aesthetic replacement. Drops Solar Almanac paper/amber theme for Linear-grade neutrals with a single blue accent. Dark-first with light toggle. Production-polish reference — the single design idea is *vendor-grade restraint*: monochrome surfaces, 1px hairlines, tabular numerals, generous negative space, and exactly one accent hue reserved for interactive affordance. Nothing decorative, no warmth, no folk character. Every number is data, every border is 1px, every card is flat.

## Tradeoffs

- **Gains:** professional enterprise feel, data density without noise, vendor-grade polish (Linear/Vercel/Stripe), better legibility for numbers, dark mode done properly, unambiguous status semantics.
- **Costs:** warmth and brand distinctiveness are gone — looks like every other SaaS dashboard. No Swedish folk-domain character. The interface now competes on craft rather than identity.
- **Risks:** loss of the Swedish folk-domain character the user earlier valued; the product becomes visually indistinguishable from any B2B SaaS; blue accent is the single most overused color in dashboards, so we lean on execution rather than concept.

## Files touched (aspirational, if approved)

- `frontend/src/design/tokens.css` — full replacement of palette, type, spacing
- `frontend/src/components/Sidebar.tsx` — 240px rail, thin separators, kbd hints, status dot footer
- `frontend/src/components/AppShell.tsx` — 48px top bar with breadcrumb, ⌘K, theme toggle, bell, avatar
- `frontend/src/components/KpiTile.tsx` — tabular-num value, inline sparkline, semantic trend arrow
- `frontend/src/components/BarChart.tsx` — SVG gridlines, axis ticks, floating tooltip
- `frontend/src/components/StatusDot.tsx` — colored dot + plain text (no filled pills anywhere)
- `frontend/src/pages/DashboardPage.tsx` — new page layout (KPIs → chart+activity → table → insight+upcoming)
- `frontend/src/pages/*.tsx` — all other pages inherit new tokens automatically
- `frontend/index.html` — `<html data-theme="dark">` default
- `frontend/src/design/typography.css` — Inter + `font-feature-settings: "tnum", "ss01", "cv11"` on body

## New tokens (tokens.css — full replacement)

```css
:root[data-theme="light"] {
  --bg: #fafafa;
  --surface: #ffffff;
  --surface-2: #f5f5f5;
  --border: #e6e6e6;
  --border-strong: #d4d4d4;
  --text: #111111;
  --text-2: #525252;
  --text-3: #8a8a8a;
  --accent: #2563eb;
  --success: #16a34a;
  --warn: #ea580c;
  --danger: #dc2626;
}

:root[data-theme="dark"] {
  --bg: #0a0a0a;
  --surface: #121212;
  --surface-2: #1a1a1a;
  --border: #222222;
  --border-strong: #2e2e2e;
  --text: #fafafa;
  --text-2: #a3a3a3;
  --text-3: #6b6b6b;
  --accent: #3b82f6;
  --success: #22c55e;
  --warn: #f97316;
  --danger: #ef4444;
}
```

Type stack: `"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", Roboto, sans-serif` with `font-feature-settings: "tnum", "ss01", "cv11"` on `body`. Mono: `"JetBrains Mono", ui-monospace, "SF Mono", Menlo, Consolas, monospace` for IDs, timestamps, cron strings.

Spacing: 4px base. Card padding 20px. Page gutter 32px. Grid gap 16px. Radius 5–6px max (never rounded-xl). Borders exactly 1px solid `--border`. Shadows only on floating elements (tooltip, dropdown) — never on static cards.

Status semantics: colored dot + plain text, never a filled pill. Trend arrows colored only when direction matches meaning (up=good → success; down=bad → danger); neutral deltas stay `text-2`.

Agent-type dots: neutral grays at varying lightness, not additional hues — blue remains the single accent.
