"""Adversarial matrix for BatchScanRequest.resolved_locations() shim.

Per BUGS.md Bug 10: /api/detect/batch should accept both
{"locations": [{"address": str}]} and {"addresses": [str]} so callers can
standardize on the simpler shape (parity with /api/enrich/batch).

Run: python3 -m pytest backend/specs/test_scan_batch_compat.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.scan import BatchScanRequest, ScanRequest


def test_only_locations_returns_locations_as_is() -> None:
    req = BatchScanRequest(
        locations=[ScanRequest(address="Kungsgatan 1, Stockholm")]
    )
    locs = req.resolved_locations()
    assert len(locs) == 1
    assert locs[0].address == "Kungsgatan 1, Stockholm"


def test_only_addresses_maps_to_locations() -> None:
    req = BatchScanRequest(addresses=["A", "B"])
    locs = req.resolved_locations()
    assert len(locs) == 2
    assert locs[0].address == "A"
    assert locs[1].address == "B"
    # Defaults applied via Pydantic
    assert locs[0].label == ""
    assert locs[0].lat is None and locs[0].lng is None


def test_both_concatenates_locations_then_addresses() -> None:
    req = BatchScanRequest(
        locations=[ScanRequest(address="X")],
        addresses=["Y", "Z"],
    )
    locs = req.resolved_locations()
    assert [l.address for l in locs] == ["X", "Y", "Z"]


def test_neither_returns_empty_list() -> None:
    req = BatchScanRequest()
    assert req.resolved_locations() == []


def test_addresses_with_explicit_empty_list_is_falsy() -> None:
    # Empty list is falsy → fall through to locations
    req = BatchScanRequest(addresses=[], locations=[ScanRequest(address="X")])
    locs = req.resolved_locations()
    assert len(locs) == 1
    assert locs[0].address == "X"


def test_addresses_with_lat_lng_in_locations_preserved() -> None:
    # Mixed shape: lat/lng location + addresses should both pass through
    req = BatchScanRequest(
        locations=[ScanRequest(lat=59.3, lng=18.1, label="Stockholm")],
        addresses=["Göteborg, Sverige"],
    )
    locs = req.resolved_locations()
    assert len(locs) == 2
    assert locs[0].lat == 59.3 and locs[0].lng == 18.1
    assert locs[1].address == "Göteborg, Sverige"


def test_addresses_does_not_mutate_input() -> None:
    addresses_input = ["A", "B"]
    req = BatchScanRequest(addresses=addresses_input)
    _ = req.resolved_locations()
    # Pydantic copies; addresses_input shouldn't be mutated
    assert addresses_input == ["A", "B"]


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
