# Spec: Agent Coordinator

The Coordinator is a process-wide singleton responsible for managing agent lifecycles, exposing system-wide status, and enforcing verification protocols on automated actions.

## Public API

1.  **`get_coordinator()`**
    *   *Type:* Function (Singleton Factory)
    *   *Description:* Returns the process-wide `Coordinator` instance. Uses LRU cache to ensure only one instance exists.
2.  **`Coordinator.all`**
    *   *Type:* Property (List)
    *   *Description:* Returns a list of all initialized agents: Detection, Scoring, Pitch, Pattern, Quality, and UI Design.
3.  **`Coordinator.status()`**
    *   *Type:* Method
    *   *Description:* Aggregates `status()` calls from all registered agents. Returns a list of status dictionaries.
4.  **`Coordinator.leaderboard()`**
    *   *Type:* Method
    *   *Description:* Returns agents ranked by performance score.
    *   *Formula:* `score = auto_full_actions + 0.5 * suggestions`
5.  **`Coordinator.run_with_verification(agent_name: str, **kwargs)`**
    *   *Type:* Async Method
    *   *Description:* Executes a specific agent and applies Chain-of-Verification (CoVe) if the agent attempts an `AUTO_FULL` decision.
    *   *Returns:* `(verified: bool, result: Any, verification: dict)`

## Invariants

*   **I1 (Initialization):** The Coordinator MUST initialize exactly six agents: `DetectionAgent`, `ScoringAgent`, `PitchAgent`, `PatternAgent`, `QualityAgent`, and `UIDesignAgent`.
*   **I2 (Singleton):** `get_coordinator()` MUST return the same object instance across multiple calls within the same process.
*   **I3 (Discovery):** The `all` property MUST contain all six initialized agents and only those agents.
*   **I4 (Status Uniformity):** All agents MUST implement a `status()` method that returns a dictionary.
*   **I5 (Ranking Logic):** The leaderboard MUST be sorted in descending order based on the defined performance formula.
*   **I6 (Verification Trigger):** CoVe verification MUST only be invoked if the agent's state is `auto_full` after execution.
*   **I7 (Implicit Trust):** Decisions resulting in `SUGGESTING` or `AUTO_LOW` states are considered verified by default (`verified=True`).
*   **I8 (Agent Isolation):** If an invalid `agent_name` is provided to `run_with_verification`, it MUST return a failure state (`verified=False`) and an error message, without attempting execution.
*   **I9 (Requirement Resolution):** `run_with_verification` MUST resolve agent-specific thresholds using `get_verification_requirements(agent_name)`.

## Adversarial Matrix

| Scenario | Expected Behavior | Risk |
| :--- | :--- | :--- |
| **Invalid Agent Name** | Return `(False, None, {"error": ...})` | System crash if not handled. |
| **Agent Execution Failure** | Exception should propagate or be caught by agent; Coordinator remains stable. | Resource leaks if agents don't clean up. |
| **CoVe Service Timeout** | Should return `verified=False` or fallback to safety. | Over-trusting a failing verification service. |
| **Conflicting State** | Agent state changes during/after `run()`. Coordinator must use state *at time of check*. | Race conditions in state-dependent logic. |
| **Stat Manipulation** | Negative `auto_full_actions` or `suggestions`. | Broken leaderboard ranking/sort order. |
| **Empty Result** | `result` is `None` but state is `auto_full`. | Verification of null/empty data. |
