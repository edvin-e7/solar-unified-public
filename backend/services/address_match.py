"""Canonical address matching for the whole project.

One normalize function, one score function. Every place that compares Swedish
addresses — hitta enrichment, CSV import dedup, prospects dedup, batch match —
routes through here. Same input → same answer, everywhere.

Why scoring and not binary match:
    Exact-string match on Swedish addresses throws away real value. "KUNGSGATAN 1,
    11143 STOCKHOLM" (CSV-uppercase) does not exact-match "Kungsgatan 1". "1A"
    does not exact-match "1". "Göteborg" does not exact-match "Goteborg". All
    three are same-address-in-practice. We keep all contacts but rank them so
    downstream (frontend, batch-executor, learning-loop) can decide the cutoff.

Scoring (see specs/enrich_person.md):
    1.0 exact street + number
    0.6 same street, different number
    0.4 same postal
    0.2 same city
    0.0 otherwise
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass
from typing import Literal

MatchKind = Literal["exact", "same-street-different-number", "same-postal", "same-city", "none"]
ConfidenceLabel = Literal["sannolik", "möjlig", "närliggande", "inget"]


@dataclass(frozen=True, slots=True)
class NormalizedAddress:
    """Canonical form. Equal addresses → equal NormalizedAddress."""

    raw: str
    street: str      # "kungsgatan" (lowercased, no punct, no umlaut-fallback applied)
    number: str      # "1" (numeric only; the letter suffix is stripped for comparison)
    number_suffix: str  # "a" if raw was "1A" (preserved for display)
    postal: str      # "11143" (5 digits, no space)
    city: str        # "stockholm" (lowercased, no punct, no umlaut-fallback applied)


@dataclass(frozen=True, slots=True)
class MatchResult:
    score: float
    kind: MatchKind
    label: ConfidenceLabel


_PUNCT_RE = re.compile(r"[,\.;:]")
_WS_RE = re.compile(r"\s+")
_STREET_NUM_RE = re.compile(r"^(?P<street>.+?)\s+(?P<num>\d+)(?P<suffix>[a-zA-Z])?\b")
_POSTAL_RE = re.compile(r"\b(\d{3})\s?(\d{2})\b")
_UMLAUT_MAP = str.maketrans({"å": "a", "ä": "a", "ö": "o", "é": "e", "è": "e", "ü": "u"})


def _strip_accents(s: str) -> str:
    return s.translate(_UMLAUT_MAP)


def _normalize_string(s: str) -> str:
    s = unicodedata.normalize("NFC", s).lower()
    s = _PUNCT_RE.sub(" ", s)
    s = _WS_RE.sub(" ", s).strip()
    return s


def normalize(address: str) -> NormalizedAddress:
    """Parse a Swedish address into its canonical components.

    Accepts messy input: CSV uppercase, comma-separated, with or without postal,
    with or without city, 1A/1B variants, mixed punctuation. Never raises — if
    structure can't be parsed, the missing parts are empty strings.
    """
    if not isinstance(address, str):
        address = ""
    clean = _normalize_string(address)

    postal_match = _POSTAL_RE.search(clean)
    postal = (postal_match.group(1) + postal_match.group(2)) if postal_match else ""

    clean_without_postal = _POSTAL_RE.sub(" ", clean).strip()
    clean_without_postal = _WS_RE.sub(" ", clean_without_postal)

    parts = [p for p in clean_without_postal.split(" ") if p]
    # Heuristic: last token = city if it contains no digits. Everything before = street+num.
    # Edge case: single non-numeric token → city only (no street).
    city = ""
    street_num_part = clean_without_postal
    if len(parts) == 1 and not any(ch.isdigit() for ch in parts[0]):
        city = parts[0]
        street_num_part = ""
    elif len(parts) >= 2 and not any(ch.isdigit() for ch in parts[-1]):
        city = parts[-1]
        street_num_part = " ".join(parts[:-1])

    street = ""
    number = ""
    suffix = ""
    m = _STREET_NUM_RE.match(street_num_part)
    if m:
        street = m.group("street").strip()
        number = m.group("num")
        suffix = (m.group("suffix") or "").lower()
    else:
        street = street_num_part.strip()

    return NormalizedAddress(
        raw=address,
        street=street,
        number=number,
        number_suffix=suffix,
        postal=postal,
        city=city,
    )


def _street_equal(a: str, b: str) -> bool:
    """Street match — tolerant of å/ä/ö fallback transliteration."""
    if not a or not b:
        return False
    if a == b:
        return True
    return _strip_accents(a) == _strip_accents(b)


def _city_equal(a: str, b: str) -> bool:
    if not a or not b:
        return False
    if a == b:
        return True
    return _strip_accents(a) == _strip_accents(b)


def score(requested: NormalizedAddress, candidate: NormalizedAddress) -> MatchResult:
    """Score a candidate address against a requested address. Pure function."""
    street_eq = _street_equal(requested.street, candidate.street)
    number_eq = bool(requested.number) and requested.number == candidate.number
    postal_eq = bool(requested.postal) and requested.postal == candidate.postal
    city_eq = _city_equal(requested.city, candidate.city)

    if street_eq and number_eq:
        return MatchResult(1.0, "exact", "sannolik")
    if street_eq:
        return MatchResult(0.6, "same-street-different-number", "möjlig")
    if postal_eq:
        return MatchResult(0.4, "same-postal", "möjlig")
    if city_eq:
        return MatchResult(0.2, "same-city", "närliggande")
    return MatchResult(0.0, "none", "inget")


def score_raw(requested: str, candidate: str) -> MatchResult:
    """Convenience — normalizes both sides then scores."""
    return score(normalize(requested), normalize(candidate))


def label_for(score_value: float) -> ConfidenceLabel:
    """Stable mapping score → label. Mirrors the thresholds used by downstream."""
    if score_value >= 0.8:
        return "sannolik"
    if score_value >= 0.4:
        return "möjlig"
    if score_value >= 0.2:
        return "närliggande"
    return "inget"
