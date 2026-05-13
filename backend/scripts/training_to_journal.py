"""Convert training_examples rows into data-gathering journal entries.

Pattern detector (backend/executors/pattern_detector.py) scans journal entries
for phase='data-gathering' with metadata.avg_confidence. Each historical area
scan is semantically a data-gathering event, so project them in.
"""

from __future__ import annotations

import sqlite3
import sys
from pathlib import Path

BACKEND = Path(__file__).resolve().parent.parent
DB_PATH = BACKEND / "data" / "prospects.db"

sys.path.insert(0, str(BACKEND))
from learning_journal import record  # noqa: E402


def main() -> None:
    con = sqlite3.connect(DB_PATH)
    rows = con.execute(
        """
        SELECT area_name, classification, detection_score, panel_ratio, annual_kwh, source
        FROM training_examples
        ORDER BY id
        """
    ).fetchall()
    con.close()

    if not rows:
        print("no training_examples — nothing to project")
        return

    emitted = 0
    for area_name, classification, detection_score, panel_ratio, annual_kwh, source in rows:
        confidence = detection_score if detection_score is not None else 0.0
        outcome = "passed" if confidence >= 0.65 else "failed"
        lesson = (
            f"Scanned {area_name}: classification={classification or 'unknown'}, "
            f"confidence={confidence:.2f}, kwh={annual_kwh or 0:.0f}"
        )
        record(
            phase="data-gathering",
            outcome=outcome,
            lesson=lesson,
            metadata={
                "avg_confidence": confidence,
                "panel_ratio": panel_ratio,
                "area": area_name,
                "source": source,
                "imported_from": "training_examples",
            },
        )
        emitted += 1

    print(f"projected {emitted} training_examples → data-gathering journal entries")


if __name__ == "__main__":
    main()
