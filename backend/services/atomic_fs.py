"""Crash-safe whole-file writes.

Atomic-tempfile + os.replace pattern. Reader on disk always sees either the
previous content or the new content — never a partial. Solves
[docs/BUGS.md](../../docs/BUGS.md) Bugs 5 (image writes), 6 (prompt
auto-applicator), 7 (scan history JSON).

Spec: backend/specs/atomic_fs.md
Adversarial matrix: backend/specs/test_atomic_fs.py
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

from services.structured_log import (
    _thread_lock_for,
)
from services.structured_log import (
    write_json_atomic as _structured_log_write_json_atomic,
)

__all__ = [
    "write_bytes_atomic",
    "write_json_atomic",
    "write_text_atomic",
]


def write_bytes_atomic(path: Path, data: bytes) -> None:
    """Write bytes atomically: tempfile + os.replace.

    Raises:
        FileNotFoundError: parent dir missing (we do NOT auto-create).
        PermissionError, OSError: from underlying filesystem ops.
    """
    if not path.parent.exists():
        raise FileNotFoundError(f"parent dir missing: {path.parent}")

    tmp = path.with_suffix(path.suffix + ".tmp")
    lock = _thread_lock_for(path)
    with lock:
        tmp.write_bytes(data)
        os.replace(tmp, path)


def write_text_atomic(path: Path, text: str, *, encoding: str = "utf-8") -> None:
    """Write text atomically: tempfile + os.replace.

    Raises:
        FileNotFoundError: parent dir missing.
        PermissionError, OSError: from underlying filesystem ops.
        UnicodeEncodeError: text not encodable in the requested encoding.
    """
    if not path.parent.exists():
        raise FileNotFoundError(f"parent dir missing: {path.parent}")

    tmp = path.with_suffix(path.suffix + ".tmp")
    lock = _thread_lock_for(path)
    with lock:
        tmp.write_text(text, encoding=encoding)
        os.replace(tmp, path)


def write_json_atomic(path: Path, data: Any) -> None:
    """Whole-file JSON atomic write. Delegates to structured_log primitive.

    Re-exported here so callers have a single ``atomic_fs`` import surface
    for all three crash-safe write shapes (bytes / text / json).
    """
    _structured_log_write_json_atomic(path, data)
