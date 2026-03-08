#!/usr/bin/env python3
"""
Track Test Execution Times

Parses pytest --durations output and updates flaky test tracker with
execution time metrics for slow test detection.

Usage:
    pytest tests/ --durations=10 | python track_execution_times.py --platform backend
    python track_execution_times.py --durations-file durations.txt --quarantine-db flaky_tests.db --platform backend
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Optional

# Add parent directory to path for imports
sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from tests.scripts.flaky_test_tracker import FlakyTestTracker


def parse_durations_output(durations_text: str) -> Dict[str, float]:
    """Parse pytest --durations output format.

    Args:
        durations_text: pytest --durations output text

    Returns:
        Dict mapping test_path -> execution_time (float in seconds)

    Example pytest --durations output:
        10.01s call     tests/test_foo.py::test_bar
        5.23s  call     tests/test_baz.py::test_qux
    """
    durations_dict = {}

    # Regex pattern: duration (float) + 's' + phase (call/setup/teardown) + test_path
    pattern = r'(\d+\.\d+)s\s+(?:call|setup|teardown)\s+([^\s]+)'

    for match in re.finditer(pattern, durations_text):
        execution_time = float(match.group(1))
        test_path = match.group(2)

        # Store execution time (use max if multiple entries)
        if test_path not in durations_dict or execution_time > durations_dict[test_path]:
            durations_dict[test_path] = execution_time

    return durations_dict


def update_execution_times(
    durations_dict: Dict[str, float],
    platform: str,
    db_path: Path
) -> int:
    """Update execution times in flaky test tracker.

    Args:
        durations_dict: Dict mapping test_path -> execution_time
        platform: Platform name (backend/frontend/mobile/desktop)
        db_path: Path to flaky_tests.db

    Returns:
        Number of tests updated
    """
    tracker = FlakyTestTracker(db_path)
    updated_count = 0

    try:
        for test_path, execution_time in durations_dict.items():
            # Check if test exists in flaky_tests table
            test_record = tracker.get_test_history(test_path, platform)

            if test_record:
                # Update execution times (convert to list for update_execution_time)
                execution_times = [execution_time]
                success = tracker.update_execution_time(test_path, platform, execution_times)
                if success:
                    updated_count += 1
            # If test doesn't exist, skip (only track times for tests already in quarantine)

    finally:
        tracker.close()

    return updated_count


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(
        description="Track test execution times from pytest --durations output",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Parse from stdin (pipe from pytest)
  pytest tests/ --durations=10 | python track_execution_times.py --platform backend

  # Parse from file
  python track_execution_times.py \\
    --durations-file test_durations.txt \\
    --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \\
    --platform backend

  # Custom slow threshold
  python track_execution_times.py \\
    --durations-file test_durations.txt \\
    --quarantine-db flaky_tests.db \\
    --platform backend \\
    --slow-threshold 15.0
        """
    )

    parser.add_argument(
        "--durations-file",
        type=Path,
        help="Path to pytest durations output file (if not reading from stdin)"
    )

    parser.add_argument(
        "--quarantine-db",
        type=Path,
        default="tests/coverage_reports/metrics/flaky_tests.db",
        help="Path to flaky_tests.db (default: tests/coverage_reports/metrics/flaky_tests.db)"
    )

    parser.add_argument(
        "--platform",
        type=str,
        required=True,
        choices=["backend", "frontend", "mobile", "desktop"],
        help="Platform name (backend/frontend/mobile/desktop)"
    )

    parser.add_argument(
        "--slow-threshold",
        type=float,
        default=10.0,
        help="Slow test threshold in seconds (default: 10.0)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        help="Optional JSON output file for slow tests list"
    )

    args = parser.parse_args()

    # Read durations input
    if args.durations_file:
        # Read from file
        if not args.durations_file.exists():
            print(f"ERROR: Durations file not found: {args.durations_file}", file=sys.stderr)
            return 2

        with open(args.durations_file) as f:
            durations_text = f.read()
    else:
        # Read from stdin
        durations_text = sys.stdin.read()

    # Parse durations
    durations_dict = parse_durations_output(durations_text)

    if not durations_dict:
        print("WARNING: No test durations found in input", file=sys.stderr)
        return 0

    # Update tracker
    updated_count = update_execution_times(durations_dict, args.platform, args.quarantine_db)

    # Get slow tests
    tracker = FlakyTestTracker(args.quarantine_db)
    try:
        slow_tests = tracker.get_slow_tests(
            min_time=args.slow_threshold,
            platform=args.platform,
            limit=50
        )
    finally:
        tracker.close()

    # Calculate statistics
    total_times = list(durations_dict.values())
    avg_time = sum(total_times) / len(total_times) if total_times else 0.0
    slow_count = len(slow_tests)

    # Print summary
    print(f"\nExecution Time Tracking")
    print(f"=" * 50)
    print(f"Platform: {args.platform}")
    print(f"Total tests tracked: {updated_count}")
    print(f"Average execution time: {avg_time:.2f}s")
    print(f"Slow tests (>{args.slow_threshold}s): {slow_count}")

    if slow_tests:
        print(f"\nTop 10 Slowest Tests:")
        for test in slow_tests[:10]:
            name = test["test_path"].split("::")[-1]
            avg = test.get("avg_execution_time", 0)
            max_time = test.get("max_execution_time", 0)
            print(f"  - {name} (avg: {avg:.1f}s, max: {max_time:.1f}s)")
        if len(slow_tests) > 10:
            print(f"  ... and {len(slow_tests) - 10} more")

    # Write output if specified
    if args.output:
        output_data = {
            "platform": args.platform,
            "slow_threshold": args.slow_threshold,
            "total_tests_updated": updated_count,
            "average_execution_time": round(avg_time, 2),
            "slow_test_count": slow_count,
            "slow_tests": slow_tests
        }

        args.output.parent.mkdir(parents=True, exist_ok=True)
        with open(args.output, "w") as f:
            json.dump(output_data, f, indent=2)

        print(f"\nOutput written to: {args.output}")

    # Exit code: 0 if no slow tests, 1 if slow tests found
    return 0 if slow_count == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
