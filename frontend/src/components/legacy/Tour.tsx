// MIGRATED 2026-04-21 from edvins-solprojekt-sandbox. Not wired into the app yet — imported on-demand when the Phase 20 Dokument tab (DocumentDropzone) / bulk enrichment (MrkollScraper) / onboarding (Tour) are built. May use slate-* / non-Solar-Almanac tokens — must retokenize before use.

import { useLayoutEffect, useEffect, useState } from "react";

export type TourStep = {
  id: string;
  title: string;
  body: string;
};

type Props = {
  steps: TourStep[];
  onClose: () => void;
};

type Rect = { top: number; left: number; width: number; height: number };

const PADDING = 8;

export function Tour({ steps, onClose }: Props) {
  const [index, setIndex] = useState(0);
  const [rect, setRect] = useState<Rect | null>(null);
  const step = steps[index];

  // Measure the highlighted element after it mounts. setRect is unavoidable
  // here — we depend on DOM layout from an element queried by selector, which
  // has no React-observable changes to subscribe to.
  /* eslint-disable react-hooks/set-state-in-effect */
  useLayoutEffect(() => {
    if (!step) return;
    const el = document.querySelector<HTMLElement>(`[data-tour="${step.id}"]`);
    if (!el) {
      setRect(null);
      return;
    }
    el.scrollIntoView({ behavior: "smooth", block: "center" });
    const r = el.getBoundingClientRect();
    setRect({
      top: r.top - PADDING,
      left: r.left - PADDING,
      width: r.width + PADDING * 2,
      height: r.height + PADDING * 2,
    });
  }, [step]);
  /* eslint-enable react-hooks/set-state-in-effect */

  useEffect(() => {
    function onKey(e: KeyboardEvent) {
      if (e.key === "Escape") onClose();
      else if (e.key === "ArrowRight" || e.key === "Enter") {
        if (index + 1 < steps.length) setIndex(index + 1);
        else onClose();
      } else if (e.key === "ArrowLeft") {
        if (index > 0) setIndex(index - 1);
      }
    }
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [index, steps.length, onClose]);

  if (!step) return null;

  const last = index === steps.length - 1;
  const tooltipTop = rect ? rect.top + rect.height + 12 : 100;
  const tooltipLeft = rect ? Math.max(16, rect.left) : 16;

  return (
    <div className="fixed inset-0 z-50" onClick={onClose} role="presentation">
      <div className="absolute inset-0 bg-black/70" />
      {rect && (
        <div
          className="absolute rounded-xl border-2 border-amber-400 shadow-[0_0_0_9999px_rgba(0,0,0,0.65)] transition-all duration-200"
          style={{
            top: rect.top,
            left: rect.left,
            width: rect.width,
            height: rect.height,
          }}
        />
      )}
      <div
        className="absolute max-w-sm rounded-2xl border border-amber-400/40 bg-slate-900/95 p-4 text-sm text-white shadow-xl"
        style={{ top: tooltipTop, left: tooltipLeft }}
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-1 flex items-center justify-between gap-3">
          <span className="text-[10px] uppercase tracking-wider text-amber-300">
            Steg {index + 1} / {steps.length}
          </span>
          <button
            type="button"
            onClick={onClose}
            className="text-xs text-white/50 hover:text-white"
          >
            Hoppa över
          </button>
        </div>
        <h4 className="mb-1 text-base font-semibold text-amber-200">{step.title}</h4>
        <p className="mb-3 text-white/80">{step.body}</p>
        <div className="flex items-center justify-between gap-2">
          <button
            type="button"
            onClick={() => setIndex(Math.max(0, index - 1))}
            disabled={index === 0}
            className="rounded-lg border border-white/15 px-3 py-1 text-xs text-white/70 hover:bg-white/10 disabled:opacity-30"
          >
            Tillbaka
          </button>
          <button
            type="button"
            onClick={() => (last ? onClose() : setIndex(index + 1))}
            className="rounded-lg bg-amber-400 px-3 py-1 text-xs font-medium text-black hover:bg-amber-300"
          >
            {last ? "Klart" : "Nästa"}
          </button>
        </div>
      </div>
    </div>
  );
}
