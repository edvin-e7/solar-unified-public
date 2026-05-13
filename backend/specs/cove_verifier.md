# CoVe Verifier Service Spec

## Public API

### Functions

- **`async verify_improvement(suggestion: dict[str, str]) -> dict[str, Any]`**
  Executes the Chain-of-Verification (CoVe) loop on a proposed code improvement.
  - `suggestion`: Dict containing `target` (file/module), `enhancement` (change), and `rationale`.
  - **Returns**: A verification report including `verified` status, `confidence` score, and the underlying Q&A audit trail.

---

## Invariants

- **I1 [Step-by-Step Chain]**: The service MUST execute verification in a strict sequence: (1) Skeptical question generation, (2) Fact-based answering, (3) Sentiment scoring, (4) Confidence aggregation.
- **I2 [Resilient Fallbacks]**: If LLM sub-calls fail, the service MUST NOT crash; it MUST use hardcoded verification questions and "neutral" answer stubs to allow the safety check to complete.
- **I3 [Pessimistic Scoring]**: Negative answer sentiments MUST be weighted twice as heavily as positive ones ($-2.0$ vs $+1.0$) to bias the system toward caution and regression prevention.
- **I4 [Strict Approval Gate]**: The `verified` flag MUST only be `True` if the final confidence score $\ge 0.75$.
- **I5 [Journal Transparency]**: Every verification attempt, regardless of outcome, MUST be recorded in the `learning_journal` with full metadata for future pattern analysis.
- **I6 [Failure Detection]**: All transient LLM failures (timeouts, malformed JSON) MUST be logged in the `llm_errors` field to signal to the orchestrator that the result is degraded.
- **I7 [Learning Reinforcement]**: Confidence scores MUST be boosted by $0.1$ if the suggestion's rationale specifically references "journal" patterns, rewarding the use of established lessons.
- **I8 [Structured Reasoning]**: The service MUST produce a human-readable summary of the verification (sentiment tags, Q&A pairs) to ensure the logic behind a "REJECT" or "APPROVE" is explainable.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Gemini times out during question gen | Uses 5 hardcoded questions; `llm_errors` includes `questions_fallback`. | I2 |
| Model identifies a breaking change | Returns `sentiment="negative"`; confidence score penalized by $-2.0$ weight. | I3 |
| Highly creative/vague suggestion | Verification questions become harder to answer positively; confidence naturally drops. | I1 |
| All answers are "positive" | Confidence maps to $1.0$; `verified` becomes `True`. | I4 |
| All answers are "neutral" | Confidence maps to $0.5$; `verified` remains `False`. | I4 |
| Suggestion lacks rationale | `assess_confidence` uses defaults; no journal boost applied. | I7 |
| Gemini returns invalid JSON for answers | `answer_questions_llm` catches error; returns list of neutral "analysis failed" stubs. | I6 |
