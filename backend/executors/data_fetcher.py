"""DataFetcher — continuously scan new addresses."""

from __future__ import annotations

from typing import Any

from learning_journal import record
from services import scanner


class DataFetcher:
    """Executor role: scan addresses, extract roof/panel data."""

    name = "data_fetcher"

    async def fetch_batch(self, addresses: list[str]) -> dict[str, Any]:
        """Scan batch of addresses.

        Args:
            addresses: List of Swedish addresses

        Returns:
            {
                "scanned": int,
                "results": [ScanResult, ...],
                "errors": [{"address": str, "error": str}, ...]
            }
        """
        results = []
        errors = []

        for addr in addresses:
            try:
                result = await scanner.scan_address(addr)
                results.append(result)
            except Exception as e:
                from error_logger import log_error
                log_error(
                    "executor-data-fetcher-scan",
                    e,
                    context={"address": addr},
                )
                errors.append({"address": addr, "error": str(e)})

        outcome = "passed" if results else "failed"
        record(
            phase="data-fetcher",
            outcome=outcome,
            lesson=f"Fetched {len(results)} addresses, {len(errors)} errors",
            metadata={
                "requested": len(addresses),
                "scanned": len(results),
                "errors": len(errors),
                "avg_confidence": (
                    sum(r["confidence"] for r in results) / len(results) if results else 0
                ),
            },
        )

        return {
            "scanned": len(results),
            "results": results,
            "errors": errors,
        }
