"""Adversarial matrix for services/geocode.py.

Per spec: backend/specs/geocode.md. Each row maps to a numbered invariant
(I1-I5) or to the documented edge cases.

httpx is monkeypatched at module scope; no real network calls.

Run: python3 -m pytest backend/specs/test_geocode.py -v
Or:  python3 backend/specs/test_geocode.py    (asyncio-fallback runner below)
"""

from __future__ import annotations

import asyncio
import sys
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import geocode as geocode_mod

# --- Fakes ---------------------------------------------------------------

class _FakeResponse:
    def __init__(self, payload: Any, status: int = 200) -> None:
        self._payload = payload
        self.status_code = status
        self.headers: dict[str, str] = {}

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            raise RuntimeError(f"http {self.status_code}")

    def json(self) -> Any:
        return self._payload


class _FakeClient:
    """Records every outbound request so we can assert User-Agent + params.

    `script` is a list of payloads returned in order (one per .get() call).
    """

    def __init__(self, *, script: list[Any], headers: dict[str, str] | None = None) -> None:
        self._script = list(script)
        self.headers = headers or {}
        self.calls: list[dict[str, Any]] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str, *, params: dict | None = None) -> _FakeResponse:
        self.calls.append({"url": url, "params": params or {}, "headers": self.headers})
        if not self._script:
            raise AssertionError("FakeClient ran out of scripted responses")
        next_payload = self._script.pop(0)
        if isinstance(next_payload, Exception):
            raise next_payload
        return _FakeResponse(next_payload)


def _patch_client(monkeypatch: pytest.MonkeyPatch, *, script: list[Any]) -> _FakeClient:
    """Install a fake AsyncClient. Returns the *single* instance used."""
    holder: dict[str, _FakeClient] = {}

    def factory(*args: Any, **kwargs: Any) -> _FakeClient:
        c = _FakeClient(script=script, headers=kwargs.get("headers", {}))
        holder["c"] = c
        return c

    monkeypatch.setattr(geocode_mod.httpx, "AsyncClient", factory)
    return holder  # type: ignore[return-value]


# --- geocode() — happy path + I2/I3 ----------------------------------------

def test_geocode_returns_lat_lng_tuple(monkeypatch: pytest.MonkeyPatch) -> None:
    holder = _patch_client(monkeypatch, script=[[{"lat": "59.3293", "lon": "18.0686"}]])
    out = asyncio.run(geocode_mod.geocode("Kungsgatan 1, Stockholm"))
    assert out == (59.3293, 18.0686)
    assert isinstance(out[0], float) and isinstance(out[1], float)
    assert holder["c"].calls[0]["params"]["countrycodes"] == "se"


def test_geocode_empty_result_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """I2: 'no result' is ValueError, never (0.0, 0.0)."""
    _patch_client(monkeypatch, script=[[], []])
    with pytest.raises(ValueError, match="Could not geocode"):
        asyncio.run(geocode_mod.geocode("definitely not a place 12345"))


def test_geocode_empty_string_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, script=[[]])
    with pytest.raises(ValueError):
        asyncio.run(geocode_mod.geocode(""))


def test_geocode_whitespace_only_raises(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, script=[[]])
    with pytest.raises(ValueError):
        asyncio.run(geocode_mod.geocode("   "))


def test_geocode_uses_user_agent_header(monkeypatch: pytest.MonkeyPatch) -> None:
    """I4: Nominatim policy requires identifying User-Agent."""
    holder = _patch_client(monkeypatch, script=[[{"lat": "59.0", "lon": "18.0"}]])
    asyncio.run(geocode_mod.geocode("Stockholm"))
    ua = holder["c"].headers.get("User-Agent", "")
    assert ua, "User-Agent must be set"
    assert "solar-unified" in ua


def test_geocode_unicode_swedish_chars_preserved(monkeypatch: pytest.MonkeyPatch) -> None:
    holder = _patch_client(monkeypatch, script=[[{"lat": "57.7", "lon": "11.97"}]])
    asyncio.run(geocode_mod.geocode("Götaplatsen, Göteborg"))
    sent = holder["c"].calls[0]["params"]["q"]
    assert "Götaplatsen" in sent and "Göteborg" in sent


