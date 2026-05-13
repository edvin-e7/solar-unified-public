"""BaseAgent — shared lifecycle for all prompt-driven agents.

Mirrors the observe → suggest → auto_low → auto_full escalation from
edvin-solar/src/agents/base_agent.py, but prompt-native (no custom NN).
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

log = logging.getLogger(__name__)


class AgentState(StrEnum):
    IDLE = "idle"
    OBSERVING = "observing"
    SUGGESTING = "suggesting"
    AUTO_LOW = "auto_low"
    AUTO_FULL = "auto_full"


@dataclass
class AgentRun:
    agent: str
    input_summary: str
    output: Any
    state: AgentState
    ts: str = field(default_factory=lambda: datetime.now(UTC).isoformat())


class BaseAgent:
    name: str = "base"
    prompt_name: str = ""  # subclasses override with a filename in prompts/

    def __init__(self) -> None:
        self.state: AgentState = AgentState.IDLE
        self.runs: list[AgentRun] = []
        self.suggestions: int = 0
        self.auto_full_actions: int = 0

    async def run(self, **kwargs: Any) -> Any:
        self.state = AgentState.OBSERVING
        try:
            result = await self._execute(**kwargs)
            self.state = self._classify_state(result)
            if self.state == AgentState.SUGGESTING:
                self.suggestions += 1
            elif self.state == AgentState.AUTO_FULL:
                self.auto_full_actions += 1
            self._record(kwargs, result)
            return result
        except Exception:
            log.exception("Agent %s failed", self.name)
            self.state = AgentState.IDLE
            raise

    async def _execute(self, **kwargs: Any) -> Any:
        raise NotImplementedError

    def _classify_state(self, result: Any) -> AgentState:
        """Subclass hook: map the result to a lifecycle state."""
        return AgentState.IDLE

    def _record(self, inputs: dict[str, Any], output: Any) -> None:
        summary = ", ".join(f"{k}={_short(v)}" for k, v in inputs.items())
        self.runs.append(
            AgentRun(
                agent=self.name,
                input_summary=summary,
                output=output,
                state=self.state,
            )
        )
        if len(self.runs) > 50:
            self.runs = self.runs[-50:]

    def status(self) -> dict[str, Any]:
        return {
            "name": self.name,
            "state": self.state.value,
            "suggestions": self.suggestions,
            "auto_full_actions": self.auto_full_actions,
            "last_run": self.runs[-1].ts if self.runs else None,
        }

    def _get_recent_lessons(self, limit: int = 5) -> str:
        """Fetch recent passed lessons from learning journal to avoid repeat mistakes."""
        try:
            from learning_journal import get_summary
            summary = get_summary()
            patterns = summary.get("patterns", {}).get("working_patterns", [])
            return "\n".join(f"- {p}" for p in patterns[-limit:])
        except Exception as exc:
            from error_logger import log_error
            log_error(
                f"agent-lessons-{getattr(self, 'name', 'unknown')}",
                exc,
                context={"limit": limit},
            )
            return ""


def _short(v: Any, limit: int = 40) -> str:
    s = str(v)
    return s if len(s) <= limit else s[: limit - 1] + "…"
