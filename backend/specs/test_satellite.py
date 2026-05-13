"""Adversarial matrix for services/satellite.py.

Per spec: backend/specs/satellite.md.

Covers I1-I5 plus the documented edge cases. httpx + PIL are stubbed at
module scope; no real network and no real image decode.

Run: python3 -m pytest backend/specs/test_satellite.py -v
"""

from __future__ import annotations

import asyncio
import sys
from io import BytesIO
from pathlib import Path
from typing import Any

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from services import satellite as sat

# --- Fakes ---------------------------------------------------------------

class _FakeResponse:
    def __init__(self, content: bytes, status: int = 200) -> None:
        self.content = content
        self.status_code = status

    def raise_for_status(self) -> None:
        if self.status_code >= 400:
            # Use the base HTTPError so we don't depend on httpx-internal
            # constructor signatures (which differ across major versions).
            raise sat.httpx.HTTPError(f"http {self.status_code}")


class _FakeClient:
    """Fixed-response fake. Records URLs for SSRF / shape assertions."""

    def __init__(self, response_factory: Any, **_: Any) -> None:
        self._factory = response_factory
        self.urls: list[str] = []

    async def __aenter__(self) -> _FakeClient:
        return self

    async def __aexit__(self, *exc: Any) -> None:
        return None

    async def get(self, url: str) -> _FakeResponse:
        self.urls.append(url)
        return self._factory(url)


def _ok_jpeg_factory() -> bytes:
    """Smallest-valid JPEG bytes (1x1 black pixel)."""
    # Minimal JPEG — won't actually decode meaningfully without PIL,
    # so tests use a stubbed Image.open below instead of relying on this.
    return b"\xff\xd8\xff\xe0\x00\x10JFIF\x00\x01\x01\x00\x00\x01\x00\x01\x00\x00\xff\xd9"


class _FakeImage:
    """Quacks like PIL.Image enough for satellite.py's paste()/save() calls."""

    def __init__(self, mode: str = "RGB", size: tuple[int, int] = (256, 256)) -> None:
        self.mode = mode
        self.size = size
        self._pasted: list[tuple[Any, tuple[int, int]]] = []

    def paste(self, tile: Any, box: tuple[int, int]) -> None:
        self._pasted.append((tile, box))

    def save(self, buf: BytesIO, format: str, quality: int) -> None:
        # Write a real JPEG SOI marker so output passes the I1 check.
        assert format == "JPEG"
        buf.write(b"\xff\xd8\xff" + b"\x00" * 1024)


def _patch_pil_ok(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(sat.Image, "new", lambda mode, size: _FakeImage(mode, size))
    monkeypatch.setattr(sat.Image, "open", lambda _buf: _FakeImage())


def _install_client(monkeypatch: pytest.MonkeyPatch, factory: Any) -> _FakeClient:
    holder: dict[str, _FakeClient] = {}

    def make(*args: Any, **kwargs: Any) -> _FakeClient:
        c = _FakeClient(factory, **kwargs)
        holder["c"] = c
        return c

    monkeypatch.setattr(sat.httpx, "AsyncClient", make)
    return holder  # type: ignore[return-value]


# --- I1: returns valid JPEG -------------------------------------------------

def test_returns_jpeg_bytes_starting_with_soi_marker(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _patch_pil_ok(monkeypatch)
    _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))

    out = asyncio.run(sat.fetch_satellite_image(59.33, 18.07, zoom=18))
    assert isinstance(out, bytes)
    assert out.startswith(b"\xff\xd8\xff"), "must be JPEG SOI"


