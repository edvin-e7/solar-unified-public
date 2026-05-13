"""Read-only exposure of runtime feature flags."""

from __future__ import annotations

import os

from fastapi import APIRouter
from pydantic import BaseModel

router = APIRouter()


class Flags(BaseModel):
    allow_external_llm: bool
    allow_google_solar_api: bool


@router.get("/flags", response_model=Flags)
async def get_flags() -> Flags:
    return Flags(
        allow_external_llm=os.getenv("ALLOW_EXTERNAL_LLM", "0") == "1",
        allow_google_solar_api=os.getenv("ALLOW_GOOGLE_SOLAR_API", "0") == "1",
    )
