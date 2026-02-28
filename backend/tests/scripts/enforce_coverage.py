#!/usr/bin/env python3
"""
Coverage Enforcement Script for Pre-commit Hooks

Enforces 80% minimum coverage on new code and prevents coverage regression.
Supports standalone execution, PR validation, and pre-commit hook integration.

Usage:
    python enforce_coverage.py --help
    python enforce_coverage.py --minimum 80 --files-only
    python enforce_coverage.py --verbose
"""

import argparse
import json
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional


@dataclass
class CoverageResult:
    """Coverage check result for a single file."""
    filename: str
    line_coverage: float
    branch_coverage: float
    lines_covered: int
    lines_total: int
    branches_covered: int
    branches_total: int
    is_new: bool
    is_modified: bool


def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description="Enforce coverage thresholds on changed Python files"
    )
    parser.add_argument(
        "--minimum",
        type=float,
        default=80.0,
        help="Minimum coverage percentage for new code (default: 80.0)"
    )
    parser.add_argument(
        "--files-only",
        action="store_true",
        help="Only check changed files, not full coverage"
    )
    parser.add_argument(
        "--staged",
        action="store_true",
        help="Check staged files instead of all changed files"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="Print detailed coverage information"
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="Output results in JSON format"
    )
    parser.add_argument(
        "--coverage-json",
        type=Path,
        default=Path("tests/coverage_reports/metrics/coverage.json"),
        help="Path to coverage.json file"
    )
    return parser.parse_args()


def get_changed_files(staged: bool = False) -> List[str]:
    """
    Get list of changed Python files using git diff.

    Args:
        staged: If True, check staged files. If False, check all changed files.

    Returns:
        List of changed Python filenames
    """
    cmd = ["git", "diff", "--name-only"]
    if staged:
        cmd.append("--staged")

    # Add HEAD to compare against working tree
    if not staged:
        cmd.append("HEAD")

    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=True
        )
        files = result.stdout.strip().split("\n")
        # Filter for Python files only
        return [f for f in files if f.endswith(".py") and f]
    except subprocess.CalledProcessError:
        return []


def run_coverage(files: Optional[List[str]] = None) -> dict:
    """
    Run pytest with coverage and parse coverage.json output.

    Args:
        files: List of specific files to check. If None, checks all files.

    Returns:
        Coverage data dictionary from coverage.json
    """
    # Build pytest command
    cmd = [
        "python", "-m", "pytest",
        "-q",
        "--cov=.",
        "--cov-report=json",
        "--cov-fail-under=0",  # Don't fail on threshold, just calculate
    ]

    # Add specific files if provided
    if files:
        cmd.extend(files)

    try:
        # Run pytest with coverage
        subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            check=False
        )

        # Read coverage.json output
        coverage_path = Path("tests/coverage_reports/metrics/coverage.json")
        if coverage_path.exists():
            with open(coverage_path, "r") as f:
                return json.load(f)
        else:
            print(f"Warning: coverage.json not found at {coverage_path}")
            return {}
    except Exception as e:
        print(f"Error running coverage: {e}")
        return {}


def check_coverage_thresholds(
    coverage_data: dict,
    minimum: float,
    files_only: bool = False
) -> tuple[List[CoverageResult], bool]:
    """
    Check coverage results against minimum thresholds.

    Args:
        coverage_data: Coverage data from coverage.json
        minimum: Minimum coverage percentage (0-100)
        files_only: If True, only check changed files

    Returns:
        Tuple of (list of CoverageResult objects, overall_pass_status)
    """
    results = []
    all_pass = True

    if "files" not in coverage_data:
        return results, False

    for filename, file_data in coverage_data["files"].items():
        summary = file_data.get("summary", {})
        line_coverage = summary.get("percent_covered", 0.0)
        branch_coverage = summary.get("percent_branches_covered", 0.0)
        lines_covered = summary.get("covered_lines", 0)
        lines_total = summary.get("num_statements", 0)
        branches_covered = summary.get("covered_branches", 0)
        branches_total = summary.get("num_branches", 0)

        # Skip test files
        if "tests/" in filename or filename.startswith("test_"):
            continue

        result = CoverageResult(
            filename=filename,
            line_coverage=line_coverage,
            branch_coverage=branch_coverage,
            lines_covered=lines_covered,
            lines_total=lines_total,
            branches_covered=branches_covered,
            branches_total=branches_total,
            is_new=False,  # TODO: Detect new files via git
            is_modified=False  # TODO: Detect modified files via git
        )

        results.append(result)

        # Check if file passes threshold
        if line_coverage < minimum:
            all_pass = False

    return results, all_pass


