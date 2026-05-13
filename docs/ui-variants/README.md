# UI Variants

Folder where UI-agent training runs drop design candidates. You browse, pick winners, and only the chosen variants feed back into the canonical design.

## Layout

```
docs/ui-variants/
├── README.md            # this file
├── _template/           # reference: shape every variant should follow
├── pending/             # agent drops new variants here
├── chosen/              # you move variants here = merge into main design
└── archived/            # rejected / superseded variants kept for reference
```

## Workflow

1. **Agent generates** → new folder in `pending/` named `YYYY-MM-DD-<slug>/`
2. **You review** → open `pending/<variant>/README.md` + screenshots
3. **Decide**:
   - Like it → `git mv pending/<variant> chosen/` and note in commit message which parts to merge
   - Discard → `git mv pending/<variant> archived/`
4. **Merge step** → plan task picks up everything in `chosen/` and applies to `frontend/src/**`

## Variant format

Each variant folder MUST contain:

- `README.md` — one paragraph: what's different about this variant, which page(s) it affects, what tradeoff it makes
- `before.png` / `after.png` — side-by-side screenshot or mock (or `mock.html` if no real render yet)
- `tokens.css` (optional) — any new design tokens the variant introduces
- `patch.diff` (optional) — unified diff against current `frontend/src/**` so merge is mechanical

See `_template/` for the reference shape. Copy-rename to start a new variant.

## Scope rules

- Variants target **one page at a time** (Dashboard, Prospekt, Sök, Detektion, Karta, Agenter, Berikning, Inställningar). Cross-page changes split into one variant per page.
- Variants stay within Solar Almanac tokens (`paper`, `ink`, `amber`, `forest`, `stone`, `barn`, `leaf`, `rule`, `azure`). A variant proposing new tokens must justify it in its README.
- No `bg-slate-*`. Non-negotiable.
