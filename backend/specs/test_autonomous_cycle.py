"""Adversarial matrix for backend/scripts/run_autonomous_cycle.py.

Spec: backend/specs/autonomous_cycle.md.

Each test feeds a synthetic journal directly into `analyze()` /
`generate_suggestions()` / `cove_vote()` so we never touch the real
journal.jsonl. Maps 1:1 onto the meta-bugs Opus flagged across cycles
51-68 — if any test goes red, we are back in the rubber-stamp loop.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

BACKEND_DIR = Path(__file__).resolve().parents[1]
SCRIPTS_DIR = BACKEND_DIR / "scripts"
for p in (str(BACKEND_DIR), str(SCRIPTS_DIR)):
    if p not in sys.path:
        sys.path.insert(0, p)

import run_autonomous_cycle as cyc  # type: ignore  # noqa: E402

# ---------- Fixture journals ----------

def _entry(phase, outcome="passed", lesson="", error="", files=None, meta=None):
    return {
        "phase": phase,
        "outcome": outcome,
        "lesson": lesson,
        "error": error,
        "files": files or [],
        "metadata": meta or {},
    }


# ============================================================
# (b) verify_count uses exact match — substring bug regression
# ============================================================

def test_verify_count_excludes_cove_verify_opus():
    """The exact bug Opus flagged in cycles 51-68: 'verify' in str(k) matched
    cove-verify-opus and self-armed S2. Count must be 0 here."""
    journal = [
        _entry("cove-verify-opus", outcome="failed"),
        _entry("cove-verify-opus", outcome="failed"),
        _entry("cove-verify-opus", outcome="failed"),
        _entry("cove-verify-opus", outcome="failed"),
        _entry("cove-verify-opus", outcome="failed"),
    ]
    analysis = cyc.analyze(journal)
    suggestions = cyc.generate_suggestions(analysis)
    s2 = [s for s in suggestions if s["id"] == "S2"]
    assert s2 == [], f"S2 must NOT be generated from cove-verify-opus alone; got {s2}"


def test_verify_count_includes_real_verify_phases():
    journal = [_entry("verify", outcome="passed") for _ in range(4)]
    analysis = cyc.analyze(journal)
    suggestions = cyc.generate_suggestions(analysis)
    s2 = [s for s in suggestions if s["id"] == "S2"]
    # S2 should be generated when canonical verify_count >= 4
    assert len(s2) == 1


# ============================================================
# (a) cove_vote() is content-analytical, not rubber-stamp
# ============================================================

def test_cove_vote_rejects_empty_rationale_low_risk():
    """Old code: low-risk -> 5/5 approve unconditionally. New code: needs 3+
    positive content signals."""
    sug = {
        "id": "X",
        "title": "x",
        "rationale": "",
        "target_file": "prompts/learned/x.md",
        "template_key": "nonexistent",
        "risk": "low",
        "already_exists": False,
    }
    analysis = {"hot_files": [], "antipattern_types": {}}
    vote = cyc.cove_vote(sug, analysis)
    assert vote["approved"] is False
    assert vote["score"] < 3


def test_cove_vote_approves_when_signals_present():
    sug = {
        "id": "X",
        "title": "Investigate JSONDecodeError in api/prospects.py",
        "rationale": (
            "JSONDecodeError occurs 15x in journal; api/prospects.py is a "
            "hot file (12 touches). Cross-product flagged this pair for inspection."
        ),
        "target_file": "prompts/learned/investigate-jsondecodeerror-api-prospects-py.md",
        "template_key": "investigate-antipattern",
        "risk": "low",
        "already_exists": False,
    }
    analysis = {
        "hot_files": [("api/prospects.py", 12)],
        "antipattern_types": {"JSONDecodeError": 15},
    }
    vote = cyc.cove_vote(sug, analysis)
    assert vote["approved"] is True, f"score={vote['score']} reason={vote.get('reason')}"
    assert vote["score"] >= 3


def test_cove_vote_already_exists_is_zero_votes():
    sug = {
        "id": "X",
        "title": "any",
        "rationale": "any",
        "target_file": "prompts/meta/x.md",
        "template_key": "autonomous-cycle",
        "risk": "low",
        "already_exists": True,
    }
    vote = cyc.cove_vote(sug, {"hot_files": [], "antipattern_types": {}})
    assert vote["approval_rate"] == 0.0
    assert vote["approved"] is False


def test_cove_vote_high_risk_needs_all_five_signals():
    sug_low = {
        "id": "L",
        "title": "Investigate X in Y",
        "rationale": "X" * 60 + " ; mentions JSONDecodeError",
        "target_file": "prompts/learned/x.md",
        "template_key": "investigate-antipattern",
        "risk": "low",
        "already_exists": False,
    }
    sug_high = dict(sug_low, risk="high", id="H")
    analysis = {
        "hot_files": [("api/prospects.py", 12)],
        "antipattern_types": {"JSONDecodeError": 15},
    }
    low_vote = cyc.cove_vote(sug_low, analysis)
    high_vote = cyc.cove_vote(sug_high, analysis)
    assert low_vote["threshold"] == 3
    assert high_vote["threshold"] == 5
    # Same content signals yield same score, different threshold may flip approval
    assert low_vote["score"] == high_vote["score"]


# ============================================================
# (g) outcome='no_op' when nothing applied — and (5) success_rate
# excludes no-op autonomous-cycle rows
# ============================================================

def test_success_rate_excludes_no_op_autonomous_cycle():
    journal = [
        _entry("verify", "passed"),  # real success
        _entry(
            "autonomous-cycle",
            outcome="passed",
            meta={"suggestions_applied": 0},  # the inflation pattern
        ),
        _entry("autonomous-cycle", outcome="passed", meta={"suggestions_applied": 0}),
    ]
    analysis = cyc.analyze(journal)
    # Only the real verify counts; the two autonomous-cycle no-ops do NOT.
    assert analysis["success_rate"] == pytest.approx(1 / 3)


def test_success_rate_counts_autonomous_cycle_with_real_application():
    journal = [
        _entry("autonomous-cycle", outcome="passed", meta={"suggestions_applied": 2}),
    ]
    analysis = cyc.analyze(journal)
    assert analysis["success_rate"] == 1.0


# ============================================================
# (c) hot files x antipatterns produce real suggestions
# ============================================================

def test_generate_suggestions_targets_hot_files():
    """Verifier finding (e) — hot files were never targets. Now they should be."""
    journal = (
        [_entry("api-prospects-bulk", outcome="error",
                files=["api/prospects.py"], meta={"error_type": "JSONDecodeError"})] * 5
        + [_entry("api-prospects-bulk", outcome="error",
                  files=["api/prospects.py"], meta={"error_type": "RuntimeError"})] * 3
    )
    analysis = cyc.analyze(journal)
    suggestions = cyc.generate_suggestions(analysis)
    # At least one suggestion should reference api/prospects.py in target or rationale
    refs = [s for s in suggestions if "prospects" in s.get("target_file", "").lower()
            or "prospects" in s.get("rationale", "").lower()]
    assert refs, f"No suggestion references hot file; got {[s['target_file'] for s in suggestions]}"


def test_generate_suggestions_caps_at_five():
    journal = []
    for i in range(20):
        journal.append(
            _entry(
                f"phase-{i}",
                outcome="error",
                files=[f"file-{i % 5}.py"],
                meta={"error_type": f"Err{i % 4}"},
            )
        )
    analysis = cyc.analyze(journal)
    suggestions = cyc.generate_suggestions(analysis)
    assert len(suggestions) <= 5


# ============================================================
# (7) all suggestion targets stay inside prompts/
# ============================================================

def test_all_suggestions_target_prompts_directory():
    journal = (
        [_entry("p", "error", files=["api/prospects.py"], meta={"error_type": "X"})] * 5
        + [_entry("autonomous-cycle", "passed", meta={"suggestions_applied": 1})] * 5
        + [_entry("verify", "passed")] * 5
    )
    analysis = cyc.analyze(journal)
    for s in cyc.generate_suggestions(analysis):
        assert s["target_file"].startswith("prompts/"), s


# ============================================================
# Integration: a full "loop until quiet" check — feed the cycle a journal
# representative of the real one and confirm no auto-rubber-stamp.
# ============================================================

def test_synthetic_full_journal_does_not_rubber_stamp():
    """The smoking gun from cycles 51-68: every low-risk got 5/5. Build a
    journal that historically triggered S1+S2 100% approve and confirm it
    is no longer a free pass."""
    journal = (
        [_entry("autonomous-cycle", "passed", meta={"suggestions_applied": 0})] * 50
        + [_entry("verify", "passed")] * 49
        + [_entry("cove-verify-opus", "failed")] * 17
    )
    analysis = cyc.analyze(journal)
    # S1 and S2 will be on the list (their preconditions hold), but cove_vote
    # must judge them on content. Both have boilerplate titles ("Codify ...",
    # "Promote ...") so the title signal is missing, dropping their score.
    suggestions = cyc.generate_suggestions(analysis)
    approvals = [s for s in suggestions if cyc.cove_vote(s, analysis)["approved"]]
    boilerplate_approvals = [
        s for s in approvals
        if any(b in s["title"].lower() for b in ("codify", "promote "))
    ]
    assert boilerplate_approvals == [], (
        "Boilerplate S1/S2 must not auto-approve via deterministic cove_vote; "
        f"approvals={[s['id'] for s in boilerplate_approvals]}"
    )
