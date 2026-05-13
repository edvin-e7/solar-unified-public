"""CollectiveVerifier — verify improvement suggestions via CoVe.

Previously simulated a 6-agent vote via substring matching on agent names
(deterministic arithmetic, no LLM call). Now delegates to the real
`cove_verifier.verify_improvement` and reports its confidence. Return-shape
preserves `consensus` and `agent_votes` keys for AutoApplicator/Orchestrator
compatibility (single-source confidence mirrored to all agents).
"""

from __future__ import annotations

from typing import Any

from agents.coordinator import get_coordinator
from cove_verifier import verify_improvement
from learning_journal import record


class CollectiveVerifier:
    """Executor role: verify improvement suggestions via CoVe."""

    name = "collective_verifier"

    async def verify_improvement(
        self, improvement: dict[str, Any]
    ) -> dict[str, Any]:
        """Verify improvement safety via a single CoVe pass.

        Args:
            improvement: {target, enhancement, rationale, type, impact}

        Returns:
            {
                "verified": bool,
                "consensus": float (0-1),      # kept for back-compat
                "confidence": float (0-1),     # CoVe's own score
                "agent_votes": {agent_name: confidence},  # mirrored
                "reasoning": str,
            }
        """
        # Real CoVe verification (async, uses Gemini)
        cove_result = await verify_improvement(improvement)

        confidence = float(cove_result.get("confidence", 0.0))
        verified = bool(cove_result.get("verified", False))
        llm_errors: list[str] = list(cove_result.get("llm_errors", []))

        # Mirror the CoVe confidence across all agents so downstream
        # consumers (orchestrator, journaler) that expect `agent_votes`
        # keep working. Multi-agent theater replaced by a single real call.
        coordinator = get_coordinator()
        agent_votes: dict[str, float] = {a.name: confidence for a in coordinator.all}

        reasoning = self._generate_reasoning(improvement, agent_votes, confidence, cove_result)

        record(
            phase="collective-verify",
            outcome="passed" if verified else "rejected",
            lesson=f"Improvement to {improvement.get('target', 'unknown')}: {confidence:.0%} CoVe confidence",
            metadata={
                "improvement_target": improvement.get("target"),
                "improvement_type": improvement.get("type"),
                "agent_votes": agent_votes,
                "consensus": confidence,
                "confidence": confidence,
                "verified": verified,
            },
        )

        return {
            "verified": verified,
            "consensus": confidence,
            "confidence": confidence,
            "agent_votes": agent_votes,
            "reasoning": reasoning,
            "llm_errors": llm_errors,
        }

    def _generate_reasoning(
        self,
        improvement: dict[str, Any],
        agent_votes: dict[str, float],
        confidence: float,
        cove_result: dict[str, Any],
    ) -> str:
        """Generate human-readable reasoning."""
        lines = [
            f"CoVe Verification (confidence: {confidence:.0%})",
            f"Target: {improvement.get('target')}",
            f"Type: {improvement.get('type')}",
            "",
        ]

        cove_reasoning = cove_result.get("reasoning", "")
        if cove_reasoning:
            lines.append(cove_reasoning)
            lines.append("")

        if confidence >= 0.75:
            lines.append("APPROVED — CoVe confidence above 75% threshold")
        else:
            lines.append("REJECTED — insufficient CoVe confidence")

        return "\n".join(lines)
