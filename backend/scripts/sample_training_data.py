#!/usr/bin/env python3
"""Build a labelled training set straight from OSM tags + ArcGIS imagery.

Replaces the Moondream-as-teacher path for bulk bootstrap. Rationale:
- OSM tags are human-curated ground truth for the binary
  "rooftop has panels?" question.
- Moondream-on-CPU is slow (~55 s/image) and poorly calibrated on Swedish
  satellite tiles — the 36-address fixture distilled into 0/9 positives,
  which is a class-balance dead end for training.
- ArcGIS imagery is free and rate-limit friendly.

Pipeline per coord:
  1. Fetch satellite tile mosaic (services.satellite.fetch_satellite_image)
  2. Save to backend/data/images/bootstrap/<sha>.jpg (cached, idempotent)
  3. Append a row to backend/data/detection/labels.jsonl with
     ``has_panels_truth`` taken from the OSM tag, ``source="osm"``.

Outputs (idempotent — re-runs add only new coords):
  - Imagery in backend/data/images/bootstrap/
  - Labels in backend/data/detection/labels.jsonl

Usage:
    python3 backend/scripts/sample_training_data.py \\
        --pos-per-city 12 --neg-per-city 12

After running, ``make ml-train`` consumes the labels.
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import random
import sys
import time
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import httpx  # noqa: E402
from services import osm_solar  # noqa: E402
from services import satellite as sat

DATA_DIR = REPO_ROOT / "backend" / "data"
IMAGES_DIR = DATA_DIR / "images" / "bootstrap"
LABELS_JSONL = DATA_DIR / "detection" / "labels.jsonl"
OVERPASS_URL = osm_solar.OVERPASS_URL

# (name, lat, lng, radius_m). Mix of metro centres + suburban-detached belts.
SEEDS: list[tuple[str, float, float, int]] = [
    ("Stockholm",   59.3293, 18.0686, 12_000),
    ("Sollentuna",  59.4288, 17.9505,  6_000),
    ("Göteborg",    57.7089, 11.9746, 12_000),
    ("Malmö",       55.6049, 13.0038, 10_000),
    ("Uppsala",     59.8586, 17.6389,  8_000),
    ("Västerås",    59.6099, 16.5448,  8_000),
    ("Örebro",      59.2753, 15.2134,  8_000),
    ("Linköping",   58.4108, 15.6214,  8_000),
    ("Helsingborg", 56.0465, 12.6945,  8_000),
    ("Norrköping",  58.5877, 16.1924,  8_000),
]


def _negative_query(south: float, west: float, north: float, east: float) -> str:
    bbox = f"({south},{west},{north},{east})"
    return (
        f"[out:json][timeout:90];\n"
        f"(\n"
        f'  way["building"~"^(house|detached|residential|apartments|terrace|semidetached_house)$"]'
        f'[!"generator:source"][!"roof:solar"][!"roof:material"]{bbox};\n'
        f");\n"
        f"out center;"
    )


async def _fetch_negatives(
    lat: float, lng: float, radius_m: int, *, limit: int = 400
) -> list[tuple[float, float]]:
    s, w, n, e = osm_solar._radius_to_bbox(lat, lng, radius_m)
    query = _negative_query(s, w, n, e)
    async with httpx.AsyncClient(timeout=120.0) as client:
        r = await client.post(
            OVERPASS_URL,
            data={"data": query},
            headers={"User-Agent": "solar-unified/0.1 (edvin.pierre03@gmail.com)"},
        )
    if r.status_code != 200:
        raise RuntimeError(f"Overpass HTTP {r.status_code}: {r.text[:200]}")
    out: list[tuple[float, float]] = []
    for el in r.json().get("elements", [])[:limit]:
        c = el.get("center") or {}
        lat_, lng_ = c.get("lat"), c.get("lon")
        if lat_ is None or lng_ is None:
            continue
        out.append((float(lat_), float(lng_)))
    return out


def _image_filename(label: str, lat: float, lng: float) -> str:
    """Same shape as bootstrap_labels.py — sha1 of coords."""
    h = hashlib.sha1(f"{lat:.6f},{lng:.6f}".encode()).hexdigest()[:12]
    safe = "".join(c if c.isalnum() else "_" for c in label)[:40].strip("_")
    return f"{safe or 'addr'}__{h}.jpg"


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


async def _process_one(
    lat: float, lng: float, *, label: str, has_panels: bool, seen: set[str]
) -> dict | None:
    fname = _image_filename(label, lat, lng)
    rel_path = f"images/bootstrap/{fname}"
    if rel_path in seen:
        return None  # idempotent skip

    abs_path = DATA_DIR / rel_path
    if not abs_path.exists():
        try:
            image_bytes = await sat.fetch_satellite_image(lat, lng, zoom=20)
        except Exception as e:  # noqa: BLE001 — satellite occasionally flakes
            print(f"  satellite fetch failed at {lat:.4f},{lng:.4f}: {type(e).__name__}: {e}", flush=True)
            return None
        abs_path.parent.mkdir(parents=True, exist_ok=True)
        abs_path.write_bytes(image_bytes)

    return {
        "ts": time.time(),
        "image_path": rel_path,
        "address": label,
        "lat": lat,
        "lng": lng,
        "has_panels_truth": has_panels,
        "confidence": 1.0,  # OSM is human-curated; we trust the tag.
        "source": "osm",
        "note": f"osm-tagged {'positive' if has_panels else 'negative'}",
    }


async def _gather(
    *, pos_per_city: int, neg_per_city: int, rng: random.Random
) -> tuple[list[tuple[str, float, float, bool]], dict]:
    """Return [(label, lat, lng, has_panels), ...] + per-city stats."""
    samples: list[tuple[str, float, float, bool]] = []
    stats: dict = {}
    for name, lat, lng, radius in SEEDS:
        print(f"==> {name} (r={radius}m)…", flush=True)
        try:
            pos_sites = await osm_solar.fetch_solar_around(lat, lng, radius, limit=200)
            pos_coords = [(s.lat, s.lng) for s in pos_sites]
        except Exception as e:  # noqa: BLE001
            print(f"   positives failed: {type(e).__name__}: {e}", flush=True)
            pos_coords = []
        try:
            neg_coords = await _fetch_negatives(lat, lng, radius)
        except Exception as e:  # noqa: BLE001
            print(f"   negatives failed: {type(e).__name__}: {e}", flush=True)
            neg_coords = []

        rng.shuffle(pos_coords)
        rng.shuffle(neg_coords)
        pos = pos_coords[:pos_per_city]
        neg = neg_coords[:neg_per_city]
        for la, lo in pos:
            samples.append((f"{name}-pos", la, lo, True))
        for la, lo in neg:
            samples.append((f"{name}-neg", la, lo, False))
        stats[name] = {"pos": len(pos), "neg": len(neg)}
        print(f"   {len(pos)} pos / {len(neg)} neg sampled", flush=True)
        # Be polite to Overpass.
        await asyncio.sleep(2.0)

    return samples, stats


async def _run(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    LABELS_JSONL.parent.mkdir(parents=True, exist_ok=True)
    IMAGES_DIR.mkdir(parents=True, exist_ok=True)

    print(f"==> Sampling {args.pos_per_city} pos + {args.neg_per_city} neg per city")
    samples, stats = await _gather(
        pos_per_city=args.pos_per_city, neg_per_city=args.neg_per_city, rng=rng
    )

    # Dedupe by 5-decimal coord (~1.1 m).
    seen_coords: set[tuple[float, float]] = set()
    deduped: list[tuple[str, float, float, bool]] = []
    for label, la, lo, hp in samples:
        key = (round(la, 5), round(lo, 5))
        if key in seen_coords:
            continue
        seen_coords.add(key)
        deduped.append((label, la, lo, hp))
    print(f"==> Total deduped samples: {len(deduped)}")

    seen_paths = _already_labelled()
    print(f"==> labels.jsonl already has {len(seen_paths)} entries")

    written = skipped = failed = 0
    with LABELS_JSONL.open("a", encoding="utf-8") as f:
        for i, (label, la, lo, hp) in enumerate(deduped, 1):
            if i % 10 == 0:
                print(f"  [{i}/{len(deduped)}]", flush=True)
            row = await _process_one(la, lo, label=label, has_panels=hp, seen=seen_paths)
            if row is None:
                if (
                    f"images/bootstrap/{_image_filename(label, la, lo)}"
                    in seen_paths
                ):
                    skipped += 1
                else:
                    failed += 1
                continue
            f.write(json.dumps(row, ensure_ascii=False) + "\n")
            f.flush()
            seen_paths.add(row["image_path"])
            written += 1

    print()
    print(f"==> Done. wrote={written}  skipped_existing={skipped}  failed={failed}")
    print(f"   per-city: {stats}")
    print(f"   total labels in {LABELS_JSONL.name}: {len(seen_paths)}")
    return 0


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--pos-per-city", type=int, default=12)
    p.add_argument("--neg-per-city", type=int, default=12)
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_run(_parse())))
