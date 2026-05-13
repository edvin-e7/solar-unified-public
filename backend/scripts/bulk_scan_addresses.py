"""
Bulk-scan addresses → save prospects to DB.

T2.13 av Tier-2 plan. Wraps scanner.scan_address för en lista av adresser.

Usage:
    python bulk_scan_addresses.py --input fixtures/bootstrap_addresses.txt
    python bulk_scan_addresses.py --input my-addresses.txt --backend embed --max 50

Backend selection:
    --backend embed      MobileNet + numpy logistic head (deterministisk, default)
    --backend moondream  Local LLM via Ollama (kräver `ollama pull moondream`)
    --backend gemini     Direct Gemini API call (BETALT — opt-in only)

För solar-leads-byrå-demo: kör mot 100-300 Sollentuna-addresses,
sedan exportera via /api/prospects/export/csv.
"""

from __future__ import annotations

import argparse
import asyncio
import os
import sys
import time
from pathlib import Path

# Resolve backend path
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent
sys.path.insert(0, str(BACKEND_DIR))

# Defer imports till efter sys.path-setup
from api.prospects import db  # noqa: E402
from error_logger import log_error  # noqa: E402
from services import scanner  # noqa: E402


def _read_addresses(input_path: Path) -> list[str]:
    """Läs adresser från fil, ignorera tomma rader + # comments."""
    lines = input_path.read_text(encoding="utf-8").splitlines()
    return [
        line.strip()
        for line in lines
        if line.strip() and not line.strip().startswith("#")
    ]


def _save_prospect(address: str, result: dict, has_panels: bool | None, confidence: float | None) -> int | None:
    """Insert prospect till DB. Returnerar id, eller None om address redan finns."""
    with db() as conn:
        existing = conn.execute(
            "SELECT id FROM prospects WHERE address = ?", (address,)
        ).fetchone()
        if existing:
            # Update score + detection on existing
            conn.execute(
                """UPDATE prospects SET
                       lat = ?, lng = ?, score = ?, notes = ?,
                       has_panels = ?, panel_confidence = ?,
                       updated_at = CURRENT_TIMESTAMP
                   WHERE id = ?""",
                (result.get("lat"), result.get("lng"), result.get("score"),
                 result.get("reasoning"), has_panels, confidence, existing["id"]),
            )
            return existing["id"]
        cur = conn.execute(
            """INSERT INTO prospects
                   (address, lat, lng, score, notes, has_panels, panel_confidence)
               VALUES (?, ?, ?, ?, ?, ?, ?)""",
            (address, result.get("lat"), result.get("lng"), result.get("score"),
             result.get("reasoning"), has_panels, confidence),
        )
        return cur.lastrowid


async def _scan_one(address: str) -> tuple[bool, str]:
    """Returns (success, summary-string)."""
    try:
        result = await scanner.scan_address(address)
        # ScanResult is a TypedDict — let's defensive-extract
        has_panels = result.get("has_panels")
        confidence = result.get("panel_confidence")
        score = result.get("score")

        prospect_id = _save_prospect(address, result, has_panels, confidence)

        summary = (
            f"id={prospect_id} score={score:.2f} " if score is not None
            else f"id={prospect_id} no-score "
        )
        summary += f"panels={has_panels} conf={confidence}"
        return True, summary
    except Exception as e:
        log_error("bulk-scan-address", e, context={"address": address})
        return False, f"FAIL: {type(e).__name__}: {str(e)[:80]}"


async def _main_async(args: argparse.Namespace) -> int:
    # Set backend if specified
    if args.backend:
        os.environ["DETECTION_BACKEND"] = args.backend

    input_path = Path(args.input)
    if not input_path.exists():
        print(f"FEL: input-fil saknas: {input_path}", file=sys.stderr)
        return 1

    addresses = _read_addresses(input_path)
    if args.max:
        addresses = addresses[: args.max]

    print(f"Bulk-scanning {len(addresses)} addresses (backend={os.getenv('DETECTION_BACKEND', 'default')})")
    print("─" * 70)

    success = 0
    failures = 0
    t0 = time.time()

    for i, address in enumerate(addresses, start=1):
        elapsed = time.time() - t0
        rate = elapsed / max(i - 1, 1) if i > 1 else 0
        eta = rate * (len(addresses) - i + 1)
        prefix = f"[{i:3}/{len(addresses)}] (ETA {eta/60:.1f}m)"

        ok, summary = await _scan_one(address)
        marker = "✓" if ok else "✗"
        print(f"{prefix} {marker} {address[:50]:50} {summary}")

        if ok:
            success += 1
        else:
            failures += 1

        # Rate-limit-respect för Nominatim (1 req/s)
        if i < len(addresses):
            await asyncio.sleep(1.2)

    print("─" * 70)
    print(f"Klart i {(time.time()-t0)/60:.1f}m. Success {success}, failures {failures}.")

    if args.export_after:
        print()
        print("Exporterar qualified-prospects till CSV...")
        from api.prospects import _export_csv_sync
        buf = _export_csv_sync(status="qualified", limit=args.max or 500)
        out_path = Path("deliverables") / f"bulk-export-{int(time.time())}.csv"
        out_path.parent.mkdir(exist_ok=True)
        out_path.write_text(buf.getvalue(), encoding="utf-8")
        print(f"→ {out_path}")

    return 0 if failures == 0 else 1


def main() -> int:
    parser = argparse.ArgumentParser(description="Bulk-scan addresses")
    parser.add_argument("--input", required=True, help="Text file med en adress per rad (# = comment)")
    parser.add_argument("--max", type=int, default=None, help="Max antal addresses att processera")
    parser.add_argument("--backend", choices=["embed", "moondream", "gemini", "auto"], default=None,
                        help="Detection backend (default: env DETECTION_BACKEND eller embed)")
    parser.add_argument("--export-after", action="store_true",
                        help="Exportera qualified-prospects till CSV efter scan")
    args = parser.parse_args()
    return asyncio.run(_main_async(args))


if __name__ == "__main__":
    sys.exit(main())
