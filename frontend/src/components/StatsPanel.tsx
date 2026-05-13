import { useEffect, useState } from "react";
import { api, type Stats } from "../api";

export default function StatsPanel() {
  const [stats, setStats] = useState<Stats | null>(null);
  const [open, setOpen] = useState(false);

  useEffect(() => {
    if (!open) return;
    void load();
    const id = setInterval(load, 30_000);
    return () => clearInterval(id);
  }, [open]);

  async function load() {
    try {
      setStats(await api.stats());
    } catch {
      /* keep last known */
    }
  }

  if (!open) {
    return (
      <button
        onClick={() => setOpen(true)}
        className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
      >
        Statistik
      </button>
    );
  }

  return (
    <div className="fixed inset-0 z-50 flex items-center justify-center bg-(--ink)/40 p-8">
      <div className="max-h-[80vh] w-[640px] overflow-y-auto rounded-lg bg-(--paper) p-6 shadow-xl">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="display text-xl">Statistik</h2>
          <button
            onClick={() => setOpen(false)}
            className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
          >
            Stäng
          </button>
        </div>

        {!stats && <p className="text-(--ink-60)">Laddar…</p>}

        {stats && (
          <div className="grid gap-4">
            <div className="grid grid-cols-4 gap-2">
              <Metric label="Totalt" value={stats.total} />
              <Metric label="Konvertering" value={`${stats.conversion_rate}%`} />
              <Metric label="Berikad data" value={`${stats.enrichment_rate}%`} />
              <Metric label="Snittscore" value={stats.avg_score} />
            </div>

            <section>
              <h3 className="caps mb-2">Status</h3>
              <div className="grid grid-cols-2 gap-2 text-sm">
                {Object.entries(stats.by_status).map(([status, n]) => (
                  <div
                    key={status}
                    className="flex items-center justify-between rounded bg-(--paper-tint) px-3 py-1.5"
                  >
                    <span className="text-(--ink-60)">{status}</span>
                    <span className="tabular font-medium">{n}</span>
                  </div>
                ))}
              </div>
            </section>

            <section>
              <h3 className="caps mb-2">Senaste 7 dagar</h3>
              <DailyBars daily={stats.daily} />
            </section>
          </div>
        )}
      </div>
    </div>
  );
}

function Metric({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded bg-(--paper-tint) p-3">
      <div className="caps">{label}</div>
      <div className="mt-1 text-2xl font-medium tabular">{value}</div>
    </div>
  );
}

function DailyBars({ daily }: { daily: { day: string; n: number }[] }) {
  if (daily.length === 0) {
    return <p className="text-sm text-(--ink-60)">Ingen aktivitet senaste veckan.</p>;
  }
  const max = Math.max(...daily.map((d) => d.n), 1);
  return (
    <div className="flex items-end gap-2 pt-2">
      {daily.map((d) => (
        <div key={d.day} className="flex flex-1 flex-col items-center gap-1">
          <span className="tabular text-xs text-(--ink-60)">{d.n}</span>
          <div
            className="w-full rounded-t bg-(--amber)"
            style={{ height: `${(d.n / max) * 80}px` }}
          />
          <span className="text-[10px] text-(--ink-60)">{d.day.slice(5)}</span>
        </div>
      ))}
    </div>
  );
}
