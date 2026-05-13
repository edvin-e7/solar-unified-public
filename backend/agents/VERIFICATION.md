---
name: Agent Verification via Chain-of-Verification
version: 1.0
---

# Agent Verification Integration

Each agent's **AUTO_FULL decisions** (automatic actions) are verified via Chain-of-Verification before execution.

## Architecture

```
Agent.run() → state classification → AUTO_FULL?
                                         ↓
                              verify_agent_decision()
                                         ↓
                       confidence ≥ threshold?
                           ↙          ↘
                         YES           NO
                         ↓             ↓
                    Execute        Reject
                    Record         Log rejection
```

## Verification Thresholds

Different agents need different confidence levels based on risk:

| Agent | Threshold | Justification |
| --- | --- | --- |
| **PIIFilter** | 95% | Privacy critical |
| **Coordinator** | 85% | Orchestrates others |
| **SolarAgent** | 80% | High stakes (roof analysis) |
| **ProspectAgent** | 75% | Medium stakes (contact data) |
| **ImageAgent** | 70% | Lower stakes (validation helper) |

## Usage

### Basic: Run Agent with Verification

```python
from agents.coordinator import get_coordinator

coordinator = get_coordinator()

# Run agent with verification gate
verified, result, verification = await coordinator.run_with_verification(
    agent_name="SolarAgent",
    address="123 Solar St, Boston MA",
    image_url="https://example.com/roof.jpg"
)

if verified:
    process_result(result)
else:
    log_rejection(verification)
```

### Advanced: Verify Specific Decisions

```python
from agents.verification import verify_agent_decision

decision = {
    "type": "prospect_contact",
    "phone": "+1-617-555-0100",
    "confidence": 0.92,
}

verified, verification = await verify_agent_decision(
    agent_name="ProspectAgent",
    state="auto_full",
    result=decision,
    threshold=0.75
)

if verified:
    send_to_prospects(decision)
```

## Verification Questions (Examples)

For each agent decision, CoVe generates questions like:

**SolarAgent Decision:**
- Will this roof geometry assessment be accurate?
- Could missing details cause downstream errors?
- Is the solar potential estimate realistic?

**ProspectAgent Decision:**
- Is the contact data valid and current?
- Could this phone number be wrong?
- Is the propensity score calibrated correctly?

**PIIFilter Decision:**
- Does this log contain any PII?
- Could de-identification break the data?
- Is the redaction complete?

## Logging & Learning

Each verification is logged in `learning_journal`:

```json
{
  "phase": "agent-verify-SolarAgent",
  "outcome": "passed",
  "lesson": "Agent SolarAgent decision: approved (confidence: 92%)",
  "metadata": {
    "agent": "SolarAgent",
    "state": "auto_full",
    "confidence": 0.92,
    "decision": {...}
  }
}
```

### Learn from Rejections

Rejected decisions → stored in journal → analyzed next cycle:

```python
from learning_journal import entries

rejections = [e for e in entries() if "rejected" in e["lesson"]]
patterns = analyze_rejections(rejections)
improve_agent_prompts(patterns)
```

## Testing Verification

```bash
cd backend/agents
python3 demo_verification.py  # Shows all agents with verification
```

## Future Enhancements

1. **Code RAG** — Search agent prompts + codebase instead of generic Q&A
2. **Human-in-Loop** — Escalate low-confidence decisions for human review
3. **Adaptive Thresholds** — Adjust confidence requirements based on agent performance
4. **Verification Feedback** — Use rejection reasons to improve agent prompts
5. **Multi-Agent Consensus** — Require agreement from multiple agents for risky decisions

## Disabling Verification (Emergency Only)

```python
# For testing/development only
verified, result, _ = await coordinator.run_with_verification(
    "SolarAgent",
    **kwargs,
    # To skip verification:
    # threshold=0.0  # Will accept any confidence
)
```

**Warning:** Disabling verification removes safety gate. Only for dev/testing.

## References

- [Chain-of-Verification Paper](https://arxiv.org/abs/2309.11236)
- [cove_verifier.py](../cove_verifier.py) — Verification implementation
- [learning_journal.py](../learning_journal.py) — Logging infrastructure
- [coordinator.py](./coordinator.py) — Orchestration with verification
