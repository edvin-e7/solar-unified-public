"""DetectionAgent — Gemini Vision over satellite imagery."""

from __future__ import annotations

from typing import Any

from prompts_loader import load, render
from services import gemini

from agents.base import AgentState, BaseAgent


class DetectionAgent(BaseAgent):
    name = "detection"
    prompt_name = "detection"

    async def _execute(self, *, address: str, image_bytes: bytes) -> dict[str, Any]:
        lessons = self._get_recent_lessons()
        prompt = render(load(self.prompt_name), {"address": address, "lessons": lessons})
        tpl = load(self.prompt_name)
        return await gemini.generate_json(prompt, model=tpl.model, image_bytes=image_bytes, phase="agent-detection")

    def _classify_state(self, result: dict[str, Any]) -> AgentState:
        conf = float(result.get("confidence", 0.0))
        if conf < 0.3:
            return AgentState.OBSERVING
        if conf < 0.7:
            return AgentState.SUGGESTING
        return AgentState.AUTO_FULL
