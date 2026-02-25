#!/usr/bin/env python
"""
Flaky Test Detection Script for Atom Test Suite

This script identifies flaky tests by running tests multiple times with different
random seeds and recording which tests fail intermittently.

Flaky tests are those that:
  - Fail in some runs but pass in others (inconsistent behavior)
  - Often indicate race conditions, timing issues, or shared state problems

Usage:
    python detect_flaky_tests.py --runs 3 --update-json
    python detect_flaky_tests.py --help

Exit Codes:
    0: No flaky tests detected
    1: Flaky tests found
    2: Error in execution
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Set, Tuple


def run_tests_with_seed(seed: int, test_path: str = "tests/", verbose: bool = False) -> Set[str]:
    """
    Run pytest with a specific random seed and return failed test names.

    Args:
        seed: Random seed for test order randomization
        test_path: Path to tests directory
        verbose: Enable verbose output

    Returns:
        Set of failed test names
    """
    cmd = [
        "python3", "-m", "pytest",
        test_path,
        "-q",
        "--random-order-seed", str(seed),
        "--tb=no",
        "--no-header"
    ]

    if verbose:
        print(f"\nRunning: {' '.join(cmd)}")

    result = subprocess.run(
        cmd,
        capture_output=True,
        text=True,
        cwd=Path(__file__).parent.parent.parent
    )

    # Parse failed tests from output
    failed_tests = set()

    # pytest output format: "FAILED tests/test_module.py::test_function"
    for line in result.stdout.split('\n'):
        if line.startswith('FAILED '):
            test_name = line.split(' ', 1)[1].strip()
            failed_tests.add(test_name)

    if verbose:
        print(f"Failed tests (seed={seed}): {len(failed_tests)}")
        for test in failed_tests:
            print(f"  - {test}")

    return failed_tests


def parse_test_results(output: str) -> Set[str]:
    """
    Parse pytest output to extract failed test names.

    Args:
        output: Pytest stdout/stderr combined output

    Returns:
        Set of failed test names
    """
    failed_tests = set()

    for line in output.split('\n'):
        if line.startswith('FAILED '):
            test_name = line.split(' ', 1)[1].strip()
            failed_tests.add(test_name)

    return failed_tests


def compare_results(results_list: List[Set[str]]) -> Dict[str, int]:
    """
    Compare test results across multiple runs to count failures.

    Args:
        results_list: List of failed test sets from each run

    Returns:
        Dictionary mapping test name to failure count
    """
    failure_counts = {}

    for failed_set in results_list:
        for test_name in failed_set:
            if test_name not in failure_counts:
                failure_counts[test_name] = 0
            failure_counts[test_name] += 1

    return failure_counts


def identify_flaky(failure_counts: Dict[str, int], total_runs: int) -> Dict[str, float]:
    """
    Identify flaky tests from failure counts.

    Flaky tests fail in at least one run but not all runs.
    They exhibit inconsistent behavior across multiple runs.

    Args:
        failure_counts: Dictionary of test -> failure count
        total_runs: Total number of test runs

    Returns:
        Dictionary mapping flaky test to failure frequency (0-1)
    """
    flaky_tests = {}

    for test_name, failures in failure_counts.items():
        # Flaky: fails in some runs but not all (0 < failures < total_runs)
        if 0 < failures < total_runs:
            frequency = failures / total_runs
            flaky_tests[test_name] = frequency

    return flaky_tests


def update_health_json(flaky_tests: Dict[str, float], phase: str = "090", plan: str = "02") -> None:
    """
    Update test_health.json with flaky test entries.

    Args:
        flaky_tests: Dictionary of flaky test -> failure frequency
        phase: Current phase number
        plan: Current plan number
    """
    health_file = Path(__file__).parent.parent / "coverage_reports" / "metrics" / "test_health.json"

    # Load existing health data or create new structure
    if health_file.exists():
        try:
            with open(health_file, 'r') as f:
                health_data = json.load(f)
        except (json.JSONDecodeError, IOError):
            health_data = {}
    else:
        health_data = {}

    # Ensure structure exists
    if "flaky_tests" not in health_data:
        health_data["flaky_tests"] = []
    if "metadata" not in health_data:
        health_data["metadata"] = {}

    # Add current flaky test detection results
    timestamp = datetime.now().isoformat()
    for test_name, frequency in flaky_tests.items():
        entry = {
            "test_name": test_name,
            "failure_frequency": round(frequency, 2),
            "detected_date": timestamp,
            "phase": phase,
            "plan": plan
        }
        health_data["flaky_tests"].append(entry)

    # Update metadata
    health_data["metadata"]["format_version"] = 1
    health_data["metadata"]["last_flaky_scan"] = timestamp

    # Write back to file
    health_file.parent.mkdir(parents=True, exist_ok=True)
    with open(health_file, 'w') as f:
        json.dump(health_data, f, indent=2)


def print_summary(
    flaky_tests: Dict[str, float],
    total_runs: int,
    failure_counts: Dict[str, int],
    verbose: bool = False
) -> None:
    """
    Print formatted summary of flaky test detection.

    Args:
        flaky_tests: Dictionary of flaky test -> failure frequency
        total_runs: Total number of test runs
        failure_counts: All failure counts (including stable failures)
        verbose: Enable verbose output
    """
    print("\n" + "="*70)
    print("FLAKY TEST DETECTION")
    print("="*70)

    print(f"\nTest Runs: {total_runs}")
    print(f"Total Failed Tests (across all runs): {len(failure_counts)}")
    print(f"Flaky Tests (inconsistent failures): {len(flaky_tests)}")

    if flaky_tests:
        print("\n" + "-"*70)
        print("FLAKY TESTS DETECTED:")
        print("-"*70)

        # Sort by failure frequency (most frequent first)
        sorted_tests = sorted(
            flaky_tests.items(),
            key=lambda x: x[1],
            reverse=True
        )

        for test_name, frequency in sorted_tests:
            failure_pct = frequency * 100
            failure_count = int(frequency * total_runs)
            print(f"\n  {test_name}")
            print(f"    Failed {failure_count}/{total_runs} times ({failure_pct:.0f}%)")

        print("\n" + "="*70)
        print("STATUS: FLAKY TESTS FOUND ✗")
        print("="*70)
        print("\nRECOMMENDED ACTIONS:")
        print("  1. Investigate race conditions or timing dependencies")
        print("  2. Check for shared state between tests")
        print("  3. Add proper mocks for external dependencies")
        print("  4. Use unique_resource_name fixture for parallel isolation")
        print("  5. Mark with @pytest.mark.flaky as TEMPORARY workaround")
        print("="*70 + "\n")
    else:
        if failure_counts:
            print("\n" + "-"*70)
            print("STABLE FAILURES (not flaky):")
            print("-"*70)
            for test_name in failure_counts.keys():
                print(f"  - {test_name}")
            print("-"*70)

        print("\n" + "="*70)
        print("STATUS: NO FLAKY TESTS ✓")
        print("="*70 + "\n")

    if verbose and failure_counts:
        print("\nVerbose Output:")
        print("All Test Failures by Frequency:")
        for test_name, count in sorted(failure_counts.items(), key=lambda x: x[1], reverse=True):
            print(f"  {test_name}: {count}/{total_runs} failures")
        print()


def main():
    """Main entry point for flaky test detection."""
    parser = argparse.ArgumentParser(
        description="Detect flaky tests by running multiple times with random seeds",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python detect_flaky_tests.py --runs 3
  python detect_flaky_tests.py --runs 2 --update-json --verbose
  python detect_flaky_tests.py --runs 3 --test-path tests/unit/

Exit Codes:
  0: No flaky tests detected
  1: Flaky tests found
  2: Error in execution

How it works:
  1. Runs the test suite N times with different random seeds
  2. Records which tests fail in each run
  3. Identifies tests that fail inconsistently (not 0 or N failures)
  4. Updates test_health.json with flaky test entries

Flaky tests indicate:
  - Race conditions in parallel execution
  - Timing dependencies without proper mocking
  - Shared state between tests
  - Non-deterministic test data
        """
    )

    parser.add_argument(
        "--runs",
        type=int,
        default=3,
        help="Number of test runs (default: 3)"
    )

    parser.add_argument(
        "--test-path",
        type=str,
        default="tests/",
        help="Path to tests directory (default: tests/)"
    )

    parser.add_argument(
        "--update-json",
        action="store_true",
        help="Update test_health.json with flaky test entries"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--phase",
        type=str,
        default="090",
        help="Current phase number for health tracking (default: 090)"
    )

    parser.add_argument(
        "--plan",
        type=str,
        default="02",
        help="Current plan number for health tracking (default: 02)"
    )

    args = parser.parse_args()

    if args.runs < 2:
        print("ERROR: --runs must be at least 2 for flaky test detection")
        sys.exit(2)

    print("="*70)
    print(f"FLAKY TEST DETECTION: {args.runs} runs with random seeds")
    print("="*70)

    # Run tests multiple times with different seeds
    results_list = []
    for i in range(args.runs):
        seed = i * 1000  # Use different seeds: 0, 1000, 2000, ...
        print(f"\nRun {i+1}/{args.runs} (seed={seed})...", end=" ")

        failed_tests = run_tests_with_seed(seed, args.test_path, args.verbose)
        results_list.append(failed_tests)

        print(f"{len(failed_tests)} failed")

    # Compare results across runs
    failure_counts = compare_results(results_list)

    # Identify flaky tests (inconsistent failures)
    flaky_tests = identify_flaky(failure_counts, args.runs)

    # Print summary
    print_summary(flaky_tests, args.runs, failure_counts, args.verbose)

    # Update health JSON if requested
    if args.update_json and flaky_tests:
        update_health_json(flaky_tests, phase=args.phase, plan=args.plan)
        if args.verbose:
            print(f"Updated test_health.json with {len(flaky_tests)} flaky tests\n")

    # Return exit code
    if flaky_tests:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
