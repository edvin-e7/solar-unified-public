# Analytics Service Spec

## Public API

### Functions

- **`track(event_name, *, subject_id, subject_type, family=None, score=None, region=None, **properties)`**
  Queues an event for asynchronous flushing to ClickHouse.
  - **Best-effort**: Returns immediately; does not raise on failure.

- **`async flush_now()`**
  Force-flushes any queued events to ClickHouse. Used during application shutdown.

---

## Invariants

- **I1 [Non-Blocking Design]**: Analytics operations MUST NOT block the main execution paths (scanning, enrichment); events MUST be buffered and flushed asynchronously.
- **I2 [PII-First Compliance]**: The `properties` dictionary MUST NOT contain raw prospect PII (names, phone numbers). Use `subject_id` (database ID) or hashes for tracking.
- **I3 [Silent Failure]**: If the ClickHouse server is unreachable, the service MUST fail silently to prevent service-level cascading failures.
- **I4 [Structured Logging]**: Flush failures MUST be recorded via `error_logger` for observability while maintaining the silent-to-caller contract.
- **I5 [Batch Efficiency]**: Events SHOULD be flushed in batches of up to 100 to minimize HTTP overhead.
- **I6 [Thread-Safe Queuing]**: Access to the internal event queue MUST be protected by a thread lock to prevent data corruption during high-concurrency ingestion.
- **I7 [Best-Effort Delivery]**: In environments without a running event loop (e.g., synchronous scripts), the service MUST spawn a daemon thread to perform the flush.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| ClickHouse server is down | `_flush` catches exception; logs to `error_logger`; queue is drained regardless. | I3, I4 |
| `properties` contains `"name": "Edvin"` | Violation of I2; should be caught by developer audit (service currently does not auto-redact). | I2 |
| Rapid sequential `track` calls | Queue grows under lock; `should_flush_now` triggers background task when limit reached. | I5, I6 |
| Shutdown before interval | Call `flush_now()` manually to ensure the final batch is sent. | I1 |
| HTTP timeout during flush | `httpx.TimeoutException` caught; events in current batch may be lost. | I7 |
| No network connection | Same as ClickHouse down; fails silently. | I3 |
