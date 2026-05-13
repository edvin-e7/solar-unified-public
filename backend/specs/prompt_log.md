# Prompt Log Service Spec

## Public API

### Functions

- **`record_prompt(*, model, phase, prompt, response, response_kind, latency_ms, error=None, image_attached=False, metadata=None)`**
  Logs the full interaction with an LLM to `prompts_log.jsonl`.
  - Automatically redacts PII before writing.

- **`tail(limit: int = 50) -> list[dict]`**
  Retrieves the most recent interaction logs.

- **`errors_only(limit: int = 100) -> list[dict]`**
  Retrieves the most recent failed interaction logs.

---

## Invariants

- **I1 [PII Redaction]**: Every log entry MUST be passed through a redaction filter that masks Swedish phone numbers, personnummer, and emails using stable hashes.
- **I2 [Metadata Sanitization]**: Metadata keys matching PII patterns (e.g., `name`, `address`, `email`) MUST have their values hashed rather than stored in plaintext.
- **I3 [Full Signal Preservation]**: Prompts and responses MUST NOT be truncated (except for PII masking) to ensure enough signal remains for debugging complex logic failures.
- **I4 [Append-Only JSONL]**: Interaction logs MUST be stored in JSONL format for efficient appending and stream-based analysis.
- **I5 [Audit Timestamps]**: Every entry MUST include a UTC ISO-8601 timestamp.
- **I6 [Atomic Sync Writes]**: Writing to the prompt log SHOULD use synchronous appends with file system locking to guarantee line integrity in multi-process environments.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Prompt contains a Swedish phone number | Replaced with `<phone:hash8>`. | I1 |
| Metadata contains `"name": "Edvin Pierre"` | Replaced with `"name": "<name:hash8>"`. | I2 |
| LLM returns 4,000 tokens | Logged in full; line length grows but no truncation applied. | I3 |
| Concurrent agent calls | `append_jsonl_sync` ensures each JSON object is a single, clean line. | I6 |
| Disk space exhausted | Logs warning to stderr; does not crash the application. | I6 |
| `response_kind` = "error" | Entry includes `error` message; `response` is likely `null`. | I4 |
