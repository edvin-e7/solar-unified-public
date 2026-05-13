"""Adversarial matrix for /api/leads/snapshot one-button orchestration.

Pins request-validation behavior. Live-flow (Overpass + Moondream) tested
via curl-smoke; here we cover input-validation + edge cases without
network.

Run: python3 -m pytest backend/specs/test_leads_snapshot.py -v
"""

from __future__ import annotations

import sys
from pathlib import Path

import pytest
from pydantic import ValidationError

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from api.leads import LeadsSnapshotRequest

# ----- H1: input validation -----------------------------------------------


def test_h1_municipality_only_is_valid() -> None:
    req = LeadsSnapshotRequest(municipality="Kungsängen")
    assert req.municipality == "Kungsängen"
    assert req.lat is None and req.lng is None


def test_h1_lat_lng_only_is_valid() -> None:
    req = LeadsSnapshotRequest(lat=59.49, lng=17.74)
    assert req.lat == 59.49 and req.lng == 17.74


def test_h1_defaults() -> None:
    req = LeadsSnapshotRequest(municipality="Stockholm")
    assert req.radius_m == 2000
    assert req.building_limit == 20
    assert req.detect is True
    assert req.skip_existing is True


def test_h1_radius_lower_bound() -> None:
    with pytest.raises(ValidationError):
        LeadsSnapshotRequest(municipality="X", radius_m=0)


def test_h1_radius_upper_bound() -> None:
    with pytest.raises(ValidationError):
        LeadsSnapshotRequest(municipality="X", radius_m=50000)


def test_h1_building_limit_lower_bound() -> None:
    with pytest.raises(ValidationError):
        LeadsSnapshotRequest(municipality="X", building_limit=0)


def test_h1_building_limit_upper_bound() -> None:
    # 200 is the documented cost-cap; 201 invalid
    with pytest.raises(ValidationError):
        LeadsSnapshotRequest(municipality="X", building_limit=500)


# ----- H2: skip_existing flag ---------------------------------------------


def test_h2_skip_existing_default_true() -> None:
    req = LeadsSnapshotRequest(municipality="X")
    assert req.skip_existing is True


def test_h2_skip_existing_can_disable() -> None:
    req = LeadsSnapshotRequest(municipality="X", skip_existing=False)
    assert req.skip_existing is False


# ----- H3: detect flag (allows preview without LLM inference) -------------


def test_h3_detect_can_disable() -> None:
    """Sales-pitch can be 'preview the region' without burning Moondream time."""
    req = LeadsSnapshotRequest(municipality="X", detect=False)
    assert req.detect is False


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
