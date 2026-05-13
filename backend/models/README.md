# Detection model weights

This directory holds the YOLOv8-seg ONNX weights consumed by
`backend/services/detection_ml.py`.

## Required file

```
backend/models/yolov8n-solar-seg.onnx
```

Approximate size: 13–18 MB. **Not** committed to the repo. The runtime is
hybrid:

- **If this file exists** + `onnxruntime` is installed, the dispatcher
  routes detection to the deterministic ML path.
- **If this file is absent**, the dispatcher falls back to Gemini Vision
  (requires `GEMINI_API_KEY`). The system stays functional but loses
  determinism — labels generated this way are useful for bootstrapping
  but should be human-confirmed before being used as training ground
  truth.

Override via env: `DETECTION_BACKEND=ml|gemini|auto` (default `auto`).

## How to obtain

Pre-trained YOLOv8-seg weights for solar panels (single-class, aerial /
satellite imagery, MIT/AGPL license) — community models that are known to
work with this codebase's `_postprocess`:

1. **`keremberke/yolov8n-solar-panel`** (HuggingFace, Ultralytics `.pt`)
2. **`Roboflow Universe → "solar-panels-segmentation"`** datasets that ship
   with pre-trained weights

### Convert PyTorch (`.pt`) → ONNX

```bash
pip install ultralytics
python - <<'PY'
from ultralytics import YOLO
YOLO("yolov8n-solar-panel.pt").export(format="onnx", imgsz=640, opset=12)
PY
mv yolov8n-solar-panel.onnx backend/models/yolov8n-solar-seg.onnx
```

### Output shape contract

`_postprocess` in `services/detection_ml.py` assumes:

- `output0`: `[1, 4 + 1 + 32, num_anchors]` — boxes + class score + mask coeffs
- `output1`: `[1, 32, mask_h, mask_w]`       — mask prototypes

If your model has different output shapes, adjust `_postprocess`.

## Building a real training set first

Before downloading random community weights, you can build a clean
dataset *as you use the app* and fine-tune from there:

1. Use the app today (Gemini fallback is active — set `GEMINI_API_KEY`).
2. Every scan auto-logs to `backend/data/detection/inferences.jsonl`.
3. After each scan, click **"Korrekt"** / **"Fel"** in the UI; that calls
   `POST /api/scan/detect/feedback` and appends to `labels.jsonl`.
4. Once `labels.jsonl` has ≥ ~500 confirmed entries, export to YOLO format
   and fine-tune off-cluster. See
   [`backend/specs/detection_model.md`](../specs/detection_model.md)
   §"Labeling pipeline".

## License

Record the model's license in `LICENSE.md` next to this file. Repo code
ships under the project license; the weights carry their upstream license.
