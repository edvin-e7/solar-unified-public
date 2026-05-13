# Detection Label Logging Service Spec

## Public API

### Functions

- **`record_inference(*, image_path, backend, has_panels, confidence, inference_ms, address=None)`**
  Logs a single model inference result to `inferences.jsonl`.
  - `image_path`: Path to the image file analyzed.
  - `backend`: Name of the detection backend used.
  - `has_panels`: Model's boolean verdict.
  - `confidence`: Model's confidence score (0.0 to 1.0).
  - `inference_ms`: Time taken for inference.
  - `address`: Optional physical address associated with the image.

- **`record_label(*, image_path, has_panels_truth, source="user", note="")`**
  Logs a ground-truth label (usually from a human or high-confidence agent) to `labels.jsonl`.
  - `has_panels_truth`: The known ground truth.
  - `source`: Origin of the label (default: "user").
  - `note`: Optional text description (truncated to 200 chars).

- **`label_count() -> int`**
  Returns the total number of labels recorded.

- **`inference_count() -> int`**
  Returns the total number of inferences recorded.

---

## Invariants

- **I1 [Append-Only JSONL]**: All logs MUST use the JSONL format (newline-delimited JSON) to allow for efficient appends and stream processing.
- **I2 [Concurrent Safety]**: File write operations MUST be protected by a global thread lock to prevent line corruption during simultaneous calls.
- **I3 [Directory Management]**: The service MUST automatically create the target data directory if it is missing before the first write.
- **I4 [UTF-8 Integrity]**: Files MUST be opened with `utf-8` encoding, and JSON serialization MUST use `ensure_ascii=False` to preserve international characters.
- **I5 [Audit Timestamps]**: Every log entry MUST include a Unix timestamp (`ts`) for traceability and training set ordering.
- **I6 [Note Sanitization]**: User-provided notes MUST be truncated to 200 characters to prevent malicious or accidental log bloat.
- **I7 [Precise Numerics]**: Confidence scores MUST be rounded to 4 decimal places, and timing MUST be stored as integers to maintain a consistent log schema.
- **I8 [Resilient Reading]**: Count functions MUST return `0` gracefully if the log files have not yet been created.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Parallel `record_inference` calls | All lines appended correctly without interleaving. | I2 |
| Data directory deleted | Re-created on next write call. | I3 |
| Note with 10,000 characters | Truncated to 200; log remains stable. | I6 |
| Address contains emojis | Logged correctly as UTF-8. | I4 |
| `label_count()` called on new install | Returns 0; does not raise error. | I8 |
| Confidence is `NaN` or `Inf` | `float()` conversion or `json.dumps` might fail; should be validated upstream, but service rounds raw input. | I7 |
