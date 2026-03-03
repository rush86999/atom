#!/usr/bin/env python3
"""
Baseline Coverage Report Generator

Generates a baseline coverage report identifying all files below 80% coverage
with per-file breakdown. This establishes the v5.0 coverage expansion baseline.

Usage:
    python3 tests/scripts/generate_baseline_coverage_report.py
    python3 tests/scripts/generate_baseline_coverage_report.py --threshold 0.85
    python3 tests/scripts/generate_baseline_coverage_report.py --coverage-file custom_coverage.json
    python3 tests/scripts/generate_baseline_coverage_report.py --output-dir reports/
    python3 tests/scripts/generate_baseline_coverage_report.py --unified

Output Files:
    - metrics/coverage_baseline.json: Machine-readable baseline data
    - COVERAGE_BASELINE_v5.0.md: Human-readable markdown report

Requirements:
    - Python 3.11+
    - coverage.json from pytest-cov

Author: Phase 100 Coverage Analysis
Generated: 2026-02-27
"""

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_coverage_data(coverage_path: str) -> Dict[str, Any]:
    """
    Load coverage.json from pytest-cov.

    Args:
        coverage_path: Path to coverage.json file

    Returns:
        Coverage data dictionary

    Raises:
        FileNotFoundError: If coverage.json doesn't exist
        json.JSONDecodeError: If coverage.json is invalid
    """
    path = Path(coverage_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Coverage file not found: {coverage_path}\n"
            f"Run tests with coverage first: "
            f"pytest --cov=core --cov=api --cov=tools --cov-report=json --cov-report=term -q"
        )

    with open(path, 'r') as f:
        return json.load(f)


def identify_below_threshold(
    coverage_data: Dict[str, Any],
    threshold: float = 0.8
) -> List[Dict[str, Any]]:
    """
    Find all files below coverage threshold.

    Args:
        coverage_data: Coverage data dictionary from load_coverage_data()
        threshold: Coverage threshold (default 0.8 = 80%)

    Returns:
        List of dicts with keys: file, coverage_pct, total_lines, uncovered_lines
        Sorted by uncovered_lines descending (largest gaps first)
    """
    files_below = []

    for file_path, file_data in coverage_data.get("files", {}).items():
        summary = file_data.get("summary", {})
        total_lines = summary.get("num_statements", 0)
        covered_lines = summary.get("covered_lines", 0)
        coverage_pct = summary.get("percent_covered", 0.0) / 100.0

        if coverage_pct < threshold and total_lines > 0:
            uncovered_lines = total_lines - covered_lines
            files_below.append({
                "file": file_path,
                "coverage_pct": round(coverage_pct * 100, 2),
                "total_lines": total_lines,
                "covered_lines": covered_lines,
                "uncovered_lines": uncovered_lines
            })

    # Sort by uncovered_lines descending
    files_below.sort(key=lambda x: x["uncovered_lines"], reverse=True)
    return files_below


