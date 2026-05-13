"""Import enriched prospect CSV from edvins-solprojekt-sandbox into prospects DB.

Input: prospektering-berikad-*.csv (33 Swedish columns, UTF-8 BOM, quoted commas).
Target: /opt/solar-unified/backend/data/prospects.db by default (service-reads).
Idempotent: preloads existing addresses into a set, skips matches.

Field map (CSV -> DB):
    adress              -> address
    lat, lng            -> lat, lng
    namn                -> owner_name
    ålder               -> owner_age (int or None)
    partiellt_tel       -> owner_phone (may be masked)
    solstatus           -> has_panels (har_paneler=1, inga_paneler=0, okänt=NULL)
    konfidens "100%"    -> panel_confidence (0..1)
    (rest)              -> notes JSON

Usage:
    python3 backend/scripts/import_sandbox_csv.py --dry-run
    python3 backend/scripts/import_sandbox_csv.py --live
    python3 backend/scripts/import_sandbox_csv.py --live --db /custom/prospects.db
"""

from __future__ import annotations

import argparse
import csv
import json
import shutil
import sqlite3
import sys
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

DEFAULT_CSV = Path(
    "/home/user/edvins-solprojekt-sandbox/.tmp/prospektering-berikad-2026-04-20.csv"
)
DEFAULT_DB = Path("/opt/solar-unified/backend/data/prospects.db")
REPO_ROOT = Path(__file__).resolve().parent.parent.parent
TMP_DB = REPO_ROOT / ".tmp" / "prospects_sandbox_dryrun.db"

SOLSTATUS_MAP = {
    "har_paneler": 1,
    "inga_paneler": 0,
    "okänt": None,
    "": None,
}

NOTES_KEYS = (
    "stad",
    "personnummer_prefix",
    "ssn_validerad",
    "kön",
    "lägenhet",
    "poststad",
    "arbetsgivare",
    "flyttade_in",
    "hushåll",
    "källor",
    "matchad_gata",
    "matchad_nr",
    "matchad_postnr",
    "matchad_stad",
    "hitta_person_sök",
    "birthday_person_sök",
    "mrkoll_person_sök",
    "eniro_person_sök",
    "google_person_sök",
    "hitta_adress",
    "mrkoll_adress",
    "eniro_adress",
    "förnamn",
    "efternamn",
    "födelsedag",
)


def parse_konfidens(s: str) -> float | None:
    s = s.strip().rstrip("%")
    if not s:
        return None
    try:
        v = float(s)
        return v / 100.0 if v > 1.5 else v
    except ValueError:
        return None


def parse_float(s: str) -> float | None:
    s = s.strip()
    if not s:
        return None
    try:
        return float(s)
    except ValueError:
        return None


def parse_int(s: str) -> int | None:
    s = s.strip()
    if not s:
        return None
    try:
        return int(s)
    except ValueError:
        return None


def build_notes(row: dict[str, str]) -> str | None:
    payload: dict[str, Any] = {
        k: row[k].strip()
        for k in NOTES_KEYS
        if k in row and row[k] and row[k].strip()
    }
    payload["source"] = "sandbox-csv-2026-04-20"
    return json.dumps(payload, ensure_ascii=False)


def import_rows(
    con: sqlite3.Connection, csv_path: Path, verbose: bool = False
) -> dict[str, int]:
    existing: set[str] = {
        row[0] for row in con.execute("SELECT address FROM prospects WHERE address IS NOT NULL")
    }
    total = 0
    inserted = 0
    skipped_dupe = 0
    skipped_no_address = 0
    panel_owners = 0
    detected_at = datetime.now(UTC).isoformat()

    with csv_path.open("r", encoding="utf-8-sig", newline="") as f:
        reader = csv.DictReader(f)
        for row in reader:
            total += 1
            address = (row.get("adress") or "").strip()
            if not address:
                skipped_no_address += 1
                continue
            if address in existing:
                skipped_dupe += 1
                continue

            solstatus = (row.get("solstatus") or "").strip()
            has_panels = SOLSTATUS_MAP.get(solstatus)
            confidence = parse_konfidens(row.get("konfidens") or "")

            con.execute(
                """
                INSERT INTO prospects
                    (address, lat, lng, status, score,
                     owner_name, owner_age, owner_phone, notes,
                     has_panels, panel_confidence, detected_at)
                VALUES (?, ?, ?, 'new', NULL, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    address,
                    parse_float(row.get("lat") or ""),
                    parse_float(row.get("lng") or ""),
                    (row.get("namn") or "").strip() or None,
                    parse_int(row.get("ålder") or ""),
                    (row.get("partiellt_tel") or "").strip() or None,
                    build_notes(row),
                    has_panels,
                    confidence if has_panels is not None else None,
                    detected_at if has_panels is not None else None,
                ),
            )
            existing.add(address)
            inserted += 1
            if has_panels == 1:
                panel_owners += 1
            if verbose and inserted % 1000 == 0:
                print(f"  ... {inserted} inserted", file=sys.stderr)

    con.commit()
    return {
        "total_rows": total,
        "inserted": inserted,
        "skipped_duplicate": skipped_dupe,
        "skipped_no_address": skipped_no_address,
        "panel_owners_added": panel_owners,
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--csv", type=Path, default=DEFAULT_CSV)
    parser.add_argument("--db", type=Path, default=DEFAULT_DB)
    parser.add_argument(
        "--dry-run", action="store_true", help="copy DB to .tmp/ and write there"
    )
    parser.add_argument("--live", action="store_true", help="write directly to --db")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    if not args.dry_run and not args.live:
        parser.error("Specify --dry-run or --live")
    if not args.csv.exists():
        parser.error(f"CSV not found: {args.csv}")
    if not args.db.exists():
        parser.error(f"DB not found: {args.db}")

    if args.dry_run:
        TMP_DB.parent.mkdir(exist_ok=True)
        shutil.copy(args.db, TMP_DB)
        target = TMP_DB
        print(f"DRY-RUN target: {target}")
    else:
        target = args.db
        print(f"LIVE target: {target}")

    con = sqlite3.connect(target)
    try:
        before = con.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        stats = import_rows(con, args.csv, verbose=args.verbose)
        after = con.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        total_panels = con.execute(
            "SELECT COUNT(*) FROM prospects WHERE has_panels=1"
        ).fetchone()[0]
    finally:
        con.close()

    print(f"\nBefore:            {before} prospects")
    print(f"After:             {after} prospects")
    print(f"CSV rows:          {stats['total_rows']}")
    print(f"Inserted:          {stats['inserted']}")
    print(f"Skipped (dupe):    {stats['skipped_duplicate']}")
    print(f"Skipped (no addr): {stats['skipped_no_address']}")
    print(f"Panel owners:      +{stats['panel_owners_added']} (total now {total_panels})")


if __name__ == "__main__":
    main()
