"""Satellite imagery — ArcGIS World Imagery (free, no API key).

3x3 tile mosaic around lat/lng at given zoom, returned as JPEG bytes.
"""

from __future__ import annotations

import asyncio
import math
from io import BytesIO

import httpx
from error_logger import log_error
from PIL import Image, UnidentifiedImageError

TILE_SERVER = "https://server.arcgisonline.com/ArcGIS/rest/services/World_Imagery/MapServer/tile"
TILE_SIZE = 256
GRID = 3
JPEG_QUALITY = 88


async def fetch_satellite_image(lat: float, lng: float, zoom: int = 18) -> bytes:
    # Coerce + range-validate up front (spec invariants I3 + I2). Out-of-range
    # coords cause math domain errors; bad types cause TypeErrors mid-pipeline.
    try:
        lat = float(lat)
        lng = float(lng)
    except (TypeError, ValueError) as e:
        raise ValueError(f"lat/lng must be numeric: lat={lat!r} lng={lng!r}") from e
    if not (-90.0 <= lat <= 90.0):
        raise ValueError(f"lat out of range [-90, 90]: {lat}")
    if not (-180.0 <= lng <= 180.0):
        raise ValueError(f"lng out of range [-180, 180]: {lng}")
    zoom = max(1, min(22, int(zoom)))

    n = 2 ** zoom
    cx = int((lng + 180) / 360 * n)
    cy = int(
        (1 - math.log(math.tan(math.radians(lat)) + 1 / math.cos(math.radians(lat))) / math.pi)
        / 2
        * n
    )

    try:
        async with httpx.AsyncClient(timeout=15) as client:
            tasks = [
                _fetch_tile(client, zoom, cx - GRID // 2 + dx, cy - GRID // 2 + dy)
                for dy in range(GRID) for dx in range(GRID)
            ]
            tiles = await asyncio.gather(*tasks)
    except (httpx.HTTPError, UnidentifiedImageError) as e:
        log_error("satellite-fetch", e, context={"lat": lat, "lng": lng, "zoom": zoom})
        raise RuntimeError(f"ArcGIS satellite tiles unavailable: {e}") from e

    canvas = Image.new("RGB", (TILE_SIZE * GRID, TILE_SIZE * GRID))
    for i, tile in enumerate(tiles):
        dx, dy = i % GRID, i // GRID
        canvas.paste(tile, (dx * TILE_SIZE, dy * TILE_SIZE))

    buf = BytesIO()
    canvas.save(buf, format="JPEG", quality=JPEG_QUALITY)
    return buf.getvalue()


async def _fetch_tile(client: httpx.AsyncClient, zoom: int, tx: int, ty: int) -> Image.Image:
    r = await client.get(f"{TILE_SERVER}/{zoom}/{ty}/{tx}")
    r.raise_for_status()
    return Image.open(BytesIO(r.content))
