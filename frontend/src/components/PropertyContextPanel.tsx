import { useEffect, useState } from "react";
import { api, type Prospect } from "../api";
import DataField from "./DataField";
import { fromNullable } from "../lib/dataState";

interface Props {
  prospect: Prospect | null;
  onChange: () => void;
}

const STATUS_OPTIONS: { value: string; label: string; key: string; color: string }[] = [
  { value: "new", label: "Ny", key: "1", color: "--stone" },
  { value: "interested", label: "Intresserad", key: "2", color: "--forest" },
  { value: "callback", label: "Återkoppling", key: "3", color: "--amber" },
  { value: "rejected", label: "Avböjd", key: "4", color: "--barn" },
];

export default function PropertyContextPanel({ prospect, onChange }: Props) {
  const [busy, setBusy] = useState<string | null>(null);
  const [notesDraft, setNotesDraft] = useState("");
  const [editingNotes, setEditingNotes] = useState(false);
  const [pitch, setPitch] = useState<string | null>(null);

  useEffect(() => {
    setNotesDraft(prospect?.notes ?? "");
    setEditingNotes(false);
    setPitch(null);
  }, [prospect?.id]);

  useEffect(() => {
    if (!prospect?.id) return;
    function onKey(e: KeyboardEvent) {
      if (editingNotes) return;
      const tag = (e.target as HTMLElement)?.tagName;
      if (tag === "INPUT" || tag === "TEXTAREA") return;
      const match = STATUS_OPTIONS.find((o) => o.key === e.key);
      if (match) {
        e.preventDefault();
        void setStatus(match.value);
      }
    }
    document.addEventListener("keydown", onKey);
    return () => document.removeEventListener("keydown", onKey);
  }, [prospect?.id, editingNotes]);

  if (!prospect) {
    return (
      <aside className="border-l border-(--rule) p-4 text-sm text-(--ink-60)">
        Välj ett prospekt för att se detaljer.
      </aside>
    );
  }

  async function setStatus(status: string) {
    if (!prospect?.id || busy) return;
    setBusy("status");
    try {
      await api.updateProspect(prospect.id, { ...prospect, status });
      onChange();
    } finally {
      setBusy(null);
    }
  }

  async function runSolar() {
    if (!prospect || prospect.lat == null || prospect.lng == null || !prospect.id) return;
    setBusy("solar");
    try {
      const r = await api.solarPotential(prospect.lat, prospect.lng);
      await api.updateProspect(prospect.id, { ...prospect, annual_kwh: r.annual_kwh });
      onChange();
    } finally {
      setBusy(null);
    }
  }

  async function runEnrich() {
    if (!prospect?.id) return;
    setBusy("enrich");
    try {
      const r = await api.enrichPerson(prospect.address);
      await api.updateProspect(prospect.id, {
        ...prospect,
        owner_name: r.name,
        owner_age: r.age,
        owner_phone: r.phone,
      });
      onChange();
    } finally {
      setBusy(null);
    }
  }

  async function runPitch() {
    if (!prospect?.id || !prospect.annual_kwh) return;
    setBusy("pitch");
    setPitch(null);
    try {
      const kwh = prospect.annual_kwh ?? 0;
      const sek = Math.round(kwh * 1.5);
      const r = await api.generatePitch({
        owner_name: prospect.owner_name ?? "",
        address: prospect.address,
        annual_kwh: kwh,
        annual_sek: sek,
      });
      setPitch(r.pitch);
    } catch (e) {
      setPitch(`Fel: ${e instanceof Error ? e.message : "okänt"}`);
    } finally {
      setBusy(null);
    }
  }

  async function saveNotes() {
    if (!prospect?.id) return;
    setBusy("notes");
    try {
      await api.updateProspect(prospect.id, { ...prospect, notes: notesDraft });
      setEditingNotes(false);
      onChange();
    } finally {
      setBusy(null);
    }
  }

  function exportProspect() {
    if (!prospect) return;
    const content = `SOLAR UNIFIED — PROSPEKT RAPPORT
----------------------------------
Adress: ${prospect.address}
Status: ${prospect.status ?? "new"}
Årlig potential: ${prospect.annual_kwh ? Math.round(prospect.annual_kwh).toLocaleString("sv-SE") : "—"} kWh
Score: ${prospect.score?.toFixed(1) ?? "—"}

KONTAKTINFORMATION
------------------
Ägare: ${prospect.owner_name ?? "—"}
Ålder: ${prospect.owner_age ?? "—"}
Telefon: ${prospect.owner_phone ?? "—"}

ANTECKNINGAR
------------
${prospect.notes || "Inga anteckningar."}

Genererad: ${new Date().toLocaleString("sv-SE")}
`;
    const blob = new Blob([content], { type: "text/plain" });
    const url = URL.createObjectURL(blob);
    const a = document.createElement("a");
    a.href = url;
    a.download = `prospekt-${prospect.address.replace(/\s+/g, "-")}.txt`;
    a.click();
    URL.revokeObjectURL(url);
  }

  const currentStatus = prospect.status ?? "new";

  return (
    <aside className="overflow-y-auto border-l border-(--rule) p-4 text-sm">
      <div className="flex items-center justify-between gap-2">
        <h2 className="truncate text-base font-medium text-(--ink)">{prospect.address}</h2>
        <button
          onClick={exportProspect}
          title="Exportera till fil"
          className="rounded p-1 text-(--ink-60) hover:bg-(--paper-tint) hover:text-(--ink)"
        >
          <svg viewBox="0 0 24 24" width="16" height="16" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round">
            <path d="M21 15v4a2 2 0 0 1-2 2H5a2 2 0 0 1-2-2v-4" />
            <polyline points="7 10 12 15 17 10" />
            <line x1="12" y1="15" x2="12" y2="3" />
          </svg>
        </button>
      </div>

      <div className="mt-3 flex flex-wrap gap-1">
        {STATUS_OPTIONS.map((opt) => {
          const active = currentStatus === opt.value;
          return (
            <button
              key={opt.value}
              onClick={() => setStatus(opt.value)}
              disabled={busy !== null}
              title={`Tryck ${opt.key}`}
              className={`rounded px-2 py-0.5 text-xs transition-colors ${
                active
                  ? `bg-(${opt.color}) text-(--paper)`
                  : "bg-(--paper-tint) text-(--ink-60) hover:bg-(--rule)"
              }`}
            >
              {opt.label}
              <span className="ml-1 text-[10px] opacity-60">{opt.key}</span>
            </button>
          );
        })}
      </div>

      <dl className="mt-4 grid grid-cols-[auto_1fr] gap-x-3 gap-y-1 text-(--ink-60)">
        <dt className="text-(--ink-60)">kWh/år</dt>
        <dd>
          <DataField
            state={fromNullable(prospect.annual_kwh ?? null)}
            format={(v) => Math.round(Number(v)).toLocaleString("sv-SE")}
          />
        </dd>
        <dt className="text-(--ink-60)">Score</dt>
        <dd>
          <DataField
            state={fromNullable(prospect.score ?? null)}
            format={(v) => Number(v).toFixed(1)}
          />
        </dd>
        <dt className="text-(--ink-60)">Ägare</dt>
        <dd><DataField state={fromNullable(prospect.owner_name)} /></dd>
        <dt className="text-(--ink-60)">Ålder</dt>
        <dd><DataField state={fromNullable(prospect.owner_age)} /></dd>
        <dt className="text-(--ink-60)">Telefon</dt>
        <dd>
          {prospect.owner_phone ? (
            <a href={`tel:${prospect.owner_phone}`} className="text-(--amber) hover:underline">
              {prospect.owner_phone}
            </a>
          ) : (
            <DataField state={fromNullable(null as string | null)} />
          )}
        </dd>
      </dl>

      <div className="mt-4 flex flex-wrap gap-2">
        <button
          disabled={busy !== null}
          onClick={runSolar}
          className="rounded bg-(--forest)/20 px-3 py-1 text-(--forest) hover:bg-(--forest)/30 disabled:opacity-50"
        >
          {busy === "solar" ? "…" : "Hämta kWh/år"}
        </button>
        <button
          disabled={busy !== null}
          onClick={runEnrich}
          className="rounded bg-(--leaf)/20 px-3 py-1 text-(--leaf) hover:bg-(--leaf)/30 disabled:opacity-50"
        >
          {busy === "enrich" ? "…" : "Berika kontakt"}
        </button>
        <button
          disabled={busy !== null || !prospect.annual_kwh}
          onClick={runPitch}
          title={!prospect.annual_kwh ? "Kräver kWh/år" : ""}
          className="rounded bg-(--amber)/20 px-3 py-1 text-(--amber) hover:bg-(--amber)/30 disabled:opacity-50"
        >
          {busy === "pitch" ? "…" : "Generera pitch"}
        </button>
      </div>

      {pitch && (
        <div className="mt-3 rounded border border-(--rule) bg-(--paper-tint) p-3">
          <div className="caps mb-1">Pitch</div>
          <p className="whitespace-pre-wrap text-(--ink)">{pitch}</p>
          <button
            onClick={() => {
              void navigator.clipboard.writeText(pitch);
            }}
            className="mt-2 rounded bg-(--paper) px-2 py-0.5 text-xs text-(--ink) hover:bg-(--rule)"
          >
            Kopiera
          </button>
        </div>
      )}

      <section className="mt-5">
        <div className="flex items-center justify-between">
          <h3 className="text-xs uppercase tracking-wide text-(--ink-60)">Anteckningar</h3>
          {!editingNotes && (
            <button
              onClick={() => setEditingNotes(true)}
              className="rounded bg-(--paper-tint) px-2 py-0.5 text-xs text-(--ink) hover:bg-(--rule)"
            >
              Redigera
            </button>
          )}
        </div>
        {editingNotes ? (
          <div className="mt-2">
            <textarea
              autoFocus
              value={notesDraft}
              onChange={(e) => setNotesDraft(e.target.value)}
              className="h-24 w-full rounded bg-(--paper-tint) p-2 text-sm text-(--ink)"
            />
            <div className="mt-1 flex gap-1">
              <button
                disabled={busy !== null}
                onClick={saveNotes}
                className="rounded bg-(--amber)/20 px-3 py-1 text-xs text-(--amber) disabled:opacity-50"
              >
                {busy === "notes" ? "…" : "Spara"}
              </button>
              <button
                onClick={() => {
                  setEditingNotes(false);
                  setNotesDraft(prospect.notes ?? "");
                }}
                className="rounded bg-(--paper-tint) px-3 py-1 text-xs text-(--ink) hover:bg-(--rule)"
              >
                Avbryt
              </button>
            </div>
          </div>
        ) : (
          <p className="mt-1 whitespace-pre-wrap text-(--ink)">
            {prospect.notes || (
              <span className="italic text-(--ink-60)">Inga anteckningar än.</span>
            )}
          </p>
        )}
      </section>
    </aside>
  );
}
