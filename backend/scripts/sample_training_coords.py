#!/usr/bin/env python3
"""Sample Swedish residential coordinates for the training set.

Pulls two classes from OSM via Overpass:
  - Positives: buildings already tagged with ``generator:source=solar`` /
    ``roof:solar=*`` / ``roof:material=solar_panels`` (uses
    ``services.osm_solar.fetch_solar_around``).
  - Negatives: ``building=house|detached|residential|apartments|terrace``
    in the same bbox WITHOUT a solar tag.

Output is a coords file (``lat,lng`` per line) that
``bootstrap_labels.py --coords`` consumes — skipping the geocode round-trip.

Why this exists: scaling past the 54 hand-curated addresses without
(a) paying for a geocoder or (b) hand-collecting hundreds of addresses.
Free, deterministic, and class-balanced by construction.

Example:
    python3 backend/scripts/sample_training_coords.py \\
        --out backend/scripts/fixtures/training_coords.txt \\
        --pos-per-city 18 --neg-per-city 18

Idempotent: re-runs overwrite the output file. ``bootstrap_labels.py``
de-dupes by image_path (sha1 of coords) so re-running it on the merged
set won't double-label anything already in ``labels.jsonl``.
"""

from __future__ import annotations

import argparse
import asyncio
import random
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

import httpx  # noqa: E402
from services import osm_solar  # noqa: E402

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
    """Buildings WITHOUT any solar tag in the bbox.

    `roof:solar` and `generator:source=solar` are the project's two known
    positive-class signals. We exclude both. ``out center`` gives one (lat,lng)
    per way without listing all nodes.
    """
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
    lat: float, lng: float, radius_m: int, limit: int
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
    for el in r.json().get("elements", []):
        c = el.get("center") or {}
        lat_, lng_ = c.get("lat"), c.get("lon")
        if lat_ is None or lng_ is None:
            continue
        out.append((float(lat_), float(lng_)))
    return out


async def _gather_one(
    seed: tuple[str, float, float, int],
    *,
    pos_per_city: int,
    neg_per_city: int,
    rng: random.Random,
) -> tuple[list[tuple[float, float]], list[tuple[float, float]]]:
    name, lat, lng, radius = seed
    print(f"  {name} (r={radius}m)…", flush=True)

    try:
        pos_sites = await osm_solar.fetch_solar_around(lat, lng, radius, limit=200)
        pos_coords = [(s.lat, s.lng) for s in pos_sites]
    except Exception as e:  # noqa: BLE001 — Overpass is flaky; degrade gracefully
        print(f"    positives failed: {type(e).__name__}: {e}")
        pos_coords = []

    try:
        neg_coords_all = await _fetch_negatives(lat, lng, radius, limit=400)
    except Exception as e:  # noqa: BLE001
        print(f"    negatives failed: {type(e).__name__}: {e}")
        neg_coords_all = []

    rng.shuffle(pos_coords)
    rng.shuffle(neg_coords_all)
    pos = pos_coords[:pos_per_city]
    neg = neg_coords_all[:neg_per_city]
    print(f"    {len(pos)} pos / {len(neg)} neg")
    return pos, neg


async def _run(args: argparse.Namespace) -> int:
    rng = random.Random(args.seed)
    print(f"==> Sampling {args.pos_per_city} pos + {args.neg_per_city} neg per city")
    print(f"==> Cities: {len(SEEDS)}")

    all_pos: list[tuple[float, float]] = []
    all_neg: list[tuple[float, float]] = []
    for seed in SEEDS:
        pos, neg = await _gather_one(
            seed,
            pos_per_city=args.pos_per_city,
            neg_per_city=args.neg_per_city,
            rng=rng,
        )
        all_pos.extend(pos)
        all_neg.extend(neg)
        # Overpass courtesy: short pause between metros.
        await asyncio.sleep(2.0)

    # Deduplicate by 5-decimal rounded coords (~1.1 m precision).
    def _dedup(rows: list[tuple[float, float]]) -> list[tuple[float, float]]:
        seen: set[tuple[float, float]] = set()
        out: list[tuple[float, float]] = []
        for la, lo in rows:
            key = (round(la, 5), round(lo, 5))
            if key in seen:
                continue
            seen.add(key)
            out.append((la, lo))
        return out

    all_pos = _dedup(all_pos)
    all_neg = _dedup(all_neg)
    print(f"==> Deduped: {len(all_pos)} pos, {len(all_neg)} neg")

    rng.shuffle(all_pos)
    rng.shuffle(all_neg)
    if args.cap_total:
        # Keep class balance at the cap.
        per_class = args.cap_total // 2
        all_pos = all_pos[:per_class]
        all_neg = all_neg[:per_class]
        print(f"==> Capped to {len(all_pos)} pos + {len(all_neg)} neg")

    out_path = Path(args.out)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8") as f:
        f.write("# OSM-sampled training coordinates.\n")
        f.write(f"# Generated by sample_training_coords.py — seed={args.seed}\n")
        f.write(f"# Positives ({len(all_pos)}): solar-tagged buildings.\n")
        for la, lo in all_pos:
            f.write(f"{la:.6f},{lo:.6f}\n")
        f.write(f"# Negatives ({len(all_neg)}): residential buildings without solar tags.\n")
        for la, lo in all_neg:
            f.write(f"{la:.6f},{lo:.6f}\n")
    print(f"==> Wrote {len(all_pos) + len(all_neg)} coords to {out_path}")
    return 0


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--out", type=Path, required=True,
                   help="Output coords file (consumed by bootstrap_labels.py --coords)")
    p.add_argument("--pos-per-city", type=int, default=15)
    p.add_argument("--neg-per-city", type=int, default=15)
    p.add_argument("--cap-total", type=int, default=0,
                   help="Cap total samples after dedup; 0 = no cap (keep class balance)")
    p.add_argument("--seed", type=int, default=42)
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_run(_parse())))
