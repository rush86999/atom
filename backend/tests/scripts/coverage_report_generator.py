#!/usr/bin/env python3
"""
Enhanced Coverage Report Generator

Generates comprehensive coverage reports with HTML drill-down, branch coverage
visualization, and actionable insights for improving test coverage.

Usage:
    python backend/tests/scripts/coverage_report_generator.py [--modules MODULES] [--threshold N] [--output FILE]

Examples:
    python backend/tests/scripts/coverage_report_generator.py
    python backend/tests/scripts/coverage_report_generator.py --modules core api
    python backend/tests/scripts/coverage_report_generator.py --threshold 60 --output coverage_summary.txt
"""

import argparse
import json
import subprocess
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


def run_coverage_tests(modules: Optional[List[str]] = None) -> bool:
    """
    Run pytest with coverage and generate all report formats.

    Args:
        modules: List of module names to test (e.g., ['core', 'api'])

    Returns:
        True if tests passed, False otherwise
    """
    cmd = [
        "python", "-m", "pytest",
        "tests/",
        "-v",
        "--cov=.",
        "--cov-report=html",
        "--cov-report=json",
        "--cov-report=term-missing",
    ]

    if modules:
        # Add specific module coverage
        for module in modules:
            cmd.append(f"--cov={module}")

    print(f"Running: {' '.join(cmd)}")
    result = subprocess.run(cmd, cwd=Path(__file__).parent.parent)

    return result.returncode == 0


def parse_coverage_json(json_path: Path) -> Dict[str, Any]:
    """
    Parse coverage.json file and extract metrics.

    Args:
        json_path: Path to coverage.json

    Returns:
        Parsed coverage data dictionary
    """
    if not json_path.exists():
        raise FileNotFoundError(f"Coverage JSON not found: {json_path}")

    with open(json_path, 'r') as f:
        coverage = json.load(f)

    return coverage


def find_low_coverage_files(coverage: Dict[str, Any], threshold: int = 50) -> List[Tuple[str, float, int]]:
    """
    Identify files with coverage below threshold.

    Args:
        coverage: Coverage data dictionary
        threshold: Coverage percentage threshold (default: 50%)

    Returns:
        List of (file_path, coverage_percent, missing_lines) tuples sorted by coverage
    """
    low_coverage = []

    for file_path, file_data in coverage.get("files", {}).items():
        summary = file_data.get("summary", {})
        percent = summary.get("percent_covered", 0)
        missing = summary.get("missing_lines", 0)

        if percent < threshold:
            low_coverage.append((file_path, percent, missing))

    # Sort by coverage percentage (ascending)
    return sorted(low_coverage, key=lambda x: x[1])


def find_untested_modules(coverage: Dict[str, Any]) -> List[str]:
    """
    Find modules with zero coverage.

    Args:
        coverage: Coverage data dictionary

    Returns:
        List of module paths with 0% coverage
    """
    untested = []

    for file_path, file_data in coverage.get("files", {}).items():
        summary = file_data.get("summary", {})
        percent = summary.get("percent_covered", 0)

        if percent == 0:
            untested.append(file_path)

    return sorted(untested)


def calculate_branch_gap(coverage: Dict[str, Any]) -> Tuple[int, int, int]:
    """
    Calculate branch coverage gap.

    Args:
        coverage: Coverage data dictionary

    Returns:
        Tuple of (covered_branches, total_branches, gap)
    """
    totals = coverage.get("totals", {})
    covered = totals.get("covered_branches", 0)
    total = totals.get("num_branches", 0)
    gap = total - covered

    return covered, total, gap


