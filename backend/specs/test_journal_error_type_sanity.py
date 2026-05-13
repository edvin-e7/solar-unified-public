"""Adversarial matrix for learning_journal.record() error_type sanity-check.

Fixes docs/BUGS.md Bug 8 — 15 consecutive failed entries from 2026-04-21 wrote
empty err= metadata, making the journal unusable for diagnosis. Sanity-check
in record() now defaults metadata.error_type="unspecified" when caller forgets
and logs a WARN.

Run: python3 -m pytest backend/specs/test_journal_error_type_sanity.py -v
"""

from __future__ import annotations

import json
import logging
import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def isolated_journal(tmp_path, monkeypatch):
    """Same fixture-pattern as test_learning_journal.py — tmp-path-rerouted."""
    sys.modules.pop("learning_journal", None)
    import learning_journal  # type: ignore

    monkeypatch.setattr(learning_journal, "LEARNED_DIR", tmp_path)
    monkeypatch.setattr(learning_journal, "JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr(learning_journal, "SUMMARY", tmp_path / "summary.md")
    return learning_journal


# ----- B1: failed outcome without metadata.error_type → defaults + warns -----


def test_failed_without_error_type_defaults_to_unspecified(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("test-phase", "failed", "broke somehow")

    entries = isolated_journal.entries()
    assert len(entries) == 1
    assert entries[0]["outcome"] == "failed"
    assert entries[0]["metadata"]["error_type"] == "unspecified"
    # Warned
    assert any("missing metadata.error_type" in r.getMessage() for r in caplog.records)


def test_error_without_error_type_defaults_to_unspecified(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("test-phase", "error", "exception X")

    entries = isolated_journal.entries()
    assert entries[0]["metadata"]["error_type"] == "unspecified"
    assert any("missing metadata.error_type" in r.getMessage() for r in caplog.records)


# ----- B2: empty-string error_type also triggers default --------------------


def test_failed_with_empty_string_error_type_defaults(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("p", "failed", "l", metadata={"error_type": ""})

    entries = isolated_journal.entries()
    assert entries[0]["metadata"]["error_type"] == "unspecified"


def test_failed_with_whitespace_error_type_defaults(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("p", "failed", "l", metadata={"error_type": "   "})

    entries = isolated_journal.entries()
    assert entries[0]["metadata"]["error_type"] == "unspecified"


def test_failed_with_none_error_type_defaults(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("p", "failed", "l", metadata={"error_type": None})

    entries = isolated_journal.entries()
    assert entries[0]["metadata"]["error_type"] == "unspecified"


# ----- B3: failed WITH a real error_type passes through unchanged + no warn -


def test_failed_with_real_error_type_preserved(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record(
            "p",
            "failed",
            "l",
            metadata={"error_type": "TimeoutError", "service": "hitta"},
        )

    entries = isolated_journal.entries()
    assert entries[0]["metadata"]["error_type"] == "TimeoutError"
    assert entries[0]["metadata"]["service"] == "hitta"
    # Should NOT warn — caller did the right thing
    assert not any(
        "missing metadata.error_type" in r.getMessage() for r in caplog.records
    )


# ----- B4: passed/no_op without error_type — NO default, NO warn ------------


def test_passed_without_error_type_no_default_no_warn(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("p", "passed", "l", metadata={"foo": "bar"})

    entries = isolated_journal.entries()
    assert "error_type" not in entries[0]["metadata"]
    assert entries[0]["metadata"]["foo"] == "bar"
    assert not any(
        "missing metadata.error_type" in r.getMessage() for r in caplog.records
    )


def test_no_op_without_error_type_no_default_no_warn(isolated_journal, caplog):
    with caplog.at_level(logging.WARNING, logger="learning_journal"):
        isolated_journal.record("p", "no_op", "l")

    entries = isolated_journal.entries()
    assert "error_type" not in entries[0]["metadata"]
    assert not any(
        "missing metadata.error_type" in r.getMessage() for r in caplog.records
    )


# ----- B5: caller's metadata dict is not mutated (defensive copy) -----------


def test_caller_metadata_not_mutated_on_default(isolated_journal):
    caller_meta = {"some_key": "value"}
    isolated_journal.record("p", "failed", "l", metadata=caller_meta)
    # The default was injected into the journal entry but NOT into caller's dict
    assert "error_type" not in caller_meta
    assert caller_meta == {"some_key": "value"}


# ----- B6: backwards-compat — pattern_detector consumes existing entries ----


def test_journal_entries_are_json_parseable_after_default(isolated_journal):
    """run_autonomous_cycle reads journal.jsonl and groups by error_type.
    Defaulted entries must be valid JSON with error_type present."""
    isolated_journal.record("phase-a", "failed", "lesson")
    isolated_journal.record("phase-b", "error", "another")

    raw_lines = isolated_journal.JOURNAL.read_text(encoding="utf-8").splitlines()
    parsed = [json.loads(line) for line in raw_lines if line.strip()]
    assert len(parsed) == 2
    for entry in parsed:
        assert entry["metadata"]["error_type"] == "unspecified"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
