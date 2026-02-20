#!/usr/bin/env python3
"""
Parse pytest JSON output and calculate pass rate.

Usage: python parse_pytest_output.py <pytest_json_file>

Output: Pass rate percentage to stdout (e.g., "98.5")
Exit code: 0 if pass rate >=98%, 1 otherwise
"""

import json
import sys


def calculate_pass_rate(json_file):
    """Calculate pass rate from pytest JSON report."""
    with open(json_file, 'r') as f:
        data = json.load(f)

    summary = data.get('summary', {})
    total = summary.get('total', 0)
    passed = summary.get('passed', 0)
    failed = summary.get('failed', 0)
    errors = summary.get('error', 0)
    skipped = summary.get('skipped', 0)

    if total == 0:
        print("100.0")
        return 100.0

    # Pass rate = passed / (passed + failed + errors)
    # Skipped tests are excluded from pass rate calculation
    attempted = passed + failed + errors
    pass_rate = (passed / attempted * 100) if attempted > 0 else 100.0

    # Output to stdout for CI capture
    print(f"{pass_rate:.1f}")

    # Optional: detailed logging to stderr
    print(f"Total: {total}, Passed: {passed}, Failed: {failed}, Errors: {errors}, Skipped: {skipped}", file=sys.stderr)

    return pass_rate


if __name__ == '__main__':
    if len(sys.argv) != 2:
        print("Usage: parse_pytest_output.py <pytest_json_file>", file=sys.stderr)
        sys.exit(1)

    json_file = sys.argv[1]
    try:
        pass_rate = calculate_pass_rate(json_file)
        # Exit with error if pass rate below 98%
        if pass_rate < 98.0:
            sys.exit(1)
    except Exception as e:
        print(f"Error parsing pytest output: {e}", file=sys.stderr)
        sys.exit(1)