def generate_baseline_metrics(
    coverage_data: Dict[str, Any],
    files_below_threshold: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Compute baseline statistics.

    Args:
        coverage_data: Coverage data dictionary
        files_below_threshold: List from identify_below_threshold()

    Returns:
        Dictionary with overall, modules, threshold analysis, distribution
    """
    totals = coverage_data.get("totals", {})
    total_lines = totals.get("num_statements", 0)
    covered_lines = totals.get("covered_lines", 0)
    percent_covered = totals.get("percent_covered", 0.0)

    # Module breakdown
    module_breakdown = {"core": {"covered": 0, "total": 0}, "api": {"covered": 0, "total": 0},
                        "tools": {"covered": 0, "total": 0}, "other": {"covered": 0, "total": 0}}

    for file_path, file_data in coverage_data.get("files", {}).items():
        summary = file_data.get("summary", {})
        file_covered = summary.get("covered_lines", 0)
        file_total = summary.get("num_statements", 0)

        if file_path.startswith("core/"):
            module_breakdown["core"]["covered"] += file_covered
            module_breakdown["core"]["total"] += file_total
        elif file_path.startswith("api/"):
            module_breakdown["api"]["covered"] += file_covered
            module_breakdown["api"]["total"] += file_total
        elif file_path.startswith("tools/"):
            module_breakdown["tools"]["covered"] += file_covered
            module_breakdown["tools"]["total"] += file_total
        else:
            module_breakdown["other"]["covered"] += file_covered
            module_breakdown["other"]["total"] += file_total

    # Calculate module percentages
    for module in module_breakdown:
        if module_breakdown[module]["total"] > 0:
            module_breakdown[module]["percent"] = round(
                module_breakdown[module]["covered"] / module_breakdown[module]["total"] * 100, 2
            )
        else:
            module_breakdown[module]["percent"] = 0.0

    # Threshold analysis
    files_below_80 = len([f for f in files_below_threshold if f["coverage_pct"] < 80])
    files_below_50 = len([f for f in files_below_threshold if f["coverage_pct"] < 50])
    files_below_20 = len([f for f in files_below_threshold if f["coverage_pct"] < 20])

    # Distribution
    all_files = []
    for file_path, file_data in coverage_data.get("files", {}).items():
        summary = file_data.get("summary", {})
        coverage_pct = summary.get("percent_covered", 0.0)
        all_files.append(coverage_pct)

    distribution = {
        "0-20%": len([c for c in all_files if c < 20]),
        "21-50%": len([c for c in all_files if 20 <= c < 50]),
        "51-80%": len([c for c in all_files if 50 <= c < 80]),
        "80%+": len([c for c in all_files if c >= 80])
    }

    return {
        "overall": {
            "percent_covered": round(percent_covered, 2),
            "covered_lines": covered_lines,
            "total_lines": total_lines,
            "coverage_gap": total_lines - covered_lines
        },
        "modules": module_breakdown,
        "threshold_analysis": {
            "files_below_80": files_below_80,
            "files_below_50": files_below_50,
            "files_below_20": files_below_20
        },
        "distribution": distribution
    }


def write_json_report(
    metrics: Dict[str, Any],
    files_below_threshold: List[Dict[str, Any]],
    output_path: str,
    unified_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Save baseline metrics to JSON.

    Args:
        metrics: Metrics from generate_baseline_metrics()
        files_below_threshold: List from identify_below_threshold()
        output_path: Path to output JSON file
        unified_data: Optional unified platform coverage data
    """
    output = {
        "timestamp": datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z',
        "baseline_version": "v5.0",
        "overall": metrics["overall"],
        "modules": metrics["modules"],
        "threshold_analysis": metrics["threshold_analysis"],
        "distribution": metrics["distribution"],
        "files_below_threshold": files_below_threshold[:50]  # Top 50 files
    }

    if unified_data:
        output["unified"] = unified_data

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        json.dump(output, f, indent=2)


def write_markdown_report(
    metrics: Dict[str, Any],
    files_below_threshold: List[Dict[str, Any]],
    output_path: str,
    unified_data: Optional[Dict[str, Any]] = None
) -> None:
    """
    Generate human-readable markdown report.

    Args:
        metrics: Metrics from generate_baseline_metrics()
        files_below_threshold: List from identify_below_threshold()
        output_path: Path to output markdown file
        unified_data: Optional unified platform coverage data
    """
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    overall = metrics["overall"]
    modules = metrics["modules"]
    threshold = metrics["threshold_analysis"]
    distribution = metrics["distribution"]

    lines = []
    lines.append(f"# Coverage Baseline Report v5.0\n")
    lines.append(f"**Generated:** {timestamp} UTC\n")
    lines.append(f"**Purpose:** Establish baseline for v5.0 coverage expansion\n")
    lines.append("\n---\n")

    # Executive Summary
    lines.append("## Executive Summary\n")
    lines.append(f"- **Overall Coverage:** {overall['percent_covered']}% ")
    lines.append(f"({overall['covered_lines']:,} / {overall['total_lines']:,} lines)\n")
    lines.append(f"- **Coverage Gap:** {overall['coverage_gap']:,} lines below 80%\n")
    lines.append(f"- **Files Below 80%:** {threshold['files_below_80']}\n")
    lines.append(f"- **Files Below 50%:** {threshold['files_below_50']}\n")
    lines.append(f"- **Files Below 20%:** {threshold['files_below_20']}\n")
    lines.append("\n")

    # Module Breakdown
    lines.append("## Module Breakdown\n")
    lines.append("| Module | Coverage | Lines | Status |\n")
    lines.append("|--------|----------|-------|--------|\n")
    for module_name in ["core", "api", "tools", "other"]:
        module_data = modules[module_name]
        status = "✅" if module_data["percent"] >= 80 else "⚠️"
        lines.append(
            f"| {module_name.capitalize()} | {module_data['percent']}% | "
            f"{module_data['covered']:,}/{module_data['total']:,} | {status} |\n"
        )
    lines.append("\n")

    # Distribution
    lines.append("## Coverage Distribution\n")
    lines.append("| Range | File Count | Percentage |\n")
    lines.append("|-------|------------|------------|\n")
    total_files = sum(distribution.values())
    for range_name in ["0-20%", "21-50%", "51-80%", "80%+"]:
        count = distribution[range_name]
        pct = round(count / total_files * 100, 1) if total_files > 0 else 0
        lines.append(f"| {range_name} | {count} | {pct}% |\n")
    lines.append("\n")

    # Files Below 80%
    lines.append("## Files Below 80% Coverage\n")
    lines.append(f"**Total:** {len(files_below_threshold)} files below threshold\n\n")
    lines.append("### Top 50 Files by Uncovered Lines\n")
    lines.append("| Rank | File | Coverage | Uncovered | Total |\n")
    lines.append("|------|------|----------|-----------|-------|\n")

    for rank, file_data in enumerate(files_below_threshold[:50], 1):
        lines.append(
            f"| {rank} | `{file_data['file']}` | {file_data['coverage_pct']}% | "
            f"{file_data['uncovered_lines']} | {file_data['total_lines']} |\n"
        )
    lines.append("\n")

    # Unified Platform Breakdown (if provided)
    if unified_data:
        lines.append("## Unified Platform Breakdown\n")
        lines.append("| Platform | Coverage | Lines | Status |\n")
        lines.append("|----------|----------|-------|--------|\n")

        for platform_name in ["python", "javascript", "mobile", "rust"]:
            if platform_name in unified_data.get("platforms", {}):
                platform_data = unified_data["platforms"][platform_name]
                status = "✅" if platform_data["coverage_pct"] >= 80 else "⚠️"
                lines.append(
                    f"| {platform_name.capitalize()} | {platform_data['coverage_pct']}% | "
                    f"{platform_data['covered']:,}/{platform_data['total']:,} | {status} |\n"
                )

        if "overall" in unified_data:
            lines.append(
                f"| **Overall** | **{unified_data['overall']['coverage_pct']}%** | "
                f"**{unified_data['overall']['covered']:,}/{unified_data['overall']['total']:,}** | **📊** |\n"
            )
        lines.append("\n")

    # Footer
    lines.append("---\n")
    lines.append(f"\n**Report Version:** v5.0 Baseline\n")
    lines.append(f"**Next Steps:** See Phases 101-110 for coverage expansion plans\n")

    output_path = Path(output_path)
    output_path.parent.mkdir(parents=True, exist_ok=True)

    with open(output_path, 'w') as f:
        f.writelines(lines)


def main() -> int:
    """Orchestrate baseline report generation."""
    parser = argparse.ArgumentParser(
        description="Generate baseline coverage report for v5.0 expansion"
    )
    parser.add_argument(
        "--coverage-file",
        default="tests/coverage_reports/metrics/coverage.json",
        help="Path to coverage.json (default: tests/coverage_reports/metrics/coverage.json)"
    )
    parser.add_argument(
        "--output-dir",
        default="tests/coverage_reports/metrics",
        help="Output directory for reports (default: tests/coverage_reports/metrics)"
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=0.8,
        help="Coverage threshold (default: 0.8 = 80%%)"
    )
    parser.add_argument(
        "--unified",
        action="store_true",
        help="Include unified platform coverage (backend + frontend + mobile + desktop)"
    )

    args = parser.parse_args()

    try:
        # Load coverage data
        print(f"Loading coverage data from {args.coverage_file}...")
        coverage_data = load_coverage_data(args.coverage_file)
        print(f"✓ Loaded coverage data")

        # Identify files below threshold
        print(f"Identifying files below {args.threshold * 100:.0f}% threshold...")
        files_below = identify_below_threshold(coverage_data, args.threshold)
        print(f"✓ Found {len(files_below)} files below threshold")

        # Generate metrics
        print("Computing baseline metrics...")
        metrics = generate_baseline_metrics(coverage_data, files_below)
        print(f"✓ Overall coverage: {metrics['overall']['percent_covered']}%")

        # Load unified coverage if requested
        unified_data = None
        if args.unified:
            print("Aggregating unified platform coverage...")
            try:
                # Import aggregate_coverage function
                sys.path.insert(0, str(Path(__file__).parent.parent))
                from aggregate_coverage import aggregate_coverage

                # Resolve paths for all platforms
                backend_path = Path(args.coverage_file)
                frontend_path = Path("../../../frontend-nextjs/coverage/coverage-final.json")
                mobile_path = Path("../../../mobile/coverage/coverage-final.json")
                desktop_path = Path("../../../frontend-nextjs/src-tauri/coverage/coverage.json")

                # Run aggregation
                unified_result = aggregate_coverage(
                    pytest_path=backend_path,
                    jest_path=frontend_path,
                    jest_expo_path=mobile_path if mobile_path.exists() else None,
                    tarpaulin_path=desktop_path if desktop_path.exists() else None
                )

                # Parse unified result
                if unified_result and "platforms" in unified_result:
                    unified_data = unified_result
                    print(f"✓ Unified coverage: {unified_data['overall']['coverage_pct']}%")

            except ImportError as e:
                print(f"⚠ Warning: Could not import aggregate_coverage: {e}")
            except Exception as e:
                print(f"⚠ Warning: Unified aggregation failed: {e}")

        # Write JSON report
        json_output = Path(args.output_dir) / "coverage_baseline.json"
        write_json_report(metrics, files_below, str(json_output), unified_data)
        print(f"✓ Wrote {json_output}")

        # Write markdown report
        md_output = Path(args.output_dir).parent / "COVERAGE_BASELINE_v5.0.md"
        write_markdown_report(metrics, files_below, str(md_output), unified_data)
        print(f"✓ Wrote {md_output}")

        # Print summary
        print("\n" + "="*60)
        print("BASELINE REPORT SUMMARY")
        print("="*60)
        print(f"Overall Coverage:    {metrics['overall']['percent_covered']}%")
        print(f"Coverage Gap:        {metrics['overall']['coverage_gap']:,} lines")
        print(f"Files Below 80%:     {metrics['threshold_analysis']['files_below_80']}")
        print(f"Files Below 50%:     {metrics['threshold_analysis']['files_below_50']}")
        if unified_data:
            print(f"Unified Coverage:    {unified_data['overall']['coverage_pct']}%")
        print("="*60)

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in coverage file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == "__main__":
    sys.exit(main())
