#!/usr/bin/env python3
"""Compare detection backends on the same satellite images.

The "is ML matching LLM yet?" measurement loop. For each input address,
fetches the satellite image once and runs every available detection backend
(ml, embed, gemini). Records per-backend verdicts + latency, then prints an
agreement matrix and writes a JSONL report for downstream analysis.

Usage
-----
    # Addresses, one per line, from a file
    python3 backend/scripts/eval_detection.py --addresses fixtures/eval_set.txt

    # Comma-separated lat,lng pairs from a file
    python3 backend/scripts/eval_detection.py --coords fixtures/eval_coords.txt

    # Pull labelled rows from prospects.db (requires DB exists)
    python3 backend/scripts/eval_detection.py --from-prospects-db --limit 100

    # Restrict which backends to run (default: all available)
    python3 backend/scripts/eval_detection.py --addresses ... --backends ml,gemini

Outputs
-------
- JSONL report at backend/data/detection/eval_<UTC-timestamp>.jsonl
  One row per (address, backend) tuple.
- Console summary: backend availability, agreement matrix, per-backend
  latency p50/p95, top disagreements (priority labelling targets).

Requirements
------------
- ZERO API keys for the free path: ArcGIS satellite (services/satellite.py)
  + Nominatim geocoding (services/geocode.py) + embed/ml local backends.
- GEMINI_API_KEY only if you include "gemini" in --backends (free tier:
  15 req/min, 1M tokens/day on flash — be deliberate, don't bulk-eval).
- DO NOT set ALLOW_GOOGLE_SOLAR_API=1 unless you want to be billed.
- At least one detection backend usable. Skips unusable backends with a
  warning rather than crashing, so the script is also a smoke test.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sqlite3
import sys
import time
from collections import Counter
from pathlib import Path
from typing import Any

REPO_ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(REPO_ROOT / "backend"))

OUTPUT_DIR = REPO_ROOT / "backend" / "data" / "detection"
PROSPECTS_DB = REPO_ROOT / "backend" / "data" / "prospects.db"
ALL_BACKENDS = ("ml", "embed", "moondream", "gemini")


def _load_addresses(args: argparse.Namespace) -> list[tuple[str, float | None, float | None]]:
    """Return list of (label, lat, lng). lat/lng may be None — geocoded later."""
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
    if args.from_prospects_db:
        if not PROSPECTS_DB.exists():
            print(f"  --from-prospects-db given but {PROSPECTS_DB} missing", file=sys.stderr)
        else:
            con = sqlite3.connect(PROSPECTS_DB)
            try:
                rows = con.execute(
                    "SELECT address, lat, lng FROM prospects "
                    "WHERE lat IS NOT NULL AND lng IS NOT NULL "
                    f"LIMIT {int(args.limit)}"
                ).fetchall()
            finally:
                con.close()
            for addr, lat, lng in rows:
                out.append((addr, float(lat), float(lng)))
    return out


def _available_backends(requested: list[str]) -> list[str]:
    """Filter requested backends to those that can actually run."""
    from services import detection_embed, detection_gemini, detection_ml, detection_moondream

    checks = {
        "ml": detection_ml.is_available,
        "embed": detection_embed.is_available,
        "moondream": detection_moondream.is_available,
        "gemini": detection_gemini.is_available,
    }
    fix_hints = {
        "ml": "drop YOLOv8-seg ONNX at backend/models/yolov8n-solar-seg.onnx",
        "embed": "run `make ml-bootstrap` then `make ml-train`",
        "moondream": "install ollama, run `make ml-moondream`, ensure `ollama serve` is up",
        "gemini": "set GEMINI_API_KEY in .env (paid)",
    }
    available: list[str] = []
    for b in requested:
        if b not in checks:
            print(f"  unknown backend: {b}", file=sys.stderr)
            continue
        try:
            if checks[b]():
                available.append(b)
            else:
                print(f"  backend {b!r} unavailable — to enable: {fix_hints[b]}", file=sys.stderr)
        except Exception as e:  # noqa: BLE001
            print(f"  backend {b!r} availability check raised {type(e).__name__}: {e}", file=sys.stderr)
    return available


async def _run_backend(backend: str, image_bytes: bytes, lat: float) -> dict[str, Any]:
    """Run one backend, never raise — return dict with error on failure."""
    from services import detection_embed, detection_gemini, detection_ml, detection_moondream

    impls = {
        "ml": detection_ml.detect,
        "embed": detection_embed.detect,
        "moondream": detection_moondream.detect,
        "gemini": detection_gemini.detect,
    }
    t0 = time.perf_counter()
    try:
        result = await impls[backend](image_bytes, lat=lat, zoom=20)
        result["wall_ms"] = int((time.perf_counter() - t0) * 1000)
        result["error"] = None
        return result
    except Exception as e:  # noqa: BLE001 — eval harness wraps stages
        return {
            "backend": backend,
            "has_panels": None,
            "confidence": None,
            "panel_area_m2": None,
            "roof_area_m2": None,
            "inference_ms": None,
            "wall_ms": int((time.perf_counter() - t0) * 1000),
            "error": f"{type(e).__name__}: {e}",
        }


def _summarise(rows: list[dict[str, Any]], backends: list[str]) -> None:
    if not rows:
        print("\nNo eval rows produced.")
        return

    by_addr: dict[str, dict[str, dict[str, Any]]] = {}
    for r in rows:
        by_addr.setdefault(r["address"], {})[r["backend"]] = r

    total = len(by_addr)
    print(f"\nEvaluated {total} addresses across {len(backends)} backends: {backends}")

    if len(backends) >= 2:
        a, b = backends[0], backends[1]
        agree = disagree = skipped = 0
        disagreements: list[tuple[str, dict[str, Any], dict[str, Any]]] = []
        for addr, per_backend in by_addr.items():
            ra, rb = per_backend.get(a), per_backend.get(b)
            if not ra or not rb or ra["has_panels"] is None or rb["has_panels"] is None:
                skipped += 1
                continue
            if ra["has_panels"] == rb["has_panels"]:
                agree += 1
            else:
                disagree += 1
                disagreements.append((addr, ra, rb))
        denom = agree + disagree
        rate = (agree / denom * 100) if denom else 0
        print(f"\nAgreement {a} vs {b}: {agree}/{denom} ({rate:.1f}%)  [skipped={skipped}]")

        if disagreements:
            print(f"\nTop {min(10, len(disagreements))} disagreements (label these first):")
            for addr, ra, rb in disagreements[:10]:
                print(
                    f"  {addr}\n    {a}: has_panels={ra['has_panels']} conf={ra['confidence']}\n"
                    f"    {b}: has_panels={rb['has_panels']} conf={rb['confidence']}"
                )

    for backend in backends:
        latencies = sorted(
            r["wall_ms"] for r in rows if r["backend"] == backend and r["error"] is None
        )
        if not latencies:
            continue
        p50 = latencies[len(latencies) // 2]
        p95 = latencies[min(len(latencies) - 1, int(len(latencies) * 0.95))]
        errors = sum(1 for r in rows if r["backend"] == backend and r["error"])
        print(f"  {backend:<7} n={len(latencies)}  p50={p50}ms  p95={p95}ms  errors={errors}")

    error_types = Counter(
        r["error"].split(":", 1)[0] for r in rows if r["error"]
    )
    if error_types:
        print(f"\nError types: {dict(error_types)}")


async def _run(args: argparse.Namespace) -> int:
    addresses = _load_addresses(args)
    if not addresses:
        print("No addresses provided. Use --addresses, --coords, or --from-prospects-db.", file=sys.stderr)
        return 2

    from services import geocode, satellite  # noqa: F401 — eager-fail if deps missing

    requested = [b.strip() for b in args.backends.split(",") if b.strip()]
    backends = _available_backends(requested)
    if not backends:
        print("No detection backend available. Install weights or set GEMINI_API_KEY.", file=sys.stderr)
        return 3

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    out_path = OUTPUT_DIR / f"eval_{int(time.time())}.jsonl"
    print(f"Writing eval rows to {out_path}")

    rows: list[dict[str, Any]] = []
    with out_path.open("w", encoding="utf-8") as f:
        for i, (label, lat, lng) in enumerate(addresses, 1):
            print(f"[{i}/{len(addresses)}] {label}")
            try:
                from services import geocode as _geo
                from services import satellite as _sat

                if lat is None or lng is None:
                    lat, lng = await _geo.geocode(label)
                image_bytes = await _sat.fetch_satellite_image(lat, lng)
            except Exception as e:  # noqa: BLE001
                print(f"  fetch failed: {type(e).__name__}: {e}")
                continue

            for backend in backends:
                result = await _run_backend(backend, image_bytes, lat)
                row = {"address": label, "lat": lat, "lng": lng, **result}
                rows.append(row)
                f.write(json.dumps(row, ensure_ascii=False) + "\n")
                f.flush()
                verdict = (
                    f"err={result['error']}" if result["error"]
                    else f"has_panels={result['has_panels']} conf={result['confidence']:.2f}"
                )
                print(f"  {backend}: {verdict} ({result['wall_ms']}ms)")

    _summarise(rows, backends)
    return 0


def _parse() -> argparse.Namespace:
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    src = p.add_argument_group("inputs (use any combination)")
    src.add_argument("--addresses", type=Path, help="File: one address per line")
    src.add_argument("--coords", type=Path, help="File: one 'lat,lng' per line")
    src.add_argument("--from-prospects-db", action="store_true", help="Sample from backend/data/prospects.db")
    src.add_argument("--limit", type=int, default=100, help="Max rows from --from-prospects-db")
    p.add_argument("--backends", default=",".join(ALL_BACKENDS), help=f"Comma-separated subset of {ALL_BACKENDS}")
    return p.parse_args()


if __name__ == "__main__":
    sys.exit(asyncio.run(_run(_parse())))
