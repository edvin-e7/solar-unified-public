# Dashboard — Action-first (Workbench)

**Page:** Dashboard
**Status:** pending
**Generated:** 2026-04-21 by claude

## What's different

Inverts the hierarchy: metrics shrink, tasks grow. Three large CTA cards ("Klistra in adresser", "Kör detektion", "Visa toppprospekt") occupy the primary column as full-bleed interactive blocks with amber hairline borders and implicit hover affordance. Secondary column shows a compact "På gång" strip (today's KPI deltas only — new prospekt, berikade, detekterade). Agent status is demoted to a footer strip of 5 status dots with last-run timestamps. Designed for daily operators whose first thought on landing is "what do I do next" not "what are the numbers".

## Tradeoffs

- **Gains:** zero-friction entry into the three most common workflows, reduces the "where do I click" hunt, embraces that Dashboard is a launch pad not a report
- **Costs:** at-a-glance metrics suffer — no chart, no trends, just today's deltas; observers (non-operators) get less value; agent visibility reduced
- **Risks:** CTA cards need to deep-link correctly into the relevant pages (Prospekt, Detektion, Prospekt?sort=score) — broken links here are especially visible; hover states must feel responsive or the cards read as decorative

## Files touched

- `frontend/src/pages/Dashboard.tsx`
- `frontend/src/components/dashboard/ActionCard.tsx` (new — large CTA block)
- `frontend/src/components/dashboard/TodayStrip.tsx` (new — compact delta row)
- `frontend/src/components/dashboard/AgentDotStrip.tsx` (new — footer status)

## New tokens (if any)

None. Uses `--amber` for CTA hairlines and hover fill, `--forest`/`--barn` for agent status dots, `--ink-60` for metadata. Azure NOT used on content.

## Polish pass 2026-04-21

- Sidebar rebuilt: warm near-black `#1a1a24` bg, 1px right edge, fixed 248px width, scroll-safe column with pinned head + bottom chip.
- Brand block: inline SVG sun-over-roof logo + 16px serif wordmark in `#f2ece0`; "PROSPECT AGENT SYSTEM" tagline 10px/0.12em in muted white; new "WORKSPACE" section label above nav.
- Nav items: replaced emoji/ascii glyphs with Lucide-style inline stroke SVGs (16×16, 1.5px, currentColor) for Dashboard/Prospekt/Sök/Detektion/Karta/Agenter/Berikning/Inställningar; 36px rows, 14px/450 labels, 120ms hover transition, `aria-current="page"` on active.
- Active state reworked: no filled pill — 2px amber left bar + subtle row tint + amber icon + `#f2ece0` label. Bottom user chip (EP avatar in amber + name + email + chevron-up), `v0.1.0` demoted to centered muted line beneath.
- Type system upgraded: `GT Alpina/Playfair` for display, `Inter` for body, global `font-feature-settings: 'tnum','ss01','cv11'`; greeting trimmed to 32px/400; lede at 16px/1.6 max-width 62ch.
- KPI strip: numbers bumped to 32px tabular 500 in amber, per-cell vertical rule hairlines, new trend microline per cell ("+8 jfr ons" etc) at 11px `--ink-60`.
- Numbered step cards: eyebrow 10px/0.14em amber; H2 reduced to 22px serif/400; body 60ch `--ink-80` 1.55; kbd hints now individual `<kbd>` chips (11px mono, `--paper-tint` bg, 1px rule, 2px radius); arrow CTA swapped to Lucide `arrow-right` SVG with slide-on-hover transform.
- Right rail polish: 20px padding, 4px radius, no shadows; live badge = 6px forest dot + 9px uppercase text (no pill); timestamps tabular 12px right-aligned; topp-3 scores tabular 14px with row hover tint; "Öppna Agenter" footer link now azure underlined with inline arrow SVG.
- Spacing locked to 4px base: 40px page gutter, 48px section gap, 24px card gap; focus ring standard 2px azure outline with 2px offset on all interactives; `aria-label`s added to aside, user chip, icon-only link.

## Motion

All transitions use `cubic-bezier(0.2, 0.8, 0.2, 1)` unless noted. Every motion respects `@media (prefers-reduced-motion: reduce)` (disabled except the focus ring).

| Element | Trigger | Duration | Property |
| --- | --- | --- | --- |
| `.greet` | page load (`body.loaded`) | 240ms @ 0ms | opacity + translateY(4px→0) |
| `.lede` | page load | 240ms @ 30ms | opacity + translateY |
| `.today` (KPI strip) | page load | 240ms @ 60ms | opacity + translateY |
| `.cta-wrap` (step cards) | page load | 240ms @ 90ms | opacity + translateY |
| `.side` (right rail) | page load | 240ms @ 120ms | opacity + translateY |
| `.agent-strip` | page load | 240ms @ 150ms | opacity + translateY |
| `.today .v` KPI number | page load | 600ms ease-out | text count-up 0→target (JS, tabular-num locked) |
| `.nav::before` active bar | nav click (`--active-top` var changes) | 180ms | top |
| `.nav a` background | hover | 120ms | background |
| `.nav a`, `.nav a svg` color | hover / active swap | 180ms | color (icon crossfade) |
| `.cta` border | hover | 120ms | border-color (--rule → --stone) |
| `.cta .arrow svg` | parent `.cta:hover` | 120ms | transform translateX(0 → 4px) |
| `.side-card li.is-live::after` dot | continuous | 2s loop | opacity 1 → 0.4 → 1 |
| `.side-card li` row bg | hover | 80ms | background (→ --paper-tint) |
| `:focus-visible` ring | focus | 100ms | outline-width + outline-offset |

## Responsive behavior

Single mock.html, cascade-based responsive with `max-width` + `min-width` queries over the desktop base.

- **≤767px (iPhone SE / phone, base 375px):** sidebar hidden; fixed 56px `.bottom-nav` at the bottom (Dashboard, Prospekt, Sök, Agenter, Inställningar — 5 items). Sticky 52px `.mobile-top` with hamburger (`<details>`) on the left revealing Detektion, Karta, Berikning, Inställningar; "Edvin Solar" centered; avatar right. No ⌘K pill. Greeting 22px. KPIs 2×2. Step cards full-width stack, 20px padding, no right rail beside them; right rail stacks below. Agent strip wraps. Main padding 16px horizontal + 72px bottom (bottom-nav clearance). Active bottom-nav item: amber dot above icon + amber label — no left-bar accent. Minimum touch target 44×44 on all `.cta`, `.bn-item`, `.m-menu-panel a`, `.side-card li`.
- **768px–1023px (iPad portrait):** sidebar collapses to 56px icon-only rail; nav labels hidden, re-appear as paper-bg tooltip (1px --rule, 11px, 120ms opacity fade) on hover or keyboard focus. `.sb-user` shows avatar only; email/name/chevron/version hidden. KPIs 2×2. Step cards full-width, right rail stacks below (flex-row wrapped for two side-cards side by side if width allows). Page gutter 24px.
- **1024px–1439px (iPad landscape / small desktop):** full 248px sidebar returns. KPIs 4×1. Step cards full-width, right rail below them (row-wrapped). Page gutter 32px.
- **1440px+ (desktop, base):** current layout — step cards + right rail (296px) side-by-side; 40px gutter.

All breakpoints: focus rings preserved, Swedish copy unchanged, `font-variant-numeric: tabular-nums` on all numeric cells. No hamburger ≥1024px (it's hidden because `.mobile-top` is `display:none` outside the ≤767px query).
