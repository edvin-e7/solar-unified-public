"""Autonomous self-improvement loop. Feeds learned patterns back into agents.

Uses learning_journal to extract what worked/failed, generates synthetic
prompts to strengthen those patterns, validates agent responses.
"""

from __future__ import annotations

import json
from datetime import UTC, datetime
from typing import Any

from learning_journal import entries, record


def extract_patterns() -> dict[str, Any]:
    """Extract success + failure patterns from journal."""
    all_entries = entries()
    passed = [e for e in all_entries if e["outcome"] == "passed"]
    failed = [e for e in all_entries if e["outcome"] in ("failed", "error")]
    return {
        "total_runs": len(all_entries),
        "success_rate": len(passed) / len(all_entries) if all_entries else 0,
        "working_patterns": [e["lesson"] for e in passed[-10:]],
        "antipatterns": [(e["lesson"], e.get("error", "")) for e in failed[-10:]],
        "last_run": max((e["ts"] for e in all_entries), default=None),
    }


def synthesize_improvement_prompt(pattern_summary: dict[str, Any]) -> str:
    """Generate prompt to reinforce good patterns."""
    return f"""# Autonomous Improvement Prompt

Based on {pattern_summary['total_runs']} runs (success rate: {pattern_summary['success_rate']:.0%}):

## What's working (reinforce these)
{chr(10).join(f"- {p}" for p in pattern_summary['working_patterns'])}

## What failed (avoid these)
{chr(10).join(f"- {p[0]} (error: {p[1]})" for p in pattern_summary['antipatterns'])}

Your task: Identify which agent or service could be improved, and suggest ONE targeted enhancement.
Respond in JSON: {{"target": "service_name", "enhancement": "description", "rationale": "why this helps"}}
"""


def validate_agent_response(response: str) -> bool:
    """Check if agent response is well-formed."""
    try:
        data = json.loads(response)
        required = {"target", "enhancement", "rationale"}
        return required.issubset(data.keys()) and all(
            isinstance(data[k], str) and len(data[k]) > 0 for k in required
        )
    except (json.JSONDecodeError, KeyError, TypeError):
        return False


def run_autonomous_cycle() -> dict[str, Any]:
    """One cycle: extract → synthesize → validate."""
    patterns = extract_patterns()
    prompt = synthesize_improvement_prompt(patterns)

    # In a real setup, this would call an agent endpoint
    # For now, log the cycle and return the synthesized prompt
    cycle = {
        "ts": datetime.now(UTC).isoformat(),
        "patterns_extracted": patterns,
        "improvement_prompt": prompt,
        "status": "ready_for_agent",
    }

    # Record that we ran a cycle
    record(
        phase="autonomous-cycle",
        outcome="passed",
        lesson=f"Synthesized improvement prompt. {patterns['total_runs']} runs analyzed.",
        metadata={"patterns": patterns},
    )

    return cycle


if __name__ == "__main__":
    cycle = run_autonomous_cycle()
    print("=== Autonomous Learning Cycle ===")
    print(f"Patterns: {cycle['patterns_extracted']}")
    print(f"\nImprovement Prompt:\n{cycle['improvement_prompt']}")
