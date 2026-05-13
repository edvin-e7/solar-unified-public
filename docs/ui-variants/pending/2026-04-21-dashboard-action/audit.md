# Icon audit — 2026-04-21 dashboard mock

Every mark in the file is already inline SVG (no `<img>`, no icon fonts, no emoji). Issues are in stroke weights, path authenticity, and a handful of non-canonical Lucide shapes.

| Location | Current icon | Issue | Fix |
| --- | --- | --- | --- |
| Sidebar brand `.sb-logo` | Custom sun-over-roof mark (filled shapes) | Not an icon — it is the brand logo. Fill, not stroke. | Leave as-is (out of scope). |
| Nav `#dashboard` | 4-rect composite | Not canonical Lucide. Close to `layout-dashboard` but incorrect rects. | Replace with real `layout-dashboard` paths. |
| Nav `#prospekt` | 2-person `users` variant | Canonical Lucide `users`, OK. | Keep; just confirm stroke 1.5 + linecap/linejoin round (already set by CSS). |
| Nav `#sok` | Magnifying glass | Canonical `search`, OK. | Keep. |
| Nav `#detektion` | Corner frame + inner ring + dot | Hand-rolled, not Lucide. | Replace with `scan-search` paths. |
| Nav `#karta` | 3-panel folded map | Canonical `map`, OK. | Keep. |
| Nav `#agenter` | Bot-ish rect with antenna + eyes + mouth | Not clean Lucide `bot` (has extra `<path d="M2 14h2"/>` ears). | Replace with real `bot` paths. |
| Nav `#berikning` | 3 sparkles | Rough `sparkles` but paths are not canonical. | Replace with real `sparkles`. |
| Nav `#installningar` | Gear | Canonical `settings`, OK. | Keep. |
| Sidebar user chip `.sb-chev` | Chevron-up | OK shape, stroke 1.5 correct. | Keep. |
| CTA card 1 arrow | Arrow-right (2 paths) | `stroke-width: 1.75` in CSS — brief mandates 1.5. Size 16×16 — brief mandates 20×20 for CTA arrows. | Stroke 1.5 + 20×20. |
| CTA card 2 arrow | Arrow-right | Same 1.75 + 16×16 issue. | Stroke 1.5 + 20×20. |
| CTA card 3 arrow | Arrow-right | Same 1.75 + 16×16 issue. | Stroke 1.5 + 20×20. |
| Agent footer link arrow | Arrow-right | `stroke-width: 1.75`, 12×12. | Stroke 1.5, keep small (inline text arrow, not a CTA) — reduce to 14×14 `currentColor`. |
| Side-card "live" dot | CSS `::before` 6px circle | Pure CSS, not an icon. Meaning is the label. | Keep. |

## New additions (empty-state illustrations)

Both 64×64 viewBox, stroke 1.5, `currentColor` for the main silhouette, `var(--amber)` on a single accent dot only. Stored as inert `<template>` elements at the bottom of the file so a future component can clone them.

- `illo-tomt-prospekt` — minimalist house outline (square + triangular roof), pending dot hovering above the roof peak in amber.
- `illo-vantar-svar` — minimalist bird silhouette (one continuous path: body + beak + tail), small amber "speech" dot to the upper right of the beak.
