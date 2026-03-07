#!/usr/bin/env python3
"""
Platform Retry Router

Extracts failed test names from platform-specific test result artifacts
and generates targeted retry commands for CI/CD workflows.

Purpose: Avoid wasting CI time re-running passing platform tests when only
one platform fails, enabling faster feedback on flaky tests.

Supported formats:
- pytest (backend): JSON report with summary.failed field
- Jest (frontend/mobile): JSON report with testResults array
- cargo (desktop): JSON output with passed field per test

Usage:
    python platform_retry_router.py --platform backend --results-file pytest_report.json --output-file retry_command.sh
    python platform_retry_router.py --platform frontend --results-file test-results.json --output-file retry_command.sh
    python platform_retry_router.py --platform desktop --results-file cargo_test_results.json --output-file retry_command.sh

Exit Codes:
    0: Tests to retry found (retry command generated)
    3: No failed tests (no retry needed)

Output Format:
    Generates shell script with platform-specific retry command
    - Backend: pytest tests/ -v <test1> <test2> ...
    - Frontend/Mobile: jest --testNamePattern="<test1>|<test2>|..."
    - Desktop: cargo test <test1> <test2> ...
"""

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file with error handling.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON dict, or empty dict with error key if parsing fails
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def extract_failed_tests(results: Dict[str, Any], platform: str) -> List[str]:
    """Extract failed test names from platform-specific test results.

    Args:
        results: Test results dict (pytest, Jest, or cargo format)
        platform: Platform name (backend, frontend, mobile, desktop)

    Returns:
        List of failed test names, empty list if none found or error
    """
    # Check for errors first
    if "error" in results:
        print(f"ERROR: {results['error']}", file=sys.stderr)
        return []

    # Backend: pytest JSON report format
    if platform == "backend":
        # pytest-json-report format: summary.failed contains list of failed tests
        summary = results.get("summary", {})
        failed_tests = summary.get("failed", [])

        # If summary.failed is a count, extract from test results
        if isinstance(failed_tests, int):
            # Alternative: extract from tests list with status="failed"
            all_tests = results.get("tests", [])
            failed_tests = [
                test.get("nodeid", "")
                for test in all_tests
                if test.get("outcome", "") == "failed"
            ]

        return failed_tests

    # Frontend/Mobile: Jest JSON test results format
    if platform in ["frontend", "mobile"]:
        # Jest format: testResults array, each test has status field
        test_results = results.get("testResults", [])
        failed_tests = []

        for test_suite in test_results:
            # Get assertion results for this test suite
            assertion_results = test_suite.get("assertionResults", [])

            for test_result in assertion_results:
                # Check if any assertion failed
                if test_result.get("status") == "failed":
                    # Get full test name (suite + title)
                    suite_name = test_suite.get("name", "")
                    test_title = " > ".join(test_result.get("title", []))

                    # Combine suite and test name
                    full_name = f"{suite_name} {test_title}".strip()
                    failed_tests.append(full_name)

        return failed_tests

    # Desktop: cargo test JSON format
    if platform == "desktop":
        # Cargo test --format json output: array of test objects with passed field
        # Handle both direct array and line-by-line JSON output
        failed_tests = []

        # Check if results is an array (parsed from multi-line output)
        if isinstance(results, list):
            test_entries = results
        else:
            # Single object, look for testResults or similar field
            test_entries = results.get("testResults", results.get("tests", []))

        for test_entry in test_entries:
            # Cargo test format: type="test", passed=false
            if test_entry.get("type") == "test":
                if not test_entry.get("passed", True):
                    test_name = test_entry.get("name", "")
                    if test_name:
                        failed_tests.append(test_name)

        return failed_tests

    # Unknown platform
    print(f"ERROR: Unknown platform '{platform}'", file=sys.stderr)
    return []


