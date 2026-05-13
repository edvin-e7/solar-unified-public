"""Import legacy prospect + scan + journal data from edvin-solar-master.

Dry-run mode copies prospects.db to .tmp/ and writes there so nothing in
backend/data/ is touched until you approve the counts.

Usage:
    python3 backend/scripts/import_legacy_data.py --dry-run
    python3 backend/scripts/import_legacy_data.py
"""

from __future__ import annotations

import argparse
import json
import shutil
import sqlite3
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent.parent
BACKEND = ROOT / "backend"
DB_PATH = BACKEND / "data" / "prospects.db"
LEGACY_DIR = Path("/home/user/edvin-solar-master/data")
TMP_DB = ROOT / ".tmp" / "prospects_dryrun.db"

STATUS_MAP = {
    "good_prospect": "interested",
    "qualified": "interested",
    "rejected": "rejected",
    "": "new",
}

TRAINING_TABLE_SQL = """
CREATE TABLE IF NOT EXISTS training_examples (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    area_name TEXT NOT NULL,
    lat REAL,
    lng REAL,
    classification TEXT,
    detection_score REAL,
    panel_ratio REAL,
    annual_kwh REAL,
    source TEXT NOT NULL,
    created_at TEXT DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(area_name, source)
);
CREATE INDEX IF NOT EXISTS idx_training_classification ON training_examples(classification);
"""


def redact(name: str | None) -> str:
    if not name:
        return "—"
    parts = name.split()
    return parts[0][0] + "." + (parts[-1][0] + "." if len(parts) > 1 else "")


def ensure_schema(con: sqlite3.Connection) -> None:
    con.executescript(TRAINING_TABLE_SQL)


def import_prospects(con: sqlite3.Connection, path: Path) -> tuple[int, int]:
    data: dict[str, Any] = json.loads(path.read_text(encoding="utf-8"))
    rows: list[dict[str, Any]] = []
    for value in data.values():
        if isinstance(value, list):
            rows.extend(value)

    inserted = 0
    skipped = 0
    notes_keys = (
        "property_value",
        "roof_area_m2",
        "roof_orientation",
        "has_panels",
        "panel_confidence",
        "electricity_price_area",
        "municipality",
    )

    for row in rows:
        address = row.get("address")
        if not address:
            skipped += 1
            continue
        notes_payload = {
            k: row[k] for k in notes_keys if k in row and row[k] not in ("", None)
        }
        cur = con.execute(
            """
            INSERT OR IGNORE INTO prospects
                (address, lat, lng, status, score, annual_kwh,
                 owner_name, owner_age, owner_phone, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                address,
                row.get("geocode_lat"),
                row.get("geocode_lon"),
                STATUS_MAP.get(row.get("pipeline_stage", ""), "new"),
                row.get("score"),
                row.get("estimated_yield_kwh"),
                row.get("name") or None,
                row.get("owner_age") or None,
                row.get("phone") or None,
                json.dumps(notes_payload, ensure_ascii=False) if notes_payload else None,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
            print(f"  + {address} (owner {redact(row.get('name'))})")
        else:
            skipped += 1

    con.commit()
    return inserted, skipped


def import_training(con: sqlite3.Connection, path: Path) -> tuple[int, int]:
    data = json.loads(path.read_text(encoding="utf-8"))
    if isinstance(data, dict):
        rows = data.get("results") or data.get("prospects") or []
    elif isinstance(data, list):
        rows = data
    else:
        rows = []

    source = path.name
    inserted = 0
    skipped = 0

    for row in rows:
        area_name = row.get("name") or row.get("area_name")
        if not area_name:
            skipped += 1
            continue
        cur = con.execute(
            """
            INSERT OR IGNORE INTO training_examples
                (area_name, lat, lng, classification, detection_score,
                 panel_ratio, annual_kwh, source)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                area_name,
                row.get("lat"),
                row.get("lon"),
                row.get("classification") or ("has_panels" if row.get("buildings_with_panels", 0) > 0 else None),
                row.get("detection_score") or row.get("gemini_confidence"),
                row.get("panel_ratio"),
                row.get("annual_kwh") or row.get("annual_kwh_6kwp"),
                source,
            ),
        )
        if cur.rowcount == 1:
            inserted += 1
        else:
            skipped += 1

    con.commit()
    return inserted, skipped


def import_learning_log(path: Path) -> int:
    data = json.loads(path.read_text(encoding="utf-8"))
    entries = data.get("entries", []) if isinstance(data, dict) else data
    if not entries:
        return 0

    sys.path.insert(0, str(BACKEND))
    from learning_journal import record  # type: ignore[import-not-found]

    merged = 0
    for entry in entries:
        lesson = entry.get("learned") or entry.get("notes") or entry.get("outcome_detail") or ""
        if not lesson:
            continue
        phase = f"legacy-{entry.get('action_type', 'unknown')}"
        outcome_raw = entry.get("outcome", "").lower()
        if "fail" in outcome_raw or "error" in outcome_raw:
            outcome = "failed"
        elif outcome_raw:
            outcome = "passed"
        else:
            continue
        record(
            phase=phase,
            outcome=outcome,
            lesson=lesson[:500],
            metadata={"agent": entry.get("agent_id"), "imported_from": "learning_log.json"},
        )
        merged += 1

    return merged


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true", help="write to .tmp/prospects_dryrun.db")
    parser.add_argument("--skip-journal", action="store_true", help="do not merge learning_log.json")
    args = parser.parse_args()

    if args.dry_run:
        TMP_DB.parent.mkdir(exist_ok=True)
        shutil.copy(DB_PATH, TMP_DB)
        target = TMP_DB
        print(f"DRY-RUN → {target}")
    else:
        target = DB_PATH
        print(f"LIVE → {target}")

    con = sqlite3.connect(target)
    try:
        ensure_schema(con)
        p_new, p_skip = import_prospects(con, LEGACY_DIR / "prospect_database.json")
        t_new = 0
        t_skip = 0
        for scan_path in (
            LEGACY_DIR / "stockholm_scan" / "full_pipeline_results.json",
            LEGACY_DIR / "stockholm_solar_prospects.json",
        ):
            if scan_path.exists():
                n, s = import_training(con, scan_path)
                t_new += n
                t_skip += s
        total_prospects = con.execute("SELECT COUNT(*) FROM prospects").fetchone()[0]
        total_training = con.execute("SELECT COUNT(*) FROM training_examples").fetchone()[0]
    finally:
        con.close()

    print(f"\nprospects        +{p_new} new, {p_skip} skipped | total now {total_prospects}")
    print(f"training_examples +{t_new} new, {t_skip} skipped | total now {total_training}")

    if not args.dry_run and not args.skip_journal:
        j_new = import_learning_log(LEGACY_DIR / "learning_log.json")
        print(f"journal          +{j_new} legacy entries merged")


if __name__ == "__main__":
    main()
