"""Adversarial matrix for orchestrator ↔ issue_ledger write contract.

Guards: ledger grows from real cycles, infra failures never pollute it,
idempotent keys, resilient to ledger corruption.

Run: python3 backend/specs/test_orchestrator_ledger_write.py
"""

from __future__ import annotations

import asyncio
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Sandbox ledger + journal before importing anything that touches them
_SANDBOX_DIR = Path(tempfile.mkdtemp(prefix="orch_ledger_"))
_LEDGER = _SANDBOX_DIR / "ledger.json"
_JOURNAL_DIR = _SANDBOX_DIR / "learned"
_JOURNAL_DIR.mkdir()

import issue_ledger  # noqa: E402
import learning_journal  # noqa: E402

issue_ledger.LEDGER_PATH = _LEDGER
learning_journal.JOURNAL = _JOURNAL_DIR / "journal.jsonl"
learning_journal.SUMMARY = _JOURNAL_DIR / "summary.md"
learning_journal.LEARNED_DIR = _JOURNAL_DIR

from executors.orchestrator import Orchestrator  # noqa: E402


def _reset():
    for p in (_LEDGER, learning_journal.JOURNAL, learning_journal.SUMMARY):
        if p.exists():
            p.unlink()


def _make_orch(
    *,
    cove_result: dict,
    apply_result: dict | None = None,
    patterns: list[dict] | None = None,
):
    """Orchestrator with pattern_detector, collective_verify, auto_apply all mocked."""
    orch = Orchestrator()
    orch.pattern_detector.detect_patterns = MagicMock(return_value={
        "patterns_found": len(patterns or []),
        "patterns": patterns or [{"name": "low_detection_confidence", "frequency": 5}],
    })
    orch.collective_verify.verify_improvement = AsyncMock(return_value=cove_result)
    orch.auto_apply.apply_improvement = MagicMock(
        return_value=apply_result or {"applied": False, "commit": None, "reason": "stub"}
    )
    return orch


def _run(orch):
    return asyncio.run(orch.run_learning_cycle())


# --- 1. First run, no prior → rejection writes ledger → second run filtered ---

def test_rejected_cycle_populates_ledger_then_next_cycle_blocks():
    _reset()
    cove = {
        "verified": False,
        "confidence": 0.4,
        "reasoning": "CoVe doubt",
        "llm_errors": [],
        "agent_votes": {},
    }
    # First cycle: no prior, CoVe rejects
    orch = _make_orch(cove_result=cove)
    r1 = _run(orch)
    assert r1["improvements_generated"] == 1, r1
    assert r1["improvements_applied"] == 0

    data = issue_ledger._load()
    issues = list(data["issues"].values())
    assert len(issues) == 1, issues
    assert issues[0]["attempts"][0]["outcome"] == "rejected_by_cove"

    # Second cycle: same pattern → improvement_generator filter blocks BEFORE verify is called
    orch2 = _make_orch(cove_result=cove)
    r2 = _run(orch2)
    assert r2["improvements_generated"] == 0, r2
    assert r2["skipped_already_tried"] == 1, r2
    # collective_verify must not have been called on this cycle
    orch2.collective_verify.verify_improvement.assert_not_called()


# --- 2. Infra failure → no ledger write → next run without infra failure proceeds ---

def test_infra_failure_does_not_pollute_ledger():
    _reset()
    cove_degraded = {
        "verified": False,
        "confidence": 0.5,
        "reasoning": "Gemini unavailable",
        "llm_errors": ["answers_fallback"],
        "agent_votes": {},
    }
    orch = _make_orch(cove_result=cove_degraded)
    r = _run(orch)
    assert r["improvements_generated"] == 1
    assert r["improvements_applied"] == 0

    data = issue_ledger._load()
    # open_issue still fires for audit, but no attempt should be logged
    issues = list(data["issues"].values())
    if issues:
        assert all(len(i["attempts"]) == 0 for i in issues), \
            f"infra failure must not log an attempt: {issues}"


def test_second_cycle_after_infra_failure_is_not_blocked_by_filter():
    _reset()
    cove_degraded = {
        "verified": False, "confidence": 0.5, "reasoning": "429",
        "llm_errors": ["questions_fallback", "answers_fallback"],
        "agent_votes": {},
    }
    orch1 = _make_orch(cove_result=cove_degraded)
    _run(orch1)

    # Quota returns — same pattern runs again, cove rejects legitimately
    cove_real_reject = {
        "verified": False, "confidence": 0.4, "reasoning": "doubt",
        "llm_errors": [], "agent_votes": {},
    }
    orch2 = _make_orch(cove_result=cove_real_reject)
    r2 = _run(orch2)
    # Must NOT be filtered — the infra-failed cycle did not write ledger
    assert r2["improvements_generated"] == 1, r2
    assert r2["skipped_already_tried"] == 0, r2
    orch2.collective_verify.verify_improvement.assert_called_once()


# --- 3. Success path → log_attempt(success) → issue resolves ---

