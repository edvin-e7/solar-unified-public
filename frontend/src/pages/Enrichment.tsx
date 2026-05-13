import { useEffect, useState } from "react";
import { api, type Prospect } from "../api";

export default function Enrichment() {
  const [prospects, setProspects] = useState<Prospect[]>([]);
  const [selected, setSelected] = useState<Set<number>>(new Set());
  const [log, setLog] = useState<string[]>([]);
  const [flags, setFlags] = useState<{
    allow_external_llm: boolean;
    allow_google_solar_api: boolean;
  } | null>(null);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api
      .listProspects()
      .then(setProspects)
      .catch(() => setProspects([]));
    void api
      .settingsFlags()
      .then(setFlags)
      .catch(() => setFlags(null));
  }, []);

  const toggle = (id: number) => {
    const next = new Set(selected);
    if (next.has(id)) next.delete(id);
    else next.add(id);
    setSelected(next);
  };

  const run = async () => {
    if (selected.size === 0 || busy) return;
    setBusy(true);
    setLog([`Startar geokodning av ${selected.size} prospekt…`]);
    try {
      const r = await api.bulkGeocode(Array.from(selected));
      setLog((prev) => [
        ...prev,
        `Geokodade: ${r.changed}`,
        `Oförändrade: ${r.unchanged}`,
        `Fel: ${r.errors.length}`,
        ...r.errors.map((e) => `  · ${JSON.stringify(e)}`),
      ]);
      setSelected(new Set());
      const fresh = await api.listProspects();
      setProspects(fresh);
    } catch (e) {
      setLog((prev) => [...prev, `Fel: ${e instanceof Error ? e.message : "okänt"}`]);
    } finally {
      setBusy(false);
    }
  };

  return (
    <section className="p-6">
      <h2 className="display text-3xl text-(--ink)">Berikning</h2>

      <div className="mt-4 flex gap-2 text-xs">
        <Chip
          label="LLM (Gemini)"
          on={flags?.allow_external_llm ?? false}
          note={flags == null ? "laddar" : flags.allow_external_llm ? "PÅ" : "AV"}
        />
        <Chip
          label="Google Solar"
          on={flags?.allow_google_solar_api ?? false}
          note={flags == null ? "laddar" : flags.allow_google_solar_api ? "PÅ" : "AV"}
        />
      </div>

      <div className="mt-6 grid grid-cols-2 gap-6">
        <div>
          <h3 className="caps text-(--ink-60)">Välj prospekt</h3>
          <ul className="mt-2 max-h-96 divide-y divide-(--rule) overflow-auto rounded border border-(--rule) bg-(--paper-tint)">
            {prospects.map((p) => (
              <li key={p.id} className="flex items-center gap-2 px-3 py-2 text-sm">
                <input
                  type="checkbox"
                  checked={p.id ? selected.has(p.id) : false}
                  onChange={() => p.id && toggle(p.id)}
                />
                <span className="truncate text-(--ink)">{p.address}</span>
                <span className="caps ml-auto text-(--ink-60)">
                  {p.owner_name ? "✓ ägare" : p.annual_kwh ? "✓ kWh" : "—"}
                </span>
              </li>
            ))}
          </ul>
          <button
            disabled={busy || selected.size === 0}
            onClick={run}
            className="mt-3 rounded bg-(--ink) px-4 py-2 text-sm text-(--paper) hover:bg-(--ink-60) disabled:opacity-50"
          >
            {busy ? "Berikar…" : `Berika ${selected.size} valda`}
          </button>
        </div>

        <div className="flex flex-col">
          <h3 className="caps text-(--ink-60)">Senaste Aktivitet</h3>
          <div className="mt-2 flex-1 rounded border border-(--rule) bg-(--paper-tint) p-4 overflow-auto">
            {log.length > 0 ? (
              <ul className="space-y-3">
                {log.map((line, i) => (
                  <li
                    key={i}
                    className={`text-xs ${line.startsWith("Fel") ? "text-(--barn)" : "text-(--ink)"}`}
                  >
                    <span className="opacity-40 mr-2">—</span>
                    {line}
                  </li>
                ))}
              </ul>
            ) : (
              <div className="flex h-full items-center justify-center text-center">
                <p className="caps text-[10px] text-(--ink-40)">Ingen aktivitet i denna session</p>
              </div>
            )}
          </div>
          {busy && (
            <div className="mt-3 flex items-center gap-2 text-xs text-(--amber)">
              <div className="h-2 w-2 animate-pulse rounded-full bg-(--amber)" />
              Agenterna arbetar med berikning…
            </div>
          )}
        </div>
      </div>
    </section>
  );
}

function Chip({ label, on, note }: { label: string; on: boolean; note: string }) {
  const cls = on ? "bg-(--forest)/20 text-(--forest)" : "bg-(--ink)/10 text-(--ink-60)";
  return (
    <span className={`caps rounded px-2 py-1 ${cls}`}>
      {label} · {note}
    </span>
  );
}
