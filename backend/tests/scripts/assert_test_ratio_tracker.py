#!/usr/bin/env python3
"""
Assert-to-Test Ratio Tracker for Atom Test Suite

This script tracks the assert-to-test ratio to detect coverage gaming (high coverage,
few assertions). Tests with low assert counts (< 2) are flagged as low-quality.

Industry Standard: 2-3 asserts per test (Google Testing Blog, Martin Fowler)

Usage:
    python assert_test_ratio_tracker.py tests/ --min-ratio 2.0
    python assert_test_ratio_tracker.py tests/ --format json --output report.json
    python assert_test_ratio_tracker.py tests/test_governance.py --min-ratio 2.0

Exit Codes:
    0: All tests meet assert ratio threshold
    1: Average assert ratio below threshold (low-quality tests detected)
    2: Error in execution
"""

import argparse
import ast
import json
import sys
from pathlib import Path
from typing import List, Dict, Any, Optional


# Constants
DEFAULT_MIN_RATIO = 2.0
DEFAULT_OUTPUT_FORMAT = "text"


class AssertCountVisitor(ast.NodeVisitor):
    """
    AST visitor to count assert statements per test function.

    Identifies test functions (name starts with 'test_') and counts
    assert statements within each function body.
    """

    def __init__(self):
        """Initialize visitor with empty test function list."""
        self.test_functions: List[Dict[str, Any]] = []
        self.current_function: Optional[Dict[str, Any]] = None
        self._in_parameterized_test = False

    def visit_FunctionDef(self, node: ast.FunctionDef) -> None:
        """
        Visit function definition nodes.

        Args:
            node: AST FunctionDef node
        """
        # Check if this is a test function
        is_test = node.name.startswith("test_")

        if is_test:
            # Check for pytest.mark.parametrize decorator
            self._in_parameterized_test = self._has_parametrize_decorator(node)

            # Create test function record
            self.current_function = {
                "name": node.name,
                "lineno": node.lineno,
                "assert_count": 0,
                "parameterized": self._in_parameterized_test
            }

        # Visit function body to count asserts
        self.generic_visit(node)

        # Add to list if it was a test function
        if is_test and self.current_function is not None:
            self.test_functions.append(self.current_function)

        # Reset
        self.current_function = None
        self._in_parameterized_test = False

    def visit_Assert(self, node: ast.Assert) -> None:
        """
        Visit assert statement nodes.

        Args:
            node: AST Assert node
        """
        if self.current_function is not None:
            self.current_function["assert_count"] += 1

    def _has_parametrize_decorator(self, node: ast.FunctionDef) -> bool:
        """
        Check if function has pytest.mark.parametrize decorator.

        Args:
            node: AST FunctionDef node

        Returns:
            True if parametrize decorator found
        """
        for decorator in node.decorator_list:
            # Check for @pytest.mark.parametrize
            if isinstance(decorator, ast.Attribute):
                if (isinstance(decorator.value, ast.Attribute) and
                    decorator.value.attr == "mark" and
                    decorator.attr == "parametrize"):
                    return True
            # Check for @pytest.mark.parametrize("arg", [...])
            if isinstance(decorator, ast.Call):
                if (isinstance(decorator.func, ast.Attribute) and
                    isinstance(decorator.func.value, ast.Attribute) and
                    decorator.func.value.attr == "mark" and
                    decorator.func.attr == "parametrize"):
                    return True
        return False


