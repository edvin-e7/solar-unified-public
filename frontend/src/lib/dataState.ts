/**
 * DataState<T> — discriminated union for fields that may be missing for
 * multiple distinguishable reasons.
 *
 * Solves docs/BUGS.md Bug 4: ProspectCard rendered "—" for null values
 * with no way to distinguish "pipeline hasn't run yet" from "pipeline ran
 * but failed" from "pipeline ran and nothing was found". A solar-sales rep
 * looking at the dashboard could not trust any row.
 *
 * Foundation PR — backend still returns plain T | null. The conversion
 * function `fromNullable()` defaults all nulls to "notfound" (the safest
 * interpretation until backend supplies explicit per-field
 * `enrichment_status`). When backend lands per-field status, callers can
 * use the typed variants directly without touching the rendering layer.
 */

export type DataState<T> =
  | { kind: "ok"; value: T }
  | { kind: "pending" }
  | { kind: "failed"; reason: string; retryable: boolean }
  | { kind: "notfound" };

/**
 * Convert a plain `T | null | undefined` to a DataState.
 *
 * Default semantics: non-null/undefined → ok, otherwise → notfound. This is
 * the conservative default until the backend supplies explicit per-field
 * enrichment_status — calls render an italic "Ej registrerad" instead of
 * "—" without any backend change.
 */
export function fromNullable<T>(value: T | null | undefined): DataState<T> {
  if (value === null || value === undefined) return { kind: "notfound" };
  return { kind: "ok", value };
}

/**
 * Convert an explicit per-field status (future backend shape) to DataState.
 *
 * Expected shape when backend lands:
 *   { value: T | null, enrichment_status: "ok" | "pending" | "failed" | "notfound",
 *     error_reason?: string, retryable?: boolean }
 */
export function fromBackendStatus<T>(input: {
  value: T | null | undefined;
  enrichment_status?: "ok" | "pending" | "failed" | "notfound";
  error_reason?: string;
  retryable?: boolean;
}): DataState<T> {
  const status = input.enrichment_status;
  if (status === "pending") return { kind: "pending" };
  if (status === "failed") {
    return {
      kind: "failed",
      reason: input.error_reason ?? "Okänt fel",
      retryable: input.retryable ?? false,
    };
  }
  if (status === "notfound") return { kind: "notfound" };
  // Default + explicit "ok": treat non-null as ok, null as notfound
  return fromNullable(input.value);
}
