#!/usr/bin/env python3
"""
Unified Coverage Aggregation Script

Combines pytest JSON coverage (backend) and Jest JSON coverage (frontend)
into a single unified report with per-platform breakdown.

Usage:
    python backend/tests/scripts/aggregate_coverage.py [OPTIONS]

Examples:
    python backend/tests/scripts/aggregate_coverage.py --format text
    python backend/tests/scripts/aggregate_coverage.py --format json
    python backend/tests/scripts/aggregate_coverage.py --format markdown
    python backend/tests/scripts/aggregate_coverage.py --output unified_coverage.json
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, Optional


def load_pytest_coverage(path: Path) -> Dict[str, Any]:
    """
    Load pytest coverage.json from backend tests.

    Args:
        path: Path to coverage.json (pytest format)

    Returns:
        Dict with platform='python', coverage_pct, covered, total metrics
        Returns coverage_pct=0.0 and error message if file not found
    """
    result = {
        "platform": "python",
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "branches_covered": 0,
        "branches_total": 0,
        "branch_coverage_pct": 0.0,
        "file": str(path),
    }

    if not path.exists():
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            coverage_data = json.load(f)

        # Extract totals from pytest coverage.json
        totals = coverage_data.get("totals", {})

        result["coverage_pct"] = totals.get("percent_covered", 0.0)
        result["covered"] = totals.get("covered_lines", 0)
        result["total"] = totals.get("num_statements", 0)
        result["branches_covered"] = totals.get("covered_branches", 0)
        result["branches_total"] = totals.get("num_branches", 0)

        # Calculate branch coverage percentage
        if result["branches_total"] > 0:
            result["branch_coverage_pct"] = (
                result["branches_covered"] / result["branches_total"] * 100
            )
        else:
            result["branch_coverage_pct"] = 0.0

    except (json.JSONDecodeError, IOError) as e:
        result["error"] = str(e)

    return result


def load_jest_coverage(path: Path) -> Dict[str, Any]:
    """
    Load Jest coverage-final.json from frontend tests.

    Args:
        path: Path to coverage-final.json (Jest format)

    Returns:
        Dict with platform='javascript', coverage_pct, covered, total metrics
        Returns coverage_pct=0.0 and error message if file not found
    """
    result = {
        "platform": "javascript",
        "coverage_pct": 0.0,
        "covered": 0,
        "total": 0,
        "branches_covered": 0,
        "branches_total": 0,
        "branch_coverage_pct": 0.0,
        "file": str(path),
    }

    if not path.exists():
        result["error"] = "file not found"
        return result

    try:
        with open(path, 'r') as f:
            coverage_data = json.load(f)

        # Jest coverage-final.json format:
        # {
        #   "/path/to/file.ts": {
        #     "s": { "1": 10, "2": 5 },  # statement counts
        #     "b": { "1": [10, 5], "2": [8, 2] },  # branch counts [taken, not taken]
        #     "f": { "1": 10 },  # function counts
        #     "l": { "1": 10 }  # line counts
        #   }
        # }

        total_statements = 0
        covered_statements = 0
        total_branches = 0
        covered_branches = 0

        for file_path, file_data in coverage_data.items():
            # Skip node_modules and test files
            if "node_modules" in file_path or "__tests__" in file_path:
                continue

            # Aggregate statements (s)
            statements = file_data.get("s", {})
            for stmt_id, count in statements.items():
                total_statements += 1
                if count > 0:
                    covered_statements += 1

            # Aggregate branches (b)
            branches = file_data.get("b", {})
            for branch_id, counts in branches.items():
                if isinstance(counts, list) and len(counts) >= 2:
                    total_branches += len(counts)
                    covered_branches += sum(1 for c in counts if c > 0)

        result["covered"] = covered_statements
        result["total"] = total_statements
        result["branches_covered"] = covered_branches
        result["branches_total"] = total_branches

        # Calculate percentages
        if result["total"] > 0:
            result["coverage_pct"] = (result["covered"] / result["total"] * 100)
        else:
            result["coverage_pct"] = 0.0

        if result["branches_total"] > 0:
            result["branch_coverage_pct"] = (
                result["branches_covered"] / result["branches_total"] * 100
            )
        else:
            result["branch_coverage_pct"] = 0.0

    except (json.JSONDecodeError, IOError) as e:
        result["error"] = str(e)

    return result


def aggregate_coverage(
    pytest_path: Path,
    jest_path: Path
) -> Dict[str, Any]:
    """
    Aggregate coverage from both platforms.

    Computes overall coverage as weighted average:
    (covered_backend + covered_frontend) / (total_backend + total_frontend)

    Args:
        pytest_path: Path to pytest coverage.json
        jest_path: Path to Jest coverage-final.json

    Returns:
        Dict with platforms, overall, timestamp keys
    """
    python_coverage = load_pytest_coverage(pytest_path)
    javascript_coverage = load_jest_coverage(jest_path)

    # Compute overall coverage (weighted average)
    total_covered = python_coverage["covered"] + javascript_coverage["covered"]
    total_lines = python_coverage["total"] + javascript_coverage["total"]

    overall_coverage_pct = 0.0
    if total_lines > 0:
        overall_coverage_pct = (total_covered / total_lines * 100)

    # Compute overall branch coverage
    total_branches_covered = (
        python_coverage["branches_covered"] + javascript_coverage["branches_covered"]
    )
    total_branches = (
        python_coverage["branches_total"] + javascript_coverage["branches_total"]
    )

    overall_branch_coverage_pct = 0.0
    if total_branches > 0:
        overall_branch_coverage_pct = (
            total_branches_covered / total_branches * 100
        )

    return {
        "platforms": {
            "python": python_coverage,
            "javascript": javascript_coverage,
        },
        "overall": {
            "coverage_pct": round(overall_coverage_pct, 2),
            "covered": total_covered,
            "total": total_lines,
            "branch_coverage_pct": round(overall_branch_coverage_pct, 2),
            "branches_covered": total_branches_covered,
            "branches_total": total_branches,
        },
        "timestamp": datetime.utcnow().isoformat() + "Z",
    }


def generate_report(
    aggregate_data: Dict[str, Any],
    format: str = "text"
) -> str:
    """
    Generate coverage report in specified format.

    Args:
        aggregate_data: Aggregated coverage data
        format: Output format (json, text, markdown)

    Returns:
        Formatted report string
    """
    if format == "json":
        return json.dumps(aggregate_data, indent=2)

    elif format == "markdown":
        return generate_markdown_report(aggregate_data)

    else:  # text
        return generate_text_report(aggregate_data)


def generate_text_report(aggregate_data: Dict[str, Any]) -> str:
    """Generate human-readable text report."""
    lines = []
    lines.append("=" * 80)
    lines.append("UNIFIED COVERAGE REPORT")
    lines.append("=" * 80)
    lines.append(f"Generated: {aggregate_data['timestamp']}")
    lines.append("")

    # Overall metrics
    overall = aggregate_data["overall"]
    lines.append("OVERALL COVERAGE")
    lines.append("-" * 80)
    lines.append(f"  Line Coverage:   {overall['coverage_pct']:6.2f}%  ({overall['covered']:7d} / {overall['total']:7d} lines)")
    lines.append(f"  Branch Coverage: {overall['branch_coverage_pct']:6.2f}%  ({overall['branches_covered']:7d} / {overall['branches_total']:7d} branches)")
    lines.append("")

    # Platform breakdown
    lines.append("PLATFORM BREAKDOWN")
    lines.append("-" * 80)

    for platform_name, platform_data in aggregate_data["platforms"].items():
        lines.append(f"\n{platform_name.upper()}:")
        lines.append(f"  File: {platform_data['file']}")

        if "error" in platform_data:
            lines.append(f"  Status: ERROR - {platform_data['error']}")
        else:
            lines.append(f"  Line Coverage:   {platform_data['coverage_pct']:6.2f}%  ({platform_data['covered']:7d} / {platform_data['total']:7d} lines)")
            lines.append(f"  Branch Coverage: {platform_data['branch_coverage_pct']:6.2f}%  ({platform_data['branches_covered']:7d} / {platform_data['branches_total']:7d} branches)")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def generate_markdown_report(aggregate_data: Dict[str, Any]) -> str:
    """Generate markdown table report (for PR comments)."""
    lines = []

    lines.append("## Unified Coverage Report")
    lines.append("")
    lines.append(f"**Generated:** {aggregate_data['timestamp']}")
    lines.append("")

    # Overall metrics
    overall = aggregate_data["overall"]
    lines.append("### Overall Coverage")
    lines.append("")
    lines.append("| Metric | Coverage | Details |")
    lines.append("|--------|----------|---------|")
    lines.append(f"| **Line Coverage** | **{overall['coverage_pct']:.2f}%** | {overall['covered']:,} / {overall['total']:,} lines |")
    lines.append(f"| **Branch Coverage** | **{overall['branch_coverage_pct']:.2f}%** | {overall['branches_covered']:,} / {overall['branches_total']:,} branches |")
    lines.append("")

    # Platform breakdown
    lines.append("### Platform Breakdown")
    lines.append("")
    lines.append("| Platform | Line Coverage | Branch Coverage | Status |")
    lines.append("|----------|---------------|-----------------|--------|")

    for platform_name, platform_data in aggregate_data["platforms"].items():
        if "error" in platform_data:
            status = f"❌ {platform_data['error']}"
            line_cov = "N/A"
            branch_cov = "N/A"
        else:
            status = "✅ OK"
            line_cov = f"{platform_data['coverage_pct']:.2f}%"
            branch_cov = f"{platform_data['branch_coverage_pct']:.2f}%"

        lines.append(f"| **{platform_name}** | {line_cov} | {branch_cov} | {status} |")

    lines.append("")

    return "\n".join(lines)


def main():
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Aggregate coverage from backend (pytest) and frontend (Jest) tests"
    )
    parser.add_argument(
        "--pytest-coverage",
        type=Path,
        default=Path(__file__).parent.parent / "coverage_reports" / "metrics" / "coverage.json",
        help="Path to pytest coverage.json (default: backend/tests/coverage_reports/metrics/coverage.json)"
    )
    parser.add_argument(
        "--jest-coverage",
        type=Path,
        default=Path(__file__).parent.parent.parent.parent / "frontend-nextjs" / "coverage" / "coverage-final.json",
        help="Path to Jest coverage-final.json (default: frontend-nextjs/coverage/coverage-final.json)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path(__file__).parent / "coverage_reports" / "unified" / "coverage.json",
        help="Output path for unified coverage JSON (default: backend/tests/scripts/coverage_reports/unified/coverage.json)"
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["json", "text", "markdown"],
        default="text",
        help="Output format (default: text)"
    )

    args = parser.parse_args()

    # Aggregate coverage
    aggregate_data = aggregate_coverage(args.pytest_coverage, args.jest_coverage)

    # Create output directory if needed
    args.output.parent.mkdir(parents=True, exist_ok=True)

    # Save unified JSON
    with open(args.output, 'w') as f:
        json.dump(aggregate_data, f, indent=2)

    # Generate and print report
    report = generate_report(aggregate_data, args.format)
    print(report)

    # Print warnings for missing coverage files
    for platform_name, platform_data in aggregate_data["platforms"].items():
        if "error" in platform_data:
            print(f"\n⚠️  WARNING: {platform_name} coverage file not found or invalid: {platform_data['file']}",
                  file=sys.stderr)

    print(f"\n✅ Unified coverage saved to: {args.output}")

    return 0


if __name__ == "__main__":
    sys.exit(main())
