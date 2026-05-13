import { useEffect, useMemo, useState } from "react";
import { api, type Prospect } from "../api";
import { rasterTileUrl } from "../utils/tiles";

interface Props {
  prospects: Prospect[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  onRefresh: () => void;
}

const STATUS_COLORS: Record<string, string> = {
  new: "bg-(--stone)",
  interested: "bg-(--forest)",
  callback: "bg-(--amber)",
  rejected: "bg-(--barn)",
};

const STATUS_LABEL_SHORT: Record<string, string> = {
  new: "Ny",
  interested: "Intr",
  callback: "Åter",
  rejected: "Avb",
};

const STATUS_FILTERS = [
  { value: "all", label: "Alla" },
  { value: "new", label: "Ny" },
  { value: "interested", label: "Intr." },
  { value: "callback", label: "Åter." },
  { value: "rejected", label: "Avböjd" },
];

const BULK_STATUSES = [
  { value: "interested", label: "Intresserad" },
  { value: "callback", label: "Återkoppling" },
  { value: "rejected", label: "Avböjd" },
  { value: "new", label: "Ny" },
];

export default function ProspectTable({ prospects, selectedId, onSelect, onRefresh }: Props) {
  const [query, setQuery] = useState("");
  const [statusFilter, setStatusFilter] = useState("all");
  const [checked, setChecked] = useState<Set<number>>(new Set());
  const [busy, setBusy] = useState<"" | "status" | "delete" | "geocode" | "contacts">("");
  const [toast, setToast] = useState<string | null>(null);

  const filtered = useMemo(() => {
    const q = query.trim().toLowerCase();
    return prospects.filter((p) => {
      if (statusFilter !== "all" && (p.status ?? "new") !== statusFilter) return false;
      if (q && !`${p.address} ${p.owner_name ?? ""}`.toLowerCase().includes(q)) return false;
      return true;
    });
  }, [prospects, query, statusFilter]);

  useEffect(() => {
    setChecked((prev) => {
      const valid = new Set<number>();
      const ids = new Set(filtered.map((p) => p.id).filter((id): id is number => id != null));
      for (const id of prev) if (ids.has(id)) valid.add(id);
      return valid;
    });
  }, [filtered]);

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      if (filtered.length === 0) return;
      const idx = filtered.findIndex((p) => p.id === selectedId);
      if (e.key === "j" || e.key === "ArrowDown") {
        e.preventDefault();
        const next = filtered[Math.min(idx + 1, filtered.length - 1)];
        if (next?.id) onSelect(next.id);
      } else if (e.key === "k" || e.key === "ArrowUp") {
        e.preventDefault();
        const prev = filtered[Math.max(idx - 1, 0)];
        if (prev?.id) onSelect(prev.id);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [filtered, selectedId, onSelect]);

  function toggleCheck(id: number) {
    setChecked((prev) => {
      const next = new Set(prev);
      if (next.has(id)) next.delete(id);
      else next.add(id);
      return next;
    });
  }

  function toggleAll() {
    setChecked((prev) => {
      if (prev.size === filtered.length) return new Set();
      return new Set(filtered.map((p) => p.id).filter((id): id is number => id != null));
    });
  }

  async function bulkSetStatus(status: string) {
    if (checked.size === 0 || busy) return;
    setBusy("status");
    try {
      await api.bulkStatus(Array.from(checked), status);
      setChecked(new Set());
      onRefresh();
    } finally {
      setBusy("");
    }
  }

  async function bulkDelete() {
    if (checked.size === 0 || busy) return;
    if (!confirm(`Ta bort ${checked.size} prospekt?`)) return;
    setBusy("delete");
    try {
      await api.bulkDelete(Array.from(checked));
      setChecked(new Set());
      onRefresh();
    } finally {
      setBusy("");
    }
  }

  async function bulkGeocode() {
    if (checked.size === 0 || busy) return;
    setBusy("geocode");
    setToast(`Geokodar ${checked.size} prospekt… (1-2s per adress)`);
    try {
      const r = await api.bulkGeocode(Array.from(checked));
      const errs = r.errors.length;
      setToast(
        `Geokodade ${r.changed}${errs ? ` · ${errs} fel` : ""}${r.unchanged ? ` · ${r.unchanged} redan klara` : ""}`,
      );
      setChecked(new Set());
      onRefresh();
    } catch (e) {
      setToast(`Fel: ${e instanceof Error ? e.message : "okänt"}`);
    } finally {
      setBusy("");
    }
  }

  async function bulkEnrichContacts() {
    if (checked.size === 0 || busy) return;
    setBusy("contacts");
    setToast(`Hämtar namn+telefon för ${checked.size} prospekt… (1-2s per rad)`);
    try {
      const r = await api.bulkEnrichContacts(Array.from(checked));
      const parts = [`Berikade ${r.changed}`];
      if (r.unchanged) parts.push(`${r.unchanged} redan klara`);
      if (r.no_match) parts.push(`${r.no_match} utan träff`);
      if (r.errors.length) parts.push(`${r.errors.length} fel`);
      setToast(parts.join(" · "));
      setChecked(new Set());
      onRefresh();
    } catch (e) {
      setToast(`Fel: ${e instanceof Error ? e.message : "okänt"}`);
    } finally {
      setBusy("");
    }
  }

  const allChecked = filtered.length > 0 && checked.size === filtered.length;

  return (
    <div className="flex flex-col overflow-hidden border-r border-(--rule)">
      <div className="border-b border-(--rule) bg-(--paper-tint) p-2">
        <input
          type="text"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
          placeholder="Sök adress eller ägare…"
          className="w-full rounded bg-(--paper) px-2 py-1 text-xs text-(--ink) placeholder:text-(--ink-60)"
        />
        <div className="mt-2 flex flex-wrap gap-1">
          {STATUS_FILTERS.map((f) => (
            <button
              key={f.value}
              onClick={() => setStatusFilter(f.value)}
              className={`rounded px-2 py-0.5 text-[10px] ${
                statusFilter === f.value
                  ? "bg-(--ink) text-(--paper)"
                  : "bg-(--paper) text-(--ink-60) hover:bg-(--rule)"
              }`}
            >
              {f.label}
            </button>
          ))}
          <span className="ml-auto text-[10px] text-(--ink-60)">
            {filtered.length}/{prospects.length}
          </span>
        </div>
      </div>

      {checked.size > 0 && (
        <div className="flex flex-wrap items-center gap-1 border-b border-(--rule) bg-(--paper-tint) p-2 text-xs">
          <span className="text-(--ink-60)">{checked.size} valda:</span>
          {BULK_STATUSES.map((s) => (
            <button
              key={s.value}
              disabled={!!busy}
              onClick={() => bulkSetStatus(s.value)}
              className="rounded bg-(--paper) px-2 py-0.5 text-(--ink) hover:bg-(--rule) disabled:opacity-50"
            >
              → {s.label}
            </button>
          ))}
          <button
            disabled={!!busy}
            onClick={bulkGeocode}
            className="rounded bg-(--forest)/20 px-2 py-0.5 text-(--forest) hover:bg-(--forest)/30 disabled:opacity-50"
          >
            {busy === "geocode" ? "Geokodar…" : "Geokoda"}
          </button>
          <button
            disabled={!!busy}
            onClick={bulkEnrichContacts}
            className="rounded bg-(--amber)/20 px-2 py-0.5 text-(--amber) hover:bg-(--amber)/30 disabled:opacity-50"
          >
            {busy === "contacts" ? "Hämtar…" : "Berika namn+tel"}
          </button>
          <button
            disabled={!!busy}
            onClick={bulkDelete}
            className="rounded bg-(--barn)/20 px-2 py-0.5 text-(--barn) hover:bg-(--barn)/30 disabled:opacity-50"
          >
            Ta bort
          </button>
          <button
            onClick={() => setChecked(new Set())}
            className="ml-auto rounded bg-(--paper) px-2 py-0.5 text-(--ink-60) hover:bg-(--rule)"
          >
            Rensa
          </button>
        </div>
      )}

      {toast && (
        <div className="flex items-center gap-2 border-b border-(--rule) bg-(--paper-tint) px-3 py-1 text-xs text-(--ink-60)">
          <span>{toast}</span>
          <button
            onClick={() => setToast(null)}
            className="ml-auto text-(--ink-60) hover:text-(--ink)"
            aria-label="Stäng"
          >
            ×
          </button>
        </div>
      )}

      <div className="flex items-center gap-2 border-b border-(--rule) bg-(--paper-tint)/60 px-3 py-1.5 text-[10px]">
        <input
          type="checkbox"
          checked={allChecked}
          onChange={toggleAll}
          aria-label="Välj alla"
          className="scale-90"
        />
        <span className="caps text-(--ink-60)">Adress</span>
        <span className="ml-auto caps text-(--ink-60)">Score</span>
      </div>

      <ul className="flex-1 divide-y divide-(--rule) overflow-y-auto">
        {filtered.length === 0 && (
          <li className="px-4 py-10 text-center text-xs text-(--ink-60)">
            {prospects.length === 0
              ? "Inga prospekt ännu. Klistra in adresser ovan."
              : "Inga träffar."}
          </li>
        )}
        {filtered.map((p) => {
          const status = p.status ?? "new";
          const statusColor = STATUS_COLORS[status] ?? "bg-(--stone)";
          const isSelected = selectedId === p.id;
          const thumb = p.lat != null && p.lng != null ? rasterTileUrl(p.lat, p.lng, 16) : null;
          return (
            <li
              key={p.id}
              onClick={() => p.id && onSelect(p.id)}
              className={`group relative flex cursor-pointer items-center gap-3 px-3 py-2 transition-colors hover:bg-(--paper-tint) ${
                isSelected ? "bg-(--paper-tint)" : ""
              }`}
            >
              <span
                className={`absolute left-0 top-0 h-full w-1 ${statusColor} ${
                  isSelected ? "opacity-100" : "opacity-60 group-hover:opacity-100"
                }`}
                aria-hidden
              />
              <input
                type="checkbox"
                onClick={(e) => e.stopPropagation()}
                checked={p.id ? checked.has(p.id) : false}
                onChange={() => p.id && toggleCheck(p.id)}
                aria-label={`Välj ${p.address}`}
                className="ml-1 scale-90"
              />
              <div className="relative h-12 w-12 shrink-0 overflow-hidden rounded border border-(--rule) bg-(--paper-tint)">
                {thumb ? (
                  <img
                    src={thumb}
                    alt=""
                    loading="lazy"
                    className="h-full w-full object-cover opacity-90"
                    referrerPolicy="no-referrer"
                  />
                ) : (
                  <span className="flex h-full w-full items-center justify-center text-[10px] text-(--ink-60)">
                    —
                  </span>
                )}
                <span className={`absolute inset-x-0 bottom-0 h-1 ${statusColor}`} aria-hidden />
              </div>
              <div className="flex min-w-0 flex-1 flex-col">
                <span className="truncate text-sm text-(--ink)">{p.address}</span>
                <span className="truncate text-[10px] text-(--ink-60)">
                  {p.owner_name ? `${p.owner_name} · ` : ""}
                  {p.annual_kwh
                    ? `${Math.round(p.annual_kwh).toLocaleString("sv-SE")} kWh/år`
                    : "Okänt kWh"}
                </span>
                <span className="caps mt-0.5 text-(--ink-60)">
                  {STATUS_LABEL_SHORT[status] ?? "Ny"}
                </span>
              </div>
              <div className="flex flex-col items-end text-right">
                <span className="display text-xl tabular-nums text-(--ink)">
                  {p.score != null ? p.score.toFixed(1) : "—"}
                </span>
                <span className="caps text-(--ink-60)">poäng</span>
              </div>
            </li>
          );
        })}
      </ul>
    </div>
  );
}
