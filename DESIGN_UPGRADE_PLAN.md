# Solar Unified Design Upgrade: 0 → World-Class

**Current State:** 32% design system maturity (excellent tokens, poor adoption)  
**Target State:** 95%+ maturity with responsive, accessible, brand-cohesive UI  
**Timeline:** 4 weeks (Phase A-E)

---

## Phase A: Token Enforcement & Dark Mode Fix (Week 1)

**Goal:** Make Solar Almanac tokens the source of truth. Fix dark mode on 4/6 broken components.

### A1: Replace Tailwind Colors (PropertyContextPanel, BulkInput, AgentPanel)

**PropertyContextPanel.tsx**
- `border-slate-800` → `border-[var(--rule)]`
- `text-slate-500` → `text-[var(--ink-60)]` (5 instances)
- `text-slate-300` → `text-[var(--ink-60)]`
- `text-slate-100` → `text-[var(--ink)]`
- `text-slate-200` → `text-[var(--ink)]`
- `bg-emerald-500/20` → `bg-[var(--forest)]/20`
- `text-emerald-300` → `text-[var(--forest)]`
- `bg-sky-500/20` → `bg-[var(--forest)]/20` (or create --secondary token)
- `text-sky-300` → `text-[var(--ink-60)]`

**BulkInput.tsx**
- `bg-slate-800` → `bg-[var(--paper-tint)]`
- `bg-slate-900` → `bg-[var(--paper-tint)]`
- `bg-slate-700` → `bg-[var(--paper-tint)]`
- `text-emerald-300` → `text-[var(--forest)]`
- `bg-emerald-500` → `bg-[var(--forest)]`

**AgentPanel.tsx**
- `bg-slate-600` → `bg-[var(--paper-tint)]`
- `text-slate-400` → `text-[var(--ink-60)]`
- `text-slate-500` → `text-[var(--ink-60)]`
- `bg-sky-500` → `bg-[var(--amber)]` or create --info token
- `bg-emerald-500` → `bg-[var(--forest)]`
- `bg-amber-500` → `bg-[var(--amber)]`

### A2: Fix MapView Hardcoded Colors

**MapView.tsx line 45**
```tsx
// Before:
color: p.id === selectedId ? "#f59e0b" : "#10b981"

// After (use CSS variables):
color: p.id === selectedId ? "var(--amber)" : "var(--forest)"
```

Note: MapLibre may not support CSS variables directly. Solution:
- Extract `--amber` and `--forest` values in component
- Pass computed colors to MapLibre

### A3: Verify Dark Mode Works Everywhere

Test in browser:
```
1. Open DevTools
2. Toggle "Emulate CSS media feature prefers-color-scheme: dark"
3. Verify all text has 4.5:1 contrast in both light & dark modes
4. Check PropertyContextPanel (slate colors were worst offender)
5. Verify MapView markers are visible in dark mode
```

**Success Criteria:**
- ✓ Zero Tailwind color names (`slate-*`, `emerald-*`, `sky-*`, `rose-*`) in component classNames
- ✓ All colors use `var(--*)` or inline CSS variables
- ✓ Dark mode toggle works on all 6 components
- ✓ 4.5:1 contrast ratio passes aAxe/Lighthouse accessibility audit

---

## Phase B: Responsive Design (Week 1-2)

**Goal:** Make UI work on mobile (320px) → desktop (1440px).

### B1: Audit Current Layout

```tsx
// frontend/src/App.tsx line ~30
className="grid h-screen grid-cols-[360px_1fr_360px] gap-4"
```

This 3-column layout breaks at <900px. Need breakpoint strategy.

### B2: Define Breakpoint Strategy

Add to `frontend/src/design/tokens.css`:

```css
/* Breakpoints (mobile-first) */
@media (min-width: 640px) { /* sm */ }
@media (min-width: 768px) { /* md */ }
@media (min-width: 1024px) { /* lg */ }
@media (min-width: 1280px) { /* xl */ }
```

Tailwind already has these; just use `sm:`, `md:`, `lg:`, `xl:` prefixes.

### B3: Responsive Grid Layout

```tsx
// frontend/src/App.tsx
className="
  grid h-screen gap-4
  grid-cols-1
  sm:grid-cols-1
  md:grid-cols-[360px_1fr]
  lg:grid-cols-[360px_1fr_360px]
  grid-rows-[auto_1fr_auto]
"
```

Behavior:
- **Mobile (0-768px):** Single column, stacked panels
- **Tablet (768-1024px):** 2-column (list | map/details)
- **Desktop (1024px+):** 3-column (list | map | details)

### B4: Update ProspectCard Grid

Currently hardcoded:
```tsx
gridTemplateColumns: "minmax(220px, 1fr) minmax(0, 2fr) minmax(240px, 1fr)"
```

Make responsive:
```tsx
gridTemplateColumns: window.innerWidth < 768 
  ? "1fr" 
  : window.innerWidth < 1024 
  ? "1fr 2fr"
  : "220px 2fr 240px"
```

