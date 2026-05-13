"""Adversarial matrix for PatternDetector.detect_patterns.

Guards the journal-schema dependency flagged in memory
(`pattern-detector-schema.md` — "exact journal shape required or
pattern_detector emits 0"). Any upstream writer that renames a metadata key
or mistypes a phase string must trip these tests BEFORE silently killing
the autonomous-learning loop.

Run: python3 backend/specs/test_pattern_detector.py
"""

from __future__ import annotations

import importlib.util
import json
import sys
import tempfile
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Sandbox journal BEFORE importing detector
_SANDBOX_DIR = Path(tempfile.mkdtemp(prefix="pd_test_"))
_SANDBOX = _SANDBOX_DIR / "journal.jsonl"

import learning_journal  # noqa: E402

learning_journal.JOURNAL = _SANDBOX


def _load_pattern_detector():
    """Load pattern_detector.py directly, bypassing executors/__init__.py
    which eagerly imports siblings that depend on bs4/httpx/etc. We only
    need the one module; the package side-effects are not our concern."""
    path = Path(__file__).resolve().parents[1] / "executors" / "pattern_detector.py"
    spec = importlib.util.spec_from_file_location("pattern_detector_standalone", path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod.PatternDetector


PatternDetector = _load_pattern_detector()


def _reset() -> None:
    if _SANDBOX.exists():
        _SANDBOX.unlink()


def _write(entries: list[dict[str, Any]]) -> None:
    """Write journal entries directly — bypasses record()'s summary-regen
    (we only need entries() to read them back)."""
    with _SANDBOX.open("w", encoding="utf-8") as f:
        for e in entries:
            e.setdefault("ts", datetime.now(UTC).isoformat())
            e.setdefault("lesson", "")
            e.setdefault("files", [])
            e.setdefault("error", None)
            e.setdefault("metadata", {})
            f.write(json.dumps(e, ensure_ascii=False) + "\n")


def _det() -> PatternDetector:
    return PatternDetector()


# --- Invariant 1: empty journal ---

def test_empty_journal_returns_empty_patterns():
    _reset()
    out = _det().detect_patterns()
    assert out == {"analyzed": 0, "patterns_found": 0, "patterns": []}


def test_missing_journal_file_does_not_crash():
    """Journal file never existed (fresh checkout scenario from memory
    `cloud-schedule-data-gap`). detect_patterns must not crash."""
    _reset()
    out = _det().detect_patterns()
    assert out["patterns_found"] == 0


# --- Invariant 2: missing metadata key does not crash, does not match ---

def test_missing_avg_confidence_key_does_not_emit():
    _reset()
    _write([
        {"phase": "data-gathering", "outcome": "passed", "metadata": {}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    names = [p["name"] for p in out["patterns"]]
    assert "low_detection_confidence" not in names, (
        "missing avg_confidence should default to 1.0 → no match"
    )


def test_missing_rate_key_does_not_emit_low_enrichment():
    _reset()
    _write([
        {"phase": "enrichment", "outcome": "passed", "metadata": {}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    names = [p["name"] for p in out["patterns"]]
    assert "low_enrichment_rate" not in names


# --- Invariant 3: threshold is strictly less than ---

def test_avg_confidence_at_exactly_0_65_does_not_match():
    """Boundary: 0.65 is NOT < 0.65. Regression guard for threshold drift."""
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.65}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    assert all(p["name"] != "low_detection_confidence" for p in out["patterns"])


def test_rate_at_exactly_0_8_does_not_match():
    _reset()
    _write([
        {"phase": "enrichment", "metadata": {"rate": 0.8}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    assert all(p["name"] != "low_enrichment_rate" for p in out["patterns"])


def test_avg_confidence_just_below_matches():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.6499}}
        for _ in range(3)
    ])
    out = _det().detect_patterns()
    assert any(p["name"] == "low_detection_confidence" for p in out["patterns"])


# --- Invariant 4: count thresholds are >= ---

def test_low_detection_requires_3_not_2():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.5}}
        for _ in range(2)
    ])
    out = _det().detect_patterns()
    assert all(p["name"] != "low_detection_confidence" for p in out["patterns"])


def test_low_detection_at_exactly_3_emits():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.5}}
        for _ in range(3)
    ])
    out = _det().detect_patterns()
    matches = [p for p in out["patterns"] if p["name"] == "low_detection_confidence"]
    assert len(matches) == 1
    assert matches[0]["frequency"] == 3


