"""UIDesignAgent — Design consciousness of Solar Unified.

Observes UI state + agent outputs, suggests improvements aligned with
Solar Almanac tokens, classifies impact (observation/safe/breaking).
"""

from __future__ import annotations

from typing import Any

from prompts_loader import load, render
from services import gemini

from agents.base import AgentState, BaseAgent


class UIDesignAgent(BaseAgent):
    name = "ui_design"
    prompt_name = "ui_design"

    async def _execute(
        self,
        *,
        ui_state: dict[str, Any],
        agent_outputs: list[dict[str, Any]],
    ) -> dict[str, Any]:
        """Analyze UI state + agent outputs, suggest design improvements.

        Args:
            ui_state: Current UI state (loading, empty, populated, errors)
            agent_outputs: Recent agent decisions from Coordinator.status()

        Returns:
            JSON with observations, suggestions, priority classification
        """
        tpl = load(self.prompt_name)
        prompt = render(
            tpl,
            {
                "ui_state": str(ui_state),
                "agent_outputs": str(agent_outputs),
            },
        )
        result = await gemini.generate_json(prompt, model=tpl.model, phase="agent-ui-design")
        # Validate response structure
        if not isinstance(result, dict):
            result = {"observations": [], "suggestions": [], "priority": "low"}
        if "suggestions" not in result:
            result["suggestions"] = []
        if "observations" not in result:
            result["observations"] = []
        return result

    def _classify_state(self, result: dict[str, Any]) -> AgentState:
        """Map suggestion impact to agent lifecycle state.

        impact="breaking" → AUTO_FULL (needs CoVe verification)
        impact="safe" → AUTO_LOW (safe to apply immediately)
        impact="observation" → SUGGESTING (FYI, no action)
        No suggestions → IDLE (analysis complete, nothing actionable)
        """
        suggestions = result.get("suggestions", [])
        if not suggestions:
            return AgentState.IDLE

        max_impact = max((s.get("impact", "observation") for s in suggestions), default="observation")
        if max_impact == "breaking":
            return AgentState.AUTO_FULL
        elif max_impact == "safe":
            return AgentState.AUTO_LOW
        else:
            return AgentState.SUGGESTING
