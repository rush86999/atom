#!/usr/bin/env python
"""
Pass Rate Validation Script for Atom Test Suite

This script validates test suite pass rate against a minimum threshold (default 98%).
It parses pytest JSON output, categorizes failures, and returns appropriate exit codes.

Usage:
    python check_pass_rate.py --json-file pytest_report.json --minimum 98
    python check_pass_rate.py --help

Exit Codes:
    0: Pass rate meets or exceeds minimum threshold
    1: Pass rate below minimum threshold
    2: Error in execution
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def parse_pytest_json(json_file: str):
    """
    Parse pytest JSON report file and extract test results.

    Args:
        json_file: Path to pytest JSON report file

    Returns:
        Dictionary with passed, failed, error, skipped counts
    """
    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: JSON report file not found: {json_file}")
        sys.exit(2)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in report file: {e}")
        sys.exit(2)

    # Initialize counters
    results = {
        "passed": 0,
        "failed": 0,
        "error": 0,
        "skipped": 0,
        "total": 0
    }

    # Parse pytest-json-report format
    if "summary" in data:
        # pytest-json-report format
        summary = data["summary"]
        results["passed"] = summary.get("passed", 0)
        results["failed"] = summary.get("failed", 0)
        results["skipped"] = summary.get("skipped", 0)
        results["total"] = summary.get("total", 0)
        # Errors are counted as failed in this format
        results["error"] = summary.get("error", 0)
    elif "tests" in data:
        # Alternative format: iterate through test list
        for test in data["tests"]:
            outcome = test.get("outcome", "unknown")
            if outcome == "passed":
                results["passed"] += 1
            elif outcome == "failed":
                results["failed"] += 1
            elif outcome == "skipped":
                results["skipped"] += 1
            elif outcome == "error":
                results["error"] += 1
            results["total"] += 1
    else:
        print("ERROR: Unknown JSON report format")
        sys.exit(2)

    return results


def calculate_pass_rate(results):
    """
    Calculate pass rate percentage.

    Args:
        results: Dictionary with test counts

    Returns:
        Pass rate percentage (0-100)
    """
    total_run = results["passed"] + results["failed"]
    if total_run == 0:
        return 100.0  # No tests run, consider as passing
    return (results["passed"] / total_run) * 100


def categorize_failures(json_file: str):
    """
    Categorize test failures by type (assertion, error, timeout, skip).

    Args:
        json_file: Path to pytest JSON report file

    Returns:
        Dictionary mapping failure type to count
    """
    categories = {
        "assertion": 0,
        "error": 0,
        "timeout": 0,
        "skip": 0
    }

    try:
        with open(json_file, 'r') as f:
            data = json.load(f)
    except (FileNotFoundError, json.JSONDecodeError):
        return categories

    # Parse test failures
    tests = data.get("tests", [])
    for test in tests:
        outcome = test.get("outcome", "")

        if outcome == "failed":
            # Check if it's an assertion error or exception
            call = test.get("call", {})
            longrepr = call.get("longrepr", "")

            if "AssertionError" in longrepr or "assert" in longrepr:
                categories["assertion"] += 1
            elif "TimeoutError" in longrepr or "timeout" in longrepr.lower():
                categories["timeout"] += 1
            else:
                categories["error"] += 1
        elif outcome == "skipped":
            categories["skip"] += 1

    return categories


def print_summary(
    pass_rate,
    results,
    categories,
    minimum,
    verbose=False
):
    """
    Print formatted summary of test results.

    Args:
        pass_rate: Calculated pass rate percentage
        results: Test result counts
        categories: Failure type counts
        minimum: Minimum pass rate threshold
        verbose: Enable verbose output
    """
    print("\n" + "="*70)
    print("TEST PASS RATE VALIDATION")
    print("="*70)

    # Test results
    print(f"\nTest Results:")
    print(f"  Total Tests:  {results['total']}")
    print(f"  Passed:       {results['passed']}")

    if results["failed"] > 0:
        print(f"  Failed:       {results['failed']}")

    if results["error"] > 0:
        print(f"  Errors:       {results['error']}")

    if results["skipped"] > 0:
        print(f"  Skipped:      {results['skipped']}")

    # Pass rate
    print(f"\nPass Rate: {pass_rate:.2f}%")
    print(f"Threshold: {minimum:.2f}%")

    # Failure breakdown
    if sum(categories.values()) > 0 or verbose:
        print(f"\nFailure Categories:")
        print(f"  Assertion Errors: {categories['assertion']}")
        print(f"  Exceptions:       {categories['error']}")
        print(f"  Timeouts:         {categories['timeout']}")
        print(f"  Skipped:          {categories['skip']}")

    # Status
    print("\n" + "="*70)
    if pass_rate >= minimum:
        print("STATUS: PASS ✓")
        print("="*70 + "\n")
    else:
        print(f"STATUS: FAIL ✗ (Pass rate {pass_rate:.2f}% below {minimum:.2f}%)")
        print("="*70 + "\n")


def update_health_json(
    results,
    pass_rate,
    categories,
    phase="090",
    plan="02",
    duration_seconds=0
):
    """
    Update test_health.json with current test results.

    Args:
        results: Test result counts
        pass_rate: Calculated pass rate percentage
        categories: Failure type counts
        phase: Current phase number
        plan: Current plan number
        duration_seconds: Test execution duration
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
    if "pass_rate_history" not in health_data:
        health_data["pass_rate_history"] = []
    if "failure_categories" not in health_data:
        health_data["failure_categories"] = {
            "assertion": 0,
            "error": 0,
            "timeout": 0,
            "skip": 0
        }
    if "baseline" not in health_data:
        health_data["baseline"] = {}
    if "metadata" not in health_data:
        health_data["metadata"] = {}

    # Add current run to history
    current_entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "phase": phase,
        "plan": plan,
        "total_tests": results["total"],
        "passed": results["passed"],
        "failed": results["failed"],
        "skipped": results["skipped"],
        "pass_rate": round(pass_rate, 2),
        "duration_seconds": duration_seconds
    }
    health_data["pass_rate_history"].append(current_entry)

    # Update failure categories (cumulative)
    for key in health_data["failure_categories"]:
        health_data["failure_categories"][key] += categories.get(key, 0)

    # Set baseline if not exists
    if not health_data["baseline"]:
        health_data["baseline"] = {
            "date": current_entry["date"],
            "pass_rate": round(pass_rate, 2),
            "total_tests": results["total"]
        }

    # Update metadata
    health_data["metadata"]["format_version"] = 1
    health_data["metadata"]["minimum_pass_rate"] = 98.0
    health_data["metadata"]["last_updated"] = datetime.now().isoformat()

    # Write back to file
    health_file.parent.mkdir(parents=True, exist_ok=True)
    with open(health_file, 'w') as f:
        json.dump(health_data, f, indent=2)


