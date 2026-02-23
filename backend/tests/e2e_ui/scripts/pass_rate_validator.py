"""
Pass Rate Validator - Calculates and validates test pass rates.

Usage:
    from scripts.pass_rate_validator import PassRateValidator

    validator = PassRateValidator()
    result = validator.validate_pytest_report("pytest_report.json")
    print(f"Pass rate: {result.pass_rate:.1%}")
"""
import json
from dataclasses import dataclass
from pathlib import Path
from typing import Dict, Optional, Tuple


@dataclass
class PassRateResult:
    """Result of pass rate calculation."""
    total: int
    passed: int
    failed: int
    skipped: int
    errors: int
    pass_rate: float
    passed_gate: bool
    gate_threshold: float


class PassRateValidator:
    """Calculates and validates test pass rates."""

    def __init__(self, gate_threshold: float = 1.0):
        """
        Initialize validator.

        Args:
            gate_threshold: Pass rate required for quality gate (default: 1.0 = 100%)
        """
        self.gate_threshold = gate_threshold

    def calculate_from_report(self, report_file: str) -> PassRateResult:
        """
        Calculate pass rate from pytest JSON report.

        Args:
            report_file: Path to pytest JSON report

        Returns:
            PassRateResult with calculated metrics
        """
        report_path = Path(report_file)
        if not report_path.exists():
            raise FileNotFoundError(f"Report file not found: {report_file}")

        with open(report_path, 'r') as f:
            report = json.load(f)

        summary = report.get("summary", {})
        total = summary.get("total", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        skipped = summary.get("skipped", 0)
        errors = summary.get("error", 0)

        # Calculate pass rate: passed / (passed + failed + errors)
        # Skipped tests are excluded from pass rate calculation
        attempted = passed + failed + errors
        pass_rate = passed / attempted if attempted > 0 else 1.0

        # Check if gate passed
        passed_gate = pass_rate >= self.gate_threshold

        return PassRateResult(
            total=total,
            passed=passed,
            failed=failed,
            skipped=skipped,
            errors=errors,
            pass_rate=pass_rate,
            passed_gate=passed_gate,
            gate_threshold=self.gate_threshold
        )

    def validate_pytest_report(self, report_file: str) -> Tuple[bool, str]:
        """
        Validate pytest report against quality gate.

        Args:
            report_file: Path to pytest JSON report

        Returns:
            Tuple of (passed: bool, message: str)
        """
        try:
            result = self.calculate_from_report(report_file)

            if result.passed_gate:
                attempted = result.passed + result.failed + result.errors
                msg = (
                    f"Quality gate PASSED: {result.pass_rate:.1%} pass rate "
                    f"({result.passed}/{attempted} tests)"
                )
                return True, msg
            else:
                msg = (
                    f"Quality gate FAILED: {result.pass_rate:.1%} pass rate "
                    f"(required: {result.gate_threshold:.0%}), "
                    f"{result.failed} failed, {result.errors} errors"
                )
                return False, msg

        except Exception as e:
            msg = f"Error validating report: {e}"
            return False, msg

    def format_summary(self, result: PassRateResult) -> str:
        """Format pass rate result as human-readable summary."""
        lines = [
            "=" * 50,
            "PASS RATE SUMMARY",
            "=" * 50,
            f"Total tests: {result.total}",
            f"Passed: {result.passed}",
            f"Failed: {result.failed}",
            f"Skipped: {result.skipped}",
            f"Errors: {result.errors}",
            "",
            f"Pass rate: {result.pass_rate:.1%}",
            f"Gate threshold: {result.gate_threshold:.0%}",
            f"Quality gate: {'PASSED' if result.passed_gate else 'FAILED'}",
            "=" * 50,
        ]
        return "\n".join(lines)


if __name__ == "__main__":
    import sys

    if len(sys.argv) != 2:
        print("Usage: pass_rate_validator.py <pytest_report.json>", file=sys.stderr)
        sys.exit(2)

    report_file = sys.argv[1]
    validator = PassRateValidator(gate_threshold=1.0)  # 100% required
    passed, message = validator.validate_pytest_report(report_file)

    print(message)

    # Print detailed summary
    result = validator.calculate_from_report(report_file)
    print()
    print(validator.format_summary(result))

    sys.exit(0 if passed else 1)
