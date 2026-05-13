"""PatternAgent — geographic + demographic clustering over a prospect batch."""

from __future__ import annotations

import json
from typing import Any

from prompts_loader import load, render
from services import gemini

from agents.base import AgentState, BaseAgent


class PatternAgent(BaseAgent):
    name = "pattern"
    prompt_name = "pattern"

    async def _execute(self, *, prospects: list[dict[str, Any]]) -> dict[str, Any]:
        if not prospects:
            return {
                "geographic_clusters": [],
                "demographic_patterns": [],
                "top_routes": [],
                "recommendations": ["Inga prospekt i batchen."],
            }
        # Strip heavy fields to keep prompt under limits.
        slim = [
            {k: p.get(k) for k in ("address", "lat", "lng", "score", "owner_age", "status")}
            for p in prospects[:200]
        ]
        tpl = load(self.prompt_name)
        lessons = self._get_recent_lessons()
        prompt = render(
            tpl,
            {
                "prospects_json": json.dumps(slim, ensure_ascii=False),
                "lessons": lessons,
            },
        )
        return await gemini.generate_json(prompt, model=tpl.model, phase="agent-pattern")

    def _classify_state(self, result: dict[str, Any]) -> AgentState:
        return AgentState.SUGGESTING if result.get("recommendations") else AgentState.OBSERVING
