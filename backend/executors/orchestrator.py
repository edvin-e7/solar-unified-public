"""Orchestrator — coordinate 8 executor roles in continuous cycle."""

from __future__ import annotations

from typing import Any

from error_logger import log_error
from issue_ledger import log_attempt, open_issue

from executors.auto_applicator import AutoApplicator
from executors.collective_verifier import CollectiveVerifier
from executors.data_fetcher import DataFetcher
from executors.data_journaler import DataJournaler
from executors.data_validator import DataValidator
from executors.enrichment_executor import EnrichmentExecutor
from executors.improvement_generator import ImprovementGenerator
from executors.pattern_detector import PatternDetector


class Orchestrator:
    """Coordinate all 8 executors in autonomous improvement cycle."""

    def __init__(self) -> None:
        self.data_fetcher = DataFetcher()
        self.enrichment = EnrichmentExecutor()
        self.validator = DataValidator()
        self.journaler = DataJournaler()
        self.pattern_detector = PatternDetector()
        self.improvement_gen = ImprovementGenerator()
        self.collective_verify = CollectiveVerifier()
        self.auto_apply = AutoApplicator()

    async def run_data_gathering_cycle(self, addresses: list[str]) -> dict[str, Any]:
        """Execute Priority 1: Gather data from addresses.

        Flow:
        1. DataFetcher scans addresses
        2. EnrichmentExecutor enriches with mrkoll
        3. DataValidator checks quality
        4. DataJournaler logs outcomes
        """
        # Scan addresses
        scan_result = await self.data_fetcher.fetch_batch(addresses)

        # Validate scans
        validations = self.validator.validate_batch(scan_result["results"])

        # Enrich with person data (mrkoll)
        enrich_result = await self.enrichment.enrich_batch(addresses)

        # Journal results
        valid_count = validations["valid"]
        self.journaler.journal_scan_batch(
            scanned=len(addresses),
            valid=valid_count,
            avg_confidence=validations["avg_quality"],
            enrichment_rate=enrich_result.get("rate", 0),
        )

        return {
            "phase": "data-gathering",
            "scanned": len(addresses),
            "valid": valid_count,
            "enrichment_rate": enrich_result.get("rate", 0),
            "journal_logged": True,
        }

    async def run_learning_cycle(self) -> dict[str, Any]:
        """Execute Priority 2: Autonomous learning & improvement.

        Flow:
        1. PatternDetector analyzes journal
        2. ImprovementGenerator creates suggestions
        3. CollectiveVerifier has agents vote (≥75%)
        4. AutoApplicator commits approved changes
        """
        # Detect patterns
        patterns_result = self.pattern_detector.detect_patterns(lookback=100)
        if not patterns_result["patterns"]:
            return {
                "phase": "autonomous-learning",
                "patterns_found": 0,
                "improvements_applied": 0,
            }

        # Generate improvements
        improvements = self.improvement_gen.generate_improvements(
            patterns_result["patterns"]
        )

        # Journal blocked paraphrases — one entry per skip so the filter's work is visible.
        for skip in improvements.get("skipped_already_tried", []):
            imp = skip.get("improvement", {})
            self.journaler.journal_skipped_paraphrase(
                pattern=skip.get("pattern", ""),
                target=imp.get("target", ""),
                enhancement=imp.get("enhancement", ""),
                matched_prior=skip.get("matched_prior", []),
            )

        # Verify & apply — each (pattern, improvement) pair writes the ledger
        # so the anti-brainrot filter has a growing corpus to match against.
        applied_count = 0
        infra_degraded_count = 0
        for pat, improvement in improvements.get("kept_tagged", []):
            issue_key = self._safe_open_issue(pat, improvement)
            verification = await self.collective_verify.verify_improvement(improvement)

            if verification.get("llm_errors"):
                # Transient infra failure (Gemini 429 etc.) — journal it but
                # DO NOT write the ledger. A ledger entry here would poison the
                # filter: next cycle would treat this improvement as "already
                # tried" even though we never actually verified it.
                infra_degraded_count += 1
                self.journaler.journal_infra_degradation(
                    pattern=pat.get("name", ""),
                    target=improvement.get("target", ""),
                    llm_errors=verification["llm_errors"],
                )
                continue

            if not verification.get("verified"):
                self._safe_log_attempt(
                    key=issue_key,
                    improvement=improvement,
                    outcome="rejected_by_cove",
                    evidence={
                        "confidence": verification.get("confidence"),
                        "reasoning": verification.get("reasoning"),
                    },
                )
                continue

            apply_result = self.auto_apply.apply_improvement(improvement, verification)
            if apply_result.get("applied"):
                applied_count += 1
                self.journaler.journal_improvement(
                    target=improvement.get("target", ""),
                    enhancement=improvement.get("enhancement", ""),
                    agent_votes=verification.get("agent_votes", {}),
                    applied=True,
                )
                self._safe_log_attempt(
                    key=issue_key,
                    improvement=improvement,
                    outcome="success",
                    evidence={
                        "commit": apply_result.get("commit"),
                        "confidence": verification.get("confidence"),
                    },
                )
            else:
                self._safe_log_attempt(
                    key=issue_key,
                    improvement=improvement,
                    outcome="failed",
                    evidence={
                        "apply_error": apply_result.get("reason"),
                        "confidence": verification.get("confidence"),
                    },
                )

        return {
            "phase": "autonomous-learning",
            "patterns_found": patterns_result["patterns_found"],
            "improvements_generated": improvements["improvements_generated"],
            "improvements_applied": applied_count,
            "skipped_already_tried": len(improvements.get("skipped_already_tried", [])),
            "infra_degraded": infra_degraded_count,
        }

    def _safe_open_issue(
        self,
        pattern: dict[str, Any],
        improvement: dict[str, Any],
    ) -> str | None:
        """open_issue wrapper — write failures must not crash the cycle."""
        try:
            return open_issue(
                error_type=pattern.get("name", ""),
                target=improvement.get("target", ""),
                title=improvement.get("enhancement", "")[:80],
                tags=[improvement.get("type", "unknown")],
                evidence={"pattern_frequency": pattern.get("frequency")},
            )
        except Exception as exc:
            log_error(
                "orchestrator-open-issue",
                exc,
                context={
                    "pattern": pattern.get("name"),
                    "target": improvement.get("target"),
                },
            )
            return None

    def _safe_log_attempt(
        self,
        *,
        key: str | None,
        improvement: dict[str, Any],
        outcome: str,
        evidence: dict[str, Any],
    ) -> None:
        """log_attempt wrapper — write failures must not crash the cycle."""
        if not key:
            return
        try:
            log_attempt(
                key=key,
                hypothesis=improvement.get("enhancement", ""),
                change_summary=improvement.get("rationale", ""),
                outcome=outcome,  # type: ignore[arg-type]
                evidence=evidence,
            )
        except Exception as exc:
            log_error(
                "orchestrator-log-attempt",
                exc,
                context={
                    "key": key,
                    "outcome": outcome,
                    "target": improvement.get("target"),
                },
            )

    async def run_full_cycle(self, addresses: list[str] | None = None) -> dict[str, Any]:
        """Run complete autonomous cycle: gather data → learn → improve.

        Args:
            addresses: List of addresses to scan (if None, skip data gathering)

        Returns:
            Cycle results
        """
        results = {
            "cycle_type": "full",
            "data_gathering": None,
            "autonomous_learning": None,
        }

        # Phase 1: Data Gathering (if addresses provided)
        if addresses:
            results["data_gathering"] = await self.run_data_gathering_cycle(addresses)

        # Phase 2: Autonomous Learning (always run)
        results["autonomous_learning"] = await self.run_learning_cycle()

        return results
