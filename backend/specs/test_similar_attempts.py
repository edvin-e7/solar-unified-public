"""Adversarial matrix for issue_ledger.similar_attempts + has_already_tried.

Focused matrix — Jaccard semantics, stopword handling, paraphrase detection,
and the "rejected outcomes only" filter.

Run: python3 backend/specs/test_similar_attempts.py
"""

from __future__ import annotations

import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

# Redirect the ledger to a sandbox file before importing
_SANDBOX = Path(tempfile.mkdtemp(prefix="ledger_test_")) / "ledger.json"
import issue_ledger  # noqa: E402

issue_ledger.LEDGER_PATH = _SANDBOX


from issue_ledger import (  # noqa: E402
    _jaccard,
    _tokenize_hypothesis,
    has_already_tried,
    log_attempt,
    open_issue,
    similar_attempts,
)


def _reset():
    # Re-set LEDGER_PATH defensively — another test-file using the same
    # monkeypatch-pattern will have overwritten the module attribute when
    # imported. Re-assert per-test for order-independence.
    issue_ledger.LEDGER_PATH = _SANDBOX
    if _SANDBOX.exists():
        _SANDBOX.unlink()


# --- tokenizer tests ---

def test_tokenize_lowercases_and_splits():
    assert _tokenize_hypothesis("Use CSS Selectors") == {"css", "selectors"}


def test_tokenize_drops_stopwords():
    # "use", "to", "the" are stopwords; only meaningful tokens remain
    assert _tokenize_hypothesis("use more to find the elements") == {"more", "find", "elements"}


def test_tokenize_drops_single_chars():
    # "a" single-char; hyphens split tokens
    assert _tokenize_hypothesis("a b c foo") == {"foo"}


def test_tokenize_keeps_swedish_chars():
    assert "göteborg" in _tokenize_hypothesis("kör till Göteborg")


def test_tokenize_empty_returns_empty():
    assert _tokenize_hypothesis("") == set()


# --- jaccard tests ---

def test_jaccard_identical_sets_is_one():
    assert _jaccard({"a", "b"}, {"a", "b"}) == 1.0


def test_jaccard_disjoint_sets_is_zero():
    assert _jaccard({"a"}, {"b"}) == 0.0


def test_jaccard_empty_is_zero():
    assert _jaccard(set(), {"a"}) == 0.0


def test_jaccard_half_overlap():
    assert _jaccard({"a", "b"}, {"a", "c"}) == 1 / 3  # 1 common of 3 unique


# --- similar_attempts tests ---

def test_similar_attempts_paraphrase_detected_at_default_threshold():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="use more CSS selectors to find elements",
        change_summary="s1",
        outcome="failed",
    )
    # Same meaningful tokens (more/css/selectors) = 3/5 = 0.6 ≥ 0.6 threshold
    matches = similar_attempts("TestBug", "tests/smoke.py", "add more CSS selectors")
    assert len(matches) == 1, matches
    assert matches[0]["_similarity"] >= 0.6


def test_similar_attempts_truly_different_hypothesis_not_flagged():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="use more CSS selectors to find elements",
        change_summary="s1",
        outcome="failed",
    )
    # JSON-LD / Next.js approach shares only stopwords → no match
    matches = similar_attempts(
        "TestBug", "tests/smoke.py", "rewrite parser using schema.org JSON-LD"
    )
    assert matches == []


def test_similar_attempts_ignores_successful_priors_by_default():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="use more CSS selectors to find elements",
        change_summary="s1",
        outcome="success",  # resolved, not a rejected pattern
    )
    # Even identical hypothesis must NOT match — success is already in resolution
    matches = similar_attempts("TestBug", "tests/smoke.py", "use more CSS selectors")
    assert matches == []


def test_similar_attempts_threshold_tunable():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="use more CSS selectors to find elements",
        change_summary="s1",
        outcome="failed",
    )
    # Very lax threshold — the 0.2-level partial overlap surfaces
    new_hypo = "investigate selectors layer"
    lax = similar_attempts("TestBug", "tests/smoke.py", new_hypo, threshold=0.1)
    strict = similar_attempts("TestBug", "tests/smoke.py", new_hypo, threshold=0.9)
    assert len(lax) >= len(strict)
    assert strict == []


def test_similar_attempts_containment_catches_prior_subset_of_longer_new():
    """Real-world paraphrase: prior (9 tokens) fully embedded in longer new (18 tokens).

    Jaccard = 9/18 = 0.5 < 0.6 (would miss), but containment = 9/9 = 1.0.
    Canonical case from improvement_generator: "add section for low-light" prior
    vs verbose restatement that preserves every meaningful token.
    """
    _reset()
    k = open_issue(error_type="low_detection_confidence", target="prompts/detection.md", title="t")
    log_attempt(
        key=k,
        hypothesis="add low-light section focus panel edges roof lines zoom",
        change_summary="s1",
        outcome="rejected_by_cove",
    )
    # Verbose paraphrase — same idea, more words
    new_hypo = (
        "Add section for low-light conditions: if image appears dim or cloudy, "
        "focus on panel edges and roof lines. Request analysis at higher zoom if available."
    )
    matches = similar_attempts("low_detection_confidence", "prompts/detection.md", new_hypo)
    assert len(matches) == 1, matches
    assert matches[0]["_containment"] >= 0.9, matches[0]
    assert matches[0]["_jaccard"] < 0.6, matches[0]


def test_similar_attempts_containment_ignores_generic_two_token_priors():
    """Guard against false positives: 2-token priors must not force-match everything.

    If prior = {"fix", "bug"}, containment against any new hypothesis containing
    those tokens would be 1.0 — meaningless. The len(prior) < 3 guard prevents this.
    """
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="fix bug",  # post-tokenize = {"fix","bug"} → length 2, below guard
        change_summary="s1",
        outcome="failed",
    )
    # New hypothesis shares both tokens but is semantically different
    matches = similar_attempts(
        "TestBug", "tests/smoke.py", "fix bug in selector layer using schema rewrite"
    )
    assert matches == [], f"generic 2-token prior must not force-match: {matches}"


def test_similar_attempts_empty_hypothesis_returns_empty():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="any prior attempt",
        change_summary="s1",
        outcome="failed",
    )
    assert similar_attempts("TestBug", "tests/smoke.py", "") == []


def test_similar_attempts_no_prior_attempts_returns_empty():
    _reset()
    open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    assert similar_attempts("TestBug", "tests/smoke.py", "any hypothesis") == []


def test_similar_attempts_unknown_issue_returns_empty():
    _reset()
    assert similar_attempts("NeverSeen", "no/file.py", "anything") == []


# --- has_already_tried bool wrapper ---

def test_has_already_tried_true_for_paraphrase():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="use more CSS selectors to find elements",
        change_summary="s1",
        outcome="failed",
    )
    assert has_already_tried("TestBug", "tests/smoke.py", "add more CSS selectors") is True


def test_has_already_tried_false_for_fresh_angle():
    _reset()
    k = open_issue(error_type="TestBug", target="tests/smoke.py", title="t")
    log_attempt(
        key=k,
        hypothesis="use more CSS selectors",
        change_summary="s1",
        outcome="failed",
    )
    assert has_already_tried("TestBug", "tests/smoke.py", "switch to JSON-LD parser") is False


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
