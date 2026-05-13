import { useCallback, useEffect, useState } from "react";
import { api, type Prospect } from "../api";
import BulkInput from "../components/BulkInput";
import ProspectTable from "../components/ProspectTable";
import { ProspectDetailTabs } from "../components/ProspectDetailTabs";
import ExportButton from "../components/ExportButton";
import { useProspectHotkeys } from "../hooks/useProspectHotkeys";

export default function Prospects() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [error, setError] = useState<string | null>(null);

  const refresh = useCallback(async () => {
    try {
      setProspects(await api.listProspects());
      setError(null);
    } catch (e) {
      setError(e instanceof Error ? e.message : "okänt fel");
    }
  }, []);

  useEffect(() => {
    void refresh();
  }, [refresh]);

  useProspectHotkeys(selectedId, () => {
    void refresh();
  });

  const selected = prospects.find((p) => p.id === selectedId) ?? null;

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
            Prospekt
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
            {prospects.length} totalt
          </p>
        </div>
        <div className="flex items-center" style={{ gap: 8 }}>
          <BulkInput onAdded={() => void refresh()} />
          <ExportButton />
        </div>
      </header>

      {error && (
        <div
          style={{
            padding: "8px 24px",
            borderBottom: "1px solid var(--rule)",
            background: "var(--paper)",
            color: "var(--barn)",
            fontSize: "var(--t-small)",
          }}
        >
          Kunde inte ladda prospekt: {error}
        </div>
      )}

      <div className="flex flex-1 overflow-hidden">
        <div style={{ width: 420, borderRight: "1px solid var(--rule)" }}>
          <ProspectTable
            prospects={prospects}
            selectedId={selectedId}
            onSelect={setSelectedId}
            onRefresh={() => void refresh()}
          />
        </div>
        <div className="flex-1" style={{ background: "var(--paper)" }}>
          <ProspectDetailTabs prospect={selected} onChange={() => void refresh()} />
        </div>
      </div>
    </section>
  );
}