def generate_summary_report(coverage: Dict[str, Any], threshold: int = 50) -> str:
    """
    Generate formatted summary report.

    Args:
        coverage: Coverage data dictionary
        threshold: Coverage threshold for low-coverage files

    Returns:
        Formatted report string
    """
    lines = []

    # Overall coverage
    totals = coverage.get("totals", {})
    line_coverage = totals.get("percent_covered", 0)
    covered_lines = totals.get("covered_lines", 0)
    total_lines = totals.get("num_statements", 0)
    missing_lines = totals.get("missing_lines", 0)

    lines.append("=" * 80)
    lines.append("COVERAGE SUMMARY REPORT")
    lines.append("=" * 80)
    lines.append("")

    # Overall metrics
    lines.append("OVERALL COVERAGE")
    lines.append("-" * 40)
    lines.append(f"  Line Coverage:   {line_coverage:.2f}%")
    lines.append(f"  Lines Covered:   {covered_lines:,} / {total_lines:,}")
    lines.append(f"  Lines Missing:   {missing_lines:,}")
    lines.append("")

    # Branch coverage
    covered_branches, total_branches, branch_gap = calculate_branch_gap(coverage)
    if total_branches > 0:
        branch_percent = (covered_branches / total_branches) * 100
        lines.append("BRANCH COVERAGE")
        lines.append("-" * 40)
        lines.append(f"  Branch Coverage: {branch_percent:.2f}%")
        lines.append(f"  Branches Covered: {covered_branches} / {total_branches}")
        lines.append(f"  Branch Gap:       {branch_gap} missing branches")
        lines.append("")

    # Low coverage files
    low_coverage_files = find_low_coverage_files(coverage, threshold)
    if low_coverage_files:
        lines.append(f"MODULES BELOW {threshold}% COVERAGE")
        lines.append("-" * 40)

        # Group by module
        by_module = {}
        for file_path, percent, missing in low_coverage_files:
            # Extract module name
            parts = file_path.split("/")
            module = parts[1] if len(parts) > 1 else "root"

            if module not in by_module:
                by_module[module] = []
            by_module[module].append((file_path, percent, missing))

        # Sort modules by worst coverage
        for module in sorted(by_module.keys()):
            lines.append(f"\n  {module.upper()}/")
            for file_path, percent, missing in sorted(by_module[module], key=lambda x: x[1]):
                short_path = file_path.replace("backend/", "")
                lines.append(f"    {percent:5.2f}%  {missing:4d} missing  {short_path}")

        lines.append("")

    # Untested modules
    untested = find_untested_modules(coverage)
    if untested:
        lines.append(f"UNTESTED MODULES (0% coverage)")
        lines.append("-" * 40)
        for file_path in untested[:20]:  # Limit to 20
            short_path = file_path.replace("backend/", "")
            lines.append(f"  {short_path}")
        if len(untested) > 20:
            lines.append(f"  ... and {len(untested) - 20} more")
        lines.append("")

    # Top files with most uncovered lines
    all_files = []
    for file_path, file_data in coverage.get("files", {}).items():
        summary = file_data.get("summary", {})
        missing = summary.get("missing_lines", 0)
        if missing > 0:
            all_files.append((file_path, missing))

    # Sort by missing lines
    top_missing = sorted(all_files, key=lambda x: x[1], reverse=True)[:10]
    if top_missing:
        lines.append("TOP 10 FILES WITH MOST UNCOVERED LINES")
        lines.append("-" * 40)
        for i, (file_path, missing) in enumerate(top_missing, 1):
            short_path = file_path.replace("backend/", "")
            lines.append(f"  {i:2d}. {missing:4d} missing  {short_path}")
        lines.append("")

    lines.append("=" * 80)
    lines.append("")

    return "\n".join(lines)


def main():
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Generate enhanced coverage reports with actionable insights"
    )
    parser.add_argument(
        "--modules",
        nargs="*",
        default=None,
        help="Modules to test (e.g., core api). Default: all modules"
    )
    parser.add_argument(
        "--threshold",
        type=int,
        default=50,
        help="Coverage threshold for low-coverage warning (default: 50%%)"
    )
    parser.add_argument(
        "--output",
        type=str,
        default=None,
        help="Output file for summary report (default: stdout)"
    )
    parser.add_argument(
        "--skip-run",
        action="store_true",
        help="Skip running tests, only parse existing coverage.json"
    )

    args = parser.parse_args()

    # Change to backend directory
    backend_dir = Path(__file__).parent.parent
    coverage_json = backend_dir / "coverage.json"
    htmlcov_dir = backend_dir / "htmlcov"

    # Run tests with coverage
    if not args.skip_run:
        print("Running coverage tests...")
        success = run_coverage_tests(args.modules)
        if not success:
            print("\nWarning: Tests failed, but generating report from existing coverage data...")
    else:
        print("Skipping test run, parsing existing coverage...")

    # Parse coverage data
    try:
        coverage = parse_coverage_json(coverage_json)
    except FileNotFoundError as e:
        print(f"Error: {e}")
        print("\nPlease run tests first or remove --skip-run flag")
        return 1

    # Generate summary report
    report = generate_summary_report(coverage, args.threshold)

    # Output report
    if args.output:
        output_path = Path(args.output)
        with open(output_path, 'w') as f:
            f.write(report)
        print(f"\nReport written to: {output_path}")
    else:
        print("\n" + report)

    # Report locations
    print("Coverage reports generated:")
    print(f"  - HTML Report:     file://{htmlcov_dir}/index.html")
    print(f"  - JSON Metrics:    {coverage_json}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
