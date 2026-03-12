#!/usr/bin/env python3
"""
Measure actual backend coverage using pytest --cov with branch coverage.

This script runs the full backend test suite with coverage measurement
to establish the true baseline after SQLAlchemy conflicts are resolved.
"""
import argparse
import json
import subprocess
import sys
from pathlib import Path
from datetime import datetime

# Backend directory
BACKEND_DIR = Path(__file__).parent.parent.parent
COVERAGE_REPORTS_DIR = BACKEND_DIR / "tests" / "coverage_reports"

def run_coverage_with_branch(verbose=False):
    """Run pytest with coverage and branch measurement."""
    cmd = [
        "python3", "-m", "pytest",
        "--cov=backend",
        "--cov-branch",  # Enable branch coverage
        "--cov-report=json",
        "--cov-report=term-missing:skip-covered",
        "--cov-report=html",
        "-v" if verbose else "-q",
    ]

    print("Running: {}".format(' '.join(cmd)))
    result = subprocess.run(cmd, cwd=BACKEND_DIR, capture_output=False)
    return result.returncode

def parse_coverage_json():
    """Parse coverage.json and extract metrics."""
    coverage_file = BACKEND_DIR / "coverage.json"
    if not coverage_file.exists():
        print("ERROR: {} not found".format(coverage_file))
        return None

    with open(coverage_file) as f:
        data = json.load(f)

    # Extract overall summary
    summary = {
        "measured_at": datetime.now().isoformat(),
        "line_coverage": data["totals"]["percent_covered"],
        "lines_covered": data["totals"]["covered_lines"],
        "lines_total": data["totals"]["num_statements"],
        "branch_coverage": data["totals"].get("percent_covered", 0),
        "branches_covered": data["totals"].get("covered_branches", 0),
        "branches_total": data["totals"].get("num_branches", 0),
        "files": [],
    }

    # Extract per-file metrics
    for file_path, file_data in data.get("files", {}).items():
        if file_path.startswith("backend/"):
            file_summary = {
                "file": file_path,
                "line_coverage": file_data["summary"]["percent_covered"],
                "lines_covered": file_data["summary"]["covered_lines"],
                "lines_total": file_data["summary"]["num_statements"],
                "missing_lines": file_data["summary"].get("missing_lines", []),
            }
            summary["files"].append(file_summary)

    # Sort files by coverage (lowest first)
    summary["files"].sort(key=lambda x: x["line_coverage"])

    return summary

def generate_markdown_report(summary_data, output_path):
    """Generate human-readable markdown report."""
    if not summary_data:
        return

    lines = [
        "# Backend Coverage Report - Phase 171",
        "**Generated:** {}".format(summary_data['measured_at']),
        "**Phase:** 171 - Gap Closure & Final Push",
        "",
        "## Executive Summary",
        "- **Line Coverage:** {:.2f}% ({:,}/{:,} lines)".format(
            summary_data['line_coverage'],
            summary_data['lines_covered'],
            summary_data['lines_total']
        ),
    ]

    # Add branch coverage if available
    if summary_data.get('branch_coverage'):
        lines.append("- **Branch Coverage:** {:.2f}%".format(summary_data['branch_coverage']))

    lines.extend([
        "",
        "## Coverage Gap to 80% Target",
        "- **Current:** {:.2f}%".format(summary_data['line_coverage']),
        "- **Target:** 80.00%",
        "- **Gap:** {:.2f} percentage points".format(80.0 - summary_data['line_coverage']),
        "- **Lines Needed:** {:,}".format(int(0.80 * summary_data['lines_total']) - summary_data['lines_covered']),
        "",
        "## Files Below 80% Coverage (Top 20)",
        ""
    ])

    # Add top 20 files with lowest coverage
    low_coverage = [f for f in summary_data["files"] if f["line_coverage"] < 80.0]
    for i, file_data in enumerate(low_coverage[:20], 1):
        lines.append("{}. **{}**".format(i, file_data['file']))
        lines.append("   - Coverage: {:.2f}% ({}/{})".format(
            file_data['line_coverage'],
            file_data['lines_covered'],
            file_data['lines_total']
        ))
        if file_data["missing_lines"]:
            lines.append("   - Missing: {} lines".format(len(file_data['missing_lines'])))
        lines.append("")

    # Add high-coverage files
    lines.extend([
        "",
        "## Files Above 80% Coverage",
        ""
    ])
    high_coverage = [f for f in summary_data["files"] if f["line_coverage"] >= 80.0]
    lines.append("{} files meet or exceed 80% coverage target:".format(len(high_coverage)))
    for file_data in high_coverage[:50]:  # First 50
        lines.append("- {}: {:.2f}%".format(file_data['file'], file_data['line_coverage']))

    output_path.write_text("\n".join(lines))
    print("Report written to: {}".format(output_path))

def main():
    parser = argparse.ArgumentParser(description="Measure backend coverage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Ensure output directory exists
    COVERAGE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    # Run coverage measurement
    print("=" * 60)
    print("Measuring backend coverage with branch measurement...")
    print("=" * 60)
    returncode = run_coverage_with_branch(verbose=args.verbose)

    if returncode != 0:
        print("WARNING: pytest exited with code {}".format(returncode))
        print("Coverage report may be incomplete.")

    # Parse and save results
    summary = parse_coverage_json()
    if summary:
        # Save JSON
        json_path = COVERAGE_REPORTS_DIR / "backend_phase_171_overall.json"
        json_path.write_text(json.dumps(summary, indent=2))
        print("JSON saved to: {}".format(json_path))

        # Generate markdown
        md_path = COVERAGE_REPORTS_DIR / "backend_phase_171_overall.md"
        generate_markdown_report(summary, md_path)

        print("\n" + "=" * 60)
        print("COVERAGE SUMMARY")
        print("=" * 60)
        print("Line Coverage: {:.2f}%".format(summary['line_coverage']))
        if summary.get('branch_coverage'):
            print("Branch Coverage: {:.2f}%".format(summary['branch_coverage']))
        print("Gap to 80%: {:.2f}pp".format(80.0 - summary['line_coverage']))
        print("=" * 60)

    return returncode

if __name__ == "__main__":
    sys.exit(main())
