"""SQLite-backed cache for agent-generated insights.

One row per (insight_type, generated day). Dashboard reads the freshest row
whose `expires_at` is in the future; on miss, callers generate live + store.
"""

from __future__ import annotations

import json
import sqlite3
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

DB_PATH = Path(__file__).parent / "data" / "prospects.db"

_SCHEMA = """
CREATE TABLE IF NOT EXISTS agent_insights (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    insight_type TEXT NOT NULL,
    generated_at TEXT NOT NULL,
    expires_at TEXT NOT NULL,
    payload_json TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS idx_insights_type_fresh
    ON agent_insights(insight_type, expires_at);
"""


def _conn() -> sqlite3.Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.executescript(_SCHEMA)
    return conn


def get_cached(insight_type: str) -> dict[str, Any] | None:
    conn = _conn()
    try:
        row = conn.execute(
            """
            SELECT payload_json FROM agent_insights
            WHERE insight_type = ? AND expires_at > ?
            ORDER BY generated_at DESC LIMIT 1
            """,
            (insight_type, datetime.now(UTC).isoformat()),
        ).fetchone()
        return json.loads(row[0]) if row else None
    finally:
        conn.close()


def store(insight_type: str, payload: dict[str, Any], ttl_hours: int = 24) -> None:
    now = datetime.now(UTC)
    expires = now + timedelta(hours=ttl_hours)
    conn = _conn()
    try:
        conn.execute(
            """
            INSERT INTO agent_insights (insight_type, generated_at, expires_at, payload_json)
            VALUES (?, ?, ?, ?)
            """,
            (insight_type, now.isoformat(), expires.isoformat(), json.dumps(payload, ensure_ascii=False)),
        )
        conn.commit()
    finally:
        conn.close()
