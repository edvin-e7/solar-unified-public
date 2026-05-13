"""Adversarial matrix for services.registry_gate.

Run: python3 backend/specs/test_registry_gate.py
Or:  python3 -m pytest backend/specs/test_registry_gate.py -v
"""

from __future__ import annotations

import asyncio
import importlib.util
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))

# Direct-file load so package __init__.py chains (bs4 from enrichment_executor) don't block.
def _load(module_name: str, relpath: str):
    path = BACKEND / relpath
    spec = importlib.util.spec_from_file_location(module_name, path)
    assert spec and spec.loader
    mod = importlib.util.module_from_spec(spec)
    sys.modules[module_name] = mod
    spec.loader.exec_module(mod)
    return mod


osm_solar = _load("osm_solar_standalone", "services/osm_solar.py")
_load("address_match_standalone", "services/address_match.py")
SolarSite = osm_solar.SolarSite


def _load_registry_gate(fake_fetch):
    """Load registry_gate with osm_solar.fetch_solar_around monkey-patched.

    We inject into both the standalone osm_solar module AND sys.modules["services.osm_solar"]
    because registry_gate.py imports as `from services import osm_solar`.
    """
    # Build a fresh osm_solar module under the real dotted name registry_gate will import.
    services_pkg = sys.modules.get("services")
    if services_pkg is None:
        import types
        services_pkg = types.ModuleType("services")
        services_pkg.__path__ = [str(BACKEND / "services")]
        sys.modules["services"] = services_pkg

    # Put our patched osm_solar under services.osm_solar
    osm_mod = _load("services.osm_solar", "services/osm_solar.py")
    osm_mod.fetch_solar_around = fake_fetch

    # address_match under services.address_match
    _load("services.address_match", "services/address_match.py")

    # Now load registry_gate (its `from services import osm_solar` will see our patched module).
    return _load("registry_gate_standalone", "services/registry_gate.py")


# --- fakes -------------------------------------------------------------


def _site(
    lat: float = 59.3361,
    lng: float = 18.0719,
    address: str | None = "Kungsgatan 1, 11143 Stockholm",
    osm_type: str = "way",
    osm_id: int = 42,
    capacity_kw: float | None = 5.0,
    method: str | None = "photovoltaic",
) -> SolarSite:
    return SolarSite(
        lat=lat, lng=lng, address=address,
        osm_type=osm_type, osm_id=osm_id,
        capacity_kw=capacity_kw, method=method,
    )


def _fake_returning(sites: list[SolarSite]):
    async def _fetch(lat, lng, radius_m, *, limit=5000):
        return list(sites)
    return _fetch


def _fake_raising(exc: BaseException):
    async def _fetch(lat, lng, radius_m, *, limit=5000):
        raise exc
    return _fetch


# --- matrix ------------------------------------------------------------


