import { useEffect, useState } from "react";
import { api, type Prospect } from "../api";

interface SavedSearch {
  name: string;
  q: string;
  status: string;
  min_score: string;
  max_score: string;
}

const STORAGE_KEY = "solar.searches.v1";

export default function Search() {
  const [q, setQ] = useState("");
  const [status, setStatus] = useState("");
  const [minScore, setMinScore] = useState("");
  const [maxScore, setMaxScore] = useState("");
  const [results, setResults] = useState<Prospect[] | null>(null);
  const [saved, setSaved] = useState<SavedSearch[]>([]);
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    try {
      const raw = localStorage.getItem(STORAGE_KEY);
      if (raw) setSaved(JSON.parse(raw));
    } catch {
      /* ignore */
    }
  }, []);

  const run = async () => {
    setBusy(true);
    try {
      const r = await api.searchProspects({
        q: q || undefined,
        status: status || undefined,
        min_score: minScore ? Number(minScore) : undefined,
        max_score: maxScore ? Number(maxScore) : undefined,
      });
      setResults(r);
    } finally {
      setBusy(false);
    }
  };

  const save = () => {
    const name = prompt("Namn för sparad sökning:");
    if (!name) return;
    const next = [...saved, { name, q, status, min_score: minScore, max_score: maxScore }];
    setSaved(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  const apply = (s: SavedSearch) => {
    setQ(s.q);
    setStatus(s.status);
    setMinScore(s.min_score);
    setMaxScore(s.max_score);
  };

  const remove = (idx: number) => {
    const next = saved.filter((_, i) => i !== idx);
    setSaved(next);
    localStorage.setItem(STORAGE_KEY, JSON.stringify(next));
  };

  return (
    <section className="p-6">
      <h2 className="display text-3xl text-(--ink)">Sök</h2>

      <form
        onSubmit={(e) => {
          e.preventDefault();
          void run();
        }}
        className="mt-6 grid grid-cols-4 gap-3 rounded border border-(--rule) bg-(--paper-tint) p-4"
      >
        <label className="col-span-2 flex flex-col gap-1 text-sm">
          <span className="caps text-(--ink-60)">Adress/ägare innehåller</span>
          <input
            value={q}
            onChange={(e) => setQ(e.target.value)}
            className="rounded bg-(--paper) px-2 py-1 text-(--ink)"
          />
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="caps text-(--ink-60)">Status</span>
          <select
            value={status}
            onChange={(e) => setStatus(e.target.value)}
            className="rounded bg-(--paper) px-2 py-1 text-(--ink)"
          >
            <option value="">(alla)</option>
            <option value="new">Ny</option>
            <option value="interested">Intresserad</option>
            <option value="callback">Återkoppling</option>
            <option value="rejected">Avböjd</option>
          </select>
        </label>
        <label className="flex flex-col gap-1 text-sm">
          <span className="caps text-(--ink-60)">Poäng min / max</span>
          <div className="flex gap-1">
            <input
              value={minScore}
              onChange={(e) => setMinScore(e.target.value)}
              placeholder="0"
              className="w-full rounded bg-(--paper) px-2 py-1 text-(--ink)"
            />
            <input
              value={maxScore}
              onChange={(e) => setMaxScore(e.target.value)}
              placeholder="10"
              className="w-full rounded bg-(--paper) px-2 py-1 text-(--ink)"
            />
          </div>
        </label>
        <div className="col-span-4 flex gap-2">
          <button
            type="submit"
            disabled={busy}
            className="rounded bg-(--ink) px-4 py-2 text-sm text-(--paper) hover:bg-(--ink-60) disabled:opacity-50"
          >
            {busy ? "Söker…" : "Sök"}
          </button>
          <button
            type="button"
            onClick={save}
            className="rounded border border-(--rule) bg-(--paper) px-4 py-2 text-sm text-(--ink) hover:bg-(--paper-tint)"
          >
            Spara sökning
          </button>
        </div>
      </form>

      {saved.length > 0 && (
        <div className="mt-4">
          <h3 className="caps text-(--ink-60)">Sparade sökningar</h3>
          <ul className="mt-2 flex flex-wrap gap-2">
            {saved.map((s, i) => (
              <li
                key={i}
                className="flex items-center gap-2 rounded border border-(--rule) bg-(--paper-tint) px-3 py-1 text-sm"
              >
                <button onClick={() => apply(s)} className="text-(--ink) hover:underline">
                  {s.name}
                </button>
                <button
                  onClick={() => remove(i)}
                  className="caps text-(--ink-60) hover:text-(--barn)"
                  aria-label={`Ta bort ${s.name}`}
                >
                  ×
                </button>
              </li>
            ))}
          </ul>
        </div>
      )}

      {results !== null && (
        <div className="mt-6">
          <h3 className="caps text-(--ink-60)">{results.length} träffar</h3>
          <ul className="mt-2 divide-y divide-(--rule) rounded border border-(--rule) bg-(--paper-tint)">
            {results.map((p) => (
              <li key={p.id} className="flex items-center gap-3 px-3 py-2 text-sm">
                <span className="truncate text-(--ink)">{p.address}</span>
                <span className="caps ml-auto text-(--ink-60)">
                  {p.status} · {p.score?.toFixed(1) ?? "—"}
                </span>
              </li>
            ))}
            {results.length === 0 && (
              <li className="px-3 py-4 text-center caps text-(--ink-60)">Inga träffar</li>
            )}
          </ul>
        </div>
      )}
    </section>
  );
}
