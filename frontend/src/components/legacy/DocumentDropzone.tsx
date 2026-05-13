// MIGRATED 2026-04-21 from edvins-solprojekt-sandbox. Not wired into the app yet — imported on-demand when the Phase 20 Dokument tab (DocumentDropzone) / bulk enrichment (MrkollScraper) / onboarding (Tour) are built. May use slate-* / non-Solar-Almanac tokens — must retokenize before use.

// TODO: the following imports reference paths from the legacy sandbox project
// that do not exist in solar-unified. Resolve before wiring this component in
// (port or rewrite `services/agent.ingestDocuments` and `useProspects.SeedItem`).
import { useCallback, useRef, useState } from "react";
import {
  ingestDocuments,
  type DocIngestFileResult,
  type DocIngestResponse,
} from "../services/agent";
import type { SeedItem } from "../hooks/useProspects";

type Props = {
  onSeeds: (items: SeedItem[]) => void;
  disabled?: boolean;
};

const recordsToSeeds = (records: DocIngestResponse["prospects"]): SeedItem[] => {
  const out: SeedItem[] = [];
  for (const r of records) {
    const address = typeof r.address === "string" ? r.address : "";
    if (!address) continue;
    const seed: SeedItem = {
      address,
      name: typeof r.name === "string" ? r.name : "",
      phone: typeof r.phone === "string" ? r.phone : "",
      region: typeof r.region === "string" ? r.region : "",
      notes: typeof r.notes === "string" ? r.notes : undefined,
      panels_detected: typeof r.panels_detected === "boolean" ? r.panels_detected : false,
      panels_confidence: typeof r.panels_confidence === "number" ? r.panels_confidence : null,
      lat: typeof r.lat === "number" ? r.lat : null,
      lng: typeof r.lng === "number" ? r.lng : null,
    };
    out.push(seed);
  }
  return out;
};

export function DocumentDropzone({ onSeeds, disabled }: Props) {
  const [uploading, setUploading] = useState(false);
  const [fileResults, setFileResults] = useState<DocIngestFileResult[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [dragOver, setDragOver] = useState(false);
  const inputRef = useRef<HTMLInputElement>(null);

  const handleFiles = useCallback(
    async (files: FileList | File[]) => {
      const arr = Array.from(files);
      if (arr.length === 0) return;
      setUploading(true);
      setError(null);
      try {
        const res = await ingestDocuments(arr);
        setFileResults(res.files);
        const seeds = recordsToSeeds(res.prospects);
        if (seeds.length > 0) onSeeds(seeds);
      } catch (err) {
        setError(err instanceof Error ? err.message : "Okänt fel");
      } finally {
        setUploading(false);
      }
    },
    [onSeeds],
  );

  const onDrop = useCallback(
    (e: React.DragEvent<HTMLLabelElement>) => {
      e.preventDefault();
      setDragOver(false);
      if (disabled || uploading) return;
      if (e.dataTransfer.files?.length) {
        void handleFiles(e.dataTransfer.files);
      }
    },
    [disabled, uploading, handleFiles],
  );

  const totalSeeds = fileResults.reduce((sum, f) => sum + f.seeds, 0);

  return (
    <section
      className="rounded-2xl border border-white/10 bg-white/[0.03] p-4"
      data-tour="document-dropzone"
    >
      <div className="mb-2 flex items-center justify-between">
        <h3 className="text-xs uppercase tracking-wider text-amber-300/80">📁 Dokumentimport</h3>
        <span className="text-[10px] text-white/40">CSV · JSON · TXT · bild · PDF*</span>
      </div>
      <label
        onDragOver={(e) => {
          e.preventDefault();
          if (!disabled && !uploading) setDragOver(true);
        }}
        onDragLeave={() => setDragOver(false)}
        onDrop={onDrop}
        className={`flex cursor-pointer flex-col items-center justify-center gap-2 rounded-xl border-2 border-dashed px-3 py-6 text-center text-xs transition ${
          dragOver
            ? "border-amber-400/70 bg-amber-400/10 text-amber-200"
            : "border-white/15 bg-black/20 text-white/60 hover:border-amber-400/40 hover:text-amber-200"
        } ${disabled || uploading ? "pointer-events-none opacity-50" : ""}`}
      >
        <span className="text-xl">⬆</span>
        <span>
          {uploading
            ? "Sorterar & kör genom agenter…"
            : "Släpp filer här eller klicka för att välja"}
        </span>
        <span className="text-[10px] text-white/35">
          Körs genom detect + pattern + scoring · seedas automatiskt
        </span>
        <input
          ref={inputRef}
          type="file"
          multiple
          accept=".csv,.tsv,.json,.txt,.pdf,image/*"
          className="hidden"
          disabled={disabled || uploading}
          onChange={(e) => {
            if (e.target.files) void handleFiles(e.target.files);
            if (inputRef.current) inputRef.current.value = "";
          }}
        />
      </label>

      {error && (
        <div className="mt-2 rounded-lg border border-red-400/30 bg-red-400/5 px-3 py-2 text-xs text-red-200/85">
          {error}
        </div>
      )}

      {fileResults.length > 0 && (
        <div className="mt-3 space-y-1">
          <div className="text-[10px] uppercase tracking-wider text-white/40">
            Resultat · {totalSeeds} prospekt tillagda
          </div>
          {fileResults.map((f) => (
            <div
              key={f.filename}
              className="flex items-center justify-between gap-2 rounded-md border border-white/5 bg-black/20 px-2 py-1 text-[11px]"
            >
              <span className="truncate text-white/80" title={f.filename}>
                {f.type === "pdf"
                  ? "📄"
                  : f.type.startsWith("j") || f.type.startsWith("p")
                    ? "🖼"
                    : "📑"}{" "}
                {f.filename}
              </span>
              <span
                className={
                  f.status === "ok" ? "shrink-0 text-amber-300/80" : "shrink-0 text-red-300/70"
                }
                title={f.hint ?? f.error ?? f.status}
              >
                {f.status === "ok"
                  ? `${f.seeds} rader`
                  : f.status === "pdf_unsupported"
                    ? "PDF ej stödd"
                    : f.status}
              </span>
            </div>
          ))}
        </div>
      )}
    </section>
  );
}
