# Issue Ledger Service Spec

## Public API

### Functions

- **`open_issue(*, error_type, target, title, tags=None, evidence=None) -> str`**
  Opens a new issue or touches an existing one. Returns a stable 12-char key.
  - `error_type`: High-level categorization of the failure.
  - `target`: The specific file, component, or address affected.

- **`log_attempt(*, key, hypothesis, change_summary, outcome, rationale_for_next=None, evidence=None, author="claude")`**
  Records a concrete fix attempt against an issue.
  - `outcome`: one of `success`, `failed`, `rejected_by_cove`, `blocked`, etc.

- **`resolve_issue(*, key, resolution_summary, evidence=None)`**
  Marks an issue as resolved. Skip subsequent automatic fix attempts.

- **`similar_attempts(error_type, target, hypothesis, threshold=0.6) -> list[dict]`**
  Searches for prior failed/rejected attempts for the same target that are semantically similar to the current hypothesis.
  - Uses a combination of Jaccard similarity and "containment" (to catch paraphrasing).

- **`find_issue(error_type, target) -> dict | None`**
  Retrieves the issue record for a specific error/target pair.

---

## Invariants

- **I1 [Stable Identification]**: Issue keys MUST be derived deterministically from the lowercase `error_type` and `target` using a stable hash (SHA-1 prefix).
- **I2 [Loop Prevention]**: Before executing a fix, agents SHOULD call `similar_attempts` to ensure they aren't repeating a hypothesis that was already rejected by CoVe or failed in a prior session.
- **I3 [Atomic Persistence]**: Updates to the ledger MUST be atomic (write-to-tmp then rename) to prevent JSON corruption during crashes.
- **I4 [Thread-Safe Access]**: All read/write operations on the ledger file MUST be protected by a global process lock (`_LOCK`).
- **I5 [Audit Trail Integrity]**: Past attempts MUST NOT be deleted or overwritten, even if an issue is reopened or resolved.
- **I6 [Paraphrase Awareness]**: The similarity engine MUST use "containment" logic ($prior \subseteq new$) to detect when a new hypothesis is just a more verbose restatement of a previously rejected one.
- **I7 [Automatic Recovery]**: If the ledger file becomes unreadable or corrupt, the service MUST log the error and initialize a fresh, empty ledger rather than crashing.
- **I8 [Idempotent Opening]**: Calling `open_issue` on a resolved issue MUST automatically flip its status back to `open` and record the reopening timestamp.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Agent tries same fix 5 times | `similar_attempts` returns 1.0 similarity; agent should skip after 1st attempt. | I2, I6 |
| Target path capitalization differs | Lowercased during key generation; maps to the same issue. | I1 |
| System crashes during `_save` | `.tmp` file remains; main ledger is untouched; `cleanup_stale_tmp` handles it on next load. | I3 |
| Hypothesis uses different words for same idea | Tokenization and Jaccard/Containment catch overlap (e.g. "Add UTF-8" vs "Support Unicode"). | I6 |
| `log_attempt` for unknown key | Log warning; do not raise exception. | I7 |
| Multiple sessions update ledger | Thread lock ensures sequential updates; JSON integrity preserved. | I4 |
