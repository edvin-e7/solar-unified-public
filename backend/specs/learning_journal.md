# Learning Journal Service Spec

## Public API

### Functions

- **`record(phase: str, outcome: Outcome, lesson: str, *, files=None, error=None, metadata=None)`**
  Appends a new entry to the learning journal and triggers a summary regeneration.
  - Automatically sanitizes PII (emails, Swedish phone numbers) in `lesson`, `error`, and `metadata`.

- **`redact_lines(replacements: dict[str, str]) -> dict[str, int]`**
  Surgically replaces substrings in the journal in-place. Used to prune accidental PII leaks.
  - **Audit Trail**: Logs a hashed summary of the redaction back into the journal.

- **`entries() -> list[dict]`**
  Retrieves the full list of journal entries as a list of dictionaries.

### Data Types

- **`Outcome` (Literal)**: `passed`, `failed`, `error`, `no_op`.

---

## Invariants

- **I1 [Append-Only JSONL]**: The primary storage MUST be a JSONL file (`journal.jsonl`) to ensure high-performance concurrent appends and easy stream processing.
- **I2 [Automatic PII Sanitization]**: Every `record` call MUST pass through a PII filter that redacts emails and Swedish phone numbers before the data hits the disk.
- **I3 [Digest Generation]**: Every successful `record` call MUST trigger the regeneration of `summary.md` to provide a human-and-LLM-readable view of the last 20 successes and failures.
- **I4 [Atomic Redaction]**: `redact_lines` MUST use an atomic write (temp-file + replace) to prevent journal corruption if the process is interrupted during redaction.
- **I5 [Surgical Integrity]**: Redaction MUST preserve the original JSON structure, line order, and timestamps, only modifying the target substrings.
- **I6 [PII-First Audit]**: The audit log for a redaction MUST NOT include the original PII substrings; it MUST use truncated SHA-256 hashes to represent the replaced patterns.
- **I7 [Safe Reading]**: Reading functions MUST gracefully skip malformed JSON lines to remain resilient against accidental manual edits to the JSONL file.
- **I8 [Outcome Normalization]**: Failures MUST be clearly categorized as `failed` (logic failed) vs `error` (exception/crash) to allow for nuanced pattern analysis.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `lesson` contains a name and email | Email is redacted to `<EMAIL_REDACTED>`; name is preserved (not auto-redacted). | I2 |
| `journal.jsonl` contains 10,000 lines | `_regenerate_summary` reads the whole file but only exports the top 20 of each type. | I3 |
| Power failure during `redact_lines` | Original journal is either fully updated or unchanged; `.tmp` file might be left behind. | I4 |
| Redaction pattern is empty string | Raises `ValueError`. | I5 |
| User manually deletes a line | System continues to work; `entries()` simply returns one fewer record. | I7 |
| Non-breaking space in phone number | Regex `\s?` and `[\d\s-]` patterns catch common Swedish formatting variations. | I2 |
