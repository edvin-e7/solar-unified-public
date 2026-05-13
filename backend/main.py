"""Unified solar prospecting backend.

Combines endpoints from solar-app (scan), edvin-solar (detect/score/enrich/agents),
and edvins-solprojekt (solar potential) behind a single FastAPI app.
"""

from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path

from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parent.parent / ".env")

_log = logging.getLogger("solar_unified.boot")

_PLACEHOLDER_VALUES = {"", "your_api_key_here", "TODO", "changeme", "xxx", "placeholder"}


def _env_key_status(name: str) -> str:
    val = os.getenv(name, "").strip()
    if val.lower() in _PLACEHOLDER_VALUES:
        return "placeholder"
    if not val:
        return "missing"
    return "ok"


def _assert_required_env() -> None:
    """Fail loud at startup if truly required keys are missing or placeholder.

    GOOGLE_MAPS_API_KEY is OPTIONAL — only needed if ALLOW_GOOGLE_SOLAR_API=1
    (Google Solar API is paid; default off). Geocoding uses Nominatim (free)
    and satellite uses ArcGIS (free), so the key is not required to boot.
    """
    required = ("GEMINI_API_KEY",)
    bad = {k: _env_key_status(k) for k in required if _env_key_status(k) != "ok"}
    if os.getenv("ALLOW_GOOGLE_SOLAR_API", "0") == "1" and _env_key_status("GOOGLE_MAPS_API_KEY") != "ok":
        bad["GOOGLE_MAPS_API_KEY"] = _env_key_status("GOOGLE_MAPS_API_KEY")
    if bad:
        _log.error("Required env vars not usable: %s", bad)
        if os.getenv("ALLOW_BOOT_WITHOUT_KEYS", "0") != "1":
            raise RuntimeError(f"Refusing to start — env keys {bad}. Fix env file or set ALLOW_BOOT_WITHOUT_KEYS=1.")


_assert_required_env()

from collections.abc import AsyncIterator  # noqa: E402
from contextlib import asynccontextmanager  # noqa: E402

from api import agents, enrich, executors, leads, panels, prospects, scan, solar  # noqa: E402
from api import insights as insights_api
from api import settings as settings_api
from apscheduler.schedulers.asyncio import AsyncIOScheduler  # noqa: E402
from apscheduler.triggers.interval import IntervalTrigger  # noqa: E402
from fastapi import FastAPI  # noqa: E402  — must load .env first
from fastapi.middleware.cors import CORSMiddleware  # noqa: E402
from fastapi.staticfiles import StaticFiles  # noqa: E402
from starlette.middleware.base import BaseHTTPMiddleware  # noqa: E402
from starlette.requests import Request  # noqa: E402
from starlette.responses import Response  # noqa: E402

ROOT = Path(__file__).parent
FRONTEND_DIST = ROOT.parent / "frontend" / "dist"

_CSP = (
    "default-src 'self'; "
    "script-src 'self'; "
    "style-src 'self' 'unsafe-inline'; "
    "img-src 'self' data: blob: https://*.googleapis.com https://*.ggpht.com "
    "https://*.openstreetmap.org https://tile.openstreetmap.org; "
    "connect-src 'self' https://solar.googleapis.com https://nominatim.openstreetmap.org "
    "https://re.jrc.ec.europa.eu https://generativelanguage.googleapis.com; "
    "font-src 'self' data: https://fonts.gstatic.com; "
    "frame-ancestors 'none'; "
    "base-uri 'self'; "
    "form-action 'self'; "
    "object-src 'none'"
)


class SecurityHeaders(BaseHTTPMiddleware):
    async def dispatch(self, request: Request, call_next) -> Response:
        response = await call_next(request)
        response.headers["Content-Security-Policy"] = _CSP
        response.headers["X-Content-Type-Options"] = "nosniff"
        response.headers["Referrer-Policy"] = "strict-origin-when-cross-origin"
        response.headers["Permissions-Policy"] = "camera=(), microphone=(), geolocation=()"
        response.headers["Cross-Origin-Opener-Policy"] = "same-origin"
        if request.url.scheme == "https":
            response.headers["Strict-Transport-Security"] = "max-age=63072000; includeSubDomains"
        return response


_scheduler: AsyncIOScheduler | None = None


async def _learning_tick() -> None:
    from error_logger import log_error
    from executors.orchestrator import Orchestrator

    try:
        result = await Orchestrator().run_learning_cycle()
        _log.info("Scheduled learning tick: %s", result)
    except Exception as e:  # noqa: BLE001 -- scheduler tick must not propagate to APScheduler
        _log.exception("Scheduled learning tick failed")
        log_error("scheduler-learning-tick", e, context={"cycle_hours": os.getenv("LEARNING_CYCLE_HOURS", "6")})


