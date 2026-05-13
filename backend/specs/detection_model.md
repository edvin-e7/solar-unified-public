# Detection Model Service Spec

## Public API

### Functions

- **`async detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> DetectionResult`**
  The primary entrypoint for image detection. Dispatches the request to the configured or automatically selected backend.
  - `image_bytes`: Raw image data (usually satellite/aerial imagery).
  - `lat`: Latitude of the image center (used for scale/area calculations).
  - `zoom`: Google-style zoom level (default 20).
  - **Returns**: `DetectionResult` dict.
  - **Raises**: `RuntimeError` if the selected backend is unusable or configuration is invalid.

- **`select_backend() -> Backend`**
  Determines which backend to use based on the `DETECTION_BACKEND` environment variable.
  - **Returns**: `ml`, `embed`, `moondream`, or `gemini`.
  - **Raises**: `RuntimeError` for invalid environment variable values.

- **`select_backend_safe() -> tuple[Backend | None, str | None]`**
  A non-raising version of `select_backend`, returning `(backend, None)` on success or `(None, error_message)` on failure. Used for status checks.

### Types

- **`DetectionResult` (TypedDict)**:
  - `has_panels`: `bool`
  - `confidence`: `float` (0.0 to 1.0)
  - `panel_area_m2`: `float | None`
  - `roof_area_m2`: `float | None`
  - `inference_ms`: `int`
  - `backend`: `str` ("ml" | "embed" | "moondream" | "gemini")

- **`Backend`**: `Literal["ml", "embed", "moondream", "gemini"]`

---

## Invariants

- **I1 [Auto-Selection Order]**: When `DETECTION_BACKEND` is "auto" (or unset), the selection priority MUST be: `ml` -> `embed` -> `moondream` -> `gemini`.
- **I2 [Strict Overrides]**: If `DETECTION_BACKEND` is set to a specific backend (e.g., "ml"), that backend MUST be used. If it is unavailable/unusable, a `RuntimeError` MUST be raised.
- **I3 [Configuration Validation]**: Any value for `DETECTION_BACKEND` that is not "auto", empty, or one of the valid backends MUST result in a `RuntimeError` during backend selection.
- **I4 [Traceability]**: Every `DetectionResult` MUST correctly identify the `backend` used to facilitate debugging and warnings about non-deterministic LLM results.
- **I5 [Safe Discovery]**: `select_backend_safe` MUST NOT raise exceptions, ensuring system-level status endpoints remain resilient to configuration errors.
- **I6 [Uniform Contract]**: All backends MUST implement a `detect` function with the same signature and return a dictionary compatible with `DetectionResult`.
- **I7 [Fallback Exhaustion]**: In "auto" mode, the system MUST fall through to the next available backend if the current one is unavailable, eventually reaching "gemini".
- **I8 [Back-Compatibility]**: The service MUST re-export core ML constants (`MODEL_PATH`, `THRESHOLD`, etc.) from `detection_ml` to maintain compatibility with legacy callers.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `DETECTION_BACKEND="invalid"` | `select_backend` raises `RuntimeError`. | I3 |
| `DETECTION_BACKEND="ml"` but `ml` is unavailable | `detect` raises `RuntimeError`. | I2 |
| `DETECTION_BACKEND="auto"` and `ml` weights missing | Skips `ml`, tries `embed`. | I1, I7 |
| Corrupt `image_bytes` | Specific backend should raise error; `detection_model` bubbles it up. | I6 |
| Gemini API key missing (as fallback) | `detection_gemini` will raise `RuntimeError` when called by `detect`. | I2, I7 |
| `select_backend_safe` with invalid env | Returns `(None, "DETECTION_BACKEND='...' unknown...")`. | I5 |
| Rapid sequential `detect` calls | Thread-safety/concurrency depends on backend (ML uses ONNX session). | I6 |
| Extreme Latitude (e.g. 90.0) | Passed to backend; if backend fails scale calc, it should error gracefully. | I6 |