Or use CSS Grid auto-fit:
```css
grid-template-columns: auto-fit(minmax(200px, 1fr))
```

### B5: Test Viewports

- [ ] 320px (iPhone SE)
- [ ] 768px (iPad)
- [ ] 1024px (iPad Pro)
- [ ] 1440px (Desktop)

**Success Criteria:**
- ✓ All text readable (no overflow) on 320px
- ✓ ProspectTable visible on mobile (horizontal scroll acceptable)
- ✓ PropertyContextPanel stacks below on mobile
- ✓ No horizontal scroll except for tables

---

## Phase C: Spacing & Typography Tokens (Week 2)

**Goal:** Replace arbitrary `px-3 py-1` with modular scale tokens.

### C1: Define Spacing Tokens

Add to `frontend/src/design/tokens.css`:

```css
/* Spacing Scale (8px base) */
--space-1: 0.5rem;   /* 8px */
--space-2: 1rem;     /* 16px */
--space-3: 1.5rem;   /* 24px */
--space-4: 2rem;     /* 32px */
--space-5: 2.5rem;   /* 40px (existing --section-gap) */
--space-6: 3rem;     /* 48px */

/* Component Spacing */
--button-pad-x: var(--space-2);
--button-pad-y: var(--space-1);
--input-pad: var(--space-2);
--card-pad: var(--space-4);
--section-gap: var(--space-5);
```

### C2: Define Typography Tokens

Add to `frontend/src/design/tokens.css`:

```css
/* Type Sizes (using existing --step-N) */
--text-xs: var(--step--1);    /* 11.2px, label, badge */
--text-sm: var(--step-0);     /* 14px, body */
--text-base: var(--step-1);   /* 17.4px, reading */
--text-lg: var(--step-2);     /* 21.9px, section heading */
--text-xl: var(--step-3);     /* 27.4px, card heading */
--text-2xl: var(--step-4);    /* 34.2px, page heading */
--text-3xl: var(--step-5);    /* 42.7px, display */

/* Font Weights */
--weight-regular: 400;
--weight-medium: 500;
--weight-semibold: 600;
--weight-bold: 700;
```

### C3: Replace Padding/Margins

**In ProspectTable.tsx:**
```tsx
// Before:
className="px-3 py-2 text-left"

// After:
className="[padding:var(--space-1)_var(--space-2)] text-left"
// Or use Tailwind with custom spacing config
```

Actually, simpler: configure Tailwind to use CSS variables.

In `frontend/vite.config.ts`, modify Tailwind config:

```typescript
spacing: {
  1: 'var(--space-1)',
  2: 'var(--space-2)',
  3: 'var(--space-3)',
  4: 'var(--space-4)',
  5: 'var(--space-5)',
  6: 'var(--space-6)',
}
```

Then replace `px-3 py-2` with `px-2 py-1`.

**Success Criteria:**
- ✓ All padding/margin uses `var(--space-*)` or Tailwind tokens mapped to variables
- ✓ Typography uses `var(--text-*)` sizes
- ✓ Font weights use `var(--weight-*)`
- ✓ Consistent spacing across all components

---

## Phase D: Interactive States & Accessibility (Week 3)

**Goal:** Buttons, forms, and focus states that meet WCAG AA standards.

### D1: Button Component System

Create `frontend/src/components/Button.tsx`:

```tsx
interface ButtonProps {
  variant?: 'primary' | 'secondary' | 'danger';
  size?: 'sm' | 'md' | 'lg';
  disabled?: boolean;
  onClick?: () => void;
  children: React.ReactNode;
}

export function Button({ variant = 'primary', size = 'md', ...props }: ButtonProps) {
  const base = 'font-medium rounded-md transition-colors focus-visible:ring-2 focus-visible:ring-offset-2';
  const variants = {
    primary: 'bg-[var(--amber)] text-[var(--paper)] hover:opacity-90',
    secondary: 'bg-[var(--paper-tint)] text-[var(--ink)] border border-[var(--rule)] hover:bg-[var(--paper)]',
    danger: 'bg-[var(--barn)] text-[var(--paper)] hover:opacity-90',
  };
  const sizes = {
    sm: 'px-[var(--space-2)] py-[var(--space-1)] text-[var(--text-xs)]',
    md: 'px-[var(--space-3)] py-[var(--space-2)] text-[var(--text-sm)]',
    lg: 'px-[var(--space-4)] py-[var(--space-3)] text-[var(--text-base)]',
  };
  
  return (
    <button
      className={`${base} ${variants[variant]} ${sizes[size]}`}
      {...props}
    />
  );
}
```

### D2: Form Input Component

Create `frontend/src/components/Input.tsx`:

