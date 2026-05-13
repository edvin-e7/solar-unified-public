"""QualityAgent — cross-source validation + completeness grading."""

from __future__ import annotations

import json
from typing import Any

from prompts_loader import load, render
from services import gemini

from agents.base import AgentState, BaseAgent


class QualityAgent(BaseAgent):
    name = "quality"
    prompt_name = "quality"

    async def _execute(self, *, prospect: dict[str, Any]) -> dict[str, Any]:
        tpl = load(self.prompt_name)
        lessons = self._get_recent_lessons()
        prompt = render(
            tpl,
            {
                "prospect_json": json.dumps(prospect, ensure_ascii=False),
                "lessons": lessons,
            },
        )
        return await gemini.generate_json(prompt, model=tpl.model, phase="agent-quality")

    def _classify_state(self, result: dict[str, Any]) -> AgentState:
        completeness = float(result.get("completeness", 0.0))
        # Logic fix: High completeness -> AUTO_FULL. Low -> SUGGESTING.
        if completeness >= 0.9:
            return AgentState.AUTO_FULL
        if completeness >= 0.6:
            return AgentState.SUGGESTING
        return AgentState.OBSERVING