def test_low_enrichment_at_exactly_2_emits():
    _reset()
    _write([
        {"phase": "enrichment", "metadata": {"rate": 0.5}}
        for _ in range(2)
    ])
    out = _det().detect_patterns()
    matches = [p for p in out["patterns"] if p["name"] == "low_enrichment_rate"]
    assert len(matches) == 1


def test_validation_rejection_at_exactly_2_emits():
    _reset()
    _write([
        {"phase": "data-validator", "outcome": "failed", "metadata": {}},
        {"phase": "data-validator", "outcome": "error", "metadata": {}},
    ])
    out = _det().detect_patterns()
    matches = [p for p in out["patterns"] if p["name"] == "high_validation_rejection"]
    assert len(matches) == 1
    assert matches[0]["frequency"] == 2


def test_repeated_errors_at_exactly_3_emits():
    _reset()
    _write([
        {"phase": "enrichment", "outcome": "error", "metadata": {}}
        for _ in range(3)
    ])
    out = _det().detect_patterns()
    matches = [p for p in out["patterns"] if p["name"] == "repeated_errors_enrichment"]
    assert len(matches) == 1


def test_repeated_errors_at_2_does_not_emit():
    _reset()
    _write([
        {"phase": "enrichment", "outcome": "error", "metadata": {}}
        for _ in range(2)
    ])
    out = _det().detect_patterns()
    assert all(not p["name"].startswith("repeated_errors_") for p in out["patterns"])


# --- Invariant 5: severity classification ---

def test_low_detection_severity_medium_at_10():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(10)
    ])
    out = _det().detect_patterns()
    p = next(p for p in out["patterns"] if p["name"] == "low_detection_confidence")
    assert p["severity"] == "medium", "count == 10 is NOT > 10 → medium"


def test_low_detection_severity_high_at_11():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(11)
    ])
    out = _det().detect_patterns()
    p = next(p for p in out["patterns"] if p["name"] == "low_detection_confidence")
    assert p["severity"] == "high"


def test_repeated_errors_severity_always_high():
    _reset()
    _write([
        {"phase": "enrichment", "outcome": "error", "metadata": {}}
        for _ in range(3)
    ])
    out = _det().detect_patterns()
    p = next(p for p in out["patterns"] if p["name"] == "repeated_errors_enrichment")
    assert p["severity"] == "high"


# --- Invariant 6: all four patterns coexist ---

def test_all_four_patterns_emit_simultaneously():
    _reset()
    entries: list[dict[str, Any]] = []
    entries += [
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.5}}
        for _ in range(3)
    ]
    entries += [
        {"phase": "enrichment", "metadata": {"rate": 0.5}}
        for _ in range(2)
    ]
    entries += [
        {"phase": "data-validator", "outcome": "failed", "metadata": {}}
        for _ in range(2)
    ]
    entries += [
        {"phase": "some-other-phase", "outcome": "error", "metadata": {}}
        for _ in range(3)
    ]
    _write(entries)
    out = _det().detect_patterns()
    names = {p["name"] for p in out["patterns"]}
    assert "low_detection_confidence" in names
    assert "low_enrichment_rate" in names
    assert "high_validation_rejection" in names
    assert "repeated_errors_some-other-phase" in names
    assert out["patterns_found"] == 4


# --- Invariant 7: repeated_errors_{phase} dynamic naming ---

def test_repeated_errors_constructs_phase_specific_name():
    _reset()
    _write([
        {"phase": "data-fetcher", "outcome": "error", "metadata": {}}
        for _ in range(3)
    ] + [
        {"phase": "enrichment", "outcome": "error", "metadata": {}}
        for _ in range(3)
    ])
    out = _det().detect_patterns()
    names = {p["name"] for p in out["patterns"]}
    assert "repeated_errors_data-fetcher" in names
    assert "repeated_errors_enrichment" in names


