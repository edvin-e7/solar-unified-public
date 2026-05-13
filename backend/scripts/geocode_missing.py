"""Backfill lat/lng for prospects via Nominatim (free OSM geocoder).

Idempotent: only touches rows where lat IS NULL OR lng IS NULL.
Rate-limited to 1 req/sec per Nominatim usage policy.
Safe to kill + restart — picks up where it left off via NULL check.

Usage:
    python3 backend/scripts/geocode_missing.py --dry-run --limit 20
    python3 backend/scripts/geocode_missing.py --limit 100
    python3 backend/scripts/geocode_missing.py                 # all missing
"""

from __future__ import annotations

import argparse
import asyncio
import sqlite3
import sys
import time
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(BACKEND))

from services import geocode  # noqa: E402

DEFAULT_DB = Path("/opt/solar-unified/backend/data/prospects.db")
NOMINATIM_DELAY_S = 1.1  # policy: max 1 req/sec


async def backfill(db_path: Path, limit: int | None, dry_run: bool) -> dict[str, int]:
    con = sqlite3.connect(db_path)
    con.row_factory = sqlite3.Row
    try:
        q = (
            "SELECT id, address FROM prospects "
            "WHERE (lat IS NULL OR lng IS NULL) "
            "AND address IS NOT NULL AND address != '' "
            "AND status != 'rejected'"
        )
        if limit:
            q += f" LIMIT {limit}"
        rows = list(con.execute(q))
        total = len(rows)
        print(f"missing coords: {total} {'(dry-run)' if dry_run else ''}", file=sys.stderr)

        updated = 0
        failed = 0
        for i, row in enumerate(rows, 1):
            try:
                lat, lng = await geocode.geocode(row["address"])
                if not dry_run:
                    con.execute(
                        "UPDATE prospects SET lat = ?, lng = ? WHERE id = ?",
                        (lat, lng, row["id"]),
                    )
                    if i % 50 == 0:
                        con.commit()
                updated += 1
            except Exception as e:
                failed += 1
                if failed <= 5:
                    print(f"  fail {row['address'][:60]!r}: {e}", file=sys.stderr)
            if i % 25 == 0:
                print(f"  [{i}/{total}] ok={updated} fail={failed}", file=sys.stderr)
            time.sleep(NOMINATIM_DELAY_S)
        con.commit()
    finally:
        con.close()

    return {"total": total, "updated": updated, "failed": failed}


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not args.db.exists():
        parser.error(f"DB not found: {args.db}")

    stats = asyncio.run(backfill(args.db, args.limit, args.dry_run))
    print(
        f"\ndone: total={stats['total']} updated={stats['updated']} failed={stats['failed']}"
    )


if __name__ == "__main__":
    main()
