# Agent Insights Service Spec

## Public API

### Functions

- **`get_cached(insight_type: str) -> dict[str, Any] | None`**
  Retrieves a valid (non-expired) insight of the given type from the SQLite cache.
  - **Returns**: The JSON payload if a fresh entry exists, else `None`.

- **`store(insight_type: str, payload: dict[str, Any], ttl_hours: int = 24) -> None`**
  Persists a new insight to the cache with a specified Time-To-Live (TTL).

---

## Invariants

- **I1 [SQLite Persistence]**: Insights MUST be stored in a local SQLite database (`prospects.db`) to survive application restarts and minimize re-generation costs.
- **I2 [Automatic Expiry]**: Every insight MUST have an `expires_at` timestamp; `get_cached` MUST filter out any entries where `expires_at` is in the past.
- **I3 [JSON Serialization]**: The `payload` MUST be stored as a JSON-serialized string with UTF-8 characters preserved (`ensure_ascii=False`).
- **I4 [Efficient Retrieval]**: The database MUST maintain a composite index on `(insight_type, expires_at)` to ensure fast lookups even as the cache grows.
- **I5 [Idempotent Initialization]**: The service MUST automatically create the `agent_insights` table and its associated index if they are missing on first connection.
- **I6 [Thread-Safe Connections]**: The service MUST open and close a fresh SQLite connection for each operation to ensure thread safety without long-lived locks.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Database file deleted | Re-created on next call; table initialized; returns `None`. | I5 |
| Insight expired 1 second ago | `get_cached` returns `None`. | I2 |
| Extremely large JSON payload | SQLite `TEXT` column handles it; `json.loads` might be slow but remains correct. | I3 |
| Concurrent `store` calls | SQLite's file-level locking manages sequential writes. | I6 |
| Clock skew (future timestamps) | `generated_at` uses system clock; system is sensitive to significant clock drift. | I2 |
