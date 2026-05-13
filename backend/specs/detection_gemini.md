# Detection Gemini Service Spec

## Public API

### Functions

- **`async detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict`**
  Runs cloud-based vision LLM inference on the provided image.
  - `image_bytes`: Raw image data.
  - `lat`: Latitude.
  - `zoom`: Zoom level.
  - **Returns**: A dictionary compatible with `DetectionResult`.

- **`is_available() -> bool`**
  Checks if `GEMINI_API_KEY` is set and the `google-genai` SDK is importable.

- **`reset_client_cache_for_tests() -> None`**
  Clears the cached `genai.Client`.

### Constants

- `THRESHOLD`: 0.5 (confidence threshold for detection).
- `DEFAULT_MODEL`: "gemini-2.5-flash".
- `MAX_ATTEMPTS`: 3 (number of retries for transient errors).
- `_RESPONSE_SCHEMA`: JSON schema enforced for structured outputs.

---

## Invariants

- **I1 [API Key Requirement]**: The service MUST NOT attempt detection unless `GEMINI_API_KEY` is present in the environment.
- **I2 [Structured Response Mode]**: The service MUST use Gemini's structured-output feature with a fixed JSON schema to prevent response parsing fragility.
- **I3 [Verdict Gating]**: `has_panels` MUST only be `True` if the model's reported `confidence` $\ge$ `THRESHOLD`.
- **I4 [Mandatory Area]**: If the model returns `has_panels=True` but the `panel_area_m2` is null, zero, or missing, the final verdict MUST be flipped to `False`.
- **I5 [Resilient Retries]**: Transient errors (429, 503, connection timeouts) MUST be retried up to `MAX_ATTEMPTS` times using exponential backoff with jitter.
- **I6 [Thread-Safe Client Pooling]**: The `genai.Client` MUST be cached and shared across threads for a given API key to optimize connection reuse.
- **I7 [Environment Overrides]**: The service MUST prioritize `GEMINI_MODEL` and `GEMINI_TIMEOUT_S` environment variables over hardcoded defaults.
- **I8 [Non-blocking Execution]**: The synchronous SDK calls MUST be offloaded to a worker thread using `asyncio.to_thread`.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `GEMINI_API_KEY` is unset | `is_available()` returns `False`; `detect` raises `RuntimeError`. | I1 |
| Rate limited (429) | Retries with backoff; succeeds or raises `RuntimeError` after 3 attempts. | I5 |
| Safety filter blocks image | Model returns empty text; `detect` raises `RuntimeError` with `finish_reason`. | I2 |
| Model returns `confidence: 0.49` | `has_panels: False`, `panel_area_m2: <value>`. | I3 |
| Model returns `panel_area_m2: 0` | `has_panels: False`. | I4 |
| Connection reset during call | Retries according to transient error logic. | I5 |
| Malformed response (unstructured) | `_extract_json` attempts regex recovery before failing with `RuntimeError`. | I2 |
| `lat` / `zoom` passed in | Currently ignored by Gemini (used for `inference_ms` timing and metadata). | I8 |
