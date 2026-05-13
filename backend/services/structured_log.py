"""Atomic structured logging primitive.

Single source of truth for every jsonl append and every json-state rewrite in
the backend. error_logger, prompt_log, issue_ledger, learning_journal all
route through here. See specs/structured_log.md.

Why this exists:
    Prior audit (2026-04-24) found every logging module re-implemented its own
    "open + write" and every one had a different correctness gap: non-atomic
    state writes, no PII hook, no async safety, sync-only context managers on
    async code paths. Fixing them in-place would ship four different fixes.
    One primitive + matrix catches the bug class once.
"""

from __future__ import annotations

import asyncio
import contextlib
import json
import os
import threading
from collections.abc import Callable, Mapping
from pathlib import Path
from typing import Any

try:
    import fcntl  # POSIX only

    _HAS_FCNTL = True
except ImportError:  # pragma: no cover — Windows fallback path
    _HAS_FCNTL = False


RedactFn = Callable[[dict], dict]


# Per-path locks: async for coroutine-concurrent callers, threading for sync callers.
_async_locks: dict[str, asyncio.Lock] = {}
_async_locks_guard = threading.Lock()
_thread_locks: dict[str, threading.Lock] = {}
_thread_locks_guard = threading.Lock()


def _async_lock_for(path: Path) -> asyncio.Lock:
    key = str(path)
    with _async_locks_guard:
        lock = _async_locks.get(key)
        if lock is None:
            lock = asyncio.Lock()
            _async_locks[key] = lock
        return lock


def _thread_lock_for(path: Path) -> threading.Lock:
    key = str(path)
    with _thread_locks_guard:
        lock = _thread_locks.get(key)
        if lock is None:
            lock = threading.Lock()
            _thread_locks[key] = lock
        return lock


def _ensure_dict(record: Any) -> dict:
    if not isinstance(record, Mapping):
        raise TypeError(
            f"structured_log expects dict-like record, got {type(record).__name__}"
        )
    return dict(record)


def _encode_jsonl_line(record: dict, redact: RedactFn | None) -> bytes:
    if redact is not None:
        record = redact(record)
    line = json.dumps(record, ensure_ascii=False, default=str)
    return (line + "\n").encode("utf-8")


def append_jsonl_sync(
    path: Path,
    record: Mapping[str, Any],
    *,
    redact: RedactFn | None = None,
) -> None:
    """Append one jsonl record. Cross-thread and cross-process safe on POSIX.

    Raises:
        TypeError: record is not a mapping.
        FileNotFoundError: parent dir missing (we do NOT auto-create).
        json.JSONEncodeError: record not json-serialisable.
    """
    data = _ensure_dict(record)
    payload = _encode_jsonl_line(data, redact)

    if not path.parent.exists():
        raise FileNotFoundError(f"parent dir missing: {path.parent}")

    lock = _thread_lock_for(path)
    with lock:
        # "ab" = append bytes, O_APPEND is atomic for single write < PIPE_BUF (4096)
        # on POSIX. flock adds cross-process safety.
        with open(path, "ab") as f:
            if _HAS_FCNTL:
                fcntl.flock(f.fileno(), fcntl.LOCK_EX)
                try:
                    f.write(payload)
                finally:
                    fcntl.flock(f.fileno(), fcntl.LOCK_UN)
            else:  # pragma: no cover
                f.write(payload)


async def append_jsonl(
    path: Path,
    record: Mapping[str, Any],
    *,
    redact: RedactFn | None = None,
) -> None:
    """Async append. Serialises concurrent coroutines via per-path asyncio.Lock
    and still relies on sync O_APPEND atomicity underneath."""
    data = _ensure_dict(record)
    payload = _encode_jsonl_line(data, redact)

    if not path.parent.exists():
        raise FileNotFoundError(f"parent dir missing: {path.parent}")

    lock = _async_lock_for(path)
    async with lock:
        # Offload the blocking write to a thread so the event loop is not
        # stalled for concurrent callers on other paths.
        await asyncio.to_thread(_blocking_append, path, payload)


def _blocking_append(path: Path, payload: bytes) -> None:
    tlock = _thread_lock_for(path)
    with tlock, open(path, "ab") as f:
        if _HAS_FCNTL:
            fcntl.flock(f.fileno(), fcntl.LOCK_EX)
            try:
                f.write(payload)
            finally:
                fcntl.flock(f.fileno(), fcntl.LOCK_UN)
        else:  # pragma: no cover
            f.write(payload)


def write_json_atomic(
    path: Path,
    data: Any,
    *,
    redact: RedactFn | None = None,
) -> None:
    """Write whole-file JSON atomically (tempfile + os.replace).

    Reader always sees either the old file or the new file — never a partial.
    If redact is given AND root is a dict, it is applied before encode; for
    non-dict roots (list/scalar), redact is ignored.
    """
    if isinstance(data, Mapping) and redact is not None:
        data = redact(dict(data))

    encoded = json.dumps(data, indent=2, ensure_ascii=False, default=str)
    tmp = path.with_suffix(path.suffix + ".tmp")

    lock = _thread_lock_for(path)
    with lock:
        tmp.write_text(encoded, encoding="utf-8")
        os.replace(tmp, path)


def cleanup_stale_tmp(path: Path) -> None:
    """Remove <path>.tmp sibling if present — left by a crashed prior write.

    Call at module import / service boot for every persistent state file.
    """
    tmp = path.with_suffix(path.suffix + ".tmp")
    if tmp.exists():
        with contextlib.suppress(OSError):
            tmp.unlink()


__all__ = [
    "RedactFn",
    "append_jsonl",
    "append_jsonl_sync",
    "cleanup_stale_tmp",
    "write_json_atomic",
]
