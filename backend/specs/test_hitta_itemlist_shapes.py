"""Adversarial matrix for hitta.parse_hitta_html ItemList-shape handling.

Bug 1 root-cause (docs/BUGS.md): hitta.se returns TWO different shapes for
ItemList entries:
  Nested (Stockholm-class):  {@type: ListItem, position, item: {type, name, address, geo, ...}}
  Flat (Malmö+Göteborg):     {@type: ListItem, position, name, url}

Pre-fix: only nested-shape parsed → 67% empty-rate for Malmö+Göteborg.
Post-fix (this PR): both shapes parsed → 100% coverage.

Live-verified against captured 2026-05-13 production HTML:
- Stockholm 'Kungsgatan 1': 17 contacts (nested, unchanged)
- Malmö 'Västra Hamngatan 3': 0 → 25 contacts
- Göteborg 'Storgatan 15':    0 → 19 contacts

Run: python3 -m pytest backend/specs/test_hitta_itemlist_shapes.py -v
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services.hitta import parse_hitta_html


def _wrap_html(json_payload: dict) -> str:
    body = json.dumps(json_payload, ensure_ascii=False)
    return f'<html><body><script type="application/ld+json">{body}</script></body></html>'


# ----- J1: nested-shape (Stockholm-class) ---------------------------------


def test_j1_nested_shape_with_local_business() -> None:
    html = _wrap_html({
        "@context": "https://schema.org",
        "@type": "ItemList",
        "numberOfItems": 1,
        "itemListElement": [{
            "@type": "ListItem",
            "position": 1,
            "item": {
                "type": "LocalBusiness",
                "name": "Webbmaffian AB",
                "telephone": "+46849004200",
                "address": {
                    "@type": "PostalAddress",
                    "streetAddress": "Kungsgatan 60",
                    "addressLocality": "Stockholm",
                    "postalCode": "11122",
                },
                "geo": {"@type": "GeoCoordinates", "latitude": 59.33, "longitude": 18.06},
                "url": "https://www.hitta.se/webbmaffian+ab",
            },
        }],
    })
    result = parse_hitta_html(html, query="Kungsgatan 1")
    assert len(result.contacts) == 1
    c = result.contacts[0]
    assert c.name == "Webbmaffian AB"
    assert c.kind == "business"
    assert c.street_address == "Kungsgatan 60"
    assert c.city == "Stockholm"
    assert c.telephone == "+46849004200"
    assert c.lat == 59.33


# ----- J2: flat-shape (Malmö+Göteborg-class) — Bug 1 fix ------------------


def test_j2_flat_shape_extracts_name() -> None:
    """Flat ItemList entry has name+url directly, no nested `item` key.
    Pre-fix: 0 contacts. Post-fix: 1 contact with name."""
    html = _wrap_html({
        "@type": "ItemList",
        "numberOfItems": 1,
        "itemListElement": [{
            "@type": "ListItem",
            "position": 1,
            "name": "Christina Grygorowicz",
            "url": "https://www.hitta.se/christina+grygorowicz/malmo/...",
        }],
    })
    result = parse_hitta_html(html, query="Västra Hamngatan 3, Malmö")
    assert len(result.contacts) == 1
    assert result.contacts[0].name == "Christina Grygorowicz"
    assert result.contacts[0].kind == "business"  # no Person-marker in flat-shape


def test_j2_flat_shape_extracts_url() -> None:
    html = _wrap_html({
        "@type": "ItemList",
        "itemListElement": [{
            "@type": "ListItem", "position": 1,
            "name": "X", "url": "https://www.hitta.se/x",
        }],
    })
    result = parse_hitta_html(html, query="q")
    assert result.contacts[0].url == "https://www.hitta.se/x"


# ----- J3: total_hits captured from numberOfItems --------------------------


def test_j3_total_hits_from_number_of_items() -> None:
    html = _wrap_html({
        "@type": "ItemList",
        "numberOfItems": 25,
        "itemListElement": [],  # empty itemList but the count is set
    })
    result = parse_hitta_html(html, query="q")
    assert result.total_hits == 25
    assert len(result.contacts) == 0  # no entries to parse


# ----- J4: mixed shapes in same response --------------------------------


def test_j4_mixed_nested_and_flat_in_one_itemlist() -> None:
    """Defensive: if hitta someday returns mixed shapes, both must parse."""
    html = _wrap_html({
        "@type": "ItemList",
        "numberOfItems": 2,
        "itemListElement": [
            {
                "@type": "ListItem", "position": 1,
                "item": {"type": "LocalBusiness", "name": "Nested Co"},
            },
            {
                "@type": "ListItem", "position": 2,
                "name": "Flat Co", "url": "https://hitta.se/flat",
            },
        ],
    })
    result = parse_hitta_html(html, query="q")
    names = sorted(c.name for c in result.contacts)
    assert names == ["Flat Co", "Nested Co"]


# ----- J5: empty itemList still gracefully handled ------------------------


def test_j5_empty_item_list_returns_zero_contacts() -> None:
    html = _wrap_html({
        "@type": "ItemList",
        "numberOfItems": 0,
        "itemListElement": [],
    })
    result = parse_hitta_html(html, query="q")
    assert len(result.contacts) == 0
    assert result.total_hits == 0


# ----- J6: malformed entry skipped, others preserved --------------------


def test_j6_malformed_entry_skipped() -> None:
    html = _wrap_html({
        "@type": "ItemList",
        "itemListElement": [
            "not-a-dict",  # invalid
            None,           # invalid
            {"@type": "ListItem"},  # no name → skipped by _contact_from_ld_item
            {"@type": "ListItem", "name": "Valid", "url": "https://x"},  # valid flat
        ],
    })
    result = parse_hitta_html(html, query="q")
    names = [c.name for c in result.contacts]
    assert "Valid" in names


# ----- J7: Person flat-shape — kind="person" via type-string check -------


def test_j7_flat_shape_with_explicit_person_type() -> None:
    """If a flat entry carries @type='Person' (rare but possible), kind=person."""
    html = _wrap_html({
        "@type": "ItemList",
        "itemListElement": [{
            "@type": "Person",
            "name": "Anna Andersson",
            "url": "https://hitta.se/anna",
        }],
    })
    result = parse_hitta_html(html, query="q")
    assert len(result.contacts) == 1
    assert result.contacts[0].kind == "person"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
