# Agent Base Specification

## Public API

### Classes

#### `BaseAgent`
The abstract foundation for all prompt-driven agents in the system.
- **`async run(**kwargs) -> Any`**: The primary lifecycle method. Sets state to `OBSERVING`, executes the agent's specific logic, and then classifies the resulting state.
- **`status() -> dict`**: Returns the current operational metrics of the agent (state, total suggestions, total auto-full actions).
- **`_classify_state(result: Any) -> AgentState`**: Subclass hook to map outputs to the lifecycle enum.

#### `Coordinator`
A singleton manager that orchestrates all specialized agents.
- **`run_with_verification(agent_name: str, **kwargs) -> (bool, Any, dict)`**: Executes an agent and applies Chain-of-Verification (CoVe) if the agent reaches the `AUTO_FULL` state.
- **`leaderboard() -> list`**: Ranks agents based on their autonomous activity (weighted sum of suggestions and auto-full actions).

### Enums

- **`AgentState`**:
  - `IDLE`: No current activity.
  - `OBSERVING`: Actively processing inputs.
  - `SUGGESTING`: Providing a recommendation for human review.
  - `AUTO_LOW`: Executing low-risk automated tasks.
  - `AUTO_FULL`: Executing high-risk automated tasks (requires CoVe).

---

## Invariants

- **I1 [Lifecycle Escalation]**: Every agent MUST follow the state escalation path: `OBSERVING` $\rightarrow$ `SUGGESTING` / `AUTO_LOW` / `AUTO_FULL`.
- **I2 [Verification Gate]**: Any agent result classified as `AUTO_FULL` MUST be verified via `verify_agent_decision` before being considered final.
- **I3 [Agent-Specific Thresholds]**: Verification MUST use agent-specific confidence thresholds (e.g., `detection` = 0.80, `quality` = 0.90) to reflect the risk profile of each agent's domain.
- **I4 [Audit Logging]**: Every agent run MUST be recorded as an `AgentRun` object, and all `AUTO_FULL` verification outcomes MUST be logged to the `learning_journal`.
- **I5 [Memory Constraints]**: To prevent memory bloat, each agent instance MUST only retain the most recent 50 `AgentRun` records.
- **I6 [Contextual Awareness]**: Agents SHOULD use `_get_recent_lessons()` to inject recent working patterns from the learning journal into their prompts, preventing repetitive errors.
- **I7 [Safe Fallback]**: If an agent execution or verification fails, the system MUST log the error and default the `verified` status to `False` to prevent unsafe autonomous actions.
- **I8 [Stateless Execution]**: The `Coordinator` MUST treat individual agent runs as independent, passing all required state through `kwargs` to ensure reproducibility.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Agent fails during `_execute` | Exception logged; state reset to `IDLE`. | I7 |
| `AUTO_FULL` decision rejected by CoVe | `verified=False` returned to coordinator; rejected decision logged. | I2 |
| Agent reaches 51 runs | Oldest run discarded; exactly 50 retained. | I5 |
| Unknown agent threshold check | Defaults to a conservative 0.75. | I3 |
| LLM returns garbage in `AUTO_FULL` | CoVe likely produces low confidence; decision rejected. | I2, I7 |
| Learning journal is corrupt/missing | `_get_recent_lessons` catches error; returns empty string; agent continues. | I6 |
| Concurrent `run_with_verification` | Coordinator handles independent async runs; agents manage their own internal counters. | I8 |
