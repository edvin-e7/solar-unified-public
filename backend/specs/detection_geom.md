# Detection Geometry Service Spec

## Public API

### Functions

- **`meters_per_pixel(lat: float, zoom: int) -> float`**
  Calculates the real-world distance represented by a single pixel at the given latitude and Web-Mercator zoom level.
  - `lat`: Latitude in degrees.
  - `zoom`: Web-Mercator zoom level (e.g., Google Maps zoom).
  - **Returns**: Meters per pixel.

- **`mask_pixels_to_m2(mask_pixel_count: int, *, lat: float, zoom: int, tile_size_px: int, model_size_px: int) -> float`**
  Converts a pixel count from a model's prediction mask into a real-world area in square meters.
  - `mask_pixel_count`: Number of active pixels in the mask.
  - `lat`: Latitude.
  - `zoom`: Zoom level.
  - `tile_size_px`: Original tile size (e.g., 512).
  - `model_size_px`: Model input size (e.g., 640).
  - **Returns**: Area in $m^2$.

---

## Invariants

- **I1 [Mercator Scaling]**: The `meters_per_pixel` calculation MUST use the standard Web-Mercator formula: $S = C \cdot \cos(\text{lat}) / 2^{\text{zoom}}$, where $C$ is the earth's circumference at zoom 0.
- **I2 [Safe Latitude Bound]**: Latitude MUST be clamped to the range `[-85.0, 85.0]` to prevent `math.cos` approaching zero or negative values at extreme poles.
- **I3 [Area Scaling Logic]**: `mask_pixels_to_m2` MUST apply the squared scale factor $(tile\_size / model\_size)^2$ to account for image resizing before applying the squared $meters\_per\_pixel$ factor.
- **I4 [Pure Math]**: The service MUST NOT perform any I/O or stateful operations; it MUST remain a pure mathematical utility.
- **I5 [Error on Non-Positive Dimensions]**: The service MUST raise a `ValueError` if `tile_size_px` or `model_size_px` are $\le 0$ to prevent division by zero or invalid scaling.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Latitude > 85.0 | Clamped to 85.0; returns a valid small number. | I2 |
| `mask_pixel_count` = 0 | Returns 0.0. | I3 |
| `tile_size_px` = 0 | Raises `ValueError`. | I5 |
| `model_size_px` = 0 | Raises `ValueError`. | I5 |
| Extremely high zoom (e.g. 30) | Returns a very small area (sub-centimeter). | I1 |
| Zoom = 0 | Returns a very large area (continental). | I1 |
