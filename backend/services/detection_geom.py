"""Satellite-tile geometry — pixel counts → square meters.

Pure math, no I/O, no model dependency. Web-Mercator meters-per-pixel formula
applied to the Google Static Maps tile we fetched (zoom + lat) and rescaled
from model-input coordinates back to tile coordinates.

Reference: https://wiki.openstreetmap.org/wiki/Slippy_map_tilenames#Resolution_and_Scale
"""

from __future__ import annotations

import math

# Google Static Maps Web-Mercator constant — meters per pixel at zoom 0, equator.
EARTH_CIRCUMFERENCE_M_PER_PX_Z0 = 156543.03392


def meters_per_pixel(lat: float, zoom: int) -> float:
    """Web-Mercator meters per pixel at a given latitude and zoom level."""
    lat_clamped = max(-85.0, min(85.0, float(lat)))
    return EARTH_CIRCUMFERENCE_M_PER_PX_Z0 * math.cos(math.radians(lat_clamped)) / (2 ** zoom)


def mask_pixels_to_m2(
    mask_pixel_count: int,
    *,
    lat: float,
    zoom: int,
    tile_size_px: int,
    model_size_px: int,
) -> float:
    """Convert a binary-mask pixel count (in model-input space) to real m².

    The model receives a tile resized to `model_size_px`. Each model pixel
    therefore covers `(tile_size_px / model_size_px)` tile pixels along each
    axis. Each tile pixel covers `meters_per_pixel(lat, zoom)` meters along
    each axis.
    """
    if mask_pixel_count <= 0:
        return 0.0
    if tile_size_px <= 0 or model_size_px <= 0:
        raise ValueError("tile_size_px and model_size_px must be positive")
    scale = tile_size_px / model_size_px
    tile_pixels = mask_pixel_count * (scale ** 2)
    mpp = meters_per_pixel(lat, zoom)
    return tile_pixels * (mpp ** 2)