async def _check_llm_health() -> None:
    """Warn on startup if free-mode (LLM_PROVIDER=ollama, default) cannot reach
    the local Ollama daemon. Non-fatal — the scanner will surface the real
    error to the caller. Hands ops a single log line so they don't have to
    grep tracebacks to discover "oh, Ollama wasn't running".
    """
    provider = os.getenv("LLM_PROVIDER", "ollama").lower()
    if provider != "ollama":
        _log.info("LLM provider: %s (free-mode disabled — explicit opt-in)", provider)
        return

    host = os.getenv("OLLAMA_HOST", "http://localhost:11434").rstrip("/")
    vision_model = os.getenv("OLLAMA_VISION_MODEL", "moondream")
    try:
        import httpx
        async with httpx.AsyncClient(timeout=3.0) as client:
            r = await client.get(f"{host}/api/tags")
            r.raise_for_status()
            models = [m["name"] for m in r.json().get("models", [])]
    except Exception as exc:  # noqa: BLE001 -- health-check must not crash startup
        _log.warning(
            "Free-mode (LLM_PROVIDER=ollama) configured but Ollama daemon at %s "
            "is unreachable: %s. Install Ollama (https://ollama.com) and run "
            "`ollama serve` + `ollama pull %s` to enable detection.",
            host,
            exc,
            vision_model,
        )
        return

    # Vision model strip ":latest" suffix for canonical match
    have = {m.split(":")[0] for m in models}
    needed = vision_model.split(":")[0]
    if needed in have:
        _log.info("LLM provider: ollama (free-mode) — host=%s, vision=%s, models=%d",
                  host, vision_model, len(models))
    else:
        _log.warning(
            "Free-mode active but Ollama is missing the vision model %r. "
            "Run: `ollama pull %s` to enable panel detection.",
            vision_model,
            vision_model,
        )


@asynccontextmanager
async def lifespan(app: FastAPI) -> AsyncIterator[None]:
    global _scheduler
    await _check_llm_health()
    # Default OFF until cove_vote() rubber-stamp + verify_count substring + PII
    # filter are landed (architecture review, Fas 0/1). Re-enable per session
    # with SCHEDULER_ENABLED=1 once Fas 1 gates pass.
    if os.getenv("SCHEDULER_ENABLED", "0") == "1":
        hours = int(os.getenv("LEARNING_CYCLE_HOURS", "6"))
        _scheduler = AsyncIOScheduler()
        _scheduler.add_job(
            _learning_tick,
            IntervalTrigger(hours=hours),
            id="learning_cycle",
            max_instances=1,
            coalesce=True,
            misfire_grace_time=600,
        )
        _scheduler.start()
        _log.warning("APScheduler started — learning cycle every %dh", hours)
    yield
    if _scheduler is not None:
        _scheduler.shutdown(wait=False)
        _log.info("APScheduler shutdown")


app = FastAPI(
    title="Solar Unified",
    version="0.1.0",
    description="One backend for Swedish solar prospecting.",
    lifespan=lifespan,
)

app.add_middleware(SecurityHeaders)

_DEV_ORIGINS = ["http://localhost:5173", "http://127.0.0.1:5173"]
_prod_origins = [o.strip() for o in os.getenv("CORS_ORIGINS", "").split(",") if o.strip()]
app.add_middleware(
    CORSMiddleware,
    allow_origins=_prod_origins or _DEV_ORIGINS,
    allow_credentials=False,
    allow_methods=["GET", "POST", "PUT", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "Authorization", "X-App-Auth"],
    max_age=600,
)

app.include_router(scan.router, prefix="/api/scan", tags=["scan"])
app.include_router(leads.router, prefix="/api/leads", tags=["leads"])
app.include_router(solar.router, prefix="/api/solar", tags=["solar"])
app.include_router(scan.router, prefix="/api/detect", tags=["detect"])
app.include_router(enrich.router, prefix="/api/enrich", tags=["enrich"])
app.include_router(prospects.router, prefix="/api/prospects", tags=["prospects"])
app.include_router(panels.router, prefix="/api/panels", tags=["panels"])
app.include_router(agents.router, prefix="/api/agents", tags=["agents"])
app.include_router(executors.router, prefix="/api/execute", tags=["execute"])
app.include_router(settings_api.router, prefix="/api/settings", tags=["settings"])
app.include_router(insights_api.router, prefix="/api/agents", tags=["insights"])


@app.get("/api/health")
async def health() -> dict:
    from api.prospects import db

    try:
        with db() as conn:
            prospect_count = conn.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
            panel_owners = conn.execute(
                "SELECT COUNT(*) FROM prospects WHERE has_panels = 1"
            ).fetchone()[0]
        db_status = "ok"
    except sqlite3.Error as e:
        from error_logger import log_error
        prospect_count = -1
        panel_owners = -1
        db_status = f"error: {e}"
        log_error("api-health-db-probe", e, context={"endpoint": "/api/health"})

    env_keys = {
        "GEMINI_API_KEY": _env_key_status("GEMINI_API_KEY"),
        "GOOGLE_MAPS_API_KEY": _env_key_status("GOOGLE_MAPS_API_KEY"),
    }
    env_ok = all(v == "ok" for v in env_keys.values())

    scheduler_info: dict = {"enabled": False}
    if _scheduler is not None and _scheduler.running:
        job = _scheduler.get_job("learning_cycle")
        scheduler_info = {
            "enabled": True,
            "next_run": job.next_run_time.isoformat() if job and job.next_run_time else None,
        }

    overall = "ok" if db_status == "ok" and env_ok else "degraded"

    return {
        "status": overall,
        "service": "solar-unified",
        "version": "0.1.0",
        "database": {
            "status": db_status,
            "prospects": prospect_count,
            "panel_owners": panel_owners,
        },
        "env": env_keys,
        "flags": {
            "google_solar": os.getenv("ALLOW_GOOGLE_SOLAR_API", "0") == "1",
            "external_llm": os.getenv("ALLOW_EXTERNAL_LLM", "0") == "1",
        },
        "scheduler": scheduler_info,
    }


if FRONTEND_DIST.is_dir():
    # Serve the built React app from the same origin in production.
    app.mount("/", StaticFiles(directory=FRONTEND_DIST, html=True), name="frontend")
