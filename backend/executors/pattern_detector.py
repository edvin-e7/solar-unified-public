"""PatternDetector — analyze journal entries, find actionable patterns."""

from __future__ import annotations

from typing import Any

from learning_journal import entries


class PatternDetector:
    """Executor role: detect recurring patterns in learning journal."""

    name = "pattern_detector"

    def detect_patterns(self, lookback: int = 100) -> dict[str, Any]:
        """Analyze recent journal entries, find patterns.

        Args:
            lookback: Number of recent entries to analyze (default 100)

        Returns:
            {
                "patterns": [
                    {
                        "name": str,
                        "severity": "low" | "medium" | "high",
                        "frequency": int,
                        "description": str,
                        "suggestion": str
                    }
                ]
            }
        """
        all_entries = entries()
        recent = all_entries[-lookback:] if len(all_entries) > lookback else all_entries

        patterns = []

        # Pattern 1: Low detection confidence
        low_conf_count = sum(
            1
            for e in recent
            if e.get("phase") == "data-gathering"
            and (_meta := e.get("metadata", {})).get("avg_confidence", 1.0) < 0.65
        )
        if low_conf_count >= 3:
            patterns.append(
                {
                    "name": "low_detection_confidence",
                    "severity": "high" if low_conf_count > 10 else "medium",
                    "frequency": low_conf_count,
                    "description": f"Detection confidence < 0.65 in {low_conf_count} recent scans",
                    "suggestion": "Refine detection.md prompt for low-light/cloudy image handling",
                }
            )

        # Pattern 2: Low enrichment rate
        low_enrich_count = sum(
            1
            for e in recent
            if e.get("phase") == "enrichment"
            and (_meta := e.get("metadata", {})).get("rate", 1.0) < 0.8
        )
        if low_enrich_count >= 2:
            patterns.append(
                {
                    "name": "low_enrichment_rate",
                    "severity": "medium",
                    "frequency": low_enrich_count,
                    "description": f"Enrichment rate < 80% in {low_enrich_count} recent batches",
                    "suggestion": "Add retry logic to mrkoll executor (handle timeouts, Cloudflare blocks)",
                }
            )

        # Pattern 3: High validation rejection
        validation_rejections = sum(
            1
            for e in recent
            if e.get("phase") == "data-validator"
            and e.get("outcome") in ("failed", "error")
        )
        if validation_rejections >= 2:
            patterns.append(
                {
                    "name": "high_validation_rejection",
                    "severity": "medium",
                    "frequency": validation_rejections,
                    "description": f"Data validation failures in {validation_rejections} recent batches",
                    "suggestion": "Investigate quality of source data (satellite images, geocoding)",
                }
            )

        # Pattern 4: Repeated errors
        error_phases = {}
        for e in recent:
            if e.get("outcome") == "error":
                phase = e.get("phase", "unknown")
                error_phases[phase] = error_phases.get(phase, 0) + 1

        for phase, count in error_phases.items():
            if count >= 3:
                patterns.append(
                    {
                        "name": f"repeated_errors_{phase}",
                        "severity": "high",
                        "frequency": count,
                        "description": f"Phase '{phase}' failed {count} times",
                        "suggestion": f"Debug and fix root cause in {phase} executor",
                    }
                )

        return {
            "analyzed": len(recent),
            "patterns_found": len(patterns),
            "patterns": patterns,
        }
