# Error Logger Service Spec

## Public API

### Functions

- **`log_error(phase: str, exc: BaseException, *, context: dict | None = None, severity: str = "error")`**
  Records a caught exception to both the `learning_journal` and a dedicated `errors.jsonl`.
  - `phase`: The logical part of the system where the error occurred (e.g., "api-enrich").
  - `exc`: The exception object.
  - `context`: Additional metadata to help with triage.
  - `severity`: "error" (default) or "swallow" (for non-critical failures).

- **`log_scope(phase: str, **context) -> ContextManager`** / **`log_scope_async(...)`**
  Wraps a block of code; any exception raised within the block is logged and then re-raised.

- **`log_and_swallow(phase: str, fallback: T, **context: Any) -> Decorator`**
  A decorator that logs any exception and returns a pre-defined fallback value instead of raising.

- **`recent_errors(limit: int = 50) -> list[dict]`**
  Retrieves the most recent error logs for use in dashboards or telemetry.

---

## Invariants

- **I1 [No Silent Catches]**: The system MUST NOT use empty `except Exception: pass` blocks; any caught exception meant to be handled SHOULD be passed through `log_error` or `log_and_swallow`.
- **I2 [Double Recording]**: Every logged error MUST be recorded in both `errors.jsonl` (for low-level triage) and `learning_journal` (for high-level autonomous pattern analysis).
- **I3 [Traceback Preservation]**: Logged errors MUST include a full formatted traceback to facilitate remote post-mortems.
- **I4 [UTF-8 Safety]**: Error logs MUST be written and read as UTF-8, with `log.exception` fallbacks if the primary write fails.
- **I5 [Context Preservation]**: Arbitrary `**kwargs` passed to decorators or context managers MUST be preserved in the `context` field of the log entry.
- **I6 [Atomic Record Keeping]**: Failures in the logging system itself (e.g., disk full) MUST NOT crash the main application; they SHOULD be caught and reported via standard `logging`.
- **I7 [Outcome-Based Reporting]**: Errors recorded in the `learning_journal` MUST always have `outcome="error"` to distinguish them from valid system logic branches.
- **I8 [Non-Critical Triage]**: Swallowed errors MUST be explicitly marked with `severity="swallow"` to allow filtering in error dashboards.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Disk is full | `append_jsonl_sync` catches `OSError`; logs failure to stderr; app continues. | I6 |
| `KeyboardInterrupt` | Re-raises immediately; not caught by decorators/managers using `except Exception`. | I2 |
| Corrupt line in `errors.jsonl` | `recent_errors` skips the line via `json.JSONDecodeError` catch. | I4 |
| High-concurrency errors | Multiple threads/processes appending; file system locking ensures line integrity. | I4 |
| Exception has no message | `str(exc)` returns empty string; log remains valid. | I3 |
| Nested `log_scope` | Both levels log the same error with different `phase` tags. | I5 |
