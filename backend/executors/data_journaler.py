"""DataJournaler — log all scan + enrichment outcomes."""

from __future__ import annotations

from learning_journal import record


class DataJournaler:
    """Executor role: record all data gathering + validation outcomes to journal."""

    name = "data_journaler"

    def journal_scan_batch(
        self,
        *,
        scanned: int,
        valid: int,
        avg_confidence: float,
        enrichment_rate: float = 0.0,
    ) -> None:
        """Record scan batch outcome.

        Args:
            scanned: Number of addresses scanned
            valid: Number passing validation
            avg_confidence: Average detection confidence
            enrichment_rate: % of scans enriched with mrkoll data
        """
        outcome = "passed" if valid == scanned and scanned > 0 else "failed"
        valid_pct = (100 * valid // scanned) if scanned > 0 else 0
        lesson = f"Scanned {scanned} addresses, {valid} valid ({valid_pct}%), avg confidence {avg_confidence:.2f}"

        record(
            phase="data-gathering",
            outcome=outcome,
            lesson=lesson,
            metadata={
                "scanned": scanned,
                "valid": valid,
                "invalid": scanned - valid,
                "avg_confidence": avg_confidence,
                "enrichment_rate": enrichment_rate,
            },
        )

    def journal_enrichment_batch(
        self,
        *,
        total: int,
        enriched: int,
        errors: int,
    ) -> None:
        """Record enrichment (mrkoll/birthday) outcome."""
        outcome = "passed" if errors == 0 else "partial"
        lesson = f"Enriched {enriched}/{total} addresses ({100*enriched//total if total else 0}%)"

        record(
            phase="enrichment",
            outcome=outcome,
            lesson=lesson,
            metadata={
                "total": total,
                "enriched": enriched,
                "errors": errors,
                "rate": enriched / total if total else 0,
            },
        )

    def journal_skipped_paraphrase(
        self,
        *,
        pattern: str,
        target: str,
        enhancement: str,
        matched_prior: list[dict],
    ) -> None:
        """Record that we blocked an improvement because it paraphrases a prior rejected attempt.

        This is the signal that the anti-brainrot filter is earning its keep —
        each entry = one Gemini cycle we didn't burn on a known-dead idea.
        """
        top = matched_prior[0] if matched_prior else {}
        lesson = (
            f"Skipped paraphrase for {pattern} → {target}: "
            f"similarity {top.get('similarity', 0):.2f} to prior '{str(top.get('hypothesis', ''))[:60]}...' "
            f"({top.get('outcome', '?')})"
        )
        record(
            phase="autonomous-improve-skip",
            outcome="passed",  # "passed" = filter worked as intended
            lesson=lesson,
            metadata={
                "pattern": pattern,
                "target": target,
                "enhancement": enhancement,
                "matched_prior": matched_prior,
                "reason": "paraphrase-of-prior-rejected",
            },
        )

    def journal_infra_degradation(
        self,
        *,
        pattern: str,
        target: str,
        llm_errors: list[str],
    ) -> None:
        """Record that an improvement cycle was SKIPPED due to transient infra
        failure (Gemini 429, network error). Crucial signal: the ledger
        intentionally was NOT written for this cycle — next cycle retries clean
        once infra recovers. Dashboards can count these to show quota impact.
        """
        record(
            phase="autonomous-improve-infra-skip",
            outcome="error",
            lesson=f"Infra-degraded cycle for {pattern} → {target}: {','.join(llm_errors)}. Ledger not written, will retry.",
            metadata={
                "pattern": pattern,
                "target": target,
                "llm_errors": llm_errors,
                "reason": "transient-llm-failure-skip-ledger",
            },
        )

    def journal_improvement(
        self,
        *,
        target: str,
        enhancement: str,
        agent_votes: dict[str, float],
        applied: bool,
    ) -> None:
        """Record autonomous improvement attempt."""
        avg_confidence = sum(agent_votes.values()) / len(agent_votes) if agent_votes else 0
        outcome = "passed" if applied else "rejected"
        lesson = f"Improvement to {target}: {enhancement[:50]}... (consensus {avg_confidence:.0%})"

        record(
            phase="autonomous-improve",
            outcome=outcome,
            lesson=lesson,
            metadata={
                "target": target,
                "enhancement": enhancement,
                "agent_votes": agent_votes,
                "consensus": avg_confidence,
                "applied": applied,
            },
        )