def test_geocode_simplification_fallback(monkeypatch: pytest.MonkeyPatch) -> None:
    """First request fails (empty), second (digits stripped) succeeds."""
    holder = _patch_client(
        monkeypatch,
        script=[[], [{"lat": "59.0", "lon": "18.0"}]],
    )
    out = asyncio.run(geocode_mod.geocode("123 Stockholm"))
    assert out == (59.0, 18.0)
    assert len(holder["c"].calls) == 2
    assert holder["c"].calls[0]["params"]["q"] == "123 Stockholm"
    assert holder["c"].calls[1]["params"]["q"] == "Stockholm"


def test_geocode_no_simplification_when_no_digits(monkeypatch: pytest.MonkeyPatch) -> None:
    """No second request if removing digits leaves the query unchanged."""
    holder = _patch_client(monkeypatch, script=[[]])
    with pytest.raises(ValueError):
        asyncio.run(geocode_mod.geocode("Stockholm"))
    assert len(holder["c"].calls) == 1


def test_geocode_sql_shaped_query_passes_through(monkeypatch: pytest.MonkeyPatch) -> None:
    """Bad input becomes a Nominatim query; httpx URL-encodes for us."""
    holder = _patch_client(monkeypatch, script=[[]])
    with pytest.raises(ValueError):
        asyncio.run(geocode_mod.geocode("'; DROP TABLE prospects; --"))
    assert holder["c"].calls[0]["params"]["q"].startswith("'")


def test_geocode_network_error_propagates(monkeypatch: pytest.MonkeyPatch) -> None:
    """Timeouts surface to the caller — they decide whether to retry."""
    _patch_client(monkeypatch, script=[TimeoutError("nominatim slow")])
    with pytest.raises(TimeoutError):
        asyncio.run(geocode_mod.geocode("Stockholm"))


# --- reverse_geocode() -----------------------------------------------------

def _reverse_payload(**addr: str) -> dict:
    return {"address": {**addr}}


def test_reverse_geocode_full_address(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        script=[
            _reverse_payload(
                country_code="se",
                road="Kungsgatan",
                house_number="1",
                postcode="111 43",
                city="Stockholm",
            )
        ],
    )
    out = asyncio.run(geocode_mod.reverse_geocode(59.33, 18.07))
    assert out == "Kungsgatan 1, 111 43 Stockholm"


def test_reverse_geocode_no_country_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """I3: best-effort enrichment returns None, doesn't raise."""
    _patch_client(monkeypatch, script=[_reverse_payload(country_code="us", road="Main St")])
    out = asyncio.run(geocode_mod.reverse_geocode(0.0, 0.0))
    assert out is None


def test_reverse_geocode_ocean_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    """Empty payload from Nominatim — return None, not crash."""
    _patch_client(monkeypatch, script=[{}])
    out = asyncio.run(geocode_mod.reverse_geocode(0.0, 0.0))
    assert out is None


def test_reverse_geocode_no_road_returns_none(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(monkeypatch, script=[_reverse_payload(country_code="se", city="Stockholm")])
    out = asyncio.run(geocode_mod.reverse_geocode(59.33, 18.07))
    assert out is None


def test_reverse_geocode_falls_back_to_pedestrian(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        script=[_reverse_payload(country_code="se", pedestrian="Sergels Torg", city="Stockholm")],
    )
    out = asyncio.run(geocode_mod.reverse_geocode(59.33, 18.07))
    assert out == "Sergels Torg, Stockholm"


def test_reverse_geocode_no_postcode_keeps_city(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_client(
        monkeypatch,
        script=[_reverse_payload(country_code="se", road="Storgatan", city="Uppsala")],
    )
    out = asyncio.run(geocode_mod.reverse_geocode(59.86, 17.64))
    assert out == "Storgatan, Uppsala"


def test_reverse_geocode_lat_lng_formatted_to_six_decimals(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    holder = _patch_client(
        monkeypatch,
        script=[_reverse_payload(country_code="se", road="X", city="Y")],
    )
    asyncio.run(geocode_mod.reverse_geocode(59.123456789, 18.987654321))
    sent = holder["c"].calls[0]["params"]
    assert sent["lat"] == "59.123457"
    assert sent["lon"] == "18.987654"


# --- Argparse-free fallback runner -----------------------------------------

if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
