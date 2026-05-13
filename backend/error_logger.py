"""Central error logger — every caught exception becomes structured signal.

Rule: no silent catches in production code. If we catch, we log — with enough
context for post-mortem (phase, error_type, traceback, metadata) to reach both
the learning journal AND a dedicated `errors.jsonl` for quick triage.

Use as decorator or context manager. Never `except Exception: pass` again.
"""

from __future__ import annotations

import contextlib
import functools
import inspect
import json
import logging
import traceback
from collections.abc import AsyncIterator, Callable, Iterator
from datetime import UTC, datetime
from typing import Any, TypeVar

from learning_journal import LEARNED_DIR, record
from services.structured_log import append_jsonl_sync

log = logging.getLogger(__name__)

ERRORS_LOG = LEARNED_DIR / "errors.jsonl"

T = TypeVar("T")


def log_error(
    phase: str,
    exc: BaseException,
    *,
    context: dict[str, Any] | None = None,
    severity: str = "error",
) -> None:
    """Record a caught exception to journal + errors.jsonl. Never swallow silently."""
    ctx = context or {}
    error_type = type(exc).__name__
    tb = "".join(traceback.format_exception(type(exc), exc, exc.__traceback__))

    entry = {
        "ts": datetime.now(UTC).isoformat(),
        "phase": phase,
        "severity": severity,
        "error_type": error_type,
        "message": str(exc),
        "traceback": tb,
        "context": ctx,
    }
    try:
        append_jsonl_sync(ERRORS_LOG, entry)
    except OSError:
        log.exception("errors.jsonl write failed")

    try:
        record(
            phase=phase,
            outcome="error",
            lesson=f"{error_type}: {exc}",
            error=str(exc),
            metadata={"error_type": error_type, "severity": severity, **ctx},
        )
    except Exception:
        log.exception("learning_journal record failed for phase=%s", phase)

    log.error("[%s] %s: %s | context=%s", phase, error_type, exc, ctx)


@contextlib.contextmanager
def log_scope(phase: str, **context: Any) -> Iterator[None]:
    """Context manager: log any exception in scope, then re-raise.

    Usage:
        with log_scope("api-enrich-person", address=addr):
            result = await lookup(addr)
    """
    try:
        yield
    except Exception as exc:
        log_error(phase, exc, context=context)
        raise


def log_and_swallow(phase: str, fallback: T, **context: Any) -> Callable[[Callable[..., T]], Callable[..., T]]:
    """Decorator: log any exception, return `fallback` instead of raising.

    Auto-detects sync vs async functions — `async def` decorated functions
    return an awaitable that still swallows via the same path.

    Only for non-critical paths where swallowing is the documented behavior
    (e.g. best-effort cache warm-up, telemetry ping). Never use on request paths.
    """

    def decorator(fn: Callable[..., T]) -> Callable[..., T]:
        if inspect.iscoroutinefunction(fn):

            @functools.wraps(fn)
            async def async_wrapper(*args: Any, **kwargs: Any) -> T:
                try:
                    return await fn(*args, **kwargs)  # type: ignore[misc]
                except Exception as exc:
                    log_error(phase, exc, context=context, severity="swallow")
                    return fallback

            return async_wrapper  # type: ignore[return-value]

        @functools.wraps(fn)
        def wrapper(*args: Any, **kwargs: Any) -> T:
            try:
                return fn(*args, **kwargs)
            except Exception as exc:
                log_error(phase, exc, context=context, severity="swallow")
                return fallback

        return wrapper

    return decorator


@contextlib.asynccontextmanager
async def log_scope_async(phase: str, **context: Any) -> AsyncIterator[None]:
    """Async context manager equivalent of `log_scope`.

    Usage:
        async with log_scope_async("api-enrich-person", address=addr):
            result = await lookup(addr)
    """
    try:
        yield
    except Exception as exc:
        log_error(phase, exc, context=context)
        raise


def recent_errors(limit: int = 50) -> list[dict[str, Any]]:
    """Return the last `limit` error entries. For dashboards / debug endpoints."""
    if not ERRORS_LOG.exists():
        return []
    lines = ERRORS_LOG.read_text(encoding="utf-8").splitlines()
    out: list[dict[str, Any]] = []
    for line in lines[-limit:]:
        try:
            out.append(json.loads(line))
        except json.JSONDecodeError:
            continue
    return out


def error_counts_by_type(limit: int = 500) -> dict[str, int]:
    """Aggregate last `limit` errors by type for Pareto triage."""
    counts: dict[str, int] = {}
    for entry in recent_errors(limit):
        t = entry.get("error_type", "Unknown")
        counts[t] = counts.get(t, 0) + 1
    return dict(sorted(counts.items(), key=lambda kv: kv[1], reverse=True))
