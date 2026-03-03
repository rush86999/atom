#!/usr/bin/env python3
"""
Unified Coverage Aggregation Script

Combines pytest JSON coverage (backend), Jest JSON coverage (frontend),
jest-expo JSON coverage (mobile), and cargo-tarpaulin JSON coverage (desktop)
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
from datetime import datetime, timezone
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


def load_jest_expo_coverage(path: Path) -> Dict[str, Any]:
    """
    Load jest-expo coverage-final.json from mobile tests.

    Args:
        path: Path to coverage-final.json (jest-expo format, same as Jest)

    Returns:
        Dict with platform='mobile', coverage_pct, covered, total metrics
        Returns coverage_pct=0.0 and error message if file not found
    """
    result = {
        "platform": "mobile",
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

        # jest-expo uses the same Jest coverage-final.json format
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


def load_tarpaulin_coverage(path: Path) -> Dict[str, Any]:
    """
    Load cargo-tarpaulin coverage.json from desktop tests.

    Args:
        path: Path to coverage.json (tarpaulin format)

    Returns:
        Dict with platform='rust', coverage_pct, covered, total metrics
        Returns coverage_pct=0.0 and error message if file not found
    """
    result = {
        "platform": "rust",
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

        # Tarpaulin coverage.json format:
        # {
        #   "files": {
        #     "path/to/file.rs": {
        #       "stats": {
        #         "covered": 50,
        #         "coverable": 100,
        #         "percent": 50.0
        #       }
        #     }
        #   }
        # }

        total_covered = 0
        total_lines = 0

        files = coverage_data.get("files", {})
        for file_path, file_data in files.items():
            stats = file_data.get("stats", {})
            total_covered += stats.get("covered", 0)
            total_lines += stats.get("coverable", 0)

        result["covered"] = total_covered
        result["total"] = total_lines

        # Calculate line coverage percentage
        if result["total"] > 0:
            result["coverage_pct"] = (result["covered"] / result["total"] * 100)
        else:
            result["coverage_pct"] = 0.0

        # Note: tarpaulin doesn't provide branch coverage
        result["branches_covered"] = 0
        result["branches_total"] = 0
        result["branch_coverage_pct"] = 0.0

    except (json.JSONDecodeError, IOError) as e:
        result["error"] = str(e)

    return result


def load_e2e_results(path: Path) -> Dict[str, Any]:
    """
    Load E2E test results from unified aggregator.

    Args:
        path: Path to e2e_unified.json (from e2e_aggregator.py)

    Returns:
        Dict with platform='e2e', total_tests, passed, failed metrics
        Returns error status if file not found
    """
    result = {
        "platform": "e2e",
        "total_tests": 0,
        "passed": 0,
        "failed": 0,
        "pass_rate": 0.0,
        "duration_seconds": 0,
        "platforms": {},
        "file": str(path),
    }

    if not path.exists():
        result["error"] = "file not found"
        result["status"] = "not_run"
        result["message"] = "E2E results not found"
        return result

    try:
        with open(path, 'r') as f:
            e2e_data = json.load(f)

        # Extract aggregate E2E metrics
        aggregate = e2e_data.get("aggregate", {})
        platforms = e2e_data.get("platforms", [])

        result["total_tests"] = aggregate.get("total_tests", 0)
        result["passed"] = aggregate.get("total_passed", 0)
        result["failed"] = aggregate.get("total_failed", 0)
        result["pass_rate"] = aggregate.get("pass_rate", 0.0)
        result["duration_seconds"] = aggregate.get("total_duration_seconds", 0)
        result["status"] = "success"

        # Extract per-platform E2E metrics
        for platform in platforms:
            platform_name = platform.get("platform", "unknown")
            result["platforms"][platform_name] = {
                "total": platform.get("total", 0),
                "passed": platform.get("passed", 0),
                "failed": platform.get("failed", 0),
                "duration": platform.get("duration", 0),
            }

    except (json.JSONDecodeError, IOError) as e:
        result["error"] = str(e)
        result["status"] = "error"
        result["message"] = f"Failed to load E2E results: {e}"

    return result


def aggregate_coverage(
    pytest_path: Path,
    jest_path: Path,
    jest_expo_path: Optional[Path] = None,
    tarpaulin_path: Optional[Path] = None,
    e2e_results_path: Optional[Path] = None
) -> Dict[str, Any]:
    """
    Aggregate coverage from all platforms.

    Computes overall coverage as weighted average:
    (covered_backend + covered_frontend + covered_mobile + covered_rust) /
    (total_backend + total_frontend + total_mobile + total_rust)

    Args:
        pytest_path: Path to pytest coverage.json
        jest_path: Path to Jest coverage-final.json
        jest_expo_path: Optional path to jest-expo coverage-final.json
        tarpaulin_path: Optional path to tarpaulin coverage.json

    Returns:
        Dict with platforms, overall, timestamp keys
    """
    python_coverage = load_pytest_coverage(pytest_path)
    javascript_coverage = load_jest_coverage(jest_path)
    mobile_coverage = load_jest_expo_coverage(jest_expo_path) if jest_expo_path else None
    rust_coverage = load_tarpaulin_coverage(tarpaulin_path) if tarpaulin_path else None

    # Build platforms dict
    platforms = {
        "python": python_coverage,
        "javascript": javascript_coverage,
    }
    if mobile_coverage:
        platforms["mobile"] = mobile_coverage
    if rust_coverage:
        platforms["rust"] = rust_coverage

    # Compute overall coverage (weighted average)
    total_covered = python_coverage["covered"] + javascript_coverage["covered"]
    total_lines = python_coverage["total"] + javascript_coverage["total"]

    total_branches_covered = (
        python_coverage["branches_covered"] + javascript_coverage["branches_covered"]
    )
    total_branches = (
        python_coverage["branches_total"] + javascript_coverage["branches_total"]
    )

    # Add mobile coverage if available
    if mobile_coverage:
        total_covered += mobile_coverage["covered"]
        total_lines += mobile_coverage["total"]
        total_branches_covered += mobile_coverage["branches_covered"]
        total_branches += mobile_coverage["branches_total"]

    # Add rust/desktop coverage if available
    if rust_coverage:
        total_covered += rust_coverage["covered"]
        total_lines += rust_coverage["total"]
        total_branches_covered += rust_coverage["branches_covered"]
        total_branches += rust_coverage["branches_total"]

    overall_coverage_pct = 0.0
    if total_lines > 0:
        overall_coverage_pct = (total_covered / total_lines * 100)

    overall_branch_coverage_pct = 0.0
    if total_branches > 0:
        overall_branch_coverage_pct = (
            total_branches_covered / total_branches * 100
        )

    result = {
        "platforms": platforms,
        "overall": {
            "coverage_pct": round(overall_coverage_pct, 2),
            "covered": total_covered,
            "total": total_lines,
            "branch_coverage_pct": round(overall_branch_coverage_pct, 2),
            "branches_covered": total_branches_covered,
            "branches_total": total_branches,
        },
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
    }

    # Add E2E test metrics if available
    if e2e_results_path:
        e2e_results = load_e2e_results(e2e_results_path)
        result["e2e_tests"] = {
            "status": e2e_results.get("status", "not_run"),
            "total_tests": e2e_results.get("total_tests", 0),
            "passed": e2e_results.get("passed", 0),
            "failed": e2e_results.get("failed", 0),
            "pass_rate": e2e_results.get("pass_rate", 0.0),
            "duration_seconds": e2e_results.get("duration_seconds", 0),
            "platforms": e2e_results.get("platforms", {}),
        }
        if "error" in e2e_results:
            result["e2e_tests"]["error"] = e2e_results["error"]
            result["e2e_tests"]["message"] = e2e_results.get("message", "Unknown error")

    return result
    if total_lines > 0:
        overall_coverage_pct = (total_covered / total_lines * 100)

    overall_branch_coverage_pct = 0.0
    if total_branches > 0:
        overall_branch_coverage_pct = (
            total_branches_covered / total_branches * 100
        )

    return {
        "platforms": platforms,
        "overall": {
            "coverage_pct": round(overall_coverage_pct, 2),
            "covered": total_covered,
            "total": total_lines,
            "branch_coverage_pct": round(overall_branch_coverage_pct, 2),
            "branches_covered": total_branches_covered,
            "branches_total": total_branches,
        },
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
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

    # E2E test metrics (if available)
    if "e2e_tests" in aggregate_data:
        e2e = aggregate_data["e2e_tests"]
        lines.append("E2E TEST RESULTS")
        lines.append("-" * 80)
        if e2e.get("status") == "not_run":
            lines.append(f"  Status: {e2e.get('message', 'Not run')}")
        elif e2e.get("status") == "error":
            lines.append(f"  Status: ERROR - {e2e.get('message', 'Unknown error')}")
        else:
            lines.append(f"  Total Tests:     {e2e['total_tests']:5d}")
            lines.append(f"  Passed:          {e2e['passed']:5d}")
            lines.append(f"  Failed:          {e2e['failed']:5d}")
            lines.append(f"  Pass Rate:       {e2e['pass_rate']:6.2f}%")
            lines.append(f"  Duration:        {e2e['duration_seconds']:5d}s")
            if e2e.get("platforms"):
                lines.append("")
                lines.append("  Platform Breakdown:")
                for platform_name, platform_data in e2e["platforms"].items():
                    lines.append(f"    {platform_name.upper()}: {platform_data['passed']}/{platform_data['total']} passed ({platform_data.get('duration', 0)}s)")
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

    # E2E test metrics (if available)
    if "e2e_tests" in aggregate_data:
        e2e = aggregate_data["e2e_tests"]
        lines.append("### E2E Test Results")
        lines.append("")

        if e2e.get("status") == "not_run":
            lines.append(f"**Status:** {e2e.get('message', 'Not run')}")
            lines.append("")
        elif e2e.get("status") == "error":
            lines.append(f"**Status:** ❌ ERROR - {e2e.get('message', 'Unknown error')}")
            lines.append("")
        else:
            lines.append("| Metric | Value |")
            lines.append("|--------|-------|")
            lines.append(f"| **Total Tests** | **{e2e['total_tests']}** |")
            lines.append(f"| **Passed** | **{e2e['passed']}** |")
            lines.append(f"| **Failed** | **{e2e['failed']}** |")
            lines.append(f"| **Pass Rate** | **{e2e['pass_rate']:.2f}%** |")
            lines.append(f"| **Duration** | **{e2e['duration_seconds']}s** |")
            lines.append("")

            if e2e.get("platforms"):
                lines.append("#### Platform Breakdown")
                lines.append("")
                lines.append("| Platform | Tests | Passed | Failed | Duration |")
                lines.append("|----------|-------|--------|--------|----------|")
                for platform_name, platform_data in e2e["platforms"].items():
                    lines.append(f"| **{platform_name}** | {platform_data['total']} | {platform_data['passed']} | {platform_data['failed']} | {platform_data.get('duration', 0)}s |")
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
        description="Aggregate coverage from backend (pytest), frontend (Jest), mobile (jest-expo), and desktop (tarpaulin) tests"
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
        "--mobile-coverage",
        type=Path,
        default=Path(__file__).parent.parent.parent.parent / "mobile" / "coverage" / "coverage-final.json",
        help="Path to jest-expo coverage-final.json (default: mobile/coverage/coverage-final.json)"
    )
    parser.add_argument(
        "--desktop-coverage",
        type=Path,
        default=Path(__file__).parent.parent.parent.parent / "frontend-nextjs" / "src-tauri" / "coverage" / "coverage.json",
        help="Path to tarpaulin coverage.json (default: frontend-nextjs/src-tauri/coverage/coverage.json)"
    )
    parser.add_argument(
        "--e2e-results",
        type=Path,
        default=None,
        help="Path to unified E2E test results JSON (from e2e_aggregator.py)"
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
    aggregate_data = aggregate_coverage(
        args.pytest_coverage,
        args.jest_coverage,
        args.mobile_coverage,
        args.desktop_coverage,
        args.e2e_results
    )

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