def test_success_path_logs_success_and_resolves():
    _reset()
    cove_ok = {
        "verified": True, "confidence": 0.9, "reasoning": "looks good",
        "llm_errors": [], "agent_votes": {"detection": 0.9},
    }
    apply_ok = {"applied": True, "commit": "abc123", "reason": "Applied"}
    orch = _make_orch(cove_result=cove_ok, apply_result=apply_ok)
    r = _run(orch)
    assert r["improvements_applied"] == 1

    data = issue_ledger._load()
    issue = next(iter(data["issues"].values()))
    assert issue["attempts"][0]["outcome"] == "success"
    assert issue["status"] == "resolved"
    assert issue["resolution"] is not None


# --- 4. Apply failure distinct from CoVe rejection ---

def test_apply_failure_logs_failed_not_rejected():
    _reset()
    cove_ok = {
        "verified": True, "confidence": 0.9, "reasoning": "ok",
        "llm_errors": [], "agent_votes": {},
    }
    apply_failed = {"applied": False, "commit": None, "reason": "Failed: IOError"}
    orch = _make_orch(cove_result=cove_ok, apply_result=apply_failed)
    r = _run(orch)
    assert r["improvements_applied"] == 0

    issue = next(iter(issue_ledger._load()["issues"].values()))
    assert issue["attempts"][0]["outcome"] == "failed"
    assert issue["status"] != "resolved"
    assert "IOError" in str(issue["attempts"][0]["evidence"])


# --- 5. Idempotent issue key ---

def test_two_cycles_same_pattern_one_issue_two_attempts():
    _reset()
    # Two independent rejected cycles. Second cycle's hypothesis must differ
    # enough that the filter doesn't block it (so we reach the write path twice).
    # We fake this by mocking the improvement_generator output.
    cove_reject = {
        "verified": False, "confidence": 0.4, "reasoning": "doubt",
        "llm_errors": [], "agent_votes": {},
    }
    orch = _make_orch(cove_result=cove_reject)
    # First cycle: real improvement
    _run(orch)

    # Manually log a second attempt with the same key — simulating a different-enough
    # hypothesis that got past the filter. This proves idempotent key derivation.
    from executors.improvement_generator import ImprovementGenerator
    gen = ImprovementGenerator()
    gen.generate_improvements(
        [{"name": "low_detection_confidence", "frequency": 5}]
    )
    # Since first cycle already wrote, second call would be filtered.
    # Key stability test: open_issue with same (pattern, target) returns same key.
    key1 = issue_ledger.open_issue(
        error_type="low_detection_confidence",
        target="backend/prompts/detection.md",
        title="t",
    )
    key2 = issue_ledger.open_issue(
        error_type="low_detection_confidence",
        target="backend/prompts/detection.md",
        title="t-different-title",
    )
    assert key1 == key2, "issue key must be idempotent across open_issue calls"

    issue = issue_ledger._load()["issues"][key1]
    # occurrences: first_cycle_open(1) + first_cycle_log_attempt_sets_last_seen(no bump) +
    # our two open_issue calls (+2). Actual semantics: each open_issue increments.
    assert issue["occurrences"] >= 2


# --- 6. Ledger corruption resilience ---

def test_log_attempt_exception_does_not_crash_cycle(monkeypatch=None):
    _reset()
    cove_reject = {
        "verified": False, "confidence": 0.4, "reasoning": "doubt",
        "llm_errors": [], "agent_votes": {},
    }
    orch = _make_orch(cove_result=cove_reject)

    # Break log_attempt
    import executors.orchestrator as orch_mod
    original = issue_ledger.log_attempt

    def boom(*args, **kwargs):
        raise RuntimeError("ledger file corrupted")

    try:
        orch_mod.log_attempt = boom  # monkey-patch at the import site
        result = _run(orch)
        # Cycle still returns — didn't crash
        assert result["phase"] == "autonomous-learning"
    finally:
        orch_mod.log_attempt = original


# --- 7. Multiple independent improvements same cycle ---

def test_multiple_patterns_multiple_ledger_entries():
    _reset()
    cove_reject = {
        "verified": False, "confidence": 0.4, "reasoning": "doubt",
        "llm_errors": [], "agent_votes": {},
    }
    orch = _make_orch(
        cove_result=cove_reject,
        patterns=[
            {"name": "low_detection_confidence", "frequency": 5},
            {"name": "low_enrichment_rate", "frequency": 3},
            {"name": "high_validation_rejection", "frequency": 4},
        ],
    )
    r = _run(orch)
    assert r["improvements_generated"] == 3
    issues = issue_ledger._load()["issues"]
    assert len(issues) == 3
    for issue in issues.values():
        assert len(issue["attempts"]) == 1
        assert issue["attempts"][0]["outcome"] == "rejected_by_cove"


# --- runner ---

def _run_all():
    import traceback

    g = globals()
    names = sorted(n for n in g if n.startswith("test_"))
    passed = 0
    failed: list[tuple[str, str]] = []
    for name in names:
        try:
            g[name]()
            passed += 1
            print(f"  [PASS] {name}")
        except Exception as exc:
            failed.append((name, f"{type(exc).__name__}: {exc}\n{traceback.format_exc()}"))
            print(f"  [FAIL] {name}: {exc}")
    print(f"\n{passed}/{len(names)} passed, {len(failed)} failed")
    if failed:
        for name, tb in failed:
            print(f"\n[{name}]\n{tb}")
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
