# Solar Almanac — Design Primitives

Paper-warm, ink-deep, amber-accented. Editorial restraint.

## Tokens

`src/design/tokens.css` is the source of truth. Use `var(--token)` in `style={}` or
Tailwind 4 `bg-(--token)` / `text-(--token)` syntax. Never hardcode hex.

Key families:

- **Paper**: `--paper`, `--paper-tint`, `--paper-deep`
- **Ink**: `--ink`, `--ink-80`, `--ink-60`, `--ink-40`, `--ink-20`
- **Accents**: `--amber`, `--forest`, `--leaf`, `--barn`, `--stone`, `--azure`
- **Surfaces**: `--warm-dark` (sidebar), `--rule`, `--rule-weight`
- **Status**: `--status-new-stone`, `--status-interested-forest`,
  `--status-callback-amber`, `--status-rejected-barn`
- **Spacing** (4px base): `--s-0` … `--s-16`
- **Radius**: `--r-0` … `--r-8`
- **Type**: `--font-display`, `--font-body`, `--font-mono`
- **Scale**: `--t-display-lg` (40), `--t-display` (32), `--t-h2` (22), `--t-h3` (16),
  `--t-body` (14), `--t-small` (12), `--t-micro` (10)
- **Letterspacing**: `--ls-tight`, `--ls-normal`, `--ls-wide`, `--ls-wider`
- **Motion**: `--ease-paper`, `--dur-snap`, `--dur-turn`

## Components

Import from `src/components/ui/<Name>`. All **named exports**, no defaults.

### `Sidebar` — primary nav shell (248px, warm-dark)

Slot: left rail. ArrowUp/ArrowDown cycles focus, Enter activates.

```tsx
import { Sidebar, type NavItem } from "./components/ui/Sidebar";

const items: NavItem[] = [
  { id: "dashboard", label: "Dashboard", icon: "layout-dashboard" },
  { id: "prospekt", label: "Prospekt", icon: "users" },
];

<Sidebar
  items={items}
  activeId="dashboard"
  onSelect={(id) => navigate(id)}
  user={{ name: "Edvin Pierre", email: "edvin@example.com", initials: "EP" }}
/>;
```

### `KpiTile` — single KPI cell inside a grid

Slot: dashboard top row. Parent grid draws dividers.

```tsx
import { KpiTile } from "./components/ui/KpiTile";

<KpiTile label="Nya idag" value="+23" trend={{ delta: "+8 jfr ons", direction: "up" }} />;
```

### `StepCard` — numbered action step

Slot: main CTA column on dashboard. 3px amber/forest/leaf left accent, arrow slides on hover.

```tsx
import { StepCard } from "./components/ui/StepCard";

<StepCard
  step={1}
  eyebrow="Vanligaste start"
  title="Klistra in adresser"
  body="Lägg till nya prospekt genom att klistra in en rå lista adresser."
  kbdHint={["Ctrl", "+", "V", "på Prospekt-sidan"]}
  ctaLabel="Öppna Prospekt"
  onCta={() => navigate("prospekt")}
/>;
```

### `EventList` — live event feed (right rail)

Slot: dashboard side panel. Shows "LIVE" chip if any event has `live: true`.

```tsx
import { EventList } from "./components/ui/EventList";

<EventList
  title="Senaste händelser"
  events={[
    { id: "1", label: "Sveagatan 12, Falun", time: "14:31", live: true },
    { id: "2", label: "CSV · 23 rader", time: "14:28" },
  ]}
/>;
```

### `Scoreboard` — top-N ranked list

Slot: dashboard side panel. Tabular scores right-aligned.

```tsx
import { Scoreboard } from "./components/ui/Scoreboard";

<Scoreboard
  title="Dagens topp 3"
  scoreLabel="score"
  rows={[
    { rank: 1, label: "Sveagatan 12, Falun", score: "9.4" },
    { rank: 2, label: "Kopparbergsv. 44, Borlänge", score: "9.1" },
  ]}
/>;
```

## Rules

1. No dark-slate. Paper + ink + amber sparingly.
2. Swedish UI strings, English code identifiers.
3. `:focus-visible` is globally styled — don't override without reason.
4. Tabular figures (`--font-body` with `font-variant-numeric: tabular-nums`) for
   any number that sits in a column.
5. No static shadows; `--shadow-hover` is reserved for hover affordance.
