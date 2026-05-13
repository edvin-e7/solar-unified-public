"""Agent-generated insights with SQLite cache fallthrough."""

from __future__ import annotations

import agent_insights
from agents.pattern import PatternAgent
from fastapi import APIRouter, HTTPException, Query

router = APIRouter()


@router.get("/insight")
async def get_insight(type: str = Query("daily", pattern="^[a-z_]+$")) -> dict:
    cached = agent_insights.get_cached(type)
    if cached:
        return {"insight_type": type, "cached": True, **cached}

    try:
        agent = PatternAgent()
        result = await agent.run(prospects=[])
    except (RuntimeError, TypeError, ValueError, AttributeError) as e:
        raise HTTPException(status_code=502, detail=f"PatternAgent error: {e}") from e

    payload = {"quote": result.get("quote", ""), "context": result.get("context", "")}
    agent_insights.store(type, payload, ttl_hours=24)
    return {"insight_type": type, "cached": False, **payload}
