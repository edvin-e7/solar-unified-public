"""Adversarial matrix for services/address_match.py.

One row per attack / edge case. Each row is a spec-level assertion that
downstream consumers rely on. Must all be green before enrich_person.md
can be called implemented.

Run: python3 -m pytest backend/specs/test_address_match.py -v
Or:  python3 backend/specs/test_address_match.py   (argparse-free fallback)
"""

from __future__ import annotations

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.address_match import (
    MatchResult,
    label_for,
    normalize,
    score_raw,
)

# --- normalize tests ---

def test_normalize_basic():
    n = normalize("Kungsgatan 1, 11143 Stockholm")
    assert n.street == "kungsgatan"
    assert n.number == "1"
    assert n.postal == "11143"
    assert n.city == "stockholm"


def test_normalize_uppercase_csv_style():
    n = normalize("KUNGSGATAN 1, 11143 STOCKHOLM")
    assert n.street == "kungsgatan"
    assert n.number == "1"
    assert n.postal == "11143"
    assert n.city == "stockholm"


def test_normalize_postal_with_space():
    n = normalize("Kungsgatan 1, 111 43 Stockholm")
    assert n.postal == "11143"


def test_normalize_without_postal():
    n = normalize("Kungsgatan 1 Stockholm")
    assert n.street == "kungsgatan"
    assert n.number == "1"
    assert n.city == "stockholm"


def test_normalize_letter_suffix():
    n = normalize("Kungsgatan 1A Stockholm")
    assert n.street == "kungsgatan"
    assert n.number == "1"
    assert n.number_suffix == "a"
    assert n.city == "stockholm"


def test_normalize_swedish_chars_preserved():
    n = normalize("Storgatan 5 Göteborg")
    assert n.street == "storgatan"
    assert n.city == "göteborg"


def test_normalize_empty_input():
    n = normalize("")
    assert n.street == ""
    assert n.number == ""
    assert n.city == ""


def test_normalize_none_input_does_not_crash():
    n = normalize(None)  # type: ignore[arg-type]
    assert n.street == ""


def test_normalize_extra_whitespace():
    n = normalize("   Kungsgatan   1    Stockholm   ")
    assert n.street == "kungsgatan"
    assert n.city == "stockholm"


def test_normalize_only_city():
    n = normalize("Stockholm")
    assert n.city == "stockholm"
    assert n.street == ""
    assert n.number == ""


# --- score tests: the core contract ---

def test_exact_match():
    r = score_raw("Kungsgatan 1, 11143 Stockholm", "Kungsgatan 1, 11143 Stockholm")
    assert r.score == 1.0
    assert r.kind == "exact"
    assert r.label == "sannolik"


def test_exact_match_uppercase_vs_mixed_case():
    r = score_raw("KUNGSGATAN 1, 11143 STOCKHOLM", "Kungsgatan 1, 11143 Stockholm")
    assert r.score == 1.0, f"uppercase CSV must match mixed-case hitta, got {r}"


def test_same_street_different_number():
    r = score_raw("Kungsgatan 1 Stockholm", "Kungsgatan 60 Stockholm")
    assert r.score == 0.6
    assert r.kind == "same-street-different-number"
    assert r.label == "möjlig"


def test_letter_variant_matches_plain():
    r = score_raw("Kungsgatan 1A Stockholm", "Kungsgatan 1 Stockholm")
    assert r.score == 1.0, f"1A and 1 are the same building, got {r}"


def test_umlaut_fallback_goteborg_without_umlaut():
    r = score_raw("Drottninggatan 50 Goteborg", "Drottninggatan 50 Göteborg")
    assert r.score == 1.0, f"umlaut fallback failed: {r}"


def test_same_postal_different_street():
    r = score_raw("Kungsgatan 1, 11143 Stockholm", "Drottninggatan 5, 11143 Stockholm")
    assert r.score == 0.4
    assert r.kind == "same-postal"


def test_same_city_different_postal():
    r = score_raw("Kungsgatan 1, 11143 Stockholm", "Skärmarbrinken 10, 12043 Stockholm")
    assert r.score == 0.2
    assert r.kind == "same-city"


def test_completely_different():
    r = score_raw("Kungsgatan 1 Stockholm", "Storgatan 5 Malmö")
    assert r.score == 0.0
    assert r.kind == "none"


# --- adversarial: worst-case reasoning ---

def test_missing_number_does_not_boost_wrong_street():
    """If requested has no number, we must NOT silently score 1.0 against any
    candidate on the same street. We still require matching number."""
    r = score_raw("Kungsgatan Stockholm", "Kungsgatan 60 Stockholm")
    # Street matches, but requested has no number → cannot be exact
    assert r.score < 1.0, f"missing-number should not claim exact match: {r}"
    assert r.kind == "same-street-different-number"


def test_empty_vs_empty_is_not_a_match():
    """Two empty addresses must not score as 'exact' — nothing to compare."""
    r = score_raw("", "")
    assert r.score == 0.0
    assert r.kind == "none"


def test_one_empty_one_populated_is_not_a_match():
    r = score_raw("", "Kungsgatan 1 Stockholm")
    assert r.score == 0.0


def test_whitespace_only_is_empty():
    r = score_raw("   ", "Kungsgatan 1 Stockholm")
    assert r.score == 0.0


def test_label_thresholds_stable():
    assert label_for(1.0) == "sannolik"
    assert label_for(0.8) == "sannolik"
    assert label_for(0.79) == "möjlig"
    assert label_for(0.4) == "möjlig"
    assert label_for(0.39) == "närliggande"
    assert label_for(0.2) == "närliggande"
    assert label_for(0.19) == "inget"


def test_very_long_garbage_does_not_crash():
    r = score_raw("x" * 5000, "Kungsgatan 1 Stockholm")
    assert isinstance(r, MatchResult)


def test_special_chars_do_not_crash():
    r = score_raw("Kungsgatan 1 Stockholm<script>alert(1)</script>", "Kungsgatan 1 Stockholm")
    # Script tag keeps the address parse-able on the candidate side;
    # requested side now has junk tokens but should still normalize street+number.
    assert r.score > 0.0, f"addressed-with-junk should still match on substantial tokens: {r}"


# --- the anti-brainrot rule: single source of truth ---

def test_score_is_deterministic():
    """Same input MUST give same output. No randomness. No context dependence."""
    r1 = score_raw("Kungsgatan 1 Stockholm", "Kungsgatan 1 Stockholm")
    r2 = score_raw("Kungsgatan 1 Stockholm", "Kungsgatan 1 Stockholm")
    assert r1 == r2


def test_score_is_symmetric_for_exact_match():
    """Symmetric for exact matches — if A exactly matches B, B exactly matches A."""
    a = "Kungsgatan 1 Stockholm"
    b = "Kungsgatan 1 Stockholm"
    assert score_raw(a, b).score == score_raw(b, a).score


def _run_all():
    """Fallback runner — detects test_ functions and runs them sequentially."""
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
    return 0 if not failed else 1


if __name__ == "__main__":
    sys.exit(_run_all())
