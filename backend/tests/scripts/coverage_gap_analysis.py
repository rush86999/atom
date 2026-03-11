#!/usr/bin/env python3
"""
Coverage Gap Analysis Tool for Phase 164

Analyzes coverage gaps and prioritizes by business impact for systematic
gap closure. Uses actual line coverage from coverage.py (not service-level
estimates) per METHODOLOGY.md guidelines.

Usage:
    cd backend
    python tests/scripts/coverage_gap_analysis.py \
        --baseline tests/coverage_reports/metrics/backend_phase_161.json \
        --impact tests/coverage_reports/metrics/business_impact_scores.json \
        --output tests/coverage_reports/metrics/backend_164_gap_analysis.json \
        --report tests/coverage_reports/GAP_ANALYSIS_164.md

Output:
    - JSON: Machine-readable gap analysis with prioritized file list
    - Markdown: Human-readable report with top 50 files by impact
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict
from datetime import datetime, timezone

# Business impact tier scores (aligned with business_impact_scores.json)
TIER_SCORES = {
    "Critical": 10,  # Agent governance, LLM routing, episodic memory
    "High": 7,       # API routes, core services
    "Medium": 5,     # Utilities, helpers
    "Low": 3,        # Non-critical, low risk
}

# Module patterns for auto-tier assignment (if not in business_impact_scores.json)
MODULE_TIER_PATTERNS = {
    "Critical": [
        "agent_governance_service",
        "byok_handler",
        "episode_segmentation_service",
        "episode_retrieval_service",
        "episode_lifecycle_service",
        "agent_graduation_service",
        "cognitive_tier_system",
        "governance_cache",
    ],
    "High": [
        "agent_execution_service",
        "agent_world_model",
        "llm/",
        "canvas_tool",
        "browser_tool",
        "device_tool",
        "api/routes",
    ],
    "Medium": [
        "analytics",
        "workflow",
        "ab_testing",
    ],
}


def load_coverage_data(baseline_path: Path) -> Dict[str, Any]:
    """Load coverage.json and extract per-file metrics."""
    with open(baseline_path) as f:
        data = json.load(f)
    return data


def load_impact_scores(impact_path: Path) -> Dict[str, str]:
    """Load business impact scores and build file->tier lookup."""
    with open(impact_path) as f:
        data = json.load(f)

    # Build lookup from all_files array
    impact_lookup = {}
    for file_data in data.get("all_files", []):
        file_path = file_data.get("file", "")
        tier = file_data.get("tier", "Medium")
        impact_lookup[file_path] = tier

    return impact_lookup


def determine_tier(file_path: str, impact_lookup: Dict[str, str]) -> str:
    """Determine business impact tier for a file."""
    # Check lookup first
    if file_path in impact_lookup:
        return impact_lookup[file_path]

    # Auto-assign based on module patterns
    for tier, patterns in MODULE_TIER_PATTERNS.items():
        for pattern in patterns:
            if pattern in file_path:
                return tier

    return "Medium"  # Default


def calculate_complexity(num_statements: int, uncovered_lines: int) -> str:
    """Estimate testing complexity based on file size and gap."""
    if uncovered_lines > 500:
        return "high"
    elif uncovered_lines > 200:
        return "medium"
    else:
        return "low"


def calculate_priority_score(
    uncovered_lines: int,
    tier: str,
    current_coverage: float,
) -> float:
    """
    Calculate priority score for gap closure.

    Formula: priority_score = (uncovered_lines * tier_score) / (current_coverage + 1)

    Higher score = higher priority (more impact per test added)
    """
    tier_score = TIER_SCORES.get(tier, 5)
    # Add 1 to avoid division by zero
    priority_score = (uncovered_lines * tier_score) / (current_coverage + 1)
    return round(priority_score, 2)


def analyze_gaps(
    coverage_data: Dict[str, Any],
    impact_lookup: Dict[str, str],
    min_coverage_threshold: float = 80.0,
) -> List[Dict[str, Any]]:
    """Analyze coverage gaps and calculate priority scores."""
    gaps = []

    # Process files from coverage.json
    files = coverage_data.get("files", {})

    for file_path, file_data in files.items():
        # Skip test files, __init__, migrations
        if any(x in file_path for x in ["tests/", "test_", "__pycache__", "migrations/", "__init__.py"]):
            continue

        # Get summary metrics (handle both coverage.py versions)
        summary = file_data.get("summary", {})
        if not summary:
            continue

        coverage_pct = summary.get("percent_covered", 0.0)
        total_lines = summary.get("num_statements", 0)
        covered_lines = summary.get("covered_lines", 0)
        uncovered_lines = total_lines - covered_lines

        # Skip if already at or above threshold
        if coverage_pct >= min_coverage_threshold:
            continue

        # Determine business impact tier
        tier = determine_tier(file_path, impact_lookup)

        # Calculate complexity
        complexity = calculate_complexity(total_lines, uncovered_lines)

        # Calculate priority score
        priority_score = calculate_priority_score(uncovered_lines, tier, coverage_pct)

        # Extract missing lines for targeted testing
        missing_lines = file_data.get("missing_lines", [])
        executed_lines = file_data.get("executed_lines", [])

        gaps.append({
            "file": file_path,
            "coverage_pct": round(coverage_pct, 2),
            "total_lines": total_lines,
            "covered_lines": covered_lines,
            "uncovered_lines": uncovered_lines,
            "missing_lines": missing_lines,  # Line numbers needing coverage
            "business_impact": tier,
            "tier_score": TIER_SCORES[tier],
            "complexity": complexity,
            "priority_score": priority_score,
            "gap_to_target": round(min_coverage_threshold - coverage_pct, 2),
        })

    # Sort by priority score (descending)
    gaps.sort(key=lambda x: x["priority_score"], reverse=True)
    return gaps


def generate_gap_report(
    gaps: List[Dict[str, Any]],
    coverage_data: Dict[str, Any],
    output_path: Path,
    report_path: Optional[Path] = None,
) -> None:
    """Generate gap analysis report (JSON + optional Markdown)."""
    # Calculate overall metrics
    totals = coverage_data.get("totals", {})
    overall_coverage = totals.get("percent_covered", 0.0)
    total_lines = totals.get("num_statements", 0)
    covered_lines = totals.get("covered_lines", 0)

    # Group by business impact tier
    by_tier = defaultdict(list)
    for gap in gaps:
        by_tier[gap["business_impact"]].append(gap)

    # Create JSON report
    timestamp = datetime.now(timezone.utc).isoformat(timespec='seconds') + 'Z'
    report = {
        "generated_at": timestamp,
        "baseline_coverage": round(overall_coverage, 2),
        "target_coverage": 80.0,
        "gap_to_target": round(80.0 - overall_coverage, 2),
        "total_files_analyzed": len(gaps),
        "total_missing_lines": sum(g["uncovered_lines"] for g in gaps),
        "tier_breakdown": {
            "Critical": {
                "file_count": len(by_tier.get("Critical", [])),
                "missing_lines": sum(g["uncovered_lines"] for g in by_tier.get("Critical", [])),
                "files": by_tier.get("Critical", [])[:50],  # Top 50 critical files
            },
            "High": {
                "file_count": len(by_tier.get("High", [])),
                "missing_lines": sum(g["uncovered_lines"] for g in by_tier.get("High", [])),
                "files": by_tier.get("High", [])[:50],
            },
            "Medium": {
                "file_count": len(by_tier.get("Medium", [])),
                "missing_lines": sum(g["uncovered_lines"] for g in by_tier.get("Medium", [])),
                "files": by_tier.get("Medium", [])[:50],
            },
            "Low": {
                "file_count": len(by_tier.get("Low", [])),
                "missing_lines": sum(g["uncovered_lines"] for g in by_tier.get("Low", [])),
                "files": by_tier.get("Low", [])[:50],
            },
        },
        "all_gaps": gaps,  # Full ranked list
    }

    # Write JSON
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(report, f, indent=2)

    print(f"Gap analysis complete: {overall_coverage:.2f}% -> 80% target")
    print(f"Files below 80%: {len(gaps)}")
    print(f"Missing lines: {report['total_missing_lines']}")
    print(f"Output: {output_path}")

    # Generate Markdown report if requested
    if report_path:
        generate_markdown_report(report, report_path)


def generate_markdown_report(report: Dict[str, Any], report_path: Path) -> None:
    """Generate human-readable Markdown report."""
    lines = [
        "# Coverage Gap Analysis - Phase 164\n",
        f"**Generated**: {report['generated_at']}",
        f"**Baseline Coverage**: {report['baseline_coverage']}%",
        f"**Target Coverage**: {report['target_coverage']}%",
        f"**Gap to Close**: {report['gap_to_target']} percentage points",
        f"**Files Below Target**: {report['total_files_analyzed']}",
        f"**Total Missing Lines**: {report['total_missing_lines']}\n",
        "## Business Impact Breakdown\n",
    ]

    for tier in ["Critical", "High", "Medium", "Low"]:
        tier_data = report["tier_breakdown"][tier]
        lines.append(
            f"### {tier} Impact\n"
            f"- Files: {tier_data['file_count']}\n"
            f"- Missing Lines: {tier_data['missing_lines']}\n"
        )

        # Top 10 files for this tier
        if tier_data["files"]:
            lines.append(f"**Top 10 {tier} Files:**\n")
            lines.append("| File | Coverage | Missing | Priority |\n")
            lines.append("|------|----------|---------|----------|\n")
            for f in tier_data["files"][:10]:
                lines.append(
                    f"| `{f['file']}` | {f['coverage_pct']}% | "
                    f"{f['uncovered_lines']} lines | {f['priority_score']} |\n"
                )
            lines.append("\n")

    # Top 50 overall
    lines.append("## Top 50 Files by Priority Score\n")
    lines.append("| Rank | File | Coverage | Impact | Missing | Priority |\n")
    lines.append("|------|------|----------|--------|---------|----------|\n")
    for i, gap in enumerate(report.get("all_gaps", [])[:50], 1):
        lines.append(
            f"| {i} | `{gap['file']}` | {gap['coverage_pct']}% | "
            f"{gap['business_impact']} | {gap['uncovered_lines']} | {gap['priority_score']} |\n"
        )

    with open(report_path, "w") as f:
        f.writelines(lines)

    print(f"Markdown report: {report_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Analyze coverage gaps and prioritize by business impact"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        default=Path("tests/coverage_reports/metrics/backend_phase_161.json"),
        help="Path to coverage.json baseline",
    )
    parser.add_argument(
        "--impact",
        type=Path,
        default=Path("tests/coverage_reports/metrics/business_impact_scores.json"),
        help="Path to business impact scores JSON",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/coverage_reports/metrics/backend_164_gap_analysis.json"),
        help="Output path for gap analysis JSON",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("tests/coverage_reports/GAP_ANALYSIS_164.md"),
        help="Output path for Markdown report",
    )
    parser.add_argument(
        "--threshold",
        type=float,
        default=80.0,
        help="Coverage threshold (default: 80.0)",
    )

    args = parser.parse_args()

    # Load data
    if not args.baseline.exists():
        print(f"Error: Baseline not found: {args.baseline}")
        sys.exit(1)

    coverage_data = load_coverage_data(args.baseline)

    impact_lookup = {}
    if args.impact.exists():
        impact_lookup = load_impact_scores(args.impact)
    else:
        print(f"Warning: Impact scores not found: {args.impact}")
        print("Using auto-tier assignment based on module patterns")

    # Analyze gaps
    gaps = analyze_gaps(coverage_data, impact_lookup, args.threshold)

    # Generate report
    generate_gap_report(gaps, coverage_data, args.output, args.report)


if __name__ == "__main__":
    main()
