// MIGRATED 2026-04-21 from edvins-solprojekt-sandbox. Not wired into the app yet — imported on-demand when the Phase 20 Dokument tab (DocumentDropzone) / bulk enrichment (MrkollScraper) / onboarding (Tour) are built. May use slate-* / non-Solar-Almanac tokens — must retokenize before use.

// TODO: the following imports reference paths from the legacy sandbox project
// that do not exist in solar-unified. Resolve before wiring this component in
// (port or rewrite `useProspects`, `PersonEnrichment`, `lookupLinks`,
// `services/enrichment`, `utils/phone`, and the `window.solprojektApi` IPC).
import { useState } from "react";
import type { Prospect } from "../hooks/useProspects";
import type { PersonEnrichment } from "../global";
import { extractCity } from "../utils/lookupLinks";
import { enrichPerson } from "../services/enrichment";
import { mergePhones } from "../utils/phone";

type EnrichPatch = Partial<
  Pick<
    Prospect,
    | "phone"
    | "phones"
    | "notes"
    | "name"
    | "address"
    | "age"
    | "personalNumber"
    | "enrichmentSource"
    | "enrichedAt"
  >
>;

// Kept the old export name so existing imports (ProspectRow) don't churn;
// internally this is now a multi-source enricher (mrkoll + hitta via
// `services/enrichment.ts`). Browser/PWA mode renders nothing because both
// scrapers live in the Electron main process.
export function MrkollScraper({
  prospect,
  onApply,
}: {
  prospect: Prospect;
  onApply: (patch: EnrichPatch) => void;
}) {
  const api = window.solprojektApi;
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<PersonEnrichment | null>(null);

  if (!api) return null;

  const city = extractCity(prospect.address);

  async function run(e: React.MouseEvent) {
    e.stopPropagation();
    setLoading(true);
    setResult(null);
    const hit = await enrichPerson({
      name: prospect.name || prospect.address.split(",")[0],
      phone: prospect.phone,
      city,
    });
    setResult(hit);
    setLoading(false);
  }

  function applyResult(r: PersonEnrichment) {
    const patch: EnrichPatch = {
      enrichmentSource: r.source,
      enrichedAt: Date.now(),
    };
    // Union every discovered number into prospect.phones (dedup on canonical
    // digit form in mergePhones). The user wants all numbers — different
    // sources surface different slices of the phone graph.
    if (r.phones?.length) {
      const nextPhones = mergePhones(prospect.phones, r.phones);
      if (nextPhones.length !== prospect.phones.length) {
        patch.phones = nextPhones;
      }
    }
    if (r.name && !prospect.name) {
      patch.name = r.name;
    }
    // Only overwrite address when the current one is a coord-fallback; a real
    // street address (from reverseGeocode / scan) is more canonical than the
    // free-text bio line from mrkoll/hitta.
    if (r.address && /·\s*-?\d+\.\d+/.test(prospect.address)) {
      patch.address = r.address;
    }
    if (r.age && !prospect.age) {
      patch.age = r.age;
    }
    // Only overwrite personalNumber if it's empty; the masked form is better
    // than nothing but never clobbers a full 12-digit PN (paid/manual entry).
    if (r.personalNumberMasked && !prospect.personalNumber) {
      patch.personalNumber = r.personalNumberMasked;
    }
    const tag =
      `[${r.source}] ${r.name ?? ""}${r.age ? ` (${r.age} år)` : ""}${r.personalNumberMasked ? ` · ${r.personalNumberMasked}` : ""}${r.phones?.length ? ` · ${r.phones.join(", ")}` : ""}${r.address ? ` · ${r.address}` : ""}`.trim();
    patch.notes = [prospect.notes, tag].filter(Boolean).join(" | ");
    onApply(patch);
  }

  const hasHit = result && result.source !== "none";
  const hasError = result && result.source === "none";

  return (
    <>
      <button
        type="button"
        onClick={run}
        disabled={loading}
        className="rounded-lg border border-amber-400/30 bg-amber-400/10 px-3 py-1.5 text-xs text-amber-200 transition hover:border-amber-400/60 hover:bg-amber-400/20 disabled:opacity-50"
      >
        {loading ? "Söker…" : "Hämta personinfo"}
      </button>
      {hasError && (
        <div
          className="mt-2 w-full rounded-lg border border-red-400/30 bg-red-400/5 p-2 text-xs text-red-200"
          onClick={(e) => e.stopPropagation()}
        >
          {result!.error ?? "Inga träffar"}
        </div>
      )}
      {hasHit && (
        <div className="mt-2 w-full" onClick={(e) => e.stopPropagation()}>
          <div className="rounded-lg border border-white/10 bg-black/30 p-3 text-xs text-white/80">
            <div className="flex items-start justify-between gap-2">
              <div className="min-w-0 flex-1">
                {result!.name && (
                  <div className="text-sm font-medium text-white">
                    {result!.name}
                    {result!.age && <span className="ml-2 text-white/50">{result!.age} år</span>}
                    <span className="ml-2 rounded border border-white/20 px-1.5 py-0.5 text-[9px] uppercase tracking-wider text-white/50">
                      {result!.source}
                    </span>
                  </div>
                )}
                {result!.address && <div className="text-white/60">{result!.address}</div>}
                {result!.personalNumberMasked && (
                  <div className="font-mono text-[11px] text-white/50">
                    🆔 {result!.personalNumberMasked}
                  </div>
                )}
                {result!.phones && result!.phones.length > 0 && (
                  <div className="text-amber-300/90">📞 {result!.phones.join(", ")}</div>
                )}
                {!result!.name && !result!.address && result!.snippet && (
                  <div className="text-white/50">{result!.snippet}</div>
                )}
              </div>
              <button
                type="button"
                onClick={(e) => {
                  e.stopPropagation();
                  applyResult(result!);
                }}
                className="shrink-0 rounded border border-amber-400/40 bg-amber-400/10 px-2 py-1 text-[10px] uppercase tracking-wider text-amber-200 hover:bg-amber-400/20"
              >
                Använd
              </button>
            </div>
          </div>
        </div>
      )}
    </>
  );
}
