import { useEffect, useMemo, useState } from "react";
import { api, type PanelCatalogItem, type PanelStats } from "../api";
import DataField from "../components/DataField";
import { fromNullable } from "../lib/dataState";

const CONFIDENCE_OPTIONS: Array<{ value: number; label: string }> = [
  { value: 0.5, label: "50%+" },
  { value: 0.6, label: "60%+" },
  { value: 0.75, label: "75%+" },
  { value: 0.9, label: "90%+" },
];

function formatNumber(n: number): string {
  return n.toLocaleString("sv-SE");
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return d.toLocaleDateString("sv-SE", { day: "2-digit", month: "short", year: "numeric" });
}

export default function Panels() {
  const [items, setItems] = useState<PanelCatalogItem[]>([]);
  const [stats, setStats] = useState<PanelStats | null>(null);
  const [minConfidence, setMinConfidence] = useState(0.6);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;
    setLoading(true);
    (async () => {
      try {
        const [cat, s] = await Promise.all([api.panelCatalog(minConfidence), api.panelStats()]);
        if (!mounted) return;
        setItems(cat.items);
        setStats(s);
        setError(null);
      } catch (e) {
        if (mounted) setError(e instanceof Error ? e.message : "okänt fel");
      } finally {
        if (mounted) setLoading(false);
      }
    })();
    return () => {
      mounted = false;
    };
  }, [minConfidence]);

  const sorted = useMemo(
    () =>
      [...items].sort((a, b) => {
        const ac = a.panel_confidence ?? 0;
        const bc = b.panel_confidence ?? 0;
        return bc - ac;
      }),
    [items],
  );

  const xlsxHref = api.panelCatalogXlsxUrl(minConfidence);

  return (
    <section
      className="flex flex-col"
      style={{ height: "calc(100vh - 48px)", background: "var(--paper)" }}
    >
      <header
        className="flex items-center justify-between"
        style={{
          gap: 12,
          borderBottom: "1px solid var(--rule)",
          background: "var(--paper-tint)",
          padding: "16px 24px",
        }}
      >
        <div>
          <h2
            className="display"
            style={{
              fontFamily: "var(--font-display)",
              fontSize: "var(--t-h2)",
              color: "var(--ink)",
              margin: 0,
              letterSpacing: "var(--ls-tight)",
            }}
          >
            Panelägare
          </h2>
          <p
            className="caps tabular"
            style={{
              marginTop: 4,
              textTransform: "uppercase",
              letterSpacing: "var(--ls-wider)",
              fontSize: "var(--t-micro)",
              color: "var(--ink-60)",
            }}
          >
            Tak där detektion bekräftat solpaneler
          </p>
        </div>
        <div className="flex items-center" style={{ gap: 12 }}>
          <label
            className="caps tabular"
            style={{
              fontSize: "var(--t-micro)",
              color: "var(--ink-60)",
              letterSpacing: "var(--ls-wider)",
            }}
          >
            Konfidens
            <select
              value={minConfidence}
              onChange={(e) => setMinConfidence(Number(e.target.value))}
              style={{
                marginLeft: 8,
                padding: "4px 8px",
                border: "1px solid var(--rule)",
                background: "var(--paper)",
                color: "var(--ink)",
                borderRadius: "var(--r-2)",
                fontSize: "var(--t-small)",
              }}
            >
              {CONFIDENCE_OPTIONS.map((opt) => (
                <option key={opt.value} value={opt.value}>
                  {opt.label}
                </option>
              ))}
            </select>
          </label>
          <a
            href={xlsxHref}
            download
            style={{
              padding: "8px 14px",
              background: "var(--amber)",
              color: "var(--ink)",
              borderRadius: "var(--r-2)",
              fontSize: "var(--t-small)",
              fontWeight: 500,
              textDecoration: "none",
              border: "1px solid var(--ink)",
            }}
          >
            Ladda ner Excel
          </a>
        </div>
      </header>

      {stats && (
        <section
          aria-label="Översikt"
          style={{
            display: "grid",
            gridTemplateColumns: "repeat(3, 1fr)",
            borderBottom: "1px solid var(--rule)",
            background: "var(--paper)",
          }}
        >
          <StatCell label="Panelägare totalt" value={formatNumber(stats.total_panel_owners)} />
          <StatCell
            label="Hög konfidens (≥75%)"
            value={formatNumber(stats.high_confidence)}
            borderLeft
          />
          <StatCell
            label="Kontakt berikad"
            value={formatNumber(stats.contact_enriched)}
            borderLeft
          />
        </section>
      )}

      {error && (
        <div
          style={{
            margin: "16px 24px",
            padding: 12,
            border: "1px solid var(--barn)",
            background: "var(--paper)",
            borderRadius: "var(--r-2)",
            color: "var(--barn)",
            fontSize: "var(--t-small)",
          }}
        >
          Kunde inte ladda paneldata: {error}
        </div>
      )}

      <div style={{ flex: 1, overflow: "auto" }}>
        {loading ? (
          <div
            className="caps"
            style={{
              padding: 40,
              textAlign: "center",
              color: "var(--ink-60)",
              fontSize: "var(--t-micro)",
              letterSpacing: "var(--ls-wider)",
            }}
          >
            Laddar…
          </div>
        ) : sorted.length === 0 ? (
          <EmptyState minConfidence={minConfidence} />
        ) : (
          <table
            className="tabular"
            style={{
              width: "100%",
              borderCollapse: "collapse",
              fontSize: "var(--t-small)",
            }}
          >
            <thead
              style={{
                position: "sticky",
                top: 0,
                background: "var(--paper-tint)",
                borderBottom: "1px solid var(--rule)",
              }}
            >
              <tr>
                <Th>Adress</Th>
                <Th>Ägare</Th>
                <Th align="right">Ålder</Th>
                <Th>Telefon</Th>
                <Th align="right">Konfidens</Th>
                <Th align="right">Score</Th>
                <Th align="right">kWh/år</Th>
                <Th>Status</Th>
                <Th>Detekterad</Th>
              </tr>
            </thead>
            <tbody>
              {sorted.map((row) => (
                <tr key={row.id} style={{ borderBottom: "1px solid var(--rule-soft)" }}>
                  <Td>{row.address}</Td>
                  <Td><DataField state={fromNullable(row.owner_name)} /></Td>
                  <Td align="right"><DataField state={fromNullable(row.owner_age)} /></Td>
                  <Td><DataField state={fromNullable(row.owner_phone)} /></Td>
                  <Td align="right">
                    <ConfidenceBadge value={row.panel_confidence} />
                  </Td>
                  <Td align="right">{row.score != null ? row.score.toFixed(1) : "—"}</Td>
                  <Td align="right">
                    {row.annual_kwh != null ? formatNumber(row.annual_kwh) : "—"}
                  </Td>
                  <Td>{row.status ?? "—"}</Td>
                  <Td>{formatDate(row.detected_at)}</Td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </section>
  );
}

function StatCell({
  label,
  value,
  borderLeft,
}: {
  label: string;
  value: string;
  borderLeft?: boolean;
}) {
  return (
    <div
      style={{
        padding: "20px 24px",
        borderLeft: borderLeft ? "1px solid var(--rule)" : "none",
      }}
    >
      <div
        className="caps tabular"
        style={{
          fontSize: "var(--t-micro)",
          letterSpacing: "var(--ls-wider)",
          color: "var(--ink-60)",
        }}
      >
        {label}
      </div>
      <div
        className="tabular"
        style={{
          marginTop: 6,
          fontSize: "var(--t-h2)",
          color: "var(--ink)",
          fontFamily: "var(--font-display)",
        }}
      >
        {value}
      </div>
    </div>
  );
}

function Th({ children, align }: { children: React.ReactNode; align?: "right" }) {
  return (
    <th
      scope="col"
      style={{
        padding: "10px 16px",
        textAlign: align ?? "left",
        textTransform: "uppercase",
        fontSize: "var(--t-micro)",
        letterSpacing: "var(--ls-wider)",
        color: "var(--ink-60)",
        fontWeight: 500,
      }}
    >
      {children}
    </th>
  );
}

function Td({ children, align }: { children: React.ReactNode; align?: "right" }) {
  return (
    <td
      style={{
        padding: "10px 16px",
        textAlign: align ?? "left",
        color: "var(--ink)",
        verticalAlign: "middle",
      }}
    >
      {children}
    </td>
  );
}

function ConfidenceBadge({ value }: { value: number | null }) {
  if (value == null) return <span style={{ color: "var(--ink-60)" }}>—</span>;
  const pct = Math.round(value * 100);
  const color = pct >= 90 ? "var(--forest)" : pct >= 75 ? "var(--amber)" : "var(--ink-60)";
  return (
    <span
      className="tabular"
      style={{
        fontWeight: 500,
        color,
      }}
    >
      {pct}%
    </span>
  );
}

function EmptyState({ minConfidence }: { minConfidence: number }) {
  return (
    <div
      style={{
        padding: "48px 24px",
        textAlign: "center",
        color: "var(--ink-60)",
      }}
    >
      <div
        className="caps tabular"
        style={{
          fontSize: "var(--t-micro)",
          letterSpacing: "var(--ls-wider)",
          marginBottom: 8,
        }}
      >
        Inga panelägare hittade
      </div>
      <div style={{ fontSize: "var(--t-small)", maxWidth: "48ch", margin: "0 auto" }}>
        Inga tak med ≥ {Math.round(minConfidence * 100)}% konfidens har detekterats ännu. Kör
        paneldetektion på nya prospekt, eller sänk konfidens-tröskeln.
      </div>
    </div>
  );
}
