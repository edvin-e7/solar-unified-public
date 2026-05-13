"""Adversarial matrix for backend/learning_journal.py.

Spec: backend/specs/learning_journal.md.

Each test isolates the journal/summary paths into a tmp dir so the real
journal at backend/prompts/learned/journal.jsonl is never touched.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
if str(BACKEND_DIR) not in sys.path:
    sys.path.insert(0, str(BACKEND_DIR))


@pytest.fixture
def isolated_journal(tmp_path, monkeypatch):
    """Re-import learning_journal with JOURNAL/SUMMARY rerouted to tmp_path."""
    sys.modules.pop("learning_journal", None)
    import learning_journal  # type: ignore

    monkeypatch.setattr(learning_journal, "LEARNED_DIR", tmp_path)
    monkeypatch.setattr(learning_journal, "JOURNAL", tmp_path / "journal.jsonl")
    monkeypatch.setattr(learning_journal, "SUMMARY", tmp_path / "summary.md")
    return learning_journal


def test_record_then_entries_roundtrip(isolated_journal):
    isolated_journal.record("test-phase", "passed", "lesson body")
    entries = isolated_journal.entries()
    assert len(entries) == 1
    assert entries[0]["phase"] == "test-phase"
    assert entries[0]["outcome"] == "passed"
    assert entries[0]["lesson"] == "lesson body"


def test_summary_regenerated_after_record(isolated_journal):
    isolated_journal.record("p", "passed", "a")
    isolated_journal.record("p", "failed", "b")
    summary = isolated_journal.SUMMARY.read_text()
    assert "Lessons journal (2 entries" in summary
    assert "**p** — a" in summary
    assert "**p** — b" in summary


def test_redact_lines_removes_name_pattern(isolated_journal):
    """Names are NOT auto-filtered by record() (too noisy regex), so
    redact_lines() is the sanctioned escape hatch for them. Phone in this
    same lesson would already have been auto-redacted by Fas 1.d filter."""
    isolated_journal.record(
        "api-prospects-bulk-enrich-contacts-row",
        "error",
        "RuntimeError: boom Anna Andersson 070-1234567",
    )
    raw_after_record = isolated_journal.JOURNAL.read_text()
    # Phone auto-redacted by record()
    assert "070-1234567" not in raw_after_record
    assert "<PHONE_REDACTED>" in raw_after_record
    # Name still present (record's filter doesn't touch names)
    assert "Anna Andersson" in raw_after_record

    counts = isolated_journal.redact_lines({"Anna Andersson": "<NAME_REDACTED>"})
    assert counts["Anna Andersson"] >= 1

    raw = isolated_journal.JOURNAL.read_text()
    assert "Anna Andersson" not in raw
    assert "<NAME_REDACTED>" in raw

    # And the redaction itself was journaled (audit trail)
    last = isolated_journal.entries()[-1]
    assert last["phase"] == "journal-redaction"


def test_redact_lines_empty_pattern_rejected(isolated_journal):
    isolated_journal.record("p", "passed", "ok")
    with pytest.raises(ValueError, match="empty pattern"):
        isolated_journal.redact_lines({"": "x"})


def test_redact_lines_no_journal_returns_zero_counts(isolated_journal):
    # journal does not exist yet (fresh tmp dir, no record() yet)
    counts = isolated_journal.redact_lines({"foo": "bar"})
    assert counts == {"foo": 0}


def test_redact_lines_atomic_no_temp_left_behind(isolated_journal):
    isolated_journal.record("p", "passed", "needle in the haystack")
    isolated_journal.redact_lines({"needle": "X"})
    # Temp file must be gone after replace()
    tmp = isolated_journal.JOURNAL.with_suffix(isolated_journal.JOURNAL.suffix + ".redact-tmp")
    assert not tmp.exists()


def test_corrupt_line_is_skipped_not_raised(isolated_journal):
    isolated_journal.record("p", "passed", "good")
    # Append a deliberately broken line bypassing record()
    with isolated_journal.JOURNAL.open("a", encoding="utf-8") as f:
        f.write("{not json\n")
    isolated_journal.record("q", "passed", "good2")
    # entries() must still return the two valid rows, silently skipping the bad one
    es = isolated_journal.entries()
    assert [e["phase"] for e in es] == ["p", "q"]


def test_redaction_count_is_pre_replacement(isolated_journal):
    isolated_journal.record("p", "passed", "aaa")
    counts = isolated_journal.redact_lines({"a": "b"})
    # The lesson "aaa" contains 3 'a's; verify counts reflects pre-replace
    assert counts["a"] >= 3


# ============================================================
# Fas 1.d — automatic PII filter on record()
# ============================================================

def test_record_redacts_swedish_phone_in_lesson(isolated_journal):
    isolated_journal.record("p", "passed", "Customer phone is 070-1234567 boom")
    raw = isolated_journal.JOURNAL.read_text()
    assert "070-1234567" not in raw
    assert "<PHONE_REDACTED>" in raw


def test_record_redacts_phone_compact_format(isolated_journal):
    isolated_journal.record("p", "passed", "Reach me at 0701234567 today")
    raw = isolated_journal.JOURNAL.read_text()
    assert "0701234567" not in raw
    assert "<PHONE_REDACTED>" in raw


def test_record_redacts_phone_international_format(isolated_journal):
    isolated_journal.record("p", "passed", "Phone: +46 70 123 45 67 ok")
    raw = isolated_journal.JOURNAL.read_text()
    assert "+46 70 123 45 67" not in raw


def test_record_redacts_email(isolated_journal):
    isolated_journal.record("p", "passed", "Got bounce from bob.test@example.com")
    raw = isolated_journal.JOURNAL.read_text()
    assert "bob.test@example.com" not in raw
    assert "<EMAIL_REDACTED>" in raw


def test_record_redacts_pii_in_error_field(isolated_journal):
    isolated_journal.record(
        "p", "error", "Failed", error="boom 070-1234567 customer at a@b.co"
    )
    raw = isolated_journal.JOURNAL.read_text()
    assert "070-1234567" not in raw
    assert "a@b.co" not in raw


def test_record_redacts_pii_recursively_in_metadata(isolated_journal):
    isolated_journal.record(
        "p", "passed", "ok",
        metadata={
            "address": "Storgatan 1",
            "contact": {"phone": "070-1234567", "email": "x@y.se"},
            "ids": ["A1", "B2"],
        },
    )
    raw = isolated_journal.JOURNAL.read_text()
    assert "070-1234567" not in raw
    assert "x@y.se" not in raw
    # Non-PII strings must NOT be redacted
    assert "Storgatan 1" in raw
    # Non-string types must survive
    assert '"A1"' in raw and '"B2"' in raw


def test_pii_filter_idempotent(isolated_journal):
    # Already-redacted markers stay intact through a second pass
    isolated_journal.record("p", "passed", "<PHONE_REDACTED> already gone")
    raw = isolated_journal.JOURNAL.read_text()
    assert "<PHONE_REDACTED>" in raw


def test_pii_filter_does_not_redact_short_numerics(isolated_journal):
    """SQL row counts, status codes, and similar short numbers should NOT
    accidentally match the phone regex."""
    isolated_journal.record(
        "p", "passed", "Created 5 prospects, HTTP 200, batch 42 succeeded"
    )
    raw = isolated_journal.JOURNAL.read_text()
    # None of the legitimate short numbers should be redacted away
    assert "Created 5" in raw
    assert "HTTP 200" in raw
    assert "batch 42" in raw
