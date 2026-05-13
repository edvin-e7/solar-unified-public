import { useState } from "react";
import type { Prospect } from "../api";
import PropertyContextPanel from "./PropertyContextPanel";

interface Props {
  prospect: Prospect | null;
  onChange: () => void;
}

type Tab = "info" | "anteckningar" | "dokument";

const TABS: Array<{ id: Tab; label: string }> = [
  { id: "info", label: "Info" },
  { id: "anteckningar", label: "Anteckningar" },
  { id: "dokument", label: "Dokument" },
];

export function ProspectDetailTabs({ prospect, onChange }: Props) {
  const [active, setActive] = useState<Tab>("info");

  if (!prospect) {
    return (
      <div
        className="flex h-full items-center justify-center"
        style={{ padding: 32, color: "var(--ink-60)", fontSize: "var(--t-small)" }}
      >
        <span
          style={{
            textTransform: "uppercase",
            letterSpacing: "var(--ls-wider)",
            fontSize: "var(--t-micro)",
          }}
        >
          Välj ett prospekt
        </span>
      </div>
    );
  }

  return (
    <div className="flex h-full flex-col">
      <div
        role="tablist"
        aria-label="Detaljpanel"
        className="flex"
        style={{
          borderBottom: "1px solid var(--rule)",
          background: "var(--paper-tint)",
        }}
      >
        {TABS.map((t) => {
          const isActive = active === t.id;
          return (
            <button
              key={t.id}
              role="tab"
              aria-selected={isActive}
              aria-controls={`panel-${t.id}`}
              id={`tab-${t.id}`}
              onClick={() => setActive(t.id)}
              className="tabular"
              style={{
                flex: 1,
                padding: "10px 12px",
                fontSize: "var(--t-small)",
                letterSpacing: "var(--ls-tight)",
                color: isActive ? "var(--ink)" : "var(--ink-60)",
                background: "transparent",
                border: "none",
                borderBottom: isActive ? "2px solid var(--azure)" : "2px solid transparent",
                cursor: "pointer",
                transition: "color var(--dur-snap) var(--ease-paper)",
              }}
            >
              {t.label}
            </button>
          );
        })}
      </div>

      <div
        role="tabpanel"
        id={`panel-${active}`}
        aria-labelledby={`tab-${active}`}
        className="flex-1 overflow-auto"
      >
        {active === "info" && <PropertyContextPanel prospect={prospect} onChange={onChange} />}
        {active === "anteckningar" && <NotesTab prospect={prospect} />}
        {active === "dokument" && <DocumentsPlaceholder />}
      </div>
    </div>
  );
}

function NotesTab({ prospect }: { prospect: Prospect }) {
  return (
    <div style={{ padding: 16, fontSize: "var(--t-body)", color: "var(--ink)" }}>
      <div
        className="caps"
        style={{
          textTransform: "uppercase",
          letterSpacing: "var(--ls-wider)",
          fontSize: "var(--t-micro)",
          color: "var(--ink-60)",
          marginBottom: 8,
        }}
      >
        Anteckningar
      </div>
      <p style={{ color: "var(--ink-80)", marginBottom: 12 }}>{prospect.address}</p>
      <p style={{ color: "var(--ink-60)", fontSize: "var(--t-small)", lineHeight: 1.55 }}>
        Redigera anteckningar i Info-fliken tills dedikerad redigerare flyttas hit (Phase B.2+).
      </p>
      {prospect.notes ? (
        <pre
          style={{
            marginTop: 12,
            padding: 12,
            background: "var(--paper-tint)",
            border: "1px solid var(--rule)",
            borderRadius: "var(--r-2)",
            whiteSpace: "pre-wrap",
            fontFamily: "var(--font-body)",
            fontSize: "var(--t-small)",
            color: "var(--ink)",
          }}
        >
          {prospect.notes}
        </pre>
      ) : (
        <p
          style={{
            marginTop: 12,
            color: "var(--ink-60)",
            fontStyle: "italic",
            fontSize: "var(--t-small)",
          }}
        >
          Inga anteckningar ännu.
        </p>
      )}
    </div>
  );
}

function DocumentsPlaceholder() {
  return (
    <div
      className="flex h-full flex-col items-center justify-center"
      style={{ padding: 32, textAlign: "center" }}
    >
      <p
        className="display"
        style={{
          fontFamily: "var(--font-display)",
          fontSize: "var(--t-h2)",
          color: "var(--ink-60)",
          margin: 0,
        }}
      >
        —
      </p>
      <p
        className="caps"
        style={{
          marginTop: 8,
          textTransform: "uppercase",
          letterSpacing: "var(--ls-wider)",
          fontSize: "var(--t-micro)",
          color: "var(--ink-60)",
        }}
      >
        Phase 20 · dokumenthantering kommer
      </p>
    </div>
  );
}
