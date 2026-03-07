#!/usr/bin/env python3
"""
Parse cargo test output and generate JSON for proptest results.

Extracts test results from Rust proptest output for aggregation script.
"""

import argparse
import json
import re
import sys
from typing import Dict, List


def parse_proptest_output(cargo_output: str) -> Dict:
    """
    Parse stdout from cargo test and extract proptest results.

    Args:
        cargo_output: Stdout text from cargo test

    Returns:
        Dict with total, passed, failed, tests list
    """
    # Pattern for proptest results
    # Format: "test prop_test_name ... ok" or "test prop_test_name ... FAILED"
    test_pattern = re.compile(r"test (prop_\w+) \.\.\. (ok|FAILED)")

    tests = []
    passed = 0
    failed = 0

    for line in cargo_output.split("\n"):
        match = test_pattern.search(line)
        if match:
            test_name = match.group(1)
            result = match.group(2)

            tests.append({"name": test_name, "result": result})

            if result == "ok":
                passed += 1
            elif result == "FAILED":
                failed += 1

    total = passed + failed

    return {
        "total": total,
        "passed": passed,
        "failed": failed,
        "tests": tests,
    }


def main() -> int:
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Parse cargo test output and generate JSON for proptest results"
    )
    parser.add_argument(
        "--input",
        type=str,
        help="Input file containing cargo test output (default: stdin)",
    )
    parser.add_argument(
        "--output",
        type=str,
        help="Output JSON file path (default: stdout)",
    )

    args = parser.parse_args()

    # Read input from file or stdin
    if args.input:
        try:
            with open(args.input, "r") as f:
                cargo_output = f.read()
        except FileNotFoundError:
            print(f"Error: Input file '{args.input}' not found", file=sys.stderr)
            return 1
    else:
        cargo_output = sys.stdin.read()

    # Parse output
    results = parse_proptest_output(cargo_output)

    # Output JSON
    json_output = json.dumps(results, indent=2)

    if args.output:
        try:
            with open(args.output, "w") as f:
                f.write(json_output)
            print(f"Results written to {args.output}", file=sys.stderr)
        except IOError as e:
            print(f"Error writing output file: {e}", file=sys.stderr)
            return 1
    else:
        print(json_output)

    return 0


if __name__ == "__main__":
    sys.exit(main())