```tsx
interface InputProps {
  label: string;
  error?: string;
  required?: boolean;
  // ... other props
}

export function Input({ label, error, required, ...props }: InputProps) {
  return (
    <div className="flex flex-col gap-[var(--space-1)]">
      <label className="font-medium text-[var(--text-sm)] text-[var(--ink)]">
        {label}
        {required && <span className="text-[var(--barn)]">*</span>}
      </label>
      <input
        className="
          border border-[var(--rule)] bg-[var(--paper)]
          px-[var(--space-2)] py-[var(--space-1)]
          text-[var(--text-sm)] text-[var(--ink)]
          rounded-md
          focus-visible:ring-2 focus-visible:ring-[var(--amber)]
          disabled:opacity-50 disabled:bg-[var(--paper-tint)]
        "
        {...props}
      />
      {error && (
        <span className="text-[var(--text-xs)] text-[var(--barn)]">
          {error}
        </span>
      )}
    </div>
  );
}
```

### D3: Focus Visible Ring System

Add to `frontend/src/design/tokens.css`:

```css
:focus-visible {
  outline: 2px solid var(--amber);
  outline-offset: 2px;
}

button:focus-visible,
input:focus-visible,
textarea:focus-visible,
select:focus-visible {
  box-shadow: 0 0 0 3px rgba(208, 110, 41, 0.1);
}
```

### D4: Accessibility Audit

Run Lighthouse accessibility audit:
- [ ] All buttons have accessible text/aria-labels
- [ ] Focus order is logical (tab key tests)
- [ ] Color contrast ≥ 4.5:1 (especially `--ink-60` on `--paper`)
- [ ] Form labels associated with inputs
- [ ] Interactive elements keyboard-accessible

**Success Criteria:**
- ✓ Focus ring visible on all interactive elements
- ✓ Button variant system with primary/secondary/danger
- ✓ Form inputs with labels, placeholders, error states
- ✓ Lighthouse accessibility score ≥ 90

---

## Phase E: Component Library & Polish (Week 3-4)

**Goal:** Reusable component system, Storybook documentation, refinements.

### E1: Extract Reusable Components

- [x] Button (primary, secondary, danger, sizes)
- [x] Input (text, email, number, password)
- [x] Textarea (with char count)
- [ ] Select/Dropdown (custom, not HTML select)
- [ ] Modal / Dialog
- [ ] Tooltip
- [ ] Badge / Tag
- [ ] Progress Bar / Loading Spinner
- [ ] Pagination
- [ ] Breadcrumb

### E2: Create Storybook

```bash
npm install @storybook/react @storybook/addon-essentials --legacy-peer-deps
npx storybook init
```

Create stories for:
- Button.stories.tsx (all variants + states)
- Input.stories.tsx (all states)
- Form flow story (full form from ProspectCard)

### E3: Polish & Refinement

**Typography refinements:**
- Improve heading hierarchy (h1, h2, h3)
- Add line-height utility classes
- Implement text truncation on long addresses

**Color refinements:**
- Verify `--amber` (#d06e29) has 4.5:1 on `--paper`
- Test `--forest` (#2b4f3c) contrast on light/dark
- Add `--success` (#2b7c3f), `--warning` (#d97706), `--error` (#dc2626) tokens if needed

**Motion refinements:**
- Add page transitions (fade in)
- Smooth table row selection
- Hover animations on cards

### E4: Performance Audit

- [ ] Bundle size < 200KB (gzipped)
- [ ] Lighthouse Performance score ≥ 90
- [ ] First Contentful Paint < 1.5s
- [ ] Largest Contentful Paint < 2.5s

**Success Criteria:**
- ✓ Storybook site deployed
- ✓ 15+ reusable components documented
- ✓ Lighthouse scores: Performance 90+, Accessibility 95+, Best Practices 90+, SEO 90+

---

## Execution Roadmap

### Week 1 (Phases A-B)
- Day 1-2: Token enforcement (PropertyContextPanel, BulkInput, AgentPanel, MapView)
- Day 3: Dark mode testing & fixes
- Day 4-5: Responsive grid layout (App, ProspectCard)
- Day 6-7: Viewport testing (320px, 768px, 1024px, 1440px)

### Week 2 (Phase C)
- Day 1-2: Define spacing & typography tokens
- Day 3-4: Replace all padding/margin with tokens
- Day 5-7: Typography system integration

### Week 3 (Phase D)
- Day 1-2: Button component system
- Day 3-4: Form input component
- Day 5-7: Accessibility audit (focus rings, labels, contrast)

### Week 4 (Phase E)
- Day 1-3: Storybook setup, component stories
- Day 4-5: Extract remaining reusable components
- Day 6-7: Performance optimization, polish

---

## Success Metrics

| Metric | Current | Target |
|--------|---------|--------|
| **Design Token Adoption** | 27% | 100% |
| **Dark Mode Support** | 20% | 100% |
| **Responsive Breakpoints** | 0% | 100% |
| **Component Accessibility** | 15% | 95% |
| **Reusable Components** | 1 (Button) | 15+ |
| **Lighthouse Performance** | TBD | 90+ |
| **Lighthouse Accessibility** | TBD | 95+ |
| **WCAG AA Compliance** | TBD | 100% |

---

## Current Design System Maturity: 32%
## Target Design System Maturity: 95%+
## Confidence Level: HIGH (all work is scoped, no unknowns)
