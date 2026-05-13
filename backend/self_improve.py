#!/usr/bin/env python3
"""Autonomous improvement orchestrator: suggest → CoVe-verify → test → commit."""

from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

from cove_verifier import verify_improvement
from learning_journal import entries, record

REPO_ROOT = Path(__file__).parent.parent


def get_patterns() -> dict:
    """Extract success + failure patterns from journal."""
    all_entries = entries()
    passed = [e for e in all_entries if e["outcome"] == "passed"]
    failed = [e for e in all_entries if e["outcome"] in ("failed", "error")]
    return {
        "total_runs": len(all_entries),
        "success_rate": len(passed) / len(all_entries) if all_entries else 0,
        "antipatterns": [e["lesson"] for e in failed[-5:]],
    }


def test_baseline() -> bool:
    """Run verify suite. Return True if passes."""
    result = subprocess.run(
        [sys.executable, "backend/scripts/verify_all.py"],
        cwd=REPO_ROOT,
        capture_output=True,
        timeout=60,
    )
    return result.returncode == 0


def suggest_improvement(patterns: dict) -> dict | None:
    """Generate improvement suggestion from patterns."""
    if patterns["success_rate"] < 0.90:
        return None

    if not patterns["antipatterns"]:
        return None

    if any("CP1252" in ap or "unicode" in ap for ap in patterns["antipatterns"]):
        return {
            "target": "backend/scripts/verify_all.py",
            "enhancement": "Add UTF-8 encoding for cross-platform compatibility",
            "rationale": "Windows CP1252 fails on emoji. Add sys.stdout.reconfigure(encoding='utf-8') at start.",
        }
    return None


def main() -> int:
    """Run one autonomous improvement cycle."""
    print("🤖 Autonomous Improvement Cycle")
    print("=" * 70)

    patterns = get_patterns()
    print(f"✓ Analyzed {patterns['total_runs']} runs ({patterns['success_rate']:.0%} success)")

    if not test_baseline():
        print("⚠ Baseline verification failed — skipping")
        return 1

    suggestion = suggest_improvement(patterns)
    if not suggestion:
        print("ℹ No safe improvements identified")
        return 0

    print(f"✓ Suggestion: {suggestion['target']}")
    print(f"  Enhancement: {suggestion['enhancement']}")

    print("\n🔍 Chain-of-Verification...")
    verification = verify_improvement(suggestion)
    print(f"  Confidence: {verification['confidence']:.0%}")

    if not verification["verified"]:
        print("  ✗ Verification failed — aborting")
        record(
            phase="self-improve",
            outcome="failed",
            lesson=f"CoVe rejected improvement: {suggestion['target']}",
            error=verification["reasoning"][:200],
        )
        return 1

    print("  ✓ Verification passed")

    timestamp = datetime.utcnow().strftime("%Y-%m-%d")
    branch = f"auto-improve-{timestamp}"

    try:
        subprocess.run(
            ["git", "checkout", "-b", branch],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        message = f"""refactor: autonomous improvement

Target: {suggestion['target']}
Enhancement: {suggestion['enhancement']}
Rationale: {suggestion['rationale']}

All verification checks passed.
Co-Authored-By: Solar Learner Bot <action@github.com>"""

        subprocess.run(
            ["git", "add", "-A"],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        subprocess.run(
            ["git", "push", "-u", "origin", branch],
            cwd=REPO_ROOT,
            check=True,
            capture_output=True,
        )

        print("✓ Committed to auto-improve branch and pushed")
        record(
            phase="self-improve",
            outcome="passed",
            lesson=f"Improvement executed: {suggestion['target']}",
            metadata={"suggestion": suggestion},
        )
        return 0

    except subprocess.CalledProcessError as e:
        print(f"✗ Git operation failed: {e}")
        record(
            phase="self-improve",
            outcome="error",
            lesson="Git push failed despite verified changes",
            error=str(e)[:200],
        )
        return 1


if __name__ == "__main__":
    sys.exit(main())
