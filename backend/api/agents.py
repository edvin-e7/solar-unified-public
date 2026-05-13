"""Agent status + direct triggers."""

from __future__ import annotations

from agents.coordinator import get_coordinator
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

router = APIRouter()


@router.get("/status")
async def status() -> dict:
    return {"agents": get_coordinator().status()}


@router.get("/leaderboard")
async def leaderboard() -> list[dict]:
    return get_coordinator().leaderboard()


class ScoreRequest(BaseModel):
    address: str
    roof_area_m2: int
    annual_kwh: float
    owner_age: int | None = None
    has_panels: bool = False
    shading_risk: str = "unknown"


@router.post("/score")
async def score(req: ScoreRequest) -> dict:
    try:
        return await get_coordinator().scoring.run(**req.model_dump())
    except RuntimeError as e:
        raise HTTPException(502, str(e))


class PitchRequest(BaseModel):
    owner_name: str
    address: str
    annual_kwh: float
    annual_sek: int


@router.post("/pitch")
async def pitch(req: PitchRequest) -> dict:
    try:
        sentence = await get_coordinator().pitch.run(**req.model_dump())
    except RuntimeError as e:
        raise HTTPException(502, str(e))
    return {"pitch": sentence}


class PatternRequest(BaseModel):
    prospects: list[dict]


@router.post("/pattern")
async def pattern(req: PatternRequest) -> dict:
    try:
        return await get_coordinator().pattern.run(prospects=req.prospects)
    except RuntimeError as e:
        raise HTTPException(502, str(e))


class QualityRequest(BaseModel):
    prospect: dict


@router.post("/quality")
async def quality(req: QualityRequest) -> dict:
    try:
        return await get_coordinator().quality.run(prospect=req.prospect)
    except RuntimeError as e:
        raise HTTPException(502, str(e))