def escape_regex_chars(test_name: str) -> str:
    """Escape special regex characters for Jest testNamePattern.

    Args:
        test_name: Test name that may contain special regex chars

    Returns:
        Escaped test name safe for regex matching
    """
    # Escape special regex characters: . * + ? ^ $ { } ( ) | [ ] \
    return re.sub(r"([.*+?^${}()|[\]\\])", r"\\\1", test_name)


def generate_retry_command(failed_tests: List[str], platform: str) -> str:
    """Generate platform-specific retry command for failed tests.

    Args:
        failed_tests: List of failed test names
        platform: Platform name (backend, frontend, mobile, desktop)

    Returns:
        Shell command string to retry failed tests, empty string if no failures
    """
    if not failed_tests:
        return ""

    if platform == "backend":
        # Backend: pytest with explicit test names
        # Usage: pytest tests/ -v tests/test_module.py::test_function
        test_args = " ".join(failed_tests)
        return f"pytest tests/ -v {test_args}"

    if platform in ["frontend", "mobile"]:
        # Frontend/Mobile: Jest with testNamePattern regex
        # Usage: jest --testNamePattern="test1|test2|test3"
        # Escape special regex characters in test names
        escaped_tests = [escape_regex_chars(test) for test in failed_tests]
        pattern = "|".join(escaped_tests)
        return f"jest --testNamePattern=\"{pattern}\""

    if platform == "desktop":
        # Desktop: cargo test with explicit test names
        # Usage: cargo test test_name1 test_name2
        test_args = " ".join(failed_tests)
        return f"cargo test {test_args}"

    # Unknown platform
    return ""


def main():
    """Main entry point for platform retry router."""
    parser = argparse.ArgumentParser(
        description="Extract failed tests and generate retry command for CI/CD",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python platform_retry_router.py \\
    --platform backend \\
    --results-file pytest_report.json \\
    --output-file retry_command.sh

  python platform_retry_router.py \\
    --platform frontend \\
    --results-file test-results.json \\
    --output-file retry_command.sh

Exit Codes:
  0: Failed tests found (retry command generated)
  3: No failed tests (no retry needed)

Supported Platforms:
  backend   - pytest JSON report format
  frontend  - Jest JSON test results format
  mobile    - Jest JSON test results format
  desktop   - cargo test JSON format
        """
    )

    parser.add_argument(
        "--platform",
        required=True,
        choices=["backend", "frontend", "mobile", "desktop"],
        help="Platform name (backend, frontend, mobile, desktop)"
    )

    parser.add_argument(
        "--results-file",
        required=True,
        help="Path to test results JSON file"
    )

    parser.add_argument(
        "--output-file",
        required=True,
        help="Path to write retry command shell script"
    )

    args = parser.parse_args()

    # Load test results
    results = load_json(args.results_file)

    # Extract failed tests
    failed_tests = extract_failed_tests(results, args.platform)

    # Generate retry command
    retry_command = generate_retry_command(failed_tests, args.platform)

    # Write to output file
    output_path = Path(args.output_file)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    if retry_command:
        # Write retry command as executable shell script
        output_path.write_text(f"#!/bin/bash\n{retry_command}\n")
        output_path.chmod(0o755)

        print(f"Found {len(failed_tests)} failed test(s) for {args.platform}")
        print(f"Retry command written to: {args.output_file}")
        print(f"Command: {retry_command}")

        # Exit code 0: tests to retry found
        sys.exit(0)
    else:
        # No failed tests or error
        if failed_tests:
            print(f"ERROR: Failed to generate retry command for {len(failed_tests)} tests", file=sys.stderr)
            sys.exit(1)
        else:
            print(f"No failed tests found for {args.platform} (no retry needed)")

            # Write empty script for consistency
            output_path.write_text("#!/bin/bash\n# No failed tests to retry\n")
            output_path.chmod(0o755)

            # Exit code 3: no failures (special code for workflow)
            sys.exit(3)


if __name__ == "__main__":
    main()
