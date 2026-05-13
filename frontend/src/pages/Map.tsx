import { useEffect, useMemo, useState } from "react";
import { api, type Prospect } from "../api";
import MapView from "../components/MapView";
import { ProspectDetailTabs } from "../components/ProspectDetailTabs";

type Filter = "all" | "new" | "interested" | "callback";

const FILTERS: Array<{ id: Filter; label: string }> = [
  { id: "all", label: "Alla" },
  { id: "new", label: "Nya" },
  { id: "interested", label: "Intresserade" },
  { id: "callback", label: "Callback" },
];

export default function MapPage() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [drawerOpen, setDrawerOpen] = useState(true);
  const [filter, setFilter] = useState<Filter>("all");

  const refresh = async () => {
    try {
      setProspects(await api.listProspects());
    } catch {
      /* ignore */
    }
  };

  useEffect(() => {
    void refresh();
  }, []);

  const counts = useMemo(() => {
    const c = { all: prospects.length, new: 0, interested: 0, callback: 0 };
    for (const p of prospects) {
      const s = p.status ?? "new";
      if (s === "new") c.new += 1;
      else if (s === "interested") c.interested += 1;
      else if (s === "callback") c.callback += 1;
    }
    return c;
  }, [prospects]);

  const visibleProspects = useMemo(() => {
    if (filter === "all") return prospects;
    return prospects.filter((p) => (p.status ?? "new") === filter);
  }, [prospects, filter]);

  const selected = prospects.find((p) => p.id === selectedId) ?? null;

  return (
    <section className="relative flex h-[calc(100vh-32px)]">
      <div className="relative flex-1">
        <MapView prospects={visibleProspects} selectedId={selectedId} onSelect={setSelectedId} />
        <div className="absolute left-4 top-4 z-10 flex gap-2" role="tablist" aria-label="Filter">
          {FILTERS.map((f) => {
            const isActive = filter === f.id;
            const count = counts[f.id];
            return (
              <button
                key={f.id}
                role="tab"
                aria-selected={isActive}
                onClick={() => setFilter(f.id)}
                className="tabular"
                style={{
                  display: "inline-flex",
                  alignItems: "center",
                  gap: 8,
                  padding: "6px 12px",
                  borderRadius: "var(--r-pill)",
                  border: "1px solid var(--rule)",
                  background: isActive ? "var(--ink)" : "var(--paper)",
                  color: isActive ? "var(--paper)" : "var(--ink)",
                  fontSize: "var(--t-small)",
                  letterSpacing: "var(--ls-tight)",
                  cursor: "pointer",
                  boxShadow: "var(--shadow-1)",
                  transition: "background var(--dur-snap) var(--ease-paper)",
                }}
              >
                <span>{f.label}</span>
                <span
                  className="tabular"
                  style={{
                    fontSize: "var(--t-micro)",
                    color: isActive ? "var(--paper)" : "var(--ink-60)",
                    opacity: 0.85,
                  }}
                >
                  {count}
                </span>
              </button>
            );
          })}
        </div>
      </div>
      {drawerOpen && (
        <aside className="flex w-96 flex-col border-l border-(--rule) bg-(--paper)">
          <div className="flex items-center justify-between border-b border-(--rule) bg-(--paper-tint) px-3 py-2">
            <span className="caps text-(--ink-60)">Detalj</span>
            <button
              onClick={() => setDrawerOpen(false)}
              className="caps text-(--ink-60) hover:text-(--ink)"
            >
              dölj
            </button>
          </div>
          <div className="flex-1 overflow-auto">
            <ProspectDetailTabs prospect={selected} onChange={refresh} />
          </div>
        </aside>
      )}
      {!drawerOpen && (
        <button
          onClick={() => setDrawerOpen(true)}
          className="absolute right-4 top-4 z-10 rounded border border-(--rule) bg-(--paper) px-3 py-1 text-xs text-(--ink) shadow hover:bg-(--paper-tint)"
        >
          Visa detalj
        </button>
      )}
    </section>
  );
}