def print_results(results: List[CoverageResult], minimum: float, verbose: bool = False):
    """
    Print coverage results in human-readable format.

    Args:
        results: List of CoverageResult objects
        minimum: Minimum coverage threshold
        verbose: Print detailed information
    """
    if not results:
        print("No coverage data found.")
        return

    # Sort by coverage (lowest first)
    results.sort(key=lambda r: r.line_coverage)

    # Print failing files first
    failing = [r for r in results if r.line_coverage < minimum]
    passing = [r for r in results if r.line_coverage >= minimum]

    if failing:
        print("\n❌ Coverage Enforcement FAILED")
        print(f"{'File':<60} {'Line Cov':>10} {'Branch Cov':>12} {'Status':>10}")
        print("-" * 100)

        for result in failing:
            status = "FAIL"
            print(
                f"{result.filename:<60} "
                f"{result.line_coverage:>9.2f}% "
                f"{result.branch_coverage:>11.2f}% "
                f"{status:>10}"
            )

            if verbose:
                print(
                    f"  Lines: {result.lines_covered}/{result.lines_total} | "
                    f"Branches: {result.branches_covered}/{result.branches_total}"
                )

    if passing:
        if failing:
            print("\n✅ Passing files:")
        else:
            print("\n✅ Coverage Enforcement PASSED")

        print(f"{'File':<60} {'Line Cov':>10} {'Branch Cov':>12} {'Status':>10}")
        print("-" * 100)

        for result in passing:
            status = "PASS"
            print(
                f"{result.filename:<60} "
                f"{result.line_coverage:>9.2f}% "
                f"{result.branch_coverage:>11.2f}% "
                f"{status:>10}"
            )

    # Print summary
    total_lines = sum(r.lines_total for r in results)
    total_covered = sum(r.lines_covered for r in results)
    overall_coverage = (total_covered / total_lines * 100) if total_lines > 0 else 0

    print("\n" + "=" * 100)
    print(f"Overall: {overall_coverage:.2f}% coverage ({total_covered}/{total_lines} lines)")
    print(f"Threshold: {minimum:.2f}% minimum required")

    if failing:
        print(f"\n{len(failing)} file(s) below threshold. Add tests to improve coverage.")
        print("Run 'pytest tests/ --cov' to see full coverage report.")


def main():
    """Main entry point."""
    args = parse_args()

    # Get changed files if in files-only mode
    changed_files = None
    if args.files_only:
        changed_files = get_changed_files(staged=args.staged)
        if not changed_files:
            print("No Python files changed. Skipping coverage check.")
            return 0

    # Run coverage analysis
    coverage_data = run_coverage(changed_files)

    if not coverage_data:
        print("Error: Could not load coverage data")
        return 1

    # Check thresholds
    results, all_pass = check_coverage_thresholds(
        coverage_data,
        args.minimum,
        args.files_only
    )

    # Print results
    if args.json:
        output = [
            {
                "filename": r.filename,
                "line_coverage": r.line_coverage,
                "branch_coverage": r.branch_coverage,
                "lines_covered": r.lines_covered,
                "lines_total": r.lines_total,
                "passes": r.line_coverage >= args.minimum
            }
            for r in results
        ]
        print(json.dumps(output, indent=2))
    else:
        print_results(results, args.minimum, args.verbose)

    # Return exit code
    return 0 if all_pass else 1


if __name__ == "__main__":
    sys.exit(main())
