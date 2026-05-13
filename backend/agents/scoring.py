"""ScoringAgent — ranks a single prospect on the 0–10 rubric."""

from __future__ import annotations

from typing import Any

from prompts_loader import load, render
from services import gemini

from agents.base import AgentState, BaseAgent


class ScoringAgent(BaseAgent):
    name = "scoring"
    prompt_name = "scoring"

    async def _execute(
        self,
        *,
        address: str,
        roof_area_m2: int,
        annual_kwh: float,
        owner_age: int | None = None,
        has_panels: bool = False,
        shading_risk: str = "unknown",
    ) -> dict[str, Any]:
        tpl = load(self.prompt_name)
        lessons = self._get_recent_lessons()
        prompt = render(
            tpl,
            {
                "address": address,
                "roof_area_m2": roof_area_m2,
                "annual_kwh": annual_kwh,
                "owner_age": owner_age if owner_age is not None else "okänd",
                "has_panels": str(has_panels).lower(),
                "shading_risk": shading_risk,
                "lessons": lessons,
            },
        )
        return await gemini.generate_json(prompt, model=tpl.model, phase="agent-scoring")

    def _classify_state(self, result: dict[str, Any]) -> AgentState:
        priority = result.get("priority", "cold")
        return {
            "hot": AgentState.AUTO_FULL,
            "warm": AgentState.SUGGESTING,
            "cold": AgentState.OBSERVING,
            "skip": AgentState.IDLE,
        }.get(priority, AgentState.OBSERVING)
