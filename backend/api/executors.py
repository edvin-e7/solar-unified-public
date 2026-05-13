"""API endpoints for autonomous executor roles."""

from __future__ import annotations

import functools

from executors.orchestrator import Orchestrator
from fastapi import APIRouter, HTTPException
from learning_journal import record

router = APIRouter()


@functools.lru_cache(maxsize=1)
def _orchestrator() -> Orchestrator:
    return Orchestrator()


@router.post("/cycle")
async def execute_full_cycle(addresses: list[str] | None = None) -> dict:
    """Run full autonomous cycle: data gathering + learning.

    Args:
        addresses: Optional list of addresses to scan. If None, skips data gathering.

    Returns:
        Cycle results with data_gathering and autonomous_learning outcomes.
    """
    try:
        result = await _orchestrator().run_full_cycle(addresses)
        record(
            phase="api-execute-full-cycle",
            outcome="passed",
            lesson=f"Executed full cycle: {result.get('data_gathering')}, {result.get('autonomous_learning')}",
            files=[],
            metadata={"addresses": len(addresses) if addresses else 0},
        )
        return result
    except Exception as e:
        record(
            phase="api-execute-full-cycle",
            outcome="error",
            lesson=str(e),
            files=[],
            error=str(e),
        )
        raise HTTPException(status_code=502, detail=f"Cycle execution failed: {e}") from e


@router.post("/learning-only")
async def execute_learning_cycle() -> dict:
    """Run autonomous learning cycle (pattern detection + improvements).

    Returns:
        Learning cycle results with patterns_found and improvements_applied.
    """
    try:
        result = await _orchestrator().run_learning_cycle()
        record(
            phase="api-execute-learning-only",
            outcome="passed",
            lesson=f"Learning cycle: {result}",
            files=[],
        )
        return {"phase": "learning-only", "autonomous_learning": result}
    except Exception as e:
        record(
            phase="api-execute-learning-only",
            outcome="error",
            lesson=str(e),
            files=[],
            error=str(e),
        )
        raise HTTPException(status_code=502, detail=f"Learning cycle failed: {e}") from e


@router.get("/status")
async def get_executor_status(limit: int = 10) -> dict:
    """Get recent journal entries for real-time thought stream.

    Returns:
        Tail of the learning_journal.
    """
    try:
        from learning_journal import entries as load_journal

        all_entries = load_journal()
        tail = all_entries[-limit:] if all_entries else []

        return {
            "entries": tail,
            "total_entries": len(all_entries),
            "status": "online",
        }
    except OSError as e:
        from error_logger import log_error

        log_error("api-executors-status", e, context={"limit": limit})
        raise HTTPException(status_code=502, detail=f"Failed to load journal: {e}") from e