def main():
    """Main entry point for pass rate validation."""
    parser = argparse.ArgumentParser(
        description="Validate test pass rate against minimum threshold",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python check_pass_rate.py --json-file pytest_report.json
  python check_pass_rate.py --json-file pytest_report.json --minimum 95
  python check_pass_rate.py --json-file pytest_report.json --verbose --update-health

Exit Codes:
  0: Pass rate meets or exceeds minimum threshold
  1: Pass rate below minimum threshold
  2: Error in execution
        """
    )

    parser.add_argument(
        "--json-file",
        type=str,
        default="pytest_report.json",
        help="Path to pytest JSON report file (default: pytest_report.json)"
    )

    parser.add_argument(
        "--minimum",
        type=float,
        default=98.0,
        help="Minimum pass rate threshold (default: 98.0)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    parser.add_argument(
        "--update-health",
        action="store_true",
        help="Update test_health.json with current results"
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

    parser.add_argument(
        "--duration",
        type=int,
        default=0,
        help="Test execution duration in seconds (default: 0)"
    )

    args = parser.parse_args()

    # Parse test results
    results = parse_pytest_json(args.json_file)

    # Calculate pass rate
    pass_rate = calculate_pass_rate(results)

    # Categorize failures
    categories = categorize_failures(args.json_file)

    # Print summary
    print_summary(pass_rate, results, categories, args.minimum, args.verbose)

    # Update health JSON if requested
    if args.update_health:
        update_health_json(
            results,
            pass_rate,
            categories,
            phase=args.phase,
            plan=args.plan,
            duration_seconds=args.duration
        )
        if args.verbose:
            print(f"Updated test_health.json with current results\n")

    # Return exit code
    if pass_rate >= args.minimum:
        sys.exit(0)
    else:
        sys.exit(1)


if __name__ == "__main__":
    main()
