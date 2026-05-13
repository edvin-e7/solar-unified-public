import { useState } from "react";
import { api } from "../api";

interface DetectionRun {
  address: string;
  ts: string;
  result: Record<string, unknown> | null;
  error: string | null;
}

export default function Detection() {
  const [addresses, setAddresses] = useState("");
  const [runs, setRuns] = useState<DetectionRun[]>([]);
  const [busy, setBusy] = useState(false);

  const run = async () => {
    const list = addresses
      .split("\n")
      .map((s) => s.trim())
      .filter(Boolean);
    if (list.length === 0 || busy) return;
    setBusy(true);
    const newRuns: DetectionRun[] = [];
    for (const address of list) {
      const ts = new Date().toISOString();
      try {
        const result = await api.detect(address);
        newRuns.push({ address, ts, result, error: null });
      } catch (e) {
        newRuns.push({
          address,
          ts,
          result: null,
          error: e instanceof Error ? e.message : "okänt fel",
        });
      }
    }
    setRuns((prev) => [...newRuns, ...prev].slice(0, 50));
    setBusy(false);
  };

  return (
    <section className="p-6">
      <h2 className="display text-3xl text-(--ink)">Detektion</h2>
      <p className="caps mt-1 text-(--ink-60)">Kör panel­detektion mot adresser</p>

      <div className="mt-6 flex gap-3">
        <textarea
          value={addresses}
          onChange={(e) => setAddresses(e.target.value)}
          placeholder="En adress per rad"
          className="h-32 flex-1 rounded border border-(--rule) bg-(--paper) p-2 text-sm text-(--ink)"
        />
        <button
          disabled={busy}
          onClick={run}
          className="self-start rounded bg-(--ink) px-4 py-2 text-sm text-(--paper) hover:bg-(--ink-60) disabled:opacity-50"
        >
          {busy ? "Kör…" : "Kör detektion"}
        </button>
      </div>

      <div className="mt-6">
        <h3 className="caps text-(--ink-60)">Resultat ({runs.length})</h3>
        <ul className="mt-2 space-y-2">
          {runs.map((r, i) => (
            <li key={i} className="rounded border border-(--rule) bg-(--paper-tint) p-4 shadow-sm transition-all hover:shadow-md">
              <div className="flex items-center justify-between">
                <div>
                  <h4 className="text-base font-medium text-(--ink)">{r.address}</h4>
                  <p className="text-xs text-(--ink-60)">{new Date(r.ts).toLocaleString("sv-SE")}</p>
                </div>
                {r.result && (
                  <span className="rounded bg-(--forest)/10 px-2 py-1 text-xs font-medium text-(--forest)">
                    Slutförd
                  </span>
                )}
                {r.error && (
                  <span className="rounded bg-(--barn)/10 px-2 py-1 text-xs font-medium text-(--barn)">
                    Misslyckades
                  </span>
                )}
              </div>
              
              {r.error && (
                <div className="mt-3 rounded border border-(--barn)/20 bg-(--barn)/5 p-2 text-sm text-(--barn)">
                  <strong>Fel:</strong> {r.error}
                </div>
              )}
              
              {r.result && (
                <div className="mt-4 grid grid-cols-2 gap-4 border-t border-(--rule) pt-3 sm:grid-cols-4">
                  <div>
                    <span className="caps block text-[10px]">Status</span>
                    <span className="text-sm font-medium text-(--ink)">
                      {(r.result as any).has_panels ? "Paneler hittade" : "Inga paneler"}
                    </span>
                  </div>
                  <div>
                    <span className="caps block text-[10px]">Konfidens</span>
                    <span className="text-sm font-medium text-(--ink)">
                      {((r.result as any).confidence * 100).toFixed(0)}%
                    </span>
                  </div>
                  <div>
                    <span className="caps block text-[10px]">Takarea (ca)</span>
                    <span className="text-sm font-medium text-(--ink)">
                      {(r.result as any).roof_area_m2 ?? "—"} m²
                    </span>
                  </div>
                  <div>
                    <span className="caps block text-[10px]">Agent</span>
                    <span className="text-sm font-medium text-(--ink)">DetectionAgent v1.2</span>
                  </div>
                </div>
              )}
            </li>
          ))}
          {runs.length === 0 && <li className="caps text-(--ink-60)">Inga körningar än</li>}
        </ul>
      </div>
    </section>
  );
}