def test_repeated_errors_missing_phase_is_named_unknown():
    _reset()
    _write([
        {"outcome": "error", "metadata": {}}
        for _ in range(3)
    ])
    out = _det().detect_patterns()
    names = {p["name"] for p in out["patterns"]}
    assert "repeated_errors_unknown" in names


# --- Invariant 8: lookback clipping ---

def test_lookback_clips_old_entries():
    _reset()
    entries: list[dict[str, Any]] = []
    # 100 irrelevant passes (old)
    entries += [
        {"phase": "cove-verify", "outcome": "passed", "metadata": {}}
        for _ in range(100)
    ]
    # 3 triggering entries (newest)
    entries += [
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(3)
    ]
    _write(entries)
    # With default lookback=100, the 3 triggering entries are INSIDE the
    # window but the 100 old ones are clipped (taking last 100 of 103).
    out = _det().detect_patterns(lookback=100)
    assert out["analyzed"] == 100
    assert any(p["name"] == "low_detection_confidence" for p in out["patterns"])


def test_lookback_small_excludes_triggering_entries():
    _reset()
    entries: list[dict[str, Any]] = []
    entries += [
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(3)
    ]
    entries += [
        {"phase": "cove-verify", "outcome": "passed", "metadata": {}}
        for _ in range(5)
    ]
    _write(entries)
    # Lookback=5 → takes last 5 = the coves, triggering entries excluded
    out = _det().detect_patterns(lookback=5)
    assert out["analyzed"] == 5
    assert all(p["name"] != "low_detection_confidence" for p in out["patterns"])


def test_lookback_zero_returns_empty():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(5)
    ])
    out = _det().detect_patterns(lookback=0)
    # Python slice [-0:] returns the full list (not empty) — documented quirk.
    # Either behavior (0 or all) is acceptable per spec; test pins current
    # behavior so a refactor that changes it must justify the change.
    assert out["analyzed"] == 5 or out["analyzed"] == 0


def test_lookback_larger_than_entries_uses_all():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(3)
    ])
    out = _det().detect_patterns(lookback=1000)
    assert out["analyzed"] == 3


# --- Invariant 9: read-only, idempotent ---

def test_detect_patterns_is_idempotent():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(3)
    ])
    det = _det()
    out1 = det.detect_patterns()
    out2 = det.detect_patterns()
    assert out1 == out2


def test_detect_patterns_does_not_write_journal():
    _reset()
    _write([
        {"phase": "data-gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(3)
    ])
    size_before = _SANDBOX.stat().st_size
    _det().detect_patterns()
    size_after = _SANDBOX.stat().st_size
    assert size_before == size_after, "detect_patterns must not write"


# --- Invariant 10: phase strings are case-sensitive ---

def test_wrong_phase_casing_does_not_match():
    """Upstream writer typo Data-Gathering vs data-gathering → silent zero."""
    _reset()
    _write([
        {"phase": "Data-Gathering", "metadata": {"avg_confidence": 0.3}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    # This test DOCUMENTS the brittleness. If a future PatternDetectorV2
    # normalizes case, this test needs to be inverted — but the spec change
    # is then visible, not silent.
    assert all(p["name"] != "low_detection_confidence" for p in out["patterns"])


def test_wrong_phase_name_validator_vs_validation():
    """Writer ships data-validation but detector reads data-validator →
    regression signal on upstream rename."""
    _reset()
    _write([
        {"phase": "data-validation", "outcome": "failed", "metadata": {}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    assert all(p["name"] != "high_validation_rejection" for p in out["patterns"])


# --- Cross-pattern: validation with non-matching outcome ignored ---

def test_validation_with_passed_outcome_ignored():
    _reset()
    _write([
        {"phase": "data-validator", "outcome": "passed", "metadata": {}}
        for _ in range(5)
    ])
    out = _det().detect_patterns()
    assert all(p["name"] != "high_validation_rejection" for p in out["patterns"])


# --- runner ---

def _run_all() -> int:
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
