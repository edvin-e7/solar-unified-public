#!/usr/bin/env python3
"""Auto-train the embed-backend classifier head from existing labelled data.

No GPU. No torch. No sklearn. Just numpy + onnxruntime (already installed).

Inputs (in priority order):
1. ``backend/data/detection/labels.jsonl`` — user-supplied ground truth
   (most trustworthy)
2. ``backend/data/prospects.db`` rows where ``has_panels IS NOT NULL``
   AND a matching image exists under ``backend/data/images/`` (Gemini-
   generated labels — knowledge distillation)

Output:
- ``backend/models/head.npz`` — trained logistic-regression head
  (fields: ``weights`` shape (D,), ``bias`` scalar, ``version`` str)

Run:
    python3 backend/scripts/auto_train_detection.py
    python3 backend/scripts/auto_train_detection.py --epochs 200 --lr 0.05
    python3 backend/scripts/auto_train_detection.py --val-split 0.2

Reports accuracy, precision, recall on a held-out validation slice.
"""

from __future__ import annotations

import argparse
import json
import sqlite3
import sys
import time
from pathlib import Path
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    import numpy as np  # type-only import — runtime imports are lazy below

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

DATA_DIR = REPO_ROOT / "backend" / "data"
IMAGES_DIR = DATA_DIR / "images"
LABELS_JSONL = DATA_DIR / "detection" / "labels.jsonl"
INFERENCES_JSONL = DATA_DIR / "detection" / "inferences.jsonl"
PROSPECTS_DB = DATA_DIR / "prospects.db"
HEAD_OUT = REPO_ROOT / "backend" / "models" / "head.npz"


def _load_user_labels() -> dict[str, bool]:
    """image_path → has_panels_truth from labels.jsonl. Latest wins on conflict."""
    out: dict[str, bool] = {}
    if not LABELS_JSONL.exists():
        return out
    with LABELS_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ip = row.get("image_path")
            if not ip:
                continue
            out[ip] = bool(row.get("has_panels_truth"))
    return out


def _load_inference_addresses() -> dict[str, str]:
    """image_path → address from inferences.jsonl, for joining to prospects DB."""
    out: dict[str, str] = {}
    if not INFERENCES_JSONL.exists():
        return out
    with INFERENCES_JSONL.open(encoding="utf-8") as f:
        for line in f:
            line = line.strip()
            if not line:
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ip, addr = row.get("image_path"), row.get("address")
            if ip and addr:
                out[ip] = addr
    return out


def _load_prospect_labels() -> dict[str, bool]:
    """address → has_panels from prospects DB. Used as Gemini-distilled labels."""
    out: dict[str, bool] = {}
    if not PROSPECTS_DB.exists():
        return out
    conn = sqlite3.connect(PROSPECTS_DB)
    try:
        for addr, hp in conn.execute(
            "SELECT address, has_panels FROM prospects WHERE has_panels IS NOT NULL"
        ):
            out[addr] = bool(hp)
    finally:
        conn.close()
    return out


def collect_labelled_pairs() -> list[tuple[Path, bool, str]]:
    """Build [(image_path, has_panels, source), ...] from all sources."""
    user_labels = _load_user_labels()
    inference_addr = _load_inference_addresses()
    prospect_labels = _load_prospect_labels()

    pairs: list[tuple[Path, bool, str]] = []
    seen_images: set[Path] = set()

    for rel_path, truth in user_labels.items():
        full = (DATA_DIR / rel_path).resolve()
        if not full.exists():
            continue
        if full in seen_images:
            continue
        pairs.append((full, truth, "user"))
        seen_images.add(full)

    for rel_path, addr in inference_addr.items():
        full = (DATA_DIR / rel_path).resolve()
        if not full.exists() or full in seen_images:
            continue
        if addr in prospect_labels:
            pairs.append((full, prospect_labels[addr], "prospects-db"))
            seen_images.add(full)

    return pairs


def embed_all(image_paths: list[Path]) -> np.ndarray:  # type: ignore[name-defined]
    """Run encoder on every image, return (N, D) embedding matrix."""
    import numpy as np
    from services import detection_embed

    rows = []
    t0 = time.perf_counter()
    for i, p in enumerate(image_paths, 1):
        with p.open("rb") as f:
            vec = detection_embed.embed(f.read())
        rows.append(vec)
        if i % 25 == 0:
            print(f"  embedded {i}/{len(image_paths)}", flush=True)
    print(f"  done — {len(image_paths)} embeddings in {time.perf_counter() - t0:.1f}s")
    return np.stack(rows, axis=0).astype(np.float32)


