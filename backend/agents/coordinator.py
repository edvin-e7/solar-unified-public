"""Coordinator — one process-wide instance, holds all agents, serves status.

Now with CoVe verification for AUTO_FULL decisions.
"""

from __future__ import annotations

import functools
from typing import Any

from agents.detection import DetectionAgent
from agents.pattern import PatternAgent
from agents.pitch import PitchAgent
from agents.quality import QualityAgent
from agents.scoring import ScoringAgent
from agents.ui_design import UIDesignAgent
from agents.verification import get_verification_requirements, verify_agent_decision


class Coordinator:
    def __init__(self) -> None:
        self.detection = DetectionAgent()
        self.scoring = ScoringAgent()
        self.pitch = PitchAgent()
        self.pattern = PatternAgent()
        self.quality = QualityAgent()
        self.ui_design = UIDesignAgent()

    @property
    def all(self) -> list[Any]:
        return [self.detection, self.scoring, self.pitch, self.pattern, self.quality, self.ui_design]

    def status(self) -> list[dict[str, Any]]:
        return [a.status() for a in self.all]

    def leaderboard(self) -> list[dict[str, Any]]:
        ranked = sorted(self.all, key=lambda a: a.auto_full_actions + 0.5 * a.suggestions, reverse=True)
        return [
            {"rank": i + 1, "agent": a.name, "score": a.auto_full_actions + 0.5 * a.suggestions}
            for i, a in enumerate(ranked)
        ]

    async def run_with_verification(
        self, agent_name: str, **kwargs: Any
    ) -> tuple[bool, Any, dict[str, Any]]:
        """Run agent and verify its AUTO_FULL decisions via CoVe.

        Args:
            agent_name: Name of agent (detection, scoring, etc.)
            **kwargs: Arguments to pass to agent.run()

        Returns:
            (verified: bool, result: Any, verification: dict)
        """
        agent = next((a for a in self.all if a.name == agent_name), None)
        if not agent:
            return False, None, {"error": f"Agent {agent_name} not found"}

        # Run agent
        result = await agent.run(**kwargs)

        # Verify if AUTO_FULL
        if agent.state.value == "auto_full":
            threshold = get_verification_requirements(agent_name)
            verified, verification = await verify_agent_decision(
                agent.name, agent.state.value, result, threshold=threshold
            )
            return verified, result, verification
        else:
            # SUGGESTING or AUTO_LOW don't need verification
            return True, result, {"verified": True, "state": agent.state.value}


@functools.lru_cache(maxsize=1)
def get_coordinator() -> Coordinator:
    return Coordinator()
