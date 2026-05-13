"""Adversarial test matrix for services.gemini._extract_json.

See backend/specs/gemini_json_parse.md for invariants I1-I12.
Tests must fail without the hardened parser and pass with it.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.gemini import _extract_json


# I1 — Empty input
def test_empty_string_raises_valueerror():
    with pytest.raises(ValueError):
        _extract_json("")


# I2 — Whitespace-only
def test_whitespace_only_raises_valueerror():
    with pytest.raises(ValueError):
        _extract_json("   \n\t  ")


# I3 — Naked JSON
def test_naked_object():
    assert _extract_json('{"a": 1}') == {"a": 1}


def test_naked_array():
    assert _extract_json("[1, 2, 3]") == [1, 2, 3]


# I7 — Nested brackets must not break extraction
def test_array_with_nested_objects():
    raw = '[{"a":[1,2]},{"b":3}]'
    out = _extract_json(raw)
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0] == {"a": [1, 2]}
    assert out[1] == {"b": 3}


def test_object_with_nested_array():
    raw = '{"qs": ["q1", "q2", "q3"]}'
    out = _extract_json(raw)
    assert out == {"qs": ["q1", "q2", "q3"]}


# I4 — Fenced JSON
def test_fenced_json_with_lang():
    raw = '```json\n{"a": 1}\n```'
    assert _extract_json(raw) == {"a": 1}


def test_fenced_json_no_lang():
    raw = "```\n[1, 2]\n```"
    assert _extract_json(raw) == [1, 2]


def test_fenced_json_array_with_nested():
    raw = '```json\n[{"q": "first?"}, {"q": "second?"}]\n```'
    out = _extract_json(raw)
    assert isinstance(out, list)
    assert len(out) == 2


# I5 — Extra data after valid JSON (the canonical "Extra data" error)
def test_array_followed_by_prose():
    raw = '[1, 2, 3]\n\nFörklaring följer här.'
    assert _extract_json(raw) == [1, 2, 3]


def test_object_followed_by_prose():
    raw = '{"a": 1}\nNot JSON anymore.'
    assert _extract_json(raw) == {"a": 1}


def test_cove_answers_realistic_extra_data():
    # Simulates the actual cove-answers failure: list of dicts followed by commentary
    raw = (
        '[{"question": "q1?", "answer": "yes", "sentiment": "positive"}, '
        '{"question": "q2?", "answer": "no", "sentiment": "negative"}]\n\n'
        'Sammanfattning: båda frågorna besvarade.'
    )
    out = _extract_json(raw)
    assert isinstance(out, list)
    assert len(out) == 2
    assert out[0]["sentiment"] == "positive"


# I6 — Prose before JSON
def test_prose_prefix_then_object():
    raw = "Svaret är:\n{\"x\": 9}"
    assert _extract_json(raw) == {"x": 9}


def test_prose_prefix_then_array():
    raw = "Här är listan:\n[1, 2, 3]"
    assert _extract_json(raw) == [1, 2, 3]


def test_swedish_prose_then_array():
    raw = "Tänker steg för steg...\n[\"q1\", \"q2\"]"
    out = _extract_json(raw)
    assert out == ["q1", "q2"]


# I9 — Only prose, no JSON
def test_only_prose_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        _extract_json("Jag kan inte svara på den frågan.")


# I10 — Malformed JSON
def test_broken_json_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        _extract_json('{"a": ')


def test_unterminated_array_raises_jsondecodeerror():
    with pytest.raises(json.JSONDecodeError):
        _extract_json('[1, 2,')


# I11 — Unicode
def test_unicode_object():
    out = _extract_json('{"namn": "Åsa", "stad": "Göteborg"}')
    assert out["namn"] == "Åsa"
    assert out["stad"] == "Göteborg"


def test_unicode_with_extra_data():
    raw = '{"sv": "åäö"}\nDetta är vad jag tror.'
    assert _extract_json(raw) == {"sv": "åäö"}


# Regression: cove-questions canonical case
def test_cove_questions_simple_list():
    raw = '["Will this solve X?", "Could it break Y?", "Is there a simpler way?"]'
    out = _extract_json(raw)
    assert isinstance(out, list)
    assert len(out) == 3


def test_cove_questions_with_explanation():
    raw = (
        '["Fungerar fixet?", "Bryter det något?"]\n\n'
        'Jag valde dessa frågor för att täcka huvudriskerna.'
    )
    out = _extract_json(raw)
    assert isinstance(out, list)
    assert len(out) == 2
