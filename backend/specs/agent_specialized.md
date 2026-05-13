# Specialized Agent Specification

## Agent Fleet Overview

The Solar Unified system employs six specialized, prompt-driven agents managed by the `Coordinator`. Each agent is responsible for a specific domain of the solar prospecting lifecycle.

### 1. Detection Agent
- **Domain**: Satellite imagery analysis.
- **Input**: Physical address and raw image bytes.
- **Logic**: Uses Gemini Vision to detect existing solar panels and calculate confidence.
- **Escalation**:
  - `AUTO_FULL`: Confidence $\ge$ 0.7.
  - `SUGGESTING`: Confidence $\ge$ 0.3.
  - `OBSERVING`: Confidence < 0.3.

### 2. Scoring Agent
- **Domain**: Prospect prioritization.
- **Input**: Address, roof area, annual consumption, owner age, existing panels, and shading risk.
- **Logic**: Applies the 0–10 solar rubric to categorize prospects.
- **Escalation**:
  - `AUTO_FULL`: Priority = "hot".
  - `SUGGESTING`: Priority = "warm".
  - `OBSERVING`: Priority = "cold".
  - `IDLE`: Priority = "skip".

### 3. Pitch Agent
- **Domain**: Communications generation.
- **Input**: Owner name, address, and annual savings (kWh and SEK).
- **Logic**: Generates a one-sentence Swedish cold-call opener.
- **Escalation**:
  - `AUTO_FULL`: Any non-empty pitch generated.
  - `IDLE`: Empty response.

### 4. Pattern Agent
- **Domain**: Batch analysis and clustering.
- **Input**: A list of up to 200 prospects (slimmed to address, coordinates, score, and status).
- **Logic**: Identifies geographic and demographic trends across a batch.
- **Escalation**:
  - `SUGGESTING`: Any recommendations produced.
  - `OBSERVING`: Analysis complete but no specific recommendations.

### 5. Quality Agent
- **Domain**: Data validation and completeness.
- **Input**: Full prospect data dictionary.
- **Logic**: Performs cross-source validation and grades data completeness (0.0 to 1.0).
- **Escalation**:
  - `AUTO_FULL`: Completeness $\ge$ 0.9.
  - `SUGGESTING`: Completeness $\ge$ 0.6.
  - `OBSERVING`: Completeness < 0.6.

### 6. UI Design Agent
- **Domain**: System UX and design consistency.
- **Input**: Current UI state and recent coordinator outputs.
- **Logic**: Monitors system "vibe" and suggests improvements aligned with Solar Almanac tokens.
- **Escalation**:
  - `AUTO_FULL`: Any suggestion with `impact="breaking"`.
  - `AUTO_LOW`: Any suggestion with `impact="safe"`.
  - `SUGGESTING`: Suggestions with `impact="observation"`.
  - `IDLE`: No suggestions.

---

## Shared Invariants

- **I1 [JSON Output]**: All agents (except Pitch) MUST return structured JSON objects to ensure reliable parsing by the `Coordinator`.
- **I2 [Lesson Injection]**: Every agent MUST use `_get_recent_lessons()` to include the latest system learnings in its prompt context.
- **I3 [Phase Transparency]**: Every LLM call MUST specify a unique `phase` (e.g., `agent-detection`) to ensure accurate logging and tracing in the learning journal.
- **I4 [Resource Conservation]**: The `PatternAgent` MUST slim down prospect data (removing heavy fields) before injection into the prompt to stay within LLM token limits.
- **I5 [Swedish Language]**: All user-facing outputs (Pitch, Recommendations, Reasoning) MUST be in Swedish, following the Solar Almanac tone.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Agent | Invariant |
| :--- | :--- | :--- | :--- |
| Image is blurry | Low confidence; remains in `OBSERVING` state. | Detection | I3 |
| Prospect batch > 200 | Truncated to first 200 entries; heavy fields removed. | Pattern | I4 |
| Data is 100% complete | Completeness 1.0; state becomes `AUTO_FULL`. | Quality | I1 |
| LLM returns non-JSON | `generate_json` raises error; agent state becomes `IDLE`. | All (JSON) | I1 |
| Pitch is empty string | Agent state becomes `IDLE`. | Pitch | I5 |
| UI State is "error" | UI Design agent suggests recovery paths; `impact="breaking"` if critical. | UI Design | I1 |
