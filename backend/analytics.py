"""
Analytics-integration mot lokal ClickHouse.

Best-effort: events bufferas + flushas batch async. Om ClickHouse är nere
fails silently — analytics får aldrig blockera scan/enrichment.

Server: http://localhost:8123 default, override CLICKHOUSE_URL env.
Schema: edvin.events (se ~/edvin-projects/clickhouse-analytics/schema.sql)

CLAUDE.md compliance:
  rule 6 (every catch logged) — flush-errors logas via error_logger
  rule 10 (PII first-class) — properties får INTE innehålla full prospect-name
"""

from __future__ import annotations

import asyncio
import json
import logging
import os
import threading
from typing import Any

import httpx

_CH_URL = os.environ.get("CLICKHOUSE_URL", "http://localhost:8123")
_PROJECT = "solar-unified"
_FLUSH_INTERVAL_S = 10.0
_MAX_BATCH = 100

_log = logging.getLogger(__name__)
_queue: list[dict] = []
_lock = threading.Lock()
_flush_task: asyncio.Task | None = None


def track(
    event_name: str,
    *,
    subject_id: str,
    subject_type: str,
    family: str | None = None,
    score: float | None = None,
    region: str | None = None,
    **properties: Any,
) -> None:
    """Queue an event. Returns immediately. Never raises.

    CAVEAT: properties får inte innehålla prospect-PII (namn, telefon).
    Use subject_id (prospect-DB-id) eller hash istället.
    """
    event: dict = {
        "project": _PROJECT,
        "event_name": event_name,
        "subject_id": str(subject_id),
        "subject_type": subject_type,
    }
    if family is not None:
        event["family"] = family
    if score is not None:
        event["score"] = float(score)
    if region is not None:
        event["region"] = region
    if properties:
        event["properties"] = json.dumps(properties, ensure_ascii=False)

    with _lock:
        _queue.append(event)
        should_flush_now = len(_queue) >= _MAX_BATCH

    if should_flush_now:
        # Trigger async flush — schedule if loop exists, else fire-and-forget
        try:
            loop = asyncio.get_event_loop()
            loop.create_task(_flush())
        except RuntimeError:
            # No running loop — caller is sync. Defer to thread.
            threading.Thread(target=lambda: asyncio.run(_flush()), daemon=True).start()


async def _flush() -> None:
    """Drain queue to ClickHouse. Silent on network-fail."""
    with _lock:
        if not _queue:
            return
        batch = _queue[:_MAX_BATCH]
        del _queue[:_MAX_BATCH]

    ndjson = "\n".join(json.dumps(e, ensure_ascii=False) for e in batch)
    url = f"{_CH_URL}/?query=INSERT+INTO+edvin.events+FORMAT+JSONEachRow"
    try:
        async with httpx.AsyncClient(timeout=2.0) as client:
            await client.post(url, content=ndjson.encode("utf-8"))
    except (httpx.HTTPError, OSError) as exc:
        # Silent fail per CLAUDE.md PII-first-class — log to error_logger
        # for visibility but don't block. error_logger import deferred to
        # avoid circular dep (analytics is leaf-import).
        try:
            from error_logger import log_error
            log_error("analytics-flush", exc, context={"batch_size": len(batch)})
        except Exception:
            _log.warning("analytics flush failed: %s (lost %d events)", exc, len(batch))


async def flush_now() -> None:
    """Force-flush remaining events. Call at shutdown."""
    await _flush()
