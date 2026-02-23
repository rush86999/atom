#!/usr/bin/env python3
"""
Quality Gate Validator - Enforces test quality standards before merge.

Quality Gate Rules:
- 100% pass rate required on 3 consecutive CI runs
- Failed tests reset consecutive run counter
- Pass rate tracked in history file for trend analysis

Usage:
    python quality_gate.py <pytest_report.json> [options]

Options:
    --threshold FLOAT   Pass rate threshold (default: 1.0)
    --consecutive INT   Required consecutive runs (default: 3)
    --history FILE      History file path (default: data/quality_gate_history.json)
    --reset             Reset history and start fresh

Exit codes:
    0: Quality gate PASSED
    1: Quality gate FAILED
    2: Error occurred
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.pass_rate_validator import PassRateValidator


class QualityGate:
    """Manages quality gate validation with consecutive run tracking."""

    def __init__(self, history_file: str, threshold: float = 1.0, consecutive: int = 3):
        """
        Initialize quality gate.

        Args:
            history_file: Path to history JSON file
            threshold: Pass rate threshold (default: 1.0 = 100%)
            consecutive: Required consecutive passing runs (default: 3)
        """
        self.history_file = Path(history_file)
        self.threshold = threshold
        self.consecutive_required = consecutive
        self.history = self._load_history()

    def _load_history(self) -> dict:
        """Load quality gate history from file."""
        if self.history_file.exists():
            with open(self.history_file, 'r') as f:
                return json.load(f)
        return {
            "runs": [],
            "consecutive_passes": 0,
            "last_gate_status": "pending",
            "created_at": datetime.now().isoformat()
        }

    def _save_history(self) -> None:
        """Save quality gate history to file."""
        self.history["updated_at"] = datetime.now().isoformat()
        self.history_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.history_file, 'w') as f:
            json.dump(self.history, f, indent=2)

    def validate(self, report_file: str) -> tuple[bool, str]:
        """
        Validate quality gate against pytest report.

        Args:
            report_file: Path to pytest JSON report

        Returns:
            Tuple of (passed: bool, message: str)
        """
        validator = PassRateValidator(gate_threshold=self.threshold)
        passed, gate_message = validator.validate_pytest_report(report_file)
        result = validator.calculate_from_report(report_file)

        # Record this run
        run_record = {
            "timestamp": datetime.now().isoformat(),
            "pass_rate": result.pass_rate,
            "passed": result.passed,
            "failed": result.failed,
            "errors": result.errors,
            "gate_passed": passed
        }
        self.history["runs"].append(run_record)

        # Update consecutive counter
        if passed:
            self.history["consecutive_passes"] += 1
        else:
            self.history["consecutive_passes"] = 0

        # Check if quality gate met
        gate_passed = self.history["consecutive_passes"] >= self.consecutive_required
        self.history["last_gate_status"] = "passed" if gate_passed else "failed"

        # Save history
        self._save_history()

        # Generate message
        if gate_passed:
            message = (
                f"Quality gate PASSED: {self.history['consecutive_passes']} consecutive "
                f"100% pass rate runs (required: {self.consecutive_required})"
            )
        else:
            remaining = self.consecutive_required - self.history["consecutive_passes"]
            message = (
                f"Quality gate PENDING: {self.history['consecutive_passes']}/{self.consecutive_required} "
                f"consecutive passes, {remaining} more run(s) required"
            )

        return gate_passed, message

    def reset(self) -> None:
        """Reset quality gate history."""
        self.history = {
            "runs": [],
            "consecutive_passes": 0,
            "last_gate_status": "pending",
            "created_at": datetime.now().isoformat(),
            "reset_at": datetime.now().isoformat()
        }
        self._save_history()

    def get_status(self) -> dict:
        """Get current quality gate status."""
        return {
            "consecutive_passes": self.history["consecutive_passes"],
            "required": self.consecutive_required,
            "status": self.history["last_gate_status"],
            "total_runs": len(self.history["runs"])
        }

    def format_report(self) -> str:
        """Format quality gate status report."""
        status = self.get_status()
        lines = [
            "=" * 60,
            "QUALITY GATE STATUS",
            "=" * 60,
            f"Consecutive passes: {status['consecutive_passes']}/{status['required']}",
            f"Total runs tracked: {status['total_runs']}",
            f"Gate status: {status['status'].upper()}",
            "=" * 60,
        ]

        # Show recent runs
        if self.history["runs"]:
            lines.append("")
            lines.append("Recent runs:")
            for run in self.history["runs"][-5:]:
                status_symbol = "PASS" if run["gate_passed"] else "FAIL"
                lines.append(
                    f"  [{run['timestamp']}] {status_symbol} - "
                    f"{run['pass_rate']:.1%} ({run['passed']} passed, {run['failed']} failed)"
                )

        return "\n".join(lines)


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Validate test quality gate"
    )
    parser.add_argument(
        "report_file",
        nargs='?',
        help="Path to pytest JSON report (not required for --status-only or --reset)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=1.0,
        help="Pass rate threshold (default: 1.0)"
    )
    parser.add_argument(
        "--consecutive",
        type=int,
        default=3,
        help="Required consecutive passing runs (default: 3)"
    )
    parser.add_argument(
        "--history",
        type=str,
        default="backend/tests/e2e_ui/data/quality_gate_history.json",
        help="History file path"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Reset history and start fresh"
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Only show current status, don't validate"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    gate = QualityGate(
        history_file=args.history,
        threshold=args.threshold,
        consecutive=args.consecutive
    )

    # Handle reset
    if args.reset:
        gate.reset()
        print("Quality gate history reset")
        print(gate.format_report())
        return 0

    # Validate against report
    if not args.status_only and not args.reset:
        if not args.report_file:
            print("Error: report_file is required unless using --status-only or --reset", file=sys.stderr)
            return 2

        if not Path(args.report_file).exists():
            print(f"Error: Report file '{args.report_file}' not found", file=sys.stderr)
            return 2

    # Handle status-only
    if args.status_only:
        print(gate.format_report())
        return 0

    passed, message = gate.validate(args.report_file)

    print(message)
    print()
    print(gate.format_report())

    return 0 if passed else 1


if __name__ == "__main__":
    sys.exit(main())
