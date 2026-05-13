# Detection Embed Service Spec

## Public API

### Functions

- **`async detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict`**
  Runs feature extraction and classification using a distilled model.
  - `image_bytes`: Raw image data.
  - `lat`: Latitude for area estimation.
  - `zoom`: Zoom level.
  - **Returns**: A dictionary compatible with `DetectionResult`.

- **`embed(image_bytes: bytes) -> np.ndarray`**
  Extracts a 1024-d feature vector from the image using the frozen encoder.
  - **Returns**: L2-normalized 1-D float32 vector.
  - **Notes**: Used by training scripts to generate dataset features.

- **`is_available() -> bool`**
  Checks if both the ONNX encoder and the `.npz` trained head are present.

- **`reset_session_for_tests() -> None`**
  Clears the cached ONNX session and the loaded head.

### Constants

- `ENCODER_PATH`: Path to the MobileNetV3-Small ONNX encoder.
- `HEAD_PATH`: Path to the `head.npz` (logistic regression weights/bias).
- `THRESHOLD`: 0.5 (confidence threshold for detection).
- `INPUT_SIZE`: 224 (required image size for MobileNetV3).

---

## Invariants

- **I1 [Component Availability]**: The service MUST verify the existence of both `ENCODER_PATH` and `HEAD_PATH` before attempting inference.
- **I2 [ImageNet Preprocessing]**: Input images MUST be resized to 224x224 and normalized using standard ImageNet statistics (`mean=[0.485, 0.456, 0.406]`, `std=[0.229, 0.224, 0.225]`).
- **I3 [L2 Normalization]**: Feature vectors from the encoder MUST be L2-normalized before being passed to the classification head.
- **I4 [Deterministic Consistency]**: The frozen encoder MUST be deterministic; identical inputs MUST produce identical embeddings across different calls.
- **I5 [Dimension Alignment]**: The dimensionality of the extracted embedding MUST exactly match the input dimension of the trained head weights.
- **I6 [Heuristic Area Scaling]**: In the absence of a segmentation mask, `panel_area_m2` MUST be estimated as `confidence * 0.3 * total_tile_area` at the given latitude/zoom.
- **I7 [Thread-Safe Lazy Loading]**: Initialization of both the ONNX session and the numpy head MUST be thread-safe and performed lazily on the first call.
- **I8 [Non-blocking IO]**: Heavy compute (encoder inference and head projection) MUST be run in a separate thread to avoid blocking the async event loop.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `image_bytes` is empty | Raises `RuntimeError("empty image bytes")`. | I2 |
| Encoder weights missing | `is_available()` returns `False`; `detect` raises `RuntimeError`. | I1 |
| Trained head missing | `is_available()` returns `False`; `detect` raises `RuntimeError`. | I1 |
| Dimension mismatch | Raises `RuntimeError` describing the mismatch. | I5 |
| Area heuristic edge case | If `panel_area_m2` calculates to $\le 0$, `has_panels` MUST be flipped to `False`. | I6 |
| Lat/Zoom at extremes | Heuristic remains stable, scaling tile area via Mercator correction. | I6 |
| `numpy` or `ort` missing | `is_available()` returns `False`; `detect` raises `RuntimeError`. | I1 |
