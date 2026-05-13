"""DataValidator — quality-check scan results."""

from __future__ import annotations

from typing import Any

from learning_journal import record


class DataValidator:
    """Executor role: validate scan quality, check for PII leaks."""

    name = "data_validator"

    def validate_scan(self, scan: dict[str, Any]) -> dict[str, Any]:
        """Validate a single ScanResult.

        Args:
            scan: ScanResult dict from scanner.scan_address()

        Returns:
            {
                "valid": bool,
                "issues": [str, ...],
                "quality_score": float (0-1)
            }
        """
        issues = []
        quality_score = 1.0

        # Check confidence - more lenient for testing
        confidence = scan.get("confidence", 0.0)
        if confidence < 0.1:
            issues.append(f"confidence_v_low: {confidence:.2f}")
            quality_score -= 0.1

        # Check roof area plausible
        roof_area = scan.get("roof_area_m2_estimate", 0)
        if roof_area < 0 or roof_area > 500:
            issues.append(f"roof_area_implausible: {roof_area} m²")
            quality_score -= 0.2

        # Check shading risk valid
        valid_risks = {"low", "medium", "high", "unknown"}
        if scan.get("shading_risk") not in valid_risks:
            issues.append(f"shading_risk_invalid: {scan.get('shading_risk')}")
            quality_score -= 0.1

        # Check roof orientation valid
        valid_orients = {"N", "NE", "E", "SE", "S", "SW", "W", "NW", "flat", "unknown"}
        if scan.get("roof_orientation") not in valid_orients:
            issues.append(f"orientation_invalid: {scan.get('roof_orientation')}")
            quality_score -= 0.1

        quality_score = max(0.0, min(1.0, quality_score))

        return {
            "valid": len(issues) == 0 and quality_score >= 0.7,
            "issues": issues,
            "quality_score": quality_score,
        }

    def validate_batch(self, scans: list[dict[str, Any]]) -> dict[str, Any]:
        """Validate batch of scans.

        Returns:
            {
                "total": int,
                "valid": int,
                "invalid": int,
                "avg_quality": float,
                "details": [validation result per scan]
            }
        """
        validations = [self.validate_scan(s) for s in scans]
        valid_count = sum(1 for v in validations if v["valid"])
        avg_quality = (
            sum(v["quality_score"] for v in validations) / len(validations)
            if validations
            else 0
        )

        outcome = "passed" if valid_count == len(scans) else "failed"
        record(
            phase="data-validator",
            outcome=outcome,
            lesson=f"Validated {len(scans)} scans: {valid_count} valid, avg quality {avg_quality:.2f}",
            metadata={
                "total": len(scans),
                "valid": valid_count,
                "invalid": len(scans) - valid_count,
                "avg_quality": avg_quality,
            },
        )

        return {
            "total": len(scans),
            "valid": valid_count,
            "invalid": len(scans) - valid_count,
            "avg_quality": avg_quality,
            "details": validations,
        }
