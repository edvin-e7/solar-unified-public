"""Adversarial matrix for ImprovementGenerator.generate_improvements.

Focus: the filter-against-ledger path (the anti-brainrot loop) and the
pattern↔improvement tagging contract. Regression-guards the idx-drift bug
that silently pass-through improvements when not every pattern produced one.

Run: python3 backend/specs/test_improvement_generator.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Sandbox the ledger BEFORE importing the generator
_SANDBOX = Path(tempfile.mkdtemp(prefix="gen_test_")) / "ledger.json"
import issue_ledger  # noqa: E402

issue_ledger.LEDGER_PATH = _SANDBOX

from executors.improvement_generator import ImprovementGenerator  # noqa: E402
from issue_ledger import log_attempt, open_issue  # noqa: E402


def _reset():
    # Defensive re-set of LEDGER_PATH — earlier test-files in the suite may
    # have re-imported issue_ledger and reverted to the real path, which then
    # leaks state into this test-file. Re-asserting per-test makes us
    # order-independent.
    issue_ledger.LEDGER_PATH = _SANDBOX
    if _SANDBOX.exists():
        _SANDBOX.unlink()


def _gen():
    return ImprovementGenerator()


# --- basic shape ---

def test_empty_patterns_returns_empty():
    _reset()
    out = _gen().generate_improvements([])
    assert out["patterns_processed"] == 0
    assert out["improvements_generated"] == 0
    assert out["improvements"] == []
    assert out["skipped_already_tried"] == []


def test_unknown_pattern_produces_no_improvement():
    _reset()
    out = _gen().generate_improvements([{"name": "not_a_known_pattern", "frequency": 3}])
    assert out["patterns_processed"] == 1
    assert out["improvements_generated"] == 0


def test_known_pattern_produces_one_improvement():
    _reset()
    out = _gen().generate_improvements([{"name": "low_enrichment_rate", "frequency": 3}])
    assert out["improvements_generated"] == 1
    assert out["improvements"][0]["target"] == "backend/executors/enrichment_executor.py"


# --- anti-brainrot filter ---

def test_filter_blocks_paraphrase_of_prior_rejected():
    _reset()
    k = open_issue(
        error_type="low_detection_confidence",
        target="backend/prompts/detection.md",
        title="t",
    )
    log_attempt(
        key=k,
        hypothesis="add low-light section focus panel edges roof lines zoom",
        change_summary="s1",
        outcome="rejected_by_cove",
    )
    out = _gen().generate_improvements(
        [{"name": "low_detection_confidence", "frequency": 5}]
    )
    assert out["improvements_generated"] == 0, out
    assert len(out["skipped_already_tried"]) == 1
    skip = out["skipped_already_tried"][0]
    assert skip["pattern"] == "low_detection_confidence"
    assert skip["matched_prior"][0]["similarity"] >= 0.6


def test_filter_lets_through_when_no_prior():
    _reset()
    out = _gen().generate_improvements(
        [{"name": "low_detection_confidence", "frequency": 5}]
    )
    assert out["improvements_generated"] == 1
    assert out["skipped_already_tried"] == []


# --- regression: idx-drift bug ---
# When patterns list has more entries than generated improvements (because some
# patterns don't match any branch), the old filter used improvement-index to
# look up the pattern — drifting and misfiling. Ensure the tagged-tuple fix
# still correctly maps each improvement to its originating pattern.

def test_idx_drift_regression_unknown_first_then_known():
    """Unknown pattern first, known pattern second: old code would map
    the one produced improvement back to the unknown pattern (wrong), so
    ledger lookup with the wrong error_type would miss the real prior.
    """
    _reset()
    # Seed a rejected prior ONLY for the known pattern
    k = open_issue(
        error_type="low_enrichment_rate",
        target="backend/executors/enrichment_executor.py",
        title="t",
    )
    log_attempt(
        key=k,
        hypothesis="exponential backoff retry cloudflare timeout hitta fallback mrkoll",
        change_summary="s1",
        outcome="rejected_by_cove",
    )
    out = _gen().generate_improvements([
        {"name": "not_a_known_pattern", "frequency": 1},
        {"name": "low_enrichment_rate", "frequency": 3},
    ])
    # Under the old idx-based mapping, improvement[0] would be looked up with
    # patterns[0]["name"] = "not_a_known_pattern" → ledger miss → let through.
    # Under the fix, the tuple carries low_enrichment_rate → ledger hit → block.
    assert out["improvements_generated"] == 0, out
    assert len(out["skipped_already_tried"]) == 1
    assert out["skipped_already_tried"][0]["pattern"] == "low_enrichment_rate"


def test_tagged_tuple_preserves_pattern_name_in_skip_record():
    _reset()
    k = open_issue(
        error_type="high_validation_rejection",
        target="backend/services/satellite.py",
        title="t",
    )
    log_attempt(
        key=k,
        hypothesis="increase tile zoom level resolution reduce unclear low-confidence detections",
        change_summary="s1",
        outcome="rejected_by_cove",
    )
    out = _gen().generate_improvements(
        [{"name": "high_validation_rejection", "frequency": 7}]
    )
    assert out["skipped_already_tried"][0]["pattern"] == "high_validation_rejection"


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
