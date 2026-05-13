# Detection ML Service Spec

## Public API

### Functions

- **`async detect(image_bytes: bytes, *, lat: float, zoom: int = 20) -> dict`**
  Runs YOLOv8-segmentation inference on the provided image.
  - `image_bytes`: Raw image data.
  - `lat`: Latitude for area scaling.
  - `zoom`: Zoom level (default 20).
  - **Returns**: A dictionary compatible with `DetectionResult`.
  - **Notes**: Runs in a separate thread via `asyncio.to_thread`.

- **`is_available() -> bool`**
  Checks if the ML model weights exist and `onnxruntime` is installed.

- **`reset_session_for_tests() -> None`**
  Clears the cached ONNX session. Used for ensuring clean state in tests.

### Constants

- `MODEL_PATH`: Path to the `.onnx` weights file.
- `MODEL_INPUT_SIZE`: 640 (standard YOLOv8-seg input).
- `THRESHOLD`: 0.5 (confidence threshold for panel detection).
- `MASK_BINARIZE_THRESHOLD`: 0.5 (threshold for mask pixel activation).

---

## Invariants

- **I1 [Weights Presence]**: The service MUST verify the existence of the ONNX model file at `MODEL_PATH` before attempting to initialize a session.
- **I2 [Deterministic Inference]**: Inference MUST be deterministic and offline-safe, using the `CPUExecutionProvider`.
- **I3 [Input Preprocessing]**: Images MUST be letterboxed to `MODEL_INPUT_SIZE` (640x640) with aspect-ratio-preserving padding (neutral gray `114, 114, 114`) and normalized to `[0, 1]`.
- **I4 [Confidence Threshold]**: A detection is only valid (`has_panels=True`) if the highest class score is $\ge$ `THRESHOLD`.
- **I5 [Mask Post-processing]**: Segmentation masks MUST be sigmoided, binarized at `MASK_BINARIZE_THRESHOLD`, and scaled back to the letterboxed coordinate system.
- **I6 [Area Accuracy]**: Active mask pixels MUST be converted to square meters using `mask_pixels_to_m2`, incorporating `lat` and `zoom` to account for Mercator projection distortion.
- **I7 [Thread-Safe Singleton]**: The ONNX `InferenceSession` MUST be managed as a thread-safe singleton to minimize memory overhead and initialization latency.
- **I8 [Non-blocking Execution]**: The synchronous `sess.run` MUST NOT block the main FastAPI event loop; it MUST be dispatched to a worker thread.

---

## Adversarial Matrix

| Scenario | Expected Behavior | Invariant |
| :--- | :--- | :--- |
| `image_bytes` is empty | Raises `RuntimeError("empty image bytes")`. | I3 |
| Weights file missing | `is_available()` returns `False`; `detect` raises `RuntimeError`. | I1 |
| `onnxruntime` not installed | `is_available()` returns `False`; `detect` raises `RuntimeError`. | I1 |
| Corrupt image data | Raises `RuntimeError("could not decode image: ...")`. | I3 |
| Multiple panel clusters | The current implementation picks the single `best_idx` (largest confidence) for area calculation. | I4 |
| Confidence 0.49 | `has_panels=False`, `panel_area_m2=None`. | I4 |
| Area calculation $\le$ 0 | `has_panels=False`, `panel_area_m2=None`. | I6 |
| Simultaneous calls | `_session_lock` ensures safe init; subsequent calls share the same session. | I7 |
