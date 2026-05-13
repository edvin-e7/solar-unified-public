"""PitchAgent — Swedish one-sentence cold-call opener."""

from __future__ import annotations

from prompts_loader import load, render
from services import gemini

from agents.base import AgentState, BaseAgent


class PitchAgent(BaseAgent):
    name = "pitch"
    prompt_name = "pitch"

    async def _execute(
        self,
        *,
        owner_name: str,
        address: str,
        annual_kwh: float,
        annual_sek: int,
    ) -> str:
        tpl = load(self.prompt_name)
        lessons = self._get_recent_lessons()
        prompt = render(
            tpl,
            {
                "owner_name": owner_name,
                "address": address,
                "annual_kwh": int(annual_kwh),
                "annual_sek": annual_sek,
                "lessons": lessons,
            },
        )
        result = await gemini.generate(prompt, model=tpl.model, phase="agent-pitch")
        return result.strip()

    def _classify_state(self, result: str) -> AgentState:
        return AgentState.AUTO_FULL if result else AgentState.IDLE
