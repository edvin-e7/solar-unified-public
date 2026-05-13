"""Adversarial matrix for services/geocode.py — GeocodeNotFound + permutations.

Fixes docs/BUGS.md Bug 2 — single ValueError raise was indistinguishable from
upstream errors; permutation-fallback for known-failing addresses.

Backwards-compat invariant: GeocodeNotFound is a ValueError subclass so all
existing `except ValueError` catch-sites in api/scan.py + services/scanner.py
continue to work without modification.

Run: python3 -m pytest backend/specs/test_geocode_typed_error.py -v
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import geocode as geocode_mod

# --- Test fixtures: Fake httpx client ---------------------------------------


class _FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    def __init__(self, *, script: list[Any]) -> None:
        self._script = list(script)
        self.requested_queries: list[str] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc_info) -> None:
        return None

    async def get(self, url: str, *, params: dict, **_) -> _FakeResponse:
        self.requested_queries.append(params.get("q", ""))
        payload = self._script.pop(0) if self._script else []
        return _FakeResponse(payload)


# --- D1: GeocodeNotFound subclass + attributes ------------------------------


def test_d1_geocode_not_found_subclasses_value_error() -> None:
    """Backwards-compat: existing `except ValueError` sites must keep working."""
    assert issubclass(geocode_mod.GeocodeNotFound, ValueError)


def test_d1_not_found_carries_address_and_tried() -> None:
    e = geocode_mod.GeocodeNotFound("Storgatan 1, Skövde", tried=["Storgatan 1, Skövde", "Skövde"])
    assert e.address == "Storgatan 1, Skövde"
    assert e.tried == ["Storgatan 1, Skövde", "Skövde"]
    assert "Storgatan 1, Skövde" in str(e)


# --- D2: _permutations ordering --------------------------------------------


def test_d2_permutations_starts_with_original() -> None:
    p = geocode_mod._permutations("Västra Hamngatan 3, Malmö")
    assert p[0] == "Västra Hamngatan 3, Malmö"


def test_d2_permutations_dedupes() -> None:
    # If "no numbers" equals original, it shouldn't be duplicated
    p = geocode_mod._permutations("Stockholm")
    assert len(p) == len(set(p))


def test_d2_permutations_includes_no_numbers() -> None:
    p = geocode_mod._permutations("Storgatan 15, Göteborg")
    # "15" should be stripped, comma collapsed
    assert any("Storgatan" in v and "15" not in v for v in p)
    # No double-comma / dangling-comma artifacts
    for v in p:
        assert ", ," not in v
        assert not v.startswith(",")
        assert not v.endswith(",")


def test_d2_permutations_truncates_comma_tail_first() -> None:
    p = geocode_mod._permutations("X, Y, Z")
    # Original first, then tail-first truncations: "X, Y" before "X"
    idx_xy = p.index("X, Y")
    idx_x = p.index("X")
    assert idx_xy < idx_x


def test_d2_permutations_falls_back_to_city_only() -> None:
    p = geocode_mod._permutations("Västra Hamngatan 3, Malmö")
    assert "Malmö" in p


def test_d2_permutations_handles_address_without_comma() -> None:
    # No comma → no comma-prefix variants, but numeric-strip still applies
    p = geocode_mod._permutations("Storgatan 15")
    assert "Storgatan 15" in p
    assert "Storgatan" in p


# --- D3: geocode() retries permutations + uses first hit -------------------


def _run(coro):
    return asyncio.get_event_loop().run_until_complete(coro) if not asyncio.get_event_loop().is_running() else None


def test_d3_geocode_hits_original_first(monkeypatch) -> None:
    fake = _FakeClient(script=[[{"lat": "59.3", "lon": "18.1"}]])
    monkeypatch.setattr(geocode_mod.httpx, "AsyncClient", lambda **kw: fake)

    result = asyncio.run(geocode_mod.geocode("Kungsgatan 1, Stockholm"))
    assert result == (59.3, 18.1)
    assert len(fake.requested_queries) == 1
    assert fake.requested_queries[0] == "Kungsgatan 1, Stockholm"


def test_d3_geocode_falls_back_to_city_only(monkeypatch) -> None:
    """Original + permutations all miss, final fallback to last token (city)
    succeeds with city-center coords. Permutation count is implementation-
    dependent — we pre-compute it from _permutations() and script accordingly."""
    address = "Västra Hamngatan 3, Malmö"
    variants = geocode_mod._permutations(address)
    # All variants except the last (city) miss; last hits
    script = [[] for _ in variants[:-1]] + [[{"lat": "55.6", "lon": "13.0"}]]
    fake = _FakeClient(script=script)
    monkeypatch.setattr(geocode_mod.httpx, "AsyncClient", lambda **kw: fake)

    result = asyncio.run(geocode_mod.geocode(address))
    assert result == (55.6, 13.0)
    # Verify the last query was the city alone
    assert fake.requested_queries[-1] == "Malmö"


def test_d3_all_permutations_miss_raises_geocode_not_found(monkeypatch) -> None:
    fake = _FakeClient(script=[[], [], [], []])  # all empty
    monkeypatch.setattr(geocode_mod.httpx, "AsyncClient", lambda **kw: fake)

    with pytest.raises(geocode_mod.GeocodeNotFound) as excinfo:
        asyncio.run(geocode_mod.geocode("Definitely Not A Real Address 9999, Nowhere"))

    e = excinfo.value
    assert e.address == "Definitely Not A Real Address 9999, Nowhere"
    assert len(e.tried) >= 2  # at least original + one permutation
    assert e.tried[0] == "Definitely Not A Real Address 9999, Nowhere"


def test_d3_legacy_value_error_catch_still_works(monkeypatch) -> None:
    """Backwards-compat: existing callers using `except ValueError` keep working."""
    fake = _FakeClient(script=[[]])
    monkeypatch.setattr(geocode_mod.httpx, "AsyncClient", lambda **kw: fake)

    raised = False
    try:
        asyncio.run(geocode_mod.geocode("nope"))
    except ValueError:
        raised = True
    assert raised


# --- D4: BUGS.md acceptance-criterion addresses ----------------------------


@pytest.mark.parametrize(
    "address,expected",
    [
        ("Kungsgatan 1, Stockholm", (59.3326, 18.0649)),
        ("Storgatan 15, Göteborg", (57.7089, 11.9746)),
        ("Västra Hamngatan 3, Malmö", (55.6050, 13.0038)),
    ],
)
def test_d4_smoke_addresses_resolve_with_fakes(monkeypatch, address, expected) -> None:
    """The 3 BUGS.md acceptance addresses must resolve under the fake client.
    Real network test is gated on Edvin's live backend; here we just verify
    the call shape produces tuple[float, float] when Nominatim returns data."""
    fake = _FakeClient(script=[[{"lat": str(expected[0]), "lon": str(expected[1])}]])
    monkeypatch.setattr(geocode_mod.httpx, "AsyncClient", lambda **kw: fake)
    result = asyncio.run(geocode_mod.geocode(address))
    assert result == expected


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
