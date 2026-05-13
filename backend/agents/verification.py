"""CoVe verification wrapper for agent decisions.

Wraps agent outputs with verification before committing to state changes.
Verifies AUTO_FULL actions (automatic changes) via Chain-of-Verification.
"""

from __future__ import annotations

from typing import Any

from cove_verifier import verify_improvement
from learning_journal import record


async def verify_agent_decision(
    agent_name: str,
    state: str,
    result: dict[str, Any] | str,
    threshold: float = 0.75,
) -> tuple[bool, dict[str, Any]]:
    """Verify an agent's decision before executing it.

    Args:
        agent_name: Name of agent (SolarAgent, ProspectAgent, etc.)
        state: Agent state (suggesting, auto_low, auto_full)
        result: Agent output (suggestion or decision)
        threshold: Confidence threshold (0-1)

    Returns:
        (verified: bool, verification_result: dict)
    """

    # Only verify AUTO_FULL decisions (automatic changes)
    if state != "auto_full":
        return True, {"verified": True, "confidence": 1.0, "reason": "Not AUTO_FULL"}

    # Convert result to decision dict
    if isinstance(result, str):
        decision = {"description": result, "type": "agent_action"}
    elif isinstance(result, dict):
        decision = result
    else:
        decision = {"description": str(result), "type": "agent_action"}

    # Add agent context
    decision["agent"] = agent_name

    # Verify via CoVe
    try:
        verification = verify_improvement(decision)
        verified = verification["confidence"] >= threshold

        record(
            phase=f"agent-verify-{agent_name}",
            outcome="passed" if verified else "failed",
            lesson=f"Agent {agent_name} decision: {'approved' if verified else 'rejected'} (confidence: {verification['confidence']:.0%})",
            metadata={
                "agent": agent_name,
                "state": state,
                "confidence": verification["confidence"],
                "decision": decision,
            },
        )

        return verified, verification

    except Exception as e:
        record(
            phase=f"agent-verify-{agent_name}",
            outcome="error",
            lesson=f"Verification failed for {agent_name}",
            error=str(e)[:200],
        )
        return False, {"verified": False, "confidence": 0.0, "error": str(e)}


def get_verification_requirements(agent_name: str) -> float:
    """Get verification threshold for a given agent by name.

    Keys match the real `agent.name` values produced by the 6 prompt-driven
    agents (detection, scoring, pitch, pattern, quality, ui_design).
    Unknown agents default to 0.75.
    """
    thresholds: dict[str, float] = {
        "detection": 0.80,   # vision + critical
        "scoring": 0.75,
        "pitch": 0.70,       # generative, lower bar
        "pattern": 0.75,
        "quality": 0.90,     # final gate, strict
        "ui_design": 0.75,
    }
    return thresholds.get(agent_name, 0.75)
