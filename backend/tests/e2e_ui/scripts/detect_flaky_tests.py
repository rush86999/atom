#!/usr/bin/env python3
"""
Detect flaky tests from pytest JSON report.

Usage:
    python detect_flaky_tests.py <pytest_report.json> [options]

Options:
    --threshold FLOAT   Pass rate threshold (default: 0.8)
    --min-runs INT      Minimum runs before considering (default: 3)
    --last-n INT        Only consider last N runs (default: all)
    --output FILE       Output file for flaky test report (default: stdout)

Exit codes:
    0: No flaky tests found
    1: Flaky tests detected
    2: Error occurred
"""
import argparse
import json
import sys
from pathlib import Path

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent))

from scripts.flaky_test_tracker import FlakyTestTracker


def parse_args():
    """Parse command line arguments."""
    parser = argparse.ArgumentParser(
        description="Detect flaky tests from pytest JSON report"
    )
    parser.add_argument(
        "report_file",
        help="Path to pytest JSON report file"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Pass rate threshold (default: 0.8)"
    )
    parser.add_argument(
        "--min-runs",
        type=int,
        default=3,
        help="Minimum runs before considering test (default: 3)"
    )
    parser.add_argument(
        "--last-n",
        type=int,
        default=None,
        help="Only consider last N runs (default: all)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for flaky test report (default: stdout)"
    )
    parser.add_argument(
        "--data-file",
        type=str,
        default="backend/tests/e2e_ui/data/flaky_tests.json",
        help="Flaky test tracker data file"
    )
    return parser.parse_args()


def main():
    """Main entry point."""
    args = parse_args()

    # Verify report file exists
    if not Path(args.report_file).exists():
        print(f"Error: Report file '{args.report_file}' not found", file=sys.stderr)
        return 2

    # Update tracker with current report
    tracker = FlakyTestTracker(data_file=args.data_file)
    try:
        tracker.update_from_pytest_report(args.report_file)
    except Exception as e:
        print(f"Error updating tracker: {e}", file=sys.stderr)
        return 2

    # Get flaky tests
    flaky_tests = tracker.get_flaky_tests(
        pass_threshold=args.threshold,
        min_runs=args.min_runs,
        last_n_runs=args.last_n
    )

    # Generate report
    report_lines = []
    report_lines.append("=" * 60)
    report_lines.append("FLAKY TEST DETECTION REPORT")
    report_lines.append("=" * 60)
    report_lines.append(f"Threshold: {args.threshold:.0%} pass rate")
    report_lines.append(f"Minimum runs: {args.min_runs}")
    report_lines.append("")

    if flaky_tests:
        report_lines.append(f"Found {len(flaky_tests)} FLAKY TESTS:")
        report_lines.append("")

        for i, test in enumerate(flaky_tests, 1):
            report_lines.append(f"{i}. {test['test']}")
            report_lines.append(f"   Pass rate: {test['pass_rate']:.1%} ({test['passed']}/{test['total_runs']} runs)")
            report_lines.append(f"   Last outcome: {test['last_outcome']}")
            report_lines.append("")

        # Summary
        summary = tracker.get_summary()
        report_lines.append("-" * 60)
        report_lines.append(f"Total tests tracked: {summary['total_tests']}")
        report_lines.append(f"Total CI runs: {summary['total_runs']}")
        report_lines.append(f"Flaky tests: {len(flaky_tests)}")
        report_lines.append("=" * 60)

        report_text = "\n".join(report_lines)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(report_text)
            print(f"Report written to {args.output}")
        else:
            print(report_text)

        return 1  # Exit code 1 = flaky tests found

    else:
        report_lines.append("No flaky tests detected!")
        report_lines.append("")

        summary = tracker.get_summary()
        report_lines.append(f"Total tests tracked: {summary['total_tests']}")
        report_lines.append(f"Total CI runs: {summary['total_runs']}")
        report_lines.append("=" * 60)

        report_text = "\n".join(report_lines)

        if args.output:
            with open(args.output, 'w') as f:
                f.write(report_text)
            print(f"Report written to {args.output}")
        else:
            print(report_text)

        return 0  # Exit code 0 = no flaky tests


if __name__ == "__main__":
    sys.exit(main())
