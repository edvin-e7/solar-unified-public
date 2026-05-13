# Overpass Service Spec

## Public API

### Functions

- **`async fetch_houses_around(lat: float, lng: float, radius_m: int, *, limit: int = 2000) -> list[House]`**
  Finds residential buildings within a square bounding box of a given radius around a point.
  - `lat`, `lng`: Center point.
  - `radius_m`: Search radius in meters.
  - **Returns**: List of `House` objects.

- **`async fetch_houses_in_bbox(south, west, north, east, *, limit: int = 2000, timeout: float = 90.0) -> list[House]`**
  Low-level function to fetch buildings within a specific coordinate bounding box.

### Data Types

- **`House` (Dataclass)**:
  - `address`: Formatted Swedish address.
  - `lat`: Latitude.
  - `lng`: Longitude.

---

## Invariants

- **I1 [Residential Focus]**: The service MUST filter for residential building types (e.g., `house`, `detached`, `residential`) and explicitly exclude non-residential uses like `commercial`, `industrial`, or `school`.
- **I2 [Address Normalization]**: Extracted addresses MUST be normalized to the format `Street Number, Postcode City`.
- **I3 [BBox Geometry]**: The radius-to-bbox calculation MUST account for the narrowing of longitude degrees at higher latitudes (Mercator compensation).
- **I4 [Strict Deduplication]**: Results MUST be de-duplicated by their lowercase formatted address to prevent multiple entries for the same physical building (e.g., node vs way).
- **I5 [Descriptive Error Mapping]**: Overpass-specific HTTP status codes (429, 504, 502) MUST be mapped to descriptive `RuntimeError` messages.
- **I6 [Policy-Compliant User-Agent]**: All outgoing requests MUST include a identifying `User-Agent` string as required by the Overpass API usage policy.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| Search radius = 0 | Returns empty list or very small bbox search. | I3 |
| Overpass rate limit (429) | Raises `RuntimeError: Overpass rate-limited (HTTP 429)`. | I5 |
| Building with only `building=yes` | Included in search (part of `HOUSE_TYPES`). | I1 |
| Building tagged as `amenity=school` | Excluded even if it matches a residential house type. | I1 |
| Address missing `addr:street` | Excluded from results. | I2 |
| Extremely high latitude | `cos(radians(lat))` clamped to 0.01 to prevent division by zero. | I3 |
