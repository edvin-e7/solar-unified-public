#!/usr/bin/env python3
"""Generate synthetic journal data to trigger pattern detection."""

from __future__ import annotations

import json
import sys
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))


def generate_synthetic_patterns() -> None:
    """Create journal entries that trigger each pattern detection rule."""
    journal_path = Path(__file__).parent.parent / "prompts" / "learned" / "journal.jsonl"

    entries = []
    now = datetime.now(datetime.now().astimezone().tzinfo)

    # Pattern 1: low_detection_confidence (avg < 0.65)
    # Create 15 entries with low confidence
    for i in range(15):
        entries.append({
            "ts": (now - timedelta(hours=20 - i)).isoformat(),
            "phase": "data-gathering",
            "outcome": "passed",
            "lesson": f"Scanned address {i}, low confidence 0.45",
            "files": [],
            "error": None,
            "metadata": {
                "scanned": 1,
                "valid": 1,
                "avg_confidence": 0.45,
                "enrichment_rate": 0.0,
            },
        })

    # Pattern 2: low_enrichment_rate (< 80%)
    # Create 10 entries with low enrichment
    for i in range(10):
        entries.append({
            "ts": (now - timedelta(hours=15 - i)).isoformat(),
            "phase": "enrichment",
            "outcome": "passed",
            "lesson": f"Enrichment batch {i}: 2/10 succeeded (20% rate)",
            "files": [],
            "error": None,
            "metadata": {
                "attempted": 10,
                "succeeded": 2,
                "enrichment_rate": 0.2,
            },
        })

    # Pattern 3: repeated_errors (3+ consecutive failures)
    for i in range(4):
        entries.append({
            "ts": (now - timedelta(hours=10 - i)).isoformat(),
            "phase": "enrichment",
            "outcome": "failed",
            "lesson": f"Enrichment failed: Electron IPC timeout #{i+1}",
            "files": [],
            "error": "Electron IPC connection timeout",
            "metadata": {
                "error_type": "timeout",
                "service": "electron",
            },
        })

    # Pattern 4: high_validation_rejection
    for i in range(8):
        entries.append({
            "ts": (now - timedelta(hours=5 - i)).isoformat(),
            "phase": "validation",
            "outcome": "passed",
            "lesson": f"Validation batch {i}: 1/10 valid (confidence gate failed)",
            "files": [],
            "error": None,
            "metadata": {
                "scanned": 10,
                "valid": 1,
                "failed_reason": "confidence < 0.7",
            },
        })

    # Append to journal
    with open(journal_path, "a") as f:
        for entry in entries:
            f.write(json.dumps(entry) + "\n")

    print(f"✓ Generated {len(entries)} synthetic journal entries")
    print("  - low_detection_confidence: 15 entries")
    print("  - low_enrichment_rate: 10 entries")
    print("  - repeated_errors: 4 entries")
    print("  - high_validation_rejection: 8 entries")
    print("\nNext pattern detection will find: 4 patterns")


if __name__ == "__main__":
    generate_synthetic_patterns()
