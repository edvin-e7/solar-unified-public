#!/usr/bin/env python3
"""Download the frozen image encoder for the embed detection backend.

Saves to ``backend/models/encoder/mobilenet_v3_small.onnx`` (the path
``services.detection_embed`` expects).

Defensive: tries multiple known-good source URLs; on failure prints
manual instructions instead of writing a corrupt file.

Usage:
    python3 backend/scripts/download_encoder.py
    python3 backend/scripts/download_encoder.py --url https://example/foo.onnx
    ENCODER_URL=https://example/foo.onnx python3 backend/scripts/download_encoder.py
"""

from __future__ import annotations

import argparse
import os
import sys
import urllib.request
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DEST_DIR = REPO_ROOT / "backend" / "models" / "encoder"
DEST = DEST_DIR / "mobilenet_v3_small.onnx"

# Ordered list of candidate sources. First success wins.
# Override via --url or ENCODER_URL env. These are intentionally
# external so the user runs this once on their own machine.
CANDIDATES: list[str] = [
    # ONNX Model Zoo (raw via GitHub LFS — usually works on real workstations)
    "https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-12.onnx",
    # Squeezenet 1.1 — even smaller (~5 MB), valid as a frozen encoder
    "https://github.com/onnx/models/raw/main/validated/vision/classification/squeezenet/model/squeezenet1.1-7.onnx",
    # Mobilenet v2 opset 7 (older but widely mirrored)
    "https://github.com/onnx/models/raw/main/validated/vision/classification/mobilenet/model/mobilenetv2-7.onnx",
]


def _download(url: str, dest: Path) -> int:
    """Stream-download `url` to `dest`. Returns bytes written. Raises on failure."""
    dest.parent.mkdir(parents=True, exist_ok=True)
    req = urllib.request.Request(url, headers={"User-Agent": "solar-unified/1.0"})
    bytes_written = 0
    with urllib.request.urlopen(req, timeout=60) as resp:
        if resp.status != 200:
            raise RuntimeError(f"HTTP {resp.status}")
        with dest.open("wb") as f:
            while True:
                chunk = resp.read(64 * 1024)
                if not chunk:
                    break
                f.write(chunk)
                bytes_written += len(chunk)
    return bytes_written


def _validate(path: Path) -> tuple[int, str]:
    """Open the file with onnxruntime to confirm it's a real model."""
    import onnxruntime as ort

    sess = ort.InferenceSession(str(path), providers=["CPUExecutionProvider"])
    inp = sess.get_inputs()[0]
    out = sess.get_outputs()[0]
    return path.stat().st_size, f"input={inp.shape} output={out.shape}"


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--url", help="Explicit encoder URL (overrides candidates)")
    p.add_argument("--force", action="store_true", help="Re-download even if file exists")
    args = p.parse_args()

    if DEST.exists() and not args.force:
        size = DEST.stat().st_size
        print(f"[skip] {DEST} already exists ({size:,} bytes). Use --force to re-download.")
        return 0

    sources: list[str] = []
    if args.url:
        sources.append(args.url)
    elif env_url := os.getenv("ENCODER_URL"):
        sources.append(env_url)
    sources.extend(CANDIDATES)

    last_err: str | None = None
    for url in sources:
        print(f"[try] {url}")
        try:
            n = _download(url, DEST)
            print(f"[ok ] downloaded {n:,} bytes")
            try:
                size, shape = _validate(DEST)
                print(f"[ok ] valid ONNX: {size:,} bytes — {shape}")
                return 0
            except Exception as e:  # noqa: BLE001 — we want any validation failure
                print(f"[bad] downloaded but ONNX validation failed: {e}")
                DEST.unlink(missing_ok=True)
                last_err = str(e)
                continue
        except Exception as e:  # noqa: BLE001 — try next source
            print(f"[err] {type(e).__name__}: {e}")
            last_err = str(e)

    print()
    print("=" * 70)
    print("All sources failed. Last error:", last_err)
    print()
    print("Manual workaround:")
    print("1. On a machine with normal internet, download a small image-")
    print("   classification ONNX (MobileNetV2/V3-Small or SqueezeNet).")
    print("2. Drop it at:")
    print(f"     {DEST}")
    print("3. Re-run: make train-detection")
    print("=" * 70)
    return 1


if __name__ == "__main__":
    sys.exit(main())
