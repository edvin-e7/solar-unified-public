import type { Prospect } from "../api";
import DataField from "./DataField";
import { fromNullable } from "../lib/dataState";

/** Solar Almanac — one prospect rendered as an almanac entry, not a table row. */

interface Props {
  prospect: Prospect;
  index: number;
  pitch?: string | null;
  onCall?: () => void;
  onNote?: () => void;
  onExport?: () => void;
}

const STATUS_LABEL: Record<string, string> = {
  new: "Ny",
  interested: "Intresserad",
  callback: "Återkom",
  rejected: "Avböjt",
};

const STATUS_INK: Record<string, string> = {
  new: "var(--ink-60)",
  interested: "var(--forest)",
  callback: "var(--leaf)",
  rejected: "var(--barn)",
};

export default function ProspectCard({ prospect, index, pitch, onCall, onNote, onExport }: Props) {
  const kwh = prospect.annual_kwh ? Math.round(prospect.annual_kwh) : null;
  const sek = kwh ? kwh * 2 : null;
  const score = prospect.score ?? null;

  return (
    <article
      className="grid gap-8 p-8"
      style={{
        background: "var(--paper)",
        borderTop: "var(--rule-weight) solid var(--ink)",
        gridTemplateColumns: "minmax(220px, 1fr) minmax(0, 2fr) minmax(240px, 1fr)",
      }}
    >
      {/* LEFT COLUMN — entry heading, owner, marginalia */}
      <header className="flex flex-col gap-4">
        <div className="flex items-baseline gap-3">
          <span
            className="display tabular"
            style={{ fontSize: "var(--step-5)", color: "var(--amber)" }}
          >
            {toRoman(index)}
          </span>
          <span className="caps">Nr.&nbsp;{index}</span>
        </div>

        <h2 className="display" style={{ fontSize: "var(--step-3)" }}>
          {prospect.address}
        </h2>

        <hr className="rule" />

        <dl className="grid grid-cols-[auto_1fr] gap-x-4 gap-y-1" style={{ fontSize: "var(--step-0)" }}>
          <dt className="caps">Ägare</dt>
          <dd><DataField state={fromNullable(prospect.owner_name)} /></dd>
          <dt className="caps">Ålder</dt>
          <dd className="tabular"><DataField state={fromNullable(prospect.owner_age)} /></dd>
          <dt className="caps">Telefon</dt>
          <dd className="tabular"><DataField state={fromNullable(prospect.owner_phone)} /></dd>
          <dt className="caps">Status</dt>
          <dd style={{ color: STATUS_INK[prospect.status ?? "new"] }}>
            {STATUS_LABEL[prospect.status ?? "new"] ?? prospect.status}
          </dd>
        </dl>

        <div className="mt-4 flex flex-wrap gap-2">
          <ActionButton onClick={onCall} primary>Ring</ActionButton>
          <ActionButton onClick={onNote}>Notera</ActionButton>
          <ActionButton onClick={onExport}>PDF</ActionButton>
        </div>
      </header>

      {/* CENTER COLUMN — arc meter + data */}
      <section className="flex items-start gap-8">
        <ArcMeter value={score ?? 0} max={10} label="Score" />

        <div className="flex flex-col gap-6">
          <Metric label="Årsproduktion" value={kwh ? kwh.toLocaleString("sv-SE") : "—"} unit="kWh" />
          <Metric label="Årsbesparing" value={sek ? sek.toLocaleString("sv-SE") : "—"} unit="kr" />
          <Metric label="Skuggrisk" value="låg" unit="" muted />
        </div>
      </section>

      {/* RIGHT COLUMN — marginal annotations + ringöppnare */}
      <aside
        className="flex flex-col gap-4 pl-8"
        style={{ borderLeft: "var(--rule-weight) solid var(--rule)" }}
      >
        <span className="caps">Ringöppnare</span>
        <p
          className="display italic"
          style={{ fontSize: "var(--step-1)", lineHeight: 1.45, color: "var(--ink)" }}
        >
          {pitch ? `"${pitch}"` : <span className="caps" style={{ letterSpacing: "0.14em" }}>ingen pitch genererad</span>}
        </p>
        <hr className="rule" />
        <span className="caps">Anteckning i marginal</span>
        <p style={{ color: "var(--ink-60)", fontSize: "var(--step--1)" }}>
          <DataField state={fromNullable(prospect.notes)} />
        </p>
      </aside>
    </article>
  );
}

function ActionButton({ onClick, primary, children }: { onClick?: () => void; primary?: boolean; children: React.ReactNode }) {
  return (
    <button
      onClick={onClick}
      className="caps transition-all"
      style={{
        padding: "0.55rem 1.1rem",
        border: primary ? "1px solid var(--ink)" : "1px solid var(--rule)",
        background: primary ? "var(--ink)" : "transparent",
        color: primary ? "var(--paper)" : "var(--ink)",
        transitionDuration: "var(--dur-snap)",
        transitionTimingFunction: "var(--ease-paper)",
      }}
    >
      {children}
    </button>
  );
}

function Metric({ label, value, unit, muted }: { label: string; value: string; unit: string; muted?: boolean }) {
  return (
    <div className="flex flex-col gap-1">
      <span className="caps">{label}</span>
      <div className="flex items-baseline gap-2">
        <span
          className="display tabular"
          style={{ fontSize: "var(--step-4)", color: muted ? "var(--ink-60)" : "var(--ink)" }}
        >
          {value}
        </span>
        <span className="caps">{unit}</span>
      </div>
    </div>
  );
}

function ArcMeter({ value, max, label }: { value: number; max: number; label: string }) {
  const pct = Math.min(1, Math.max(0, value / max));
  const size = 140;
  const r = 58;
  const c = 2 * Math.PI * r;
  const dashOffset = c * (1 - pct * 0.75); // 3/4 arc, like a sundial
  const rotation = -225; // start at SW, sweep to SE

  return (
    <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} aria-label={`${label}: ${value} av ${max}`}>
      <g transform={`translate(${size / 2} ${size / 2}) rotate(${rotation})`}>
        <circle r={r} fill="none" stroke="var(--rule)" strokeWidth="1" strokeDasharray={`${c * 0.75} ${c}`} />
        <circle
          r={r}
          fill="none"
          stroke="var(--amber)"
          strokeWidth="3"
          strokeLinecap="butt"
          strokeDasharray={`${c * 0.75} ${c}`}
          strokeDashoffset={dashOffset - c * 0.75 + c * 0.75 * (1 - pct)}
          style={{ transition: "stroke-dashoffset var(--dur-turn) var(--ease-paper)" }}
        />
      </g>
      <text
        x="50%"
        y="50%"
        textAnchor="middle"
        dominantBaseline="central"
        className="display tabular"
        style={{ fontSize: "var(--step-4)", fill: "var(--ink)", fontWeight: 500 }}
      >
        {value.toFixed(1)}
      </text>
      <text
        x="50%"
        y="75%"
        textAnchor="middle"
        className="caps"
        style={{ fontSize: "10px", fill: "var(--ink-60)" }}
      >
        {label}
      </text>
    </svg>
  );
}

function toRoman(num: number): string {
  const map: [number, string][] = [
    [1000, "M"], [900, "CM"], [500, "D"], [400, "CD"],
    [100, "C"], [90, "XC"], [50, "L"], [40, "XL"],
    [10, "X"], [9, "IX"], [5, "V"], [4, "IV"], [1, "I"],
  ];
  let result = "";
  let remaining = num;
  for (const [v, s] of map) {
    while (remaining >= v) {
      result += s;
      remaining -= v;
    }
  }
  return result;
}
