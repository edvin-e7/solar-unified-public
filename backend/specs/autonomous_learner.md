# Autonomous Learner Service Spec

## Public API

### Functions

- **`extract_patterns() -> dict[str, Any]`**
  Analyzes the `learning_journal` to identify what is working and what is failing.
  - **Returns**: Success rate, top 10 working patterns, and top 10 antipatterns.

- **`synthesize_improvement_prompt(pattern_summary: dict) -> str`**
  Generates a meta-prompt for an LLM to suggest code or prompt enhancements based on recent history.

- **`run_autonomous_cycle() -> dict`**
  Executes a single pattern-extraction and prompt-synthesis cycle.

---

## Invariants

- **I1 [Empirical Foundation]**: Improvement suggestions MUST be derived directly from recent entries in the `learning_journal`.
- **I2 [Recency Bias]**: Pattern extraction MUST prioritize the last 10 entries of each type (passed vs. failed) to ensure the system adapts to the most recent changes.
- **I3 [Structured Synthesis]**: The improvement prompt MUST demand a JSON response with a specific schema (`target`, `enhancement`, `rationale`) to allow for automated parsing and validation.
- **I4 [Self-Correction Loop]**: Antipatterns included in the meta-prompt MUST include the associated error message to provide the LLM with enough context for effective self-correction.
- **I5 [Transparent Metadata]**: Every autonomous cycle MUST be recorded back into the `learning_journal` for full meta-traceability.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Journal is empty | `extract_patterns` returns 0% success and empty lists; `synthesize` prompt reflects no data. | I1, I2 |
| Success rate is 100% | Antipatterns list is empty; prompt focuses solely on reinforcement. | I1 |
| LLM returns invalid JSON | `validate_agent_response` returns `False`; cycle terminates before committing. | I3 |
| Rapid sequential cycles | Each cycle analyzes the latest journal state, including outcomes of the previous cycle. | I2 |
| Journal contains thousands of entries | Only the most recent 10 are analyzed for pattern extraction to prevent context bloat. | I2 |
