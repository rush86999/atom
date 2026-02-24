#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coverage Report Generator

Generates comprehensive coverage reports for the Atom backend.
Produces JSON metrics, HTML reports, and markdown documentation.

Usage:
    python3 coverage_report_generator.py              # Generate all reports
    python3 coverage_report_generator.py json         # JSON only
    python3 coverage_report_generator.py html         # HTML only
    python3 coverage_report_generator.py markdown     # Markdown only

Output:
    metrics/coverage.json - Machine-readable coverage metrics
    html/index.html - Human-readable HTML coverage report
    COVERAGE_REPORT_v3.2.md - Comprehensive markdown report
"""

import json
import os
import subprocess
import sys
from datetime import datetime
from pathlib import Path


# Configuration
SCRIPT_DIR = Path(__file__).parent
BACKEND_DIR = SCRIPT_DIR.parent.parent
METRICS_DIR = SCRIPT_DIR / "metrics"
HTML_DIR = SCRIPT_DIR / "html"
COVERAGE_JSON = METRICS_DIR / "coverage.json"
HTML_INDEX = HTML_DIR / "index.html"
MARKDOWN_REPORT = SCRIPT_DIR / "COVERAGE_REPORT_v3.2.md"

# Coverage source directories
SOURCE_DIRS = ["core", "api", "tools"]

# Baseline coverage from Phase 01
BASELINE_COVERAGE = 5.13


def run_pytest_coverage():
    """
    Run pytest with coverage enabled.

    Returns:
        Tuple of (success, output)
    """
    print("Running pytest with coverage...")

    cmd = [
        "python3", "-m", "pytest",
        "--cov=core",
        "--cov=api",
        "--cov=tools",
        "--cov-report=json",
        "--cov-report=html:{}".format(HTML_DIR),
        "--cov-report=term-missing",
        "-v",
        "--tb=short"
    ]

    try:
        result = subprocess.run(
            cmd,
            cwd=BACKEND_DIR,
            capture_output=True,
            text=True,
            timeout=300  # 5 minute timeout
        )

        success = result.returncode == 0
        output = result.stdout + result.stderr

        return success, output
    except subprocess.TimeoutExpired:
        return False, "Error: pytest timed out after 5 minutes"
    except Exception as e:
        return False, "Error running pytest: {}".format(e)


def parse_coverage_json(filepath):
    """
    Load and parse coverage.json.

    Args:
        filepath: Path to coverage.json

    Returns:
        Parsed coverage data or None if error
    """
    if not filepath.exists():
        print("Error: {} not found".format(filepath))
        return None

    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except json.JSONDecodeError as e:
        print("Error: Invalid JSON in {}: {}".format(filepath, e))
        return None
    except Exception as e:
        print("Error reading {}: {}".format(filepath, e))
        return None


def get_file_coverage(coverage_data, file_path):
    """
    Get coverage for a specific file.

    Args:
        coverage_data: Parsed coverage.json data
        file_path: Path to file (relative to backend/)

    Returns:
        File coverage dict or None if not found
    """
    files = coverage_data.get("files", {})

    # Normalize file path (remove leading 'backend/' if present)
    normalized_path = file_path
    if file_path.startswith("backend/"):
        normalized_path = file_path[8:]

    # Try exact match
    if normalized_path in files:
        return files[normalized_path]

    # Try with 'backend/' prefix
    with_backend = "backend/{}".format(normalized_path)
    if with_backend in files:
        return files[with_backend]

    return None


def get_module_summary(coverage_data, module_name):
    """
    Get summary for a specific module (core/api/tools).

    Args:
        coverage_data: Parsed coverage.json data
        module_name: Module name (core, api, or tools)

    Returns:
        Summary dict with keys: files, lines, covered, coverage_percent
    """
    files = coverage_data.get("files", {})

    # Filter files for this module
    module_files = {}
    for path, data in files.items():
        if path.startswith("backend/{}/".format(module_name)) or path.startswith("{}/".format(module_name)):
            module_files[path] = data

    if not module_files:
        return {
            "files": 0,
            "lines": 0,
            "covered": 0,
            "coverage_percent": 0.0
        }

    # Aggregate metrics
    total_files = len(module_files)
    total_lines = 0
    total_covered = 0

    for data in module_files.values():
        total_lines += data.get("summary", {}).get("num_statements", 0)
        total_covered += data.get("summary", {}).get("covered_lines", 0)

    coverage_percent = (total_covered / total_lines * 100) if total_lines > 0 else 0.0

    return {
        "files": total_files,
        "lines": total_lines,
        "covered": total_covered,
        "coverage_percent": round(coverage_percent, 2)
    }


def calculate_coverage_trend(current, baseline):
    """
    Calculate coverage improvement over baseline.

    Args:
        current: Current coverage percentage
        baseline: Baseline coverage percentage

    Returns:
        Dict with absolute_change, relative_change, improvement_factor
    """
    absolute_change = current - baseline
    relative_change = (absolute_change / baseline * 100) if baseline > 0 else 0
    improvement_factor = (current / baseline) if baseline > 0 else 0

    return {
        "absolute_change": round(absolute_change, 2),
        "relative_change": round(relative_change, 2),
        "improvement_factor": round(improvement_factor, 2)
    }


def get_coverage_distribution(coverage_data):
    """
    Calculate coverage distribution across files.

    Args:
        coverage_data: Parsed coverage.json data

    Returns:
        Dict mapping ranges to lists of files
    """
    files = coverage_data.get("files", {})

    distribution = {
        "0%": [],
        "1-20%": [],
        "21-50%": [],
        "51-70%": [],
        "71-90%": [],
        "90%+": []
    }

    for path, data in files.items():
        summary = data.get("summary", {})
        total = summary.get("num_statements", 0)
        covered = summary.get("covered_lines", 0)

        if total == 0:
            continue

        coverage_percent = (covered / total * 100)

        if coverage_percent == 0:
            distribution["0%"].append(path)
        elif coverage_percent <= 20:
            distribution["1-20%"].append(path)
        elif coverage_percent <= 50:
            distribution["21-50%"].append(path)
        elif coverage_percent <= 70:
            distribution["51-70%"].append(path)
        elif coverage_percent < 90:
            distribution["71-90%"].append(path)
        else:
            distribution["90%+"].append(path)

    return distribution


def get_top_files_by_uncovered(coverage_data, limit=50):
    """
    Get top files with most uncovered lines.

    Args:
        coverage_data: Parsed coverage.json data
        limit: Maximum number of files to return

    Returns:
        List of dicts with filename, total, covered, coverage, uncovered
    """
    files = coverage_data.get("files", {})

    file_metrics = []

    for path, data in files.items():
        summary = data.get("summary", {})
        total = summary.get("num_statements", 0)
        covered = summary.get("covered_lines", 0)

        if total == 0:
            continue

        uncovered = total - covered
        coverage_percent = round((covered / total * 100), 2)

        file_metrics.append({
            "filename": path,
            "total": total,
            "covered": covered,
            "coverage": coverage_percent,
            "uncovered": uncovered
        })

    # Sort by uncovered lines descending
    file_metrics.sort(key=lambda x: x["uncovered"], reverse=True)

    return file_metrics[:limit]


def generate_markdown_report(coverage_data, output_path):
    """
    Generate comprehensive markdown coverage report.

    Args:
        coverage_data: Parsed coverage.json data
        output_path: Path to output markdown file

    Returns:
        True if successful
    """
    print("Generating markdown report: {}".format(output_path))

    totals = coverage_data.get("totals", {})
    overall_coverage = totals.get("percent_covered", 0.0)
    lines_covered = totals.get("covered_lines", 0)
    lines_total = totals.get("num_statements", 0)

    # Module summaries
    core_summary = get_module_summary(coverage_data, "core")
    api_summary = get_module_summary(coverage_data, "api")
    tools_summary = get_module_summary(coverage_data, "tools")

    # Coverage trend
    trend = calculate_coverage_trend(overall_coverage, BASELINE_COVERAGE)

    # Distribution
    distribution = get_coverage_distribution(coverage_data)

    # Top files by uncovered lines
    top_files = get_top_files_by_uncovered(coverage_data, limit=50)

    # Calculate distribution stats
    total_files = sum(len(files) for files in distribution.values())

    # Generate markdown
    lines = []

    # Header
    lines.append("# Coverage Report v3.2 - Baseline for Bug Finding & Coverage Expansion")
    lines.append("")
    lines.append("**Generated:** {}".format(datetime.now().strftime('%Y-%m-%d')))
    lines.append("**Phase:** 81-01")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    lines.append("**Overall Coverage: {:.2f}%**".format(overall_coverage))
    lines.append("")
    lines.append("| Metric | Value |")
    lines.append("|--------|-------|")
    lines.append("| Lines Covered | {:,} |".format(lines_covered))
    lines.append("| Lines Missing | {:,} |".format(lines_total - lines_covered))
    lines.append("| Total Lines | {:,} |".format(lines_total))
    lines.append("| Coverage vs Baseline | {:+.2f}% ({:+.1f}% change) |".format(trend['absolute_change'], trend['relative_change']))
    lines.append("| Improvement Factor | {:.2f}x |".format(trend['improvement_factor']))
    lines.append("")

    if overall_coverage > BASELINE_COVERAGE:
        lines.append("Coverage has **improved** by {:.2f} percentage points since baseline (5.13%).".format(trend['absolute_change']))
    else:
        lines.append("Coverage has **decreased** by {:.2f} percentage points since baseline (5.13%).".format(abs(trend['absolute_change'])))

    lines.append("")

    # Module Breakdown
    lines.append("## Module Breakdown")
    lines.append("")
    lines.append("| Module | Files | Lines | Covered | Coverage |")
    lines.append("|--------|-------|-------|---------|----------|")
    lines.append("| core | {:,} | {:,} | {:,} | {:.2f}% |".format(
        core_summary['files'], core_summary['lines'], core_summary['covered'], core_summary['coverage_percent']))
    lines.append("| api | {:,} | {:,} | {:,} | {:.2f}% |".format(
        api_summary['files'], api_summary['lines'], api_summary['covered'], api_summary['coverage_percent']))
    lines.append("| tools | {:,} | {:,} | {:,} | {:.2f}% |".format(
        tools_summary['files'], tools_summary['lines'], tools_summary['covered'], tools_summary['coverage_percent']))
    lines.append("")

    # Coverage Distribution
    lines.append("## Coverage Distribution")
    lines.append("")
    lines.append("**Total Files Analyzed:** {:,}".format(total_files))
    lines.append("")

    for range_name, files_list in distribution.items():
        file_count = len(files_list)
        percentage = (file_count / total_files * 100) if total_files > 0 else 0
        lines.append("- **{} coverage:** {} files ({:.1f}%)".format(range_name, file_count, percentage))

    lines.append("")

    # File-by-File Details (Top 50 by uncovered lines)
    lines.append("## File-by-File Details (Top 50 by Uncovered Lines)")
    lines.append("")
    lines.append("Sorted by number of uncovered lines (highest gap first).")
    lines.append("")
    lines.append("| Rank | File | Total Lines | Covered | Coverage | Uncovered | Priority |")
    lines.append("|------|------|-------------|---------|----------|-----------|----------|")

    for idx, file_data in enumerate(top_files, 1):
        filename = file_data["filename"]
        # Truncate filename if too long
        if len(filename) > 50:
            filename = "..." + filename[-47:]

        total = file_data["total"]
        covered = file_data["covered"]
        coverage = file_data["coverage"]
        uncovered = file_data["uncovered"]

        # Determine priority
        if total > 200 and coverage < 30:
            priority = "HIGH"
        elif total > 100 and coverage < 50:
            priority = "MED"
        elif coverage < 10:
            priority = "LOW"
        else:
            priority = "OK"

        lines.append("| {} | {} | {} | {} | {}% | {} | {} |".format(
            idx, filename, total, covered, coverage, uncovered, priority))

    lines.append("")

    # Priority Files Section
    lines.append("## Priority Files for Testing")
    lines.append("")
    lines.append("### High Priority (>200 lines, <30% coverage)")
    lines.append("")

    high_priority = [
        f for f in top_files
        if f["total"] > 200 and f["coverage"] < 30
    ][:20]

    if high_priority:
        lines.append("These files have significant code with minimal coverage - prioritize for testing:")
        lines.append("")
        for file_data in high_priority:
            lines.append("- **{}**".format(file_data['filename']))
            lines.append("  - {:,} lines, {:.2f}% coverage".format(file_data['total'], file_data['coverage']))
            lines.append("  - {:,} uncovered lines".format(file_data['uncovered']))
            lines.append("")
    else:
        lines.append("No files match the high-priority criteria (>200 lines, <30% coverage).")
        lines.append("")

    # Data Sources
    lines.append("## Data Sources")
    lines.append("")
    lines.append("- **Coverage Report:** `tests/coverage_reports/metrics/coverage.json`")
    lines.append("- **HTML Report:** `tests/coverage_reports/html/index.html`")
    lines.append("- **Test Execution:** pytest with pytest-cov")
    lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("**Report Generated:** {}".format(datetime.now().isoformat()))
    lines.append("**Phase:** 81-01 (Coverage Analysis & Prioritization)")
    lines.append("")

    # Write to file
    try:
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write('\n'.join(lines))

        print("Generated markdown report: {}".format(output_path))
        return True
    except Exception as e:
        print("Error writing markdown report: {}".format(e))
        return False


def generate_coverage_report(output_format="all"):
    """
    Generate coverage report in specified format(s).

    Args:
        output_format: One of: all, json, html, markdown

    Returns:
        Dict with success status and metrics
    """
    print("=" * 60)
    print("Coverage Report Generator v3.2")
    print("=" * 60)
    print()

    # Run pytest with coverage
    success, output = run_pytest_coverage()

    if not success:
        print("Warning: pytest had failures, but coverage data may still be valid")
        print(output)
    else:
        print("pytest completed successfully")

    print()

    # Parse coverage.json
    coverage_data = parse_coverage_json(COVERAGE_JSON)

    if coverage_data is None:
        return {
            "success": False,
            "error": "Failed to parse coverage.json"
        }

    # Extract overall metrics
    totals = coverage_data.get("totals", {})
    overall_coverage = totals.get("percent_covered", 0.0)
    lines_covered = totals.get("covered_lines", 0)
    lines_total = totals.get("num_statements", 0)

    print("Overall Coverage: {:.2f}%".format(overall_coverage))
    print("Lines: {:,} / {:,}".format(lines_covered, lines_total))
    print()

    # Generate reports based on format
    if output_format in ["all", "json"]:
        print("JSON report: {}".format(COVERAGE_JSON))

    if output_format in ["all", "html"]:
        if HTML_INDEX.exists():
            print("HTML report: {}".format(HTML_INDEX))
            print("  Open in browser: file://{}".format(HTML_INDEX.absolute()))
        else:
            print("Warning: HTML report not found at {}".format(HTML_INDEX))

    if output_format in ["all", "markdown"]:
        generate_markdown_report(coverage_data, MARKDOWN_REPORT)

    print()
    print("=" * 60)
    print("Coverage Report Generation Complete")
    print("=" * 60)

    return {
        "success": True,
        "overall_coverage": overall_coverage,
        "lines_covered": lines_covered,
        "lines_total": lines_total,
        "coverage_json": str(COVERAGE_JSON),
        "html_report": str(HTML_INDEX),
        "markdown_report": str(MARKDOWN_REPORT)
    }


def main():
    """Main entry point."""
    # Parse output format from command line
    output_format = "all"
    if len(sys.argv) > 1:
        arg = sys.argv[1].lower()
        if arg in ["json", "html", "markdown", "all"]:
            output_format = arg
        else:
            print("Invalid format: {}".format(arg))
            print("Usage: python3 coverage_report_generator.py [json|html|markdown|all]")
            sys.exit(1)

    # Generate report
    result = generate_coverage_report(output_format)

    if not result["success"]:
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
