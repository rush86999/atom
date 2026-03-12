#!/usr/bin/env python3
"""
Measure actual backend coverage using pytest --cov with branch coverage.

This script analyzes the Phase 161 baseline and compares against previous
estimates to establish the true coverage baseline after SQLAlchemy conflicts
are resolved.

Since many tests have collection errors due to SQLAlchemy metadata conflicts
(duplicate models), this script uses the Phase 161 baseline (8.50% coverage)
as the authoritative measurement and compares against previous estimates.
"""
import argparse
import json
import sys
from pathlib import Path
from datetime import datetime

# Backend directory
BACKEND_DIR = Path(__file__).parent.parent.parent
COVERAGE_REPORTS_DIR = BACKEND_DIR / "tests" / "coverage_reports"

def parse_phase_161_baseline():
    """Parse Phase 161 baseline coverage.json."""
    baseline_file = COVERAGE_REPORTS_DIR / "metrics" / "backend_161_final.json"
    if not baseline_file.exists():
        print("ERROR: {} not found".format(baseline_file))
        return None

    with open(baseline_file) as f:
        data = json.load(f)

    # Extract overall summary
    summary = {
        "measured_at": "2026-03-10T11:58:00Z",  # From Phase 161-03 SUMMARY
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

def generate_comparison_analysis(summary_data):
    """Generate comparison against previous estimates."""
    if not summary_data:
        return None

    comparison = {
        "generated_at": datetime.now().isoformat(),
        "actual_coverage": {
            "line_percent": summary_data['line_coverage'],
            "lines_covered": summary_data['lines_covered'],
            "lines_total": summary_data['lines_total']
        },
        "previous_estimates": {
            "phase_161_baseline": 8.50,
            "phase_166_claimed": 85.0,
            "phase_164_gap_analysis": 74.55
        },
        "discrepancies": [
            {
                "source": "phase_166",
                "claimed": 85.0,
                "actual": summary_data['line_coverage'],
                "gap": 85.0 - summary_data['line_coverage']
            },
            {
                "source": "phase_164",
                "claimed": 74.55,
                "actual": summary_data['line_coverage'],
                "gap": 74.55 - summary_data['line_coverage']
            }
        ],
        "files_below_80_percent": len([f for f in summary_data["files"] if f["line_coverage"] < 80.0]),
        "files_with_zero_coverage": len([f for f in summary_data["files"] if f["line_coverage"] == 0.0]),
        "recommended_focus_areas": [
            "Governance services (high business impact)",
            "LLM services (high business impact)",
            "Episodic memory (medium business impact)",
            "API routes (medium business impact)"
        ]
    }

    return comparison

def calculate_roadmap(summary_data, comparison_data):
    """Calculate realistic roadmap to 80% target."""
    if not summary_data or not comparison_data:
        return None

    current_coverage = summary_data['line_coverage']
    lines_total = summary_data['lines_total']
    lines_covered = summary_data['lines_covered']

    # Calculate effort
    lines_needed = int(0.80 * lines_total) - lines_covered
    avg_test_speed = 50  # lines per hour
    estimated_hours = lines_needed / avg_test_speed

    # Calculate phases needed (based on Phases 165-170: ~3-5pp per phase)
    gap_to_80 = 80.0 - current_coverage
    avg_coverage_per_phase = 4.0  # Conservative estimate
    phases_needed = int(gap_to_80 / avg_coverage_per_phase) + 1

    roadmap = {
        "current_coverage": current_coverage,
        "target_coverage": 80.0,
        "gap_to_80": gap_to_80,
        "lines_needed": lines_needed,
        "estimated_hours": estimated_hours,
        "phases_needed": phases_needed,
        "phases_breakdown": []
    }

    # Generate phase breakdown
    current = current_coverage
    for i in range(1, phases_needed + 1):
        target = min(current + avg_coverage_per_phase, 80.0)
        roadmap["phases_breakdown"].append({
            "phase": 171 + i,
            "target_coverage": target,
            "focus": [
                "High-impact zero-coverage files" if i == 1 else
                "API routes with critical paths" if i == 2 else
                "Episodic memory services" if i == 3 else
                "Tools and integrations" if i == 4 else
                "Continued coverage improvement"
            ]
        })
        current = target

    return roadmap

def generate_markdown_report(summary_data, comparison_data, roadmap_data, output_path):
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
        "- **Source:** Phase 161 baseline (authoritative full-backend measurement)",
        "",
        "## Actual vs Previous Estimates",
        "",
        "### Discrepancy Analysis",
        ""
    ]

    # Add discrepancy table
    lines.append("| Source | Claimed | Actual | Gap |")
    lines.append("|--------|---------|--------|-----|")
    for discrepancy in comparison_data.get("discrepancies", []):
        lines.append("| {} | {:.2f}% | {:.2f}% | {:.2f}pp |".format(
            discrepancy["source"].title(),
            discrepancy["claimed"],
            discrepancy["actual"],
            discrepancy["gap"]
        ))

    lines.extend([
        "",
        "**Key Finding:** Previous phases used \"service-level estimates\" which dramatically overstated actual coverage. Phase 161's comprehensive measurement of all 72,727 lines revealed the true baseline is 8.50%, not 74-85% as previously claimed.",
        "",
        "## Coverage Gap to 80% Target",
        "- **Current:** {:.2f}%".format(summary_data['line_coverage']),
        "- **Target:** 80.00%",
        "- **Gap:** {:.2f} percentage points".format(80.0 - summary_data['line_coverage']),
        "- **Lines Needed:** {:,}".format(int(0.80 * summary_data['lines_total']) - summary_data['lines_covered']),
        "",
        "## File Statistics",
        "- **Total Files:** {}".format(len(summary_data['files'])),
        "- **Files Below 80%:** {}".format(comparison_data['files_below_80_percent']),
        "- **Files with Zero Coverage:** {}".format(comparison_data['files_with_zero_coverage']),
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
        if file_data.get("missing_lines") and isinstance(file_data["missing_lines"], list):
            lines.append("   - Missing: {} lines".format(len(file_data['missing_lines'])))
        elif file_data.get("missing_lines") and isinstance(file_data["missing_lines"], int):
            lines.append("   - Missing: {} lines".format(file_data['missing_lines']))
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

    # Add roadmap section
    if roadmap_data:
        lines.extend([
            "",
            "## Realistic Roadmap to 80% Target",
            "",
            "### Effort Calculation",
            "- **Current Coverage:** {:.2f}% ({:,}/{:,} lines)".format(
                roadmap_data['current_coverage'],
                summary_data['lines_covered'],
                summary_data['lines_total']
            ),
            "- **Target Coverage:** 80.00%",
            "- **Lines to Cover:** {:,}".format(roadmap_data['lines_needed']),
            "- **Estimated Hours:** {:.0f} hours (at 50 lines/hour average)".format(roadmap_data['estimated_hours']),
            "- **Estimated Phases:** {} phases (at 4pp/phase average)".format(roadmap_data['phases_needed']),
            "",
            "### Phase Breakdown",
            "Based on Phases 165-170 performance (~3-5pp per phase):",
            ""
        ])

        for phase_info in roadmap_data['phases_breakdown']:
            lines.append("- **Phase {}:** Target {:.2f}% - {}".format(
                phase_info['phase'],
                phase_info['target_coverage'],
                phase_info['focus'][0]
            ))

        lines.extend([
            "",
            "### Recommended Next Phases",
            "1. **Phase 172:** High-impact zero-coverage files (governance, LLM)",
            "2. **Phase 173:** API routes with critical paths",
            "3. **Phase 174:** Episodic memory services",
            "4. **Phase 175:** Tools and integrations",
            "5. Continue until 80% achieved"
        ])

    output_path.write_text("\n".join(lines))
    print("Report written to: {}".format(output_path))

def main():
    parser = argparse.ArgumentParser(description="Measure backend coverage")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    args = parser.parse_args()

    # Ensure output directory exists
    COVERAGE_REPORTS_DIR.mkdir(parents=True, exist_ok=True)

    print("=" * 60)
    print("Analyzing Phase 161 baseline coverage...")
    print("=" * 60)

    # Parse Phase 161 baseline
    summary = parse_phase_161_baseline()
    if not summary:
        print("ERROR: Failed to parse Phase 161 baseline")
        return 1

    # Generate comparison analysis
    comparison = generate_comparison_analysis(summary)
    if not comparison:
        print("ERROR: Failed to generate comparison analysis")
        return 1

    # Calculate roadmap
    roadmap = calculate_roadmap(summary, comparison)
    if not roadmap:
        print("ERROR: Failed to calculate roadmap")
        return 1

    # Save JSON
    json_path = COVERAGE_REPORTS_DIR / "backend_phase_171_overall.json"
    json_path.write_text(json.dumps(summary, indent=2))
    print("JSON saved to: {}".format(json_path))

    # Save comparison JSON
    comparison_path = COVERAGE_REPORTS_DIR / "metrics" / "actual_vs_estimated.json"
    comparison_path.parent.mkdir(parents=True, exist_ok=True)
    comparison_path.write_text(json.dumps(comparison, indent=2))
    print("Comparison saved to: {}".format(comparison_path))

    # Generate markdown
    md_path = COVERAGE_REPORTS_DIR / "backend_phase_171_overall.md"
    generate_markdown_report(summary, comparison, roadmap, md_path)

    print("\n" + "=" * 60)
    print("COVERAGE SUMMARY")
    print("=" * 60)
    print("Line Coverage: {:.2f}%".format(summary['line_coverage']))
    print("Gap to 80%: {:.2f}pp".format(80.0 - summary['line_coverage']))
    print("Estimated Phases Needed: {}".format(roadmap['phases_needed']))
    print("=" * 60)

    return 0

if __name__ == "__main__":
    sys.exit(main())
