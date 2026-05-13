# Orchestrator Service Spec

## Public API

### Classes

#### `Orchestrator`
The central coordinator for the 8-executor autonomous cycle.
- **`async run_data_gathering_cycle(addresses: list[str]) -> dict`**: Executes the data gathering phase (fetch → enrich → validate → journal).
- **`async run_learning_cycle() -> dict`**: Executes the autonomous learning phase (detect → generate → verify → apply).
- **`async run_full_cycle(addresses: list[str] | None = None) -> dict`**: Runs both phases in sequence.

---

## Invariants

- **I1 [Executor Coordination]**: The Orchestrator MUST manage the dependencies between the 8 specialized executors (Fetcher, Enrichment, Validator, Journaler, Pattern, Generator, Verifier, Applicator).
- **I2 [Safe Learning State]**: If the `collective_verify` step identifies infrastructure degradation (e.g., LLM errors), the Orchestrator MUST skip writing to the `issue_ledger` for that attempt to prevent poisoning the "already tried" filter.
- **I3 [Atomic Issue Management]**: Every learning cycle MUST attempt to `open_issue` and `log_attempt` for each improvement candidate to ensure perfect traceability.
- **I4 [Non-Blocking Resilience]**: Errors in non-critical lifecycle steps (e.g., writing to the ledger, journaling) MUST NOT crash the overall cycle; they MUST be caught and logged via `error_logger`.
- **I5 [Outcome Accountability]**: The final state of every improvement attempt (success, failed, rejected, or infra-degraded) MUST be explicitly journaled and logged in the ledger.
- **I6 [Paraphrase Visibility]**: Suggestions that are skipped because they were "already tried" MUST still be journaled to make the work of the anti-brainrot filter visible to developers.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Gemini 429 during verification | `llm_errors` populated; Orchestrator journals "infra-degradation"; `issue_ledger` is NOT updated. | I2 |
| `open_issue` fails (DB lock) | `_safe_open_issue` catches exception; logs error; cycle continues without ledger tracking for that item. | I4 |
| All addresses invalid in batch | `DataValidator` reports 0% quality; `Journaler` records failure; learning phase still proceeds. | I1 |
| Successive cycles with same bug | `improvement_gen` filters out "already tried" candidates; `orchestrator` journals the skips. | I6 |
| Git push fails after verification | `log_attempt` records `outcome="failed"`; `apply_error` included in evidence. | I5 |
| `PatternDetector` finds 0 patterns | Learning cycle exits early with `patterns_found: 0`. | I1 |
