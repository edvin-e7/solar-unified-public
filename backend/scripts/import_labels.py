#!/usr/bin/env python3
"""Import a CSV of pre-labelled images into labels.jsonl.

Complements ``bootstrap_labels.py`` (which generates labels via a teacher
backend). Use this when you already have ground-truth labels — e.g.
- A public dataset you downloaded and unpacked
- Screenshots + manual review
- Exported from another labelling tool
- Hand-curated set from your sales territory

CSV format (header required):
    path,has_panels[,note]
    /home/me/data/img1.jpg,true,suburb-clear-day
    /home/me/data/img2.png,false,
    /home/me/data/sub/img3.jpg,True

- ``path`` — absolute or relative-to-cwd path to an image file on disk
- ``has_panels`` — true / false / 1 / 0 / yes / no (case-insensitive)
- ``note`` — optional free text (truncated to 200 chars)

The script copies each image into ``backend/data/images/imported/`` with
a stable sha1-derived filename so re-imports are idempotent. Existing
labels.jsonl rows for the same image_path are NOT duplicated.

Usage
-----
    python3 backend/scripts/import_labels.py --csv labels.csv
    python3 backend/scripts/import_labels.py --csv labels.csv --dry-run
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import shutil
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
DATA_DIR = REPO_ROOT / "backend" / "data"
IMAGES_DIR = DATA_DIR / "images" / "imported"
LABELS_JSONL = DATA_DIR / "detection" / "labels.jsonl"

TRUE_VALUES = {"true", "1", "yes", "y", "t"}
FALSE_VALUES = {"false", "0", "no", "n", "f"}


def _parse_bool(raw: str, *, row_num: int) -> bool:
    s = raw.strip().lower()
    if s in TRUE_VALUES:
        return True
    if s in FALSE_VALUES:
        return False
    raise ValueError(f"row {row_num}: cannot parse has_panels={raw!r}; use true/false")


def _stable_filename(src: Path) -> str:
    """Hash file contents → stable filename. Re-imports of identical bytes
    collapse to the same destination, so duplicates are de-duped naturally."""
    h = hashlib.sha1()
    with src.open("rb") as f:
        for chunk in iter(lambda: f.read(65536), b""):
            h.update(chunk)
    return f"{h.hexdigest()[:16]}{src.suffix.lower() or '.jpg'}"


def _already_labelled() -> set[str]:
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


def _read_rows(csv_path: Path) -> list[tuple[Path, bool, str]]:
    out: list[tuple[Path, bool, str]] = []
    with csv_path.open(encoding="utf-8", newline="") as f:
        reader = csv.DictReader(f)
        if not reader.fieldnames or "path" not in reader.fieldnames \
                or "has_panels" not in reader.fieldnames:
            raise SystemExit(
                f"CSV missing required columns. Got {reader.fieldnames!r}, "
                "need at least: path,has_panels"
            )
        for i, raw in enumerate(reader, start=2):  # start=2 to account for header
            path_str = (raw.get("path") or "").strip()
            if not path_str:
                continue
            try:
                has_panels = _parse_bool(raw.get("has_panels", ""), row_num=i)
            except ValueError as e:
                print(f"  skip: {e}", file=sys.stderr)
                continue
            note = (raw.get("note") or "").strip()[:200]
            out.append((Path(path_str).expanduser(), has_panels, note))
    return out


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", type=Path, required=True, help="CSV with columns: path,has_panels[,note]")
    ap.add_argument("--dry-run", action="store_true", help="Show what would happen, write nothing")
    args = ap.parse_args()

    if not args.csv.exists():
        print(f"CSV not found: {args.csv}", file=sys.stderr)
        return 2

    rows = _read_rows(args.csv)
    if not rows:
        print("No rows to import.", file=sys.stderr)
        return 1

    print(f"==> Loaded {len(rows)} rows from {args.csv}")

    seen = _already_labelled()
    print(f"==> labels.jsonl already has {len(seen)} entries")

    if not args.dry_run:
        IMAGES_DIR.mkdir(parents=True, exist_ok=True)
        LABELS_JSONL.parent.mkdir(parents=True, exist_ok=True)

    written = 0
    skipped_existing = 0
    missing_files = 0
    pos = neg = 0
    label_rows: list[dict] = []

    for src, has_panels, note in rows:
        if not src.exists():
            missing_files += 1
            print(f"  missing file: {src}", file=sys.stderr)
            continue

        fname = _stable_filename(src)
        rel_path = f"images/imported/{fname}"
        dest = DATA_DIR / rel_path

        if rel_path in seen:
            skipped_existing += 1
            continue

        if not args.dry_run and not dest.exists():
            shutil.copy2(src, dest)

        label_rows.append({
            "ts": time.time(),
            "image_path": rel_path,
            "has_panels_truth": has_panels,
            "source": "imported-csv",
            "note": note or f"from {args.csv.name}",
        })
        seen.add(rel_path)
        pos += int(has_panels)
        neg += int(not has_panels)
        written += 1

    if not args.dry_run and label_rows:
        with LABELS_JSONL.open("a", encoding="utf-8") as f:
            for r in label_rows:
                f.write(json.dumps(r, ensure_ascii=False) + "\n")

    verb = "would write" if args.dry_run else "wrote"
    print(f"==> Done. {verb}={written}  skipped_existing={skipped_existing}  missing_files={missing_files}")
    print(f"   class balance: {pos} positive, {neg} negative")
    if not args.dry_run:
        print(f"   total labels in {LABELS_JSONL.name}: {len(seen)}")
        print()
        print("Next: `make ml-train` to train the embed head on these labels.")
    return 0


if __name__ == "__main__":
    sys.exit(main())