def test_fetches_full_3x3_grid(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    holder = _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    asyncio.run(sat.fetch_satellite_image(59.33, 18.07))
    assert len(holder["c"].urls) == sat.GRID * sat.GRID == 9


# --- I2: zoom clamp ---------------------------------------------------------

def test_zoom_above_22_is_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    holder = _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    asyncio.run(sat.fetch_satellite_image(59.33, 18.07, zoom=99))
    # Each URL embeds the zoom as the first path segment after /tile/
    for u in holder["c"].urls:
        z = int(u.rsplit("/tile/", 1)[1].split("/")[0])
        assert z == 22


def test_zoom_below_1_is_clamped(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    holder = _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    asyncio.run(sat.fetch_satellite_image(59.33, 18.07, zoom=0))
    for u in holder["c"].urls:
        z = int(u.rsplit("/tile/", 1)[1].split("/")[0])
        assert z == 1


# --- I3: SSRF / lat-lng validation ------------------------------------------

def test_lat_out_of_range_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    with pytest.raises(ValueError, match="lat out of range"):
        asyncio.run(sat.fetch_satellite_image(91.0, 18.0))


def test_lng_out_of_range_raises_value_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    with pytest.raises(ValueError, match="lng out of range"):
        asyncio.run(sat.fetch_satellite_image(59.0, 181.0))


def test_lat_negative_extreme_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    with pytest.raises(ValueError):
        asyncio.run(sat.fetch_satellite_image(-90.5, 18.0))


def test_non_numeric_lat_lng_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)
    _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    with pytest.raises(ValueError, match="lat/lng must be numeric"):
        asyncio.run(sat.fetch_satellite_image("not-a-coord", 18.0))  # type: ignore[arg-type]


def test_url_only_contains_tile_server_and_int_path(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """Construction is f-string with int math results — no user strings.

    Confirms there's no path-traversal vector in the upstream URL.
    """
    _patch_pil_ok(monkeypatch)
    holder = _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))
    asyncio.run(sat.fetch_satellite_image(59.33, 18.07, zoom=18))
    for u in holder["c"].urls:
        assert u.startswith(sat.TILE_SERVER + "/")
        # path after server is /<zoom>/<y>/<x> — three integer segments
        tail = u[len(sat.TILE_SERVER) + 1 :]
        parts = tail.split("/")
        assert len(parts) == 3
        for p in parts:
            int(p)  # raises if not a clean int


# --- I1 negative path: corrupt upstream -------------------------------------

def test_arcgis_404_raises_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    _patch_pil_ok(monkeypatch)

    def factory(url: str) -> _FakeResponse:
        # Use a real httpx error so the except (httpx.HTTPError, ...) branch fires.
        raise sat.httpx.HTTPError("404 not found")

    _install_client(monkeypatch, factory)
    with pytest.raises(RuntimeError, match="ArcGIS satellite tiles unavailable"):
        asyncio.run(sat.fetch_satellite_image(59.33, 18.07))


def test_corrupt_image_bytes_raise_runtime_error(monkeypatch: pytest.MonkeyPatch) -> None:
    """Non-image bytes from upstream (e.g. HTML rate-limit page)."""

    def bad_open(_buf: Any) -> Any:
        raise sat.UnidentifiedImageError("not an image")

    monkeypatch.setattr(sat.Image, "open", bad_open)
    monkeypatch.setattr(sat.Image, "new", lambda mode, size: _FakeImage(mode, size))
    _install_client(monkeypatch, lambda url: _FakeResponse(b"<html>rate limit</html>"))

    with pytest.raises(RuntimeError, match="ArcGIS satellite tiles unavailable"):
        asyncio.run(sat.fetch_satellite_image(59.33, 18.07))


# --- I5: no local persistence -----------------------------------------------

def test_no_disk_writes_in_satellite_module(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    """satellite.py must not write to disk; persistence is scanner._save_image."""
    _patch_pil_ok(monkeypatch)
    _install_client(monkeypatch, lambda url: _FakeResponse(_ok_jpeg_factory()))

    monkeypatch.chdir(tmp_path)
    out = asyncio.run(sat.fetch_satellite_image(59.33, 18.07))
    assert isinstance(out, bytes)
    # tmp_path should still be empty (excluding pytest's own scaffolding)
    leftovers = [p for p in tmp_path.iterdir() if not p.name.startswith(".")]
    assert leftovers == []


if __name__ == "__main__":
    raise SystemExit(pytest.main([__file__, "-v"]))