def test_no_sites_returns_none():
    rg = _load_registry_gate(_fake_returning([]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is None


def test_exact_addr_match_returns_hit_confidence_0_9():
    rg = _load_registry_gate(_fake_returning([_site(address="Kungsgatan 1, 11143 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.has_panels is True
    assert result.confidence == 0.9
    assert result.source == "osm-tag"


def test_same_street_different_number_is_not_a_hit():
    rg = _load_registry_gate(_fake_returning([_site(address="Kungsgatan 60, 11122 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is None


def test_same_postal_different_street_is_not_a_hit():
    rg = _load_registry_gate(_fake_returning([_site(address="Drottninggatan 5, 11143 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, 11143 Stockholm", 59.3361, 18.0719))
    assert result is None


def test_same_city_only_is_not_a_hit():
    rg = _load_registry_gate(_fake_returning([_site(address="Drottninggatan 5, 11122 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, 11143 Stockholm", 59.3361, 18.0719))
    assert result is None


def test_proximity_only_no_addr_tags_is_not_a_hit():
    """OSM site with address=None at same coords MUST NOT produce a hit.

    Covers the multi-unit apartment building false-positive: one unit has panels,
    query is a different unit — proximity ≠ identity.
    """
    rg = _load_registry_gate(_fake_returning([_site(address=None, lat=59.3361, lng=18.0719)]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is None


def test_overpass_raises_returns_none_fail_open():
    rg = _load_registry_gate(_fake_raising(RuntimeError("Overpass HTTP 429")))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is None


def test_overpass_raises_httpx_error_returns_none():
    import httpx
    rg = _load_registry_gate(_fake_raising(httpx.ConnectError("DNS failure")))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is None


def test_empty_address_returns_none_without_network():
    called = {"n": 0}
    async def _fetch(*a, **kw):
        called["n"] += 1
        return []
    rg = _load_registry_gate(_fetch)
    result = asyncio.run(rg.check("", 59.3361, 18.0719))
    assert result is None
    assert called["n"] == 0  # short-circuit: no Overpass call for empty address


def test_whitespace_address_returns_none_without_network():
    called = {"n": 0}
    async def _fetch(*a, **kw):
        called["n"] += 1
        return []
    rg = _load_registry_gate(_fetch)
    result = asyncio.run(rg.check("   ", 59.3361, 18.0719))
    assert result is None
    assert called["n"] == 0


def test_radius_zero_returns_none_without_network():
    called = {"n": 0}
    async def _fetch(*a, **kw):
        called["n"] += 1
        return []
    rg = _load_registry_gate(_fetch)
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719, radius_m=0))
    assert result is None
    assert called["n"] == 0


def test_radius_oversize_is_clipped_no_raise():
    rg = _load_registry_gate(_fake_returning([]))
    # Just must not raise — passing 99999 is clipped silently.
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719, radius_m=99_999))
    assert result is None


def test_uppercase_addr_tag_still_matches():
    """Address_match normalizes case. OSM addr tags in uppercase must still match."""
    rg = _load_registry_gate(_fake_returning([_site(address="KUNGSGATAN 1, 11143 STOCKHOLM")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.confidence == 0.9


def test_umlaut_fallback_matches():
    """Goteborg / Göteborg are the same city — address_match uses umlaut fallback."""
    rg = _load_registry_gate(_fake_returning([_site(address="Storgatan 5, 41120 Goteborg")]))
    result = asyncio.run(rg.check("Storgatan 5, Göteborg", 57.7, 11.97))
    assert result is not None
    assert result.has_panels is True


def test_multiple_sites_best_match_wins():
    """If one site is exact and another is same-street, the exact one is chosen."""
    sites = [
        _site(address="Kungsgatan 60, 11122 Stockholm", osm_id=100, capacity_kw=3.0),
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=200, capacity_kw=5.0),
    ]
    rg = _load_registry_gate(_fake_returning(sites))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.evidence["osm_id"] == 200
    assert result.evidence["matched_address"] == "Kungsgatan 1, 11143 Stockholm"


def test_tie_break_prefer_larger_capacity():
    """Two exact matches — prefer the one with larger capacity_kw."""
    sites = [
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=100, capacity_kw=3.0),
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=200, capacity_kw=8.0),
    ]
    rg = _load_registry_gate(_fake_returning(sites))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.evidence["osm_id"] == 200
    assert result.evidence["capacity_kw"] == 8.0


def test_tie_break_prefer_smaller_osm_id_when_capacity_equal():
    """Two exact matches, same capacity — deterministic tie-break by smaller osm_id."""
    sites = [
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=200, capacity_kw=5.0),
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=100, capacity_kw=5.0),
    ]
    rg = _load_registry_gate(_fake_returning(sites))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.evidence["osm_id"] == 100


def test_tie_break_capacity_none_sorts_last():
    """capacity_kw=None should not win over a site with an actual capacity."""
    sites = [
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=100, capacity_kw=None),
        _site(address="Kungsgatan 1, 11143 Stockholm", osm_id=200, capacity_kw=1.0),
    ]
    rg = _load_registry_gate(_fake_returning(sites))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.evidence["osm_id"] == 200


def test_evidence_contains_required_keys():
    rg = _load_registry_gate(_fake_returning([_site(
        address="Kungsgatan 1, 11143 Stockholm",
        osm_type="way", osm_id=99, capacity_kw=7.5, method="photovoltaic",
    )]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    ev = result.evidence
    assert ev["osm_type"] == "way"
    assert ev["osm_id"] == 99
    assert ev["capacity_kw"] == 7.5
    assert ev["matched_address"] == "Kungsgatan 1, 11143 Stockholm"
    assert ev["match_score"] == 1.0


def test_evidence_contains_no_pii_keys():
    """Anti-regression: evidence dict must never carry name/phone/email/personnummer fields."""
    rg = _load_registry_gate(_fake_returning([_site(address="Kungsgatan 1, 11143 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    banned = {"name", "phone", "email", "personnummer", "pnr", "ssn"}
    assert not (banned & set(result.evidence.keys())), f"PII leak in evidence: {result.evidence}"


def test_deterministic_same_input_same_output():
    sites = [_site(address="Kungsgatan 1, 11143 Stockholm")]
    rg = _load_registry_gate(_fake_returning(sites))
    a = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    b = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert a == b


def test_source_field_is_osm_tag():
    rg = _load_registry_gate(_fake_returning([_site(address="Kungsgatan 1, 11143 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.source == "osm-tag"


def test_has_panels_is_always_true_on_hit():
    rg = _load_registry_gate(_fake_returning([_site(address="Kungsgatan 1, 11143 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.has_panels is True  # invariant 5: gate never returns has_panels=False


def test_exact_confidence_is_exactly_0_9():
    """Boundary: confidence mapping for exact match is 0.9, never 1.0 (registry drift)."""
    rg = _load_registry_gate(_fake_returning([_site(address="Kungsgatan 1, 11143 Stockholm")]))
    result = asyncio.run(rg.check("Kungsgatan 1, Stockholm", 59.3361, 18.0719))
    assert result is not None
    assert result.confidence == 0.9
    assert result.confidence != 1.0


# --- runner ------------------------------------------------------------

if __name__ == "__main__":
    import traceback

    tests = [(n, f) for n, f in globals().items() if n.startswith("test_") and callable(f)]
    passed = 0
    failed: list[tuple[str, str]] = []
    for name, fn in tests:
        try:
            fn()
            passed += 1
            print(f"  PASS  {name}")
        except AssertionError as e:
            failed.append((name, f"AssertionError: {e}"))
            print(f"  FAIL  {name}: {e}")
        except Exception:
            failed.append((name, traceback.format_exc()))
            print(f"  ERR   {name}")
            traceback.print_exc()

    print(f"\n{passed}/{len(tests)} passed")
    if failed:
        sys.exit(1)
