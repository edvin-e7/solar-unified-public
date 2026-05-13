# OSM Solar Service Spec

## Public API

### Functions

- **`async fetch_solar_around(lat: float, lng: float, radius_m: int, *, limit: int = 5000) -> list[SolarSite]`**
  Finds existing solar PV installations within a given radius.
  - `lat`, `lng`: Center point.
  - `radius_m`: Search radius in meters.
  - **Returns**: List of `SolarSite` objects.

### Data Types

- **`SolarSite` (Dataclass)**:
  - `lat`, `lng`: Coordinates.
  - `address`: Optional formatted address.
  - `osm_type`: "node", "way", or "relation".
  - `osm_id`: OSM unique identifier.
  - `capacity_kw`: Installed capacity in kilowatts ($kW$).
  - `method`: Solar generation method (e.g., "photovoltaic").

---

## Invariants

- **I1 [Solar Tagging Coverage]**: The service MUST query for multiple tagging standards: `generator:source=solar`, `power=generator`, `roof:solar=yes`, and `roof:material=solar_panels`.
- **I2 [Unit Normalization]**: Capacity values MUST be normalized to kilowatts ($kW$), handling suffixes like `MW`, `kW`, and `W` case-insensitively and removing whitespaces.
- **I3 [Spatial Centroid Extraction]**: For non-node elements (ways/relations), the service MUST use the `center` coordinate provided by Overpass.
- **I4 [Strict Global Deduplication]**: Results MUST be de-duplicated using the unique `(osm_type, osm_id)` pair.
- **I5 [BBox Geometry]**: Radius-to-bbox conversion MUST account for latitude-based longitude narrowing for spatial accuracy.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `generator:output:electricity` = "1.5 MW" | Normalized to `1500.0` kW. | I2 |
| `plant:output:electricity` = "200 w" | Normalized to `0.2` kW. | I2 |
| Solar site on a `way` (rooftop) | Correctly extracts center coordinates. | I3 |
| Duplicate ID in different result sets | Filtered out by `seen` set. | I4 |
| Address missing `addr:street` | `address` field set to `None`. | I1 (Address helper) |
| Overpass returns no elements | Returns an empty list. | I4 |
