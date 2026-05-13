# `_bulk_import_csv_sync` — invariants

The bulk-paste flow is the most-trafficked ingest path: Edvin pastes a list
of Swedish addresses (typically copy-pasted from a CRM or a sheet). The
parser must preserve the address literally — including the comma between
street and city — or every prospect ends up geocoded to the wrong town.

## Public contract

`_bulk_import_csv_sync(payload: BulkCsvPayload) -> {"created": N, "skipped": M, "errors": [...]}`

Returns 422 on empty input. Errors list capped at 10 entries.

## Invariants

1. **Mode detection by literal header.** "Header mode" only when the first
   line, parsed as CSV, contains a column whose stripped lowercase value
   is exactly `address`. Anything else → address-per-line mode. No
   heuristics, no column-count guessing.
2. **Address-per-line mode preserves commas.** Each line in the input
   becomes one address string. "Storgatan 12, Falun" stays as the literal
   string `"Storgatan 12, Falun"`. The bug this replaces split it into
   `["Storgatan 12", " Falun"]` and stored only the first.
3. **Empty lines are skipped, not errored.** Trailing newlines, blank
   separator lines, accidental double newlines all increment `skipped`.
4. **Whitespace is trimmed per address.** Leading/trailing spaces and
   tabs are stripped; interior whitespace is preserved.
5. **Header mode supports `address`, `owner_name`, `owner_phone`, `notes`
   columns.** Other columns are ignored. Column order does not matter.
   Empty values map to SQL NULL.
6. **Created count counts successful inserts only.** SQLite errors append
   to `errors` and do NOT increment `created`.
7. **Errors carry 1-based row/line numbers.** Header mode uses "Row N+2"
   (header is row 1, data starts at 2); address-per-line uses "Line N+1".

## Adversarial matrix

See `backend/specs/test_bulk_csv.py`. Cases:

- single line, no comma → 1 created
- single line with comma `"Storgatan 12, Falun"` → 1 created, address kept whole
- multi-line address-per-line (Edvin's primary flow) → N created, all addresses include their cities
- header mode `address,owner_name\n...` → 1 created with owner populated
- header mode with extra/unknown columns → unknown columns ignored
- BOM at start of input → handled
- CRLF line endings → handled
- empty input → 422
- whitespace-only input → 422
- input that's only blank lines → 0 created, all skipped
- malformed unicode → caller's bytes preserved
- duplicate address → relies on UNIQUE constraint to error (covered by SQL layer test)
