/**
 * DataField — render a DataState<string | number> with semantically distinct
 * UI per state (ok / pending / failed / notfound). Replaces ad-hoc `?? "—"`
 * patterns. Uses Solar Almanac design tokens (no slate, no Tailwind defaults).
 *
 * docs/BUGS.md Bug 4: a salesperson must be able to distinguish "data is
 * being fetched" from "fetch failed, retry" from "ran and found nothing".
 */

import type { DataState } from "../lib/dataState";

interface Props {
  state: DataState<string | number>;
  /** Format value before render — e.g. `(n) => n.toLocaleString("sv-SE")`. */
  format?: (v: string | number) => string;
  /** Optional inline-action; rendered next to the "Försök igen" button on `failed`. */
  onRetry?: () => void;
  /** Render-class passed through on the `ok` state for token-respecting alignment. */
  className?: string;
}

export default function DataField({ state, format, onRetry, className }: Props) {
  switch (state.kind) {
    case "ok": {
      const text = format ? format(state.value) : String(state.value);
      return <span className={className}>{text}</span>;
    }
    case "pending":
      return (
        <span
          className="caps"
          style={{ color: "var(--ink-60)", letterSpacing: "0.14em", fontStyle: "italic" }}
          aria-busy="true"
        >
          Hämtar…
        </span>
      );
    case "failed":
      return (
        <span style={{ color: "var(--barn)", display: "inline-flex", gap: "0.5rem", alignItems: "baseline" }}>
          <span style={{ fontStyle: "italic" }}>Misslyckades</span>
          {state.retryable && onRetry && (
            <button
              type="button"
              onClick={onRetry}
              className="caps"
              style={{
                fontSize: "var(--step--2)",
                color: "var(--barn)",
                background: "transparent",
                border: "none",
                padding: 0,
                textDecoration: "underline",
                cursor: "pointer",
              }}
              title={state.reason}
            >
              Försök igen
            </button>
          )}
        </span>
      );
    case "notfound":
      return (
        <span
          style={{ color: "var(--ink-60)", fontStyle: "italic" }}
          title="Ingen data registrerad"
        >
          Ej registrerad
        </span>
      );
  }
}
