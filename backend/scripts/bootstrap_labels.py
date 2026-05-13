#!/usr/bin/env python3
"""Generate a labelled training set by distilling a teacher backend.

The chicken-and-egg problem: training the fast `embed` head needs
labelled images, but we have no labelled images. This script breaks
the loop by using a slow but capable teacher (Moondream by default)
to label a list of addresses, then writes the standard
``labels.jsonl`` + on-disk images that ``auto_train_detection.py``
already knows how to consume.

Once the embed head is trained from teacher-generated labels, the
embed backend serves real traffic at 25–220 ms per image with the
teacher's accuracy. The teacher is then only needed for periodic
retrains (or for low-confidence escalations in production).

Usage
-----
    # Default: moondream teacher, free path, addresses from a file
    python3 backend/scripts/bootstrap_labels.py \\
        --addresses backend/scripts/fixtures/eval_set_sample.txt

    # Pre-supplied lat,lng (skips geocoding)
    python3 backend/scripts/bootstrap_labels.py --coords coords.txt

    # Use a different teacher (e.g. ml if you have YOLOv8 weights)
    python3 backend/scripts/bootstrap_labels.py --teacher ml --addresses ...

    # Confidence floor — discard borderline calls instead of mis-labelling
    python3 backend/scripts/bootstrap_labels.py --min-confidence 0.7 ...

Costs
-----
- Moondream teacher: $0 (local Ollama).
- ML / embed teacher: $0.
- Gemini teacher: PAID (per call). Default refuses unless --allow-paid.
- Geocoding (Nominatim): free.
- Satellite (ArcGIS): free.

Idempotent: skips addresses that already have a labels.jsonl entry.
Re-runs are safe — incremental, won't double-label.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

DATA_DIR = REPO_ROOT / "backend" / "data"
IMAGES_DIR = DATA_DIR / "images" / "bootstrap"
LABELS_JSONL = DATA_DIR / "detection" / "labels.jsonl"
PAID_TEACHERS = {"gemini"}


def _load_addresses(args: argparse.Namespace) -> list[tuple[str, float | None, float | None]]:
    out: list[tuple[str, float | None, float | None]] = []
    if args.addresses:
        for line in Path(args.addresses).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if line and not line.startswith("#"):
                out.append((line, None, None))
    if args.coords:
        for line in Path(args.coords).read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                lat_s, lng_s = line.split(",", 1)
                lat, lng = float(lat_s), float(lng_s)
            except ValueError:
                print(f"  skip malformed coord line: {line!r}", file=sys.stderr)
                continue
            out.append((f"{lat:.5f},{lng:.5f}", lat, lng))
    return out


def _already_labelled() -> set[str]:
    """Return set of image_paths that already appear in labels.jsonl."""
    seen: set[str] = set()
    if not LABELS_JSONL.exists():
        return seen
    with LABELS_JSONL.open(encoding="utf-8") as f:
        for line in f:
            try:
                row = json.loads(line)
            except json.JSONDecodeError:
                continue
            ip = row.get("image_path")
            if ip:
                seen.add(ip)
    return seen


def _image_filename(label: str, lat: float, lng: float) -> str:
    """Stable per-coord filename so re-runs hit the same file."""
    h = hashlib.sha1(f"{lat:.6f},{lng:.6f}".encode()).hexdigest()[:12]
    safe = "".join(c if c.isalnum() else "_" for c in label)[:40].strip("_")
    return f"{safe or 'addr'}__{h}.jpg"


def _resolve_teacher(name: str) -> tuple[str, callable]:
    from services import detection_embed, detection_gemini, detection_ml, detection_moondream

    teachers = {
        "moondream": (detection_moondream.is_available, detection_moondream.detect),
        "ml": (detection_ml.is_available, detection_ml.detect),
        "embed": (detection_embed.is_available, detection_embed.detect),
        "gemini": (detection_gemini.is_available, detection_gemini.detect),
    }
    if name not in teachers:
        raise SystemExit(f"unknown --teacher {name!r}; pick one of {sorted(teachers)}")
    avail, detect = teachers[name]
    if not avail():
        raise SystemExit(
            f"teacher {name!r} not available — install/configure it first.\n"
            f"  moondream: `make ml-moondream` + `ollama serve`\n"
            f"  ml:        drop YOLOv8-seg ONNX at backend/models/yolov8n-solar-seg.onnx\n"
            f"  embed:     `make ml-bootstrap` + a prior `make ml-train`\n"
            f"  gemini:    set GEMINI_API_KEY (paid)"
        )
    return name, detect


async def _process_one(
    label: str,
    lat: float | None,
    lng: float | None,
    teacher_detect,
    teacher_name: str,
    *,
    min_confidence: float,
    write_borderline: bool,
) -> dict | None:
    """Geocode (if needed) → fetch satellite → label via teacher → return row.

    Returns None if the call failed or was below the confidence floor.
    """
    from services import geocode as _geo
    from services import satellite as _sat

    if lat is None or lng is None:
        try:
            lat, lng = await _geo.geocode(label)
        except Exception as e:  # noqa: BLE001
            print(f"  geocode failed for {label!r}: {type(e).__name__}: {e}")
            return None

    fname = _image_filename(label, lat, lng)
    rel_path = f"images/bootstrap/{fname}"
    abs_path = DATA_DIR / rel_path

    if not abs_path.exists():
        try:
            image_bytes = await _sat.fetch_satellite_image(lat, lng)
        except Exception as e:  # noqa: BLE001
            print(f"  satellite fetch failed for {label!r}: {type(e).__name__}: {e}")
            return None
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(image_bytes)
    else:
        image_bytes = abs_path.read_bytes()

    try:
        result = await teacher_detect(image_bytes, lat=lat, zoom=20)
    except Exception as e:  # noqa: BLE001
        print(f"  teacher {teacher_name!r} failed for {label!r}: {type(e).__name__}: {e}")
        return None

    confidence = float(result.get("confidence", 0.0))
    has_panels = bool(result.get("has_panels", False))

    if confidence < min_confidence and not write_borderline:
        print(
            f"  {label}: skip (confidence {confidence:.2f} below floor {min_confidence:.2f}) — "
            "image saved for human review"
        )
        return None

    return {
        "ts": time.time(),
        "image_path": rel_path,
        "address": label,
        "lat": lat,
        "lng": lng,
        "has_panels_truth": has_panels,
        "confidence": confidence,
        "source": f"teacher:{teacher_name}",
        "note": f"distilled by {teacher_name} at conf={confidence:.2f}",
    }


async def _run(args: argparse.Namespace) -> int:
    addresses = _load_addresses(args)
    if not addresses:
        print("No addresses provided. Use --addresses or --coords.", file=sys.stderr)
        return 2

    if args.teacher in PAID_TEACHERS and not args.allow_paid:
        print(
            f"Refusing to use paid teacher {args.teacher!r} without --allow-paid. "
            "Use --teacher moondream for the free path.",
            file=sys.stderr,
        )
        return 4

    teacher_name, teacher_detect = _resolve_teacher(args.teacher)
    print(f"==> Teacher: {teacher_name}")

    seen = _already_labelled()
    print(f"==> labels.jsonl already has {len(seen)} entries")

    LABELS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped_existing = 0
    failed = 0
    pos = neg = 0

    with LABELS_JSONL.open("a", encoding="utf-8") as f:
        for i, (label, lat, lng) in enumerate(addresses, 1):
            print(f"[{i}/{len(addresses)}] {label}")

            # Check by would-be image_path BEFORE we hit the teacher (cheap skip).
            if lat is not None and lng is not None:
                rel = f"images/bootstrap/{_image_filename(label, lat, lng)}"
                if rel in seen:
                    skipped_existing += 1
                    print("  already labelled — skip")
                    continue

            row = await _process_one(
                label, lat, lng, teacher_detect, teacher_name,
                min_confidence=args.min_confidence,
                write_borderline=args.write_borderline,
            )
            if row is None:
                failed += 1
                continue

            # Late de-dup: if we geocoded inside _process_one, the resolved
            # image_path may collide with a prior entry. Don't double-write.
            if row["image_path"] in seen:
                skipped_existing += 1
                print("  resolved to existing label — skip")
                continue

            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            seen.add(row["image_path"])
            written += 1
            pos += int(row["has_panels_truth"])
            neg += int(not row["has_panels_truth"])
            print(
                f"  labelled has_panels={row['has_panels_truth']} "
                f"confidence={row['confidence']:.2f} → {row['image_path']}"
            )

    print()
    print(f"==> Done. wrote={written}  skipped_existing={skipped_existing}  failed={failed}")
    print(f"   class balance: {pos} positive, {neg} negative")
    print(f"   total labels in {LABELS_JSONL.name}: {len(seen)}")
    print()
    print("Next: `make ml-train` to train the embed head on these labels.")
    return 0


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(
        description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter
    )
    src = p.add_argument_group("inputs (use --addresses or --coords)")
    src.add_argument("--addresses", type=Path, help="File: one address per line")
    src.add_argument("--coords", type=Path, help="File: one 'lat,lng' per line")
    p.add_argument(
        "--teacher", default="moondream",
        choices=("moondream", "ml", "embed", "gemini"),
        help="Backend to label with (default: moondream — free local LLM)",
    )
    p.add_argument(
        "--min-confidence", type=float, default=0.6,
        help="Discard teacher predictions below this confidence (default: 0.6)",
    )
    p.add_argument(
        "--write-borderline", action="store_true",
        help="Write labels even when teacher confidence is below the floor "
             "(useful for retrospective analysis; not recommended for training)",
    )
    p.add_argument(
        "--allow-paid", action="store_true",
        help="Required to use --teacher gemini (which is paid per call).",
    )
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_run(_parse())))
