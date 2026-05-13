"""ImprovementGenerator — convert patterns into improvement suggestions.

Each raw suggestion is filtered through `issue_ledger.similar_attempts` BEFORE
being returned so the CoVe gate never re-sees a rejected paraphrase. This is
the concrete hook that breaks the brute-force loop (same rejected idea every
session → Gemini quota burn → no learning).
"""

from __future__ import annotations

import logging
from typing import Any

from issue_ledger import similar_attempts

log = logging.getLogger(__name__)


class ImprovementGenerator:
    """Executor role: generate improvement suggestions from patterns."""

    name = "improvement_generator"

    def generate_improvements(self, patterns: list[dict[str, Any]]) -> dict[str, Any]:
        """Convert detected patterns into improvement suggestions.

        Args:
            patterns: List of patterns from PatternDetector

        Returns:
            {
                "improvements": [
                    {
                        "target": str (file to modify),
                        "enhancement": str (what to change),
                        "rationale": str (why),
                        "type": str (prompt_refinement | config_change | logic_fix),
                        "impact": str (safe | risky)
                    }
                ]
            }
        """
        tagged: list[tuple[dict[str, Any], dict[str, Any]]] = []

        for pattern in patterns:
            name = pattern.get("name", "")

            if name == "low_detection_confidence":
                tagged.append((pattern, {
                    "target": "backend/prompts/detection.md",
                    "enhancement": "Add section for low-light conditions: 'If image appears dim or cloudy, focus on panel edges and roof lines. Request analysis at higher zoom if available.'",
                    "rationale": f"Pattern detected: confidence < 0.65 in {pattern.get('frequency', 0)} scans. Low-light images lose confidence.",
                    "type": "prompt_refinement",
                    "impact": "safe",
                }))

            elif name == "low_enrichment_rate":
                tagged.append((pattern, {
                    "target": "backend/executors/enrichment_executor.py",
                    "enhancement": "Implement exponential backoff + retry on Cloudflare timeout. Add fallback to hitta-only if mrkoll unavailable.",
                    "rationale": f"Pattern detected: enrichment rate < 80% in {pattern.get('frequency', 0)} batches. Cloudflare blocking mrkoll.",
                    "type": "logic_fix",
                    "impact": "safe",
                }))

            elif name == "high_validation_rejection":
                tagged.append((pattern, {
                    "target": "backend/services/satellite.py",
                    "enhancement": "Increase tile zoom level from 18 to 19 for better resolution (reduces unclear/low-confidence detections).",
                    "rationale": f"Pattern detected: {pattern.get('frequency', 0)} validation rejections. Root cause likely poor image resolution.",
                    "type": "config_change",
                    "impact": "safe",
                }))

            elif name.startswith("repeated_errors_"):
                phase = name.replace("repeated_errors_", "")
                tagged.append((pattern, {
                    "target": f"backend/executors/{phase}.py",
                    "enhancement": "Add detailed error logging + early return on exception (avoid cascading failures).",
                    "rationale": f"Pattern detected: {phase} executor failing {pattern.get('frequency', 0)} consecutive times.",
                    "type": "logic_fix",
                    "impact": "risky",  # might mask deeper issues
                }))

        kept_tagged, skipped = _filter_already_tried(tagged)
        kept = [imp for _, imp in kept_tagged]
        return {
            "patterns_processed": len(patterns),
            "improvements_generated": len(kept),
            "improvements": kept,
            "skipped_already_tried": skipped,
            # [(pattern, improvement), ...] of only surviving pairs — orchestrator
            # uses this to map each improvement back to its originating pattern
            # for ledger writes. Skipped paraphrases are reported separately in
            # skipped_already_tried and not included here.
            "kept_tagged": kept_tagged,
        }


def _filter_already_tried(
    tagged: list[tuple[dict[str, Any], dict[str, Any]]],
) -> tuple[list[tuple[dict[str, Any], dict[str, Any]]], list[dict[str, Any]]]:
    """Drop improvements whose (pattern-name, target, enhancement) trio matches
    a prior rejected attempt in the issue ledger.

    Takes (pattern, improvement) tuples so each improvement is unambiguously
    linked to the pattern that produced it — removing the brittle index-based
    mapping that drifted when a pattern produced no improvement.

    Returns (kept_tagged, skipped) — kept_tagged preserves the tuple form so
    the orchestrator can open_issue/log_attempt against the correct pattern.

    Ledger query convention:
        error_type = pattern["name"]
        target     = improvement["target"]
        hypothesis = improvement["enhancement"]
    """
    kept: list[tuple[dict[str, Any], dict[str, Any]]] = []
    skipped: list[dict[str, Any]] = []
    for pat, imp in tagged:
        pat_name = pat.get("name", "")
        target = imp.get("target", "")
        hypothesis = imp.get("enhancement", "")
        if not pat_name or not target or not hypothesis:
            kept.append((pat, imp))
            continue
        try:
            matches = similar_attempts(pat_name, target, hypothesis)
        except Exception:  # pragma: no cover — ledger unreadable must not block
            log.exception("issue_ledger.similar_attempts failed; not filtering")
            kept.append((pat, imp))
            continue
        if matches:
            skipped.append(
                {
                    "improvement": imp,
                    "pattern": pat_name,
                    "matched_prior": [
                        {
                            "similarity": m["_similarity"],
                            "hypothesis": m["hypothesis"],
                            "outcome": m["outcome"],
                        }
                        for m in matches[:3]
                    ],
                    "reason": "paraphrase of prior rejected attempt — anti-brainrot filter",
                }
            )
        else:
            kept.append((pat, imp))
    return kept, skipped