def train_logistic(
    X: np.ndarray,  # type: ignore[name-defined]
    y: np.ndarray,  # type: ignore[name-defined]
    *,
    epochs: int,
    lr: float,
    l2: float,
) -> tuple[np.ndarray, float]:  # type: ignore[name-defined]
    """Pure-numpy mini-batch gradient descent on a logistic-regression head.

    Returns (weights shape (D,), bias scalar).
    """
    import numpy as np

    n, d = X.shape
    rng = np.random.default_rng(42)
    w = rng.standard_normal(d).astype(np.float32) * 0.01
    b = 0.0

    for epoch in range(1, epochs + 1):
        # Shuffle each epoch
        perm = rng.permutation(n)
        Xs, ys = X[perm], y[perm]
        # Forward
        z = Xs @ w + b
        # Numerically-stable sigmoid
        p = np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))
        # Loss = binary cross-entropy + L2
        eps = 1e-7
        loss = -float(np.mean(ys * np.log(p + eps) + (1 - ys) * np.log(1 - p + eps)))
        loss += l2 * float(np.sum(w * w))
        # Backward
        dz = (p - ys) / n
        dw = Xs.T @ dz + 2 * l2 * w
        db = float(np.sum(dz))
        w -= lr * dw
        b -= lr * db
        if epoch == 1 or epoch % 50 == 0 or epoch == epochs:
            acc = float(np.mean((p >= 0.5) == (ys >= 0.5)))
            print(f"  epoch {epoch:>4d}  loss={loss:.4f}  train-acc={acc:.3f}")

    return w, b


def evaluate(
    X: np.ndarray,  # type: ignore[name-defined]
    y: np.ndarray,  # type: ignore[name-defined]
    w: np.ndarray,  # type: ignore[name-defined]
    b: float,
) -> dict:
    import numpy as np

    z = X @ w + b
    p = np.where(z >= 0, 1.0 / (1.0 + np.exp(-z)), np.exp(z) / (1.0 + np.exp(z)))
    pred = (p >= 0.5).astype(np.int32)
    truth = y.astype(np.int32)
    tp = int(np.sum((pred == 1) & (truth == 1)))
    fp = int(np.sum((pred == 1) & (truth == 0)))
    fn = int(np.sum((pred == 0) & (truth == 1)))
    tn = int(np.sum((pred == 0) & (truth == 0)))
    n = len(y)
    acc = (tp + tn) / n if n else 0.0
    prec = tp / (tp + fp) if (tp + fp) else 0.0
    rec = tp / (tp + fn) if (tp + fn) else 0.0
    f1 = 2 * prec * rec / (prec + rec) if (prec + rec) else 0.0
    return {"n": n, "acc": acc, "precision": prec, "recall": rec, "f1": f1,
            "tp": tp, "fp": fp, "fn": fn, "tn": tn}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--epochs", type=int, default=200)
    ap.add_argument("--lr", type=float, default=0.1)
    ap.add_argument("--l2", type=float, default=1e-4)
    ap.add_argument("--val-split", type=float, default=0.2)
    ap.add_argument("--min-samples", type=int, default=10,
                    help="Minimum labelled samples required to train (refuses below).")
    args = ap.parse_args()

    print("==> Collecting labelled pairs...")
    pairs = collect_labelled_pairs()
    print(f"   found {len(pairs)} labelled images")
    if len(pairs) < args.min_samples:
        print(f"   need ≥ {args.min_samples} to train. Aborting.")
        print("   Hint: scan more addresses, or set --min-samples lower for a smoke test.")
        return 1

    pos = sum(1 for _, t, _ in pairs if t)
    neg = len(pairs) - pos
    print(f"   class balance: {pos} positive, {neg} negative")
    if pos == 0 or neg == 0:
        print("   training requires both classes. Aborting.")
        return 1

    # Encoder precheck — fail fast with helpful message instead of cryptic
    # ORT error mid-script after we've already done DB + image loading work.
    from services import detection_embed

    if not detection_embed.ENCODER_PATH.exists():
        print(f"==> Encoder ONNX missing at {detection_embed.ENCODER_PATH}")
        print("   Run: make download-encoder")
        return 1

    print("==> Embedding images...")
    paths = [p for p, _, _ in pairs]
    truths = [1 if t else 0 for _, t, _ in pairs]

    import numpy as np

    X = embed_all(paths)
    y = np.asarray(truths, dtype=np.float32)

    # Stratified train/val split
    rng = np.random.default_rng(7)
    idx = np.arange(len(y))
    rng.shuffle(idx)
    n_val = max(1, round(args.val_split * len(y)))
    val_idx, tr_idx = idx[:n_val], idx[n_val:]
    print(f"==> Split: {len(tr_idx)} train, {len(val_idx)} val")

    print("==> Training logistic head...")
    w, b = train_logistic(X[tr_idx], y[tr_idx], epochs=args.epochs, lr=args.lr, l2=args.l2)

    print("==> Evaluating...")
    train_metrics = evaluate(X[tr_idx], y[tr_idx], w, b)
    val_metrics = evaluate(X[val_idx], y[val_idx], w, b)
    print(f"   train: {train_metrics}")
    print(f"   val:   {val_metrics}")

    print(f"==> Saving head → {HEAD_OUT}")
    HEAD_OUT.parent.mkdir(parents=True, exist_ok=True)
    np.savez(
        HEAD_OUT,
        weights=w.astype(np.float32),
        bias=np.array(b, dtype=np.float32),
        version=np.array(time.strftime("%Y%m%d-%H%M%S")),
    )

    # Reset embed-backend cache so a hot-reloaded backend picks up the new head
    try:
        from services import detection_embed
        detection_embed.reset_session_for_tests()
    except Exception:  # noqa: BLE001 — best-effort cache reset
        pass  # invariant-ok: PY-SILENT-EXC — best-effort embed-cache reset

    print("==> Done. Embed backend will auto-pick up the new head on next request.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