def analyze_test_file(file_path: Path) -> List[Dict[str, Any]]:
    """
    Analyze a test file and count asserts per test function.

    Args:
        file_path: Path to test file

    Returns:
        List of test function dicts with assert counts
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            source_code = f.read()
    except (IOError, UnicodeDecodeError) as e:
        print(f"Warning: Could not read {file_path}: {e}", file=sys.stderr)
        return []

    try:
        tree = ast.parse(source_code, filename=str(file_path))
    except SyntaxError as e:
        print(f"Warning: Syntax error in {file_path}: {e}", file=sys.stderr)
        return []

    visitor = AssertCountVisitor()
    visitor.visit(tree)

    # Add file path to each test function
    for test_func in visitor.test_functions:
        test_func["file"] = str(file_path)
        # Try to make relative to current working directory
        try:
            test_func["file_short"] = str(file_path.relative_to(Path.cwd()))
        except ValueError:
            # If file is not under cwd, use absolute path
            test_func["file_short"] = str(file_path)

    return visitor.test_functions


def calculate_assert_ratio(
    tests: List[Dict[str, Any]],
    min_ratio: float,
    include_parameterized: bool = False
) -> Dict[str, Any]:
    """
    Calculate assert-to-test ratio and identify low-quality tests.

    Args:
        tests: List of test function dicts
        min_ratio: Minimum assert ratio threshold
        include_parameterized: Include parameterized tests in calculation

    Returns:
        Dict with ratio metrics and low-quality test list
    """
    # Filter tests based on parameterized flag
    if include_parameterized:
        filtered_tests = tests
    else:
        filtered_tests = [t for t in tests if not t.get("parameterized", False)]

    if not filtered_tests:
        return {
            "total_tests": 0,
            "total_asserts": 0,
            "avg_ratio": 0.0,
            "low_quality_tests": [],
            "parameterized_tests_excluded": len(tests) - len(filtered_tests)
        }

    # Calculate totals
    total_asserts = sum(t["assert_count"] for t in filtered_tests)
    total_tests = len(filtered_tests)
    avg_ratio = total_asserts / total_tests if total_tests > 0 else 0.0

    # Identify low-quality tests (< min_ratio asserts)
    low_quality_tests = [
        t for t in filtered_tests
        if t["assert_count"] < min_ratio
    ]

    return {
        "total_tests": total_tests,
        "total_asserts": total_asserts,
        "avg_ratio": round(avg_ratio, 2),
        "low_quality_tests": low_quality_tests,
        "parameterized_tests_excluded": len(tests) - len(filtered_tests)
    }


def find_test_files(test_path: Path) -> List[Path]:
    """
    Find all test files in directory recursively.

    Args:
        test_path: Path to tests directory or file

    Returns:
        List of test file paths
    """
    if test_path.is_file():
        return [test_path]

    # Find all test_*.py files recursively
    test_files = list(test_path.rglob("test_*.py"))
    return test_files


def print_text_report(
    ratio_metrics: Dict[str, Any],
    min_ratio: float,
    verbose: bool = False
) -> None:
    """
    Print text format report to stdout.

    Args:
        ratio_metrics: Ratio calculation results
        min_ratio: Minimum ratio threshold
        verbose: Enable verbose output
    """
    print("\n" + "=" * 70)
    print("ASSERT-TO-TEST RATIO REPORT")
    print("=" * 70)
    print(f"\nTotal Tests:        {ratio_metrics['total_tests']}")
    print(f"Total Asserts:      {ratio_metrics['total_asserts']}")
    print(f"Average Asserts/Test: {ratio_metrics['avg_ratio']:.2f}")
    print(f"Minimum Threshold:   {min_ratio:.2f}")

    if ratio_metrics.get("parameterized_tests_excluded", 0) > 0:
        print(f"\n(Parameterized tests excluded: {ratio_metrics['parameterized_tests_excluded']})")

    print("")

    # Low-quality tests
    low_quality = ratio_metrics["low_quality_tests"]
    if low_quality:
        print("-" * 70)
        print("LOW-QUALITY TESTS DETECTED:")
        print("-" * 70)
        print(f"\nTests with < {min_ratio} assert(s): {len(low_quality)}\n")

        # Sort by assert count (lowest first)
        sorted_tests = sorted(low_quality, key=lambda t: t["assert_count"])

        # Show top 10
        for test in sorted_tests[:10]:
            file_short = test.get("file_short", test["file"])
            print(f"  {file_short}::{test['name']} (line {test['lineno']})")
            print(f"    → {test['assert_count']} assert(s)")

        if len(low_quality) > 10:
            print(f"\n  ... and {len(low_quality) - 10} more")

        print("\n" + "=" * 70)
        print("STATUS: LOW-QUALITY TESTS FOUND ✗")
        print("=" * 70)
        print("\nRECOMMENDED ACTIONS:")
        print("  1. Add more assertions to validate expected behavior")
        print("  2. Check for missing edge case testing")
        print("  3. Verify assertions actually test behavior (not just None checks)")
        print("  4. Consider splitting complex tests into multiple focused tests")
        print("=" * 70 + "\n")
    else:
        print("=" * 70)
        print("STATUS: ALL TESTS MEET QUALITY THRESHOLD ✓")
        print("=" * 70 + "\n")

    # Verbose: List all tests if requested
    if verbose and ratio_metrics['total_tests'] > 0:
        print("\nVerbose Output:")
        print("All test functions analyzed (excluding parameterized):")
        print(f"  Total: {ratio_metrics['total_tests']} tests")
        print(f"  Low-quality: {len(low_quality)} tests")
        print(f"  Quality: {((ratio_metrics['total_tests'] - len(low_quality)) / ratio_metrics['total_tests'] * 100):.1f}% pass rate\n")


def print_json_report(
    ratio_metrics: Dict[str, Any],
    output_path: Optional[Path] = None
) -> None:
    """
    Print or save JSON format report.

    Args:
        ratio_metrics: Ratio calculation results
        output_path: Optional path to save JSON file
    """
    # Format for JSON output
    output_data = {
        "total_tests": ratio_metrics["total_tests"],
        "total_asserts": ratio_metrics["total_asserts"],
        "avg_ratio": ratio_metrics["avg_ratio"],
        "low_quality_count": len(ratio_metrics["low_quality_tests"]),
        "parameterized_excluded": ratio_metrics.get("parameterized_tests_excluded", 0),
        "low_quality_tests": [
            {
                "file": t.get("file_short", t["file"]),
                "name": t["name"],
                "lineno": t["lineno"],
                "assert_count": t["assert_count"]
            }
            for t in ratio_metrics["low_quality_tests"]
        ]
    }

    json_str = json.dumps(output_data, indent=2)

    if output_path:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(json_str)
        print(f"JSON report saved to: {output_path}\n")
    else:
        print(json_str + "\n")


def main():
    """Main entry point for assert-to-test ratio tracking."""
    parser = argparse.ArgumentParser(
        description="Track assert-to-test ratio to detect coverage gaming",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  python assert_test_ratio_tracker.py tests/
  python assert_test_ratio_tracker.py tests/ --min-ratio 2.0 --format json --output report.json
  python assert_test_ratio_tracker.py tests/test_governance.py --min-ratio 3.0

Exit Codes:
  0: All tests meet assert ratio threshold
  1: Average assert ratio below threshold
  2: Error in execution

Industry Standard:
  2-3 asserts per test (Google Testing Blog, Martin Fowler)

How it works:
  1. Scans all test_*.py files recursively
  2. Parses Python AST to identify test functions
  3. Counts assert statements per test function
  4. Calculates average asserts per test
  5. Flags tests with < N asserts as low-quality
  6. Excludes parameterized tests (pytest.mark.parametrize)

Coverage Gaming Detection:
  - High coverage % + Low assert count = Tests execute code but don't validate behavior
  - Example: 90% coverage with 1.0 avg asserts/test indicates low-quality tests
  - Target: 2.0+ avg asserts/test for meaningful test coverage
        """
    )

    parser.add_argument(
        "test_path",
        type=Path,
        help="Path to tests directory or specific test file"
    )

    parser.add_argument(
        "--min-ratio",
        type=float,
        default=DEFAULT_MIN_RATIO,
        help=f"Minimum asserts per test threshold (default: {DEFAULT_MIN_RATIO})"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json"],
        default=DEFAULT_OUTPUT_FORMAT,
        help="Output format (default: text)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=None,
        help="Output path for JSON report (default: stdout)"
    )

    parser.add_argument(
        "--include-parameterized",
        action="store_true",
        help="Include parameterized tests in ratio calculation (default: excluded)"
    )

    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Enable verbose output"
    )

    args = parser.parse_args()

    # Validate test path
    if not args.test_path.exists():
        print(f"Error: Test path not found: {args.test_path}", file=sys.stderr)
        sys.exit(2)

    # Find all test files
    test_files = find_test_files(args.test_path)

    if not test_files:
        print(f"Error: No test files found in: {args.test_path}", file=sys.stderr)
        sys.exit(2)

    print(f"Scanning {len(test_files)} test files...\n")

    # Analyze all test files
    all_tests = []
    for test_file in test_files:
        tests = analyze_test_file(test_file)
        if tests:
            all_tests.extend(tests)

    if not all_tests:
        print("Error: No test functions found", file=sys.stderr)
        sys.exit(2)

    # Calculate assert ratio
    ratio_metrics = calculate_assert_ratio(
        all_tests,
        args.min_ratio,
        args.include_parameterized
    )

    # Print report
    if args.format == "text":
        print_text_report(ratio_metrics, args.min_ratio, args.verbose)
    else:
        print_json_report(ratio_metrics, args.output)

    # Exit with code based on ratio
    if ratio_metrics["avg_ratio"] < args.min_ratio:
        sys.exit(1)
    else:
        sys.exit(0)


if __name__ == "__main__":
    main()
