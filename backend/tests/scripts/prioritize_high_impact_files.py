#!/usr/bin/env python3
"""
High-Impact File Prioritization Script

Purpose: Rank files by priority_score = (uncovered_lines * impact_score) / (current_coverage_pct + 1)
This formula maximizes coverage gain per test added by prioritizing files where:
  1. Many lines are uncovered (large coverage gap)
  2. Business impact is high (critical functionality)
  3. Current coverage is low (quick wins)

Usage:
    python3 tests/scripts/prioritize_high_impact_files.py \
        --baseline tests/coverage_reports/metrics/coverage_baseline.json \
        --impact tests/coverage_reports/metrics/business_impact_scores.json \
        --output tests/coverage_reports/metrics/prioritized_files_v5.0.json \
        --report tests/coverage_reports/HIGH_IMPACT_PRIORITIZATION.md

Output:
    - JSON: Machine-readable ranked file list with priority scores
    - Markdown: Human-readable report with top 50 files and quick wins
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Dict, List, Optional
from collections import defaultdict


def calculate_priority_score(file_data: Dict[str, Any], impact_score: int) -> float:
    """
    Calculate priority score for a file.

    Formula: priority_score = (uncovered_lines * impact_score) / (current_coverage_pct + 1)

    The +1 prevents division by zero for files with 0% coverage.

    Higher score = higher priority (more impact per test added)

    Args:
        file_data: File coverage data with 'coverage_pct' and 'uncovered_lines'
        impact_score: Business impact score (3=Low, 5=Medium, 7=High, 10=Critical)

    Returns:
        Priority score (float)

    Examples:
        >>> calculate_priority_score({"coverage_pct": 20.0, "uncovered_lines": 100}, 10)
        47.61904761904762
        >>> calculate_priority_score({"coverage_pct": 0.0, "uncovered_lines": 100}, 10)
        1000.0
        >>> calculate_priority_score({"coverage_pct": 50.0, "uncovered_lines": 50}, 7)
        6.666666666666667
    """
    uncovered_lines = file_data.get("uncovered_lines", 0)
    coverage_pct = file_data.get("coverage_pct", 0.0)

    # Add 1 to avoid division by zero for 0% coverage files
    priority_score = (uncovered_lines * impact_score) / (coverage_pct + 1)

    return round(priority_score, 2)


def estimate_tests_needed(file_data: Dict[str, Any], target_coverage: float = 50.0) -> int:
    """
    Estimate number of tests needed to reach target coverage.

    Target: 50% coverage (proven sustainable from Phase 8.6)
    Assumption: 20 lines covered per test on average

    Args:
        file_data: File coverage data with 'uncovered_lines'
        target_coverage: Target coverage percentage (default 50%)

    Returns:
        Estimated number of tests needed (integer, minimum 10)
    """
    uncovered_lines = file_data.get("uncovered_lines", 0)

    # Lines to cover = 50% of uncovered lines
    lines_to_cover = uncovered_lines * (target_coverage / 100.0)

    # Estimate 20 lines per test average
    estimated_tests = max(10, int(lines_to_cover / 20))

    return estimated_tests


def rank_files(
    baseline_data: Dict[str, Any],
    impact_scores: Dict[str, Dict[str, Any]],
    min_coverage_threshold: float = 80.0,
) -> List[Dict[str, Any]]:
    """
    Rank files by priority score.

    Merges coverage baseline with impact scores, calculates priority_score,
    and sorts by priority_score descending.

    Args:
        baseline_data: Coverage baseline data from coverage_baseline.json
        impact_scores: Business impact scores from business_impact_scores.json
        min_coverage_threshold: Minimum coverage threshold (default 80%)

    Returns:
        Ranked list of files with priority scores, sorted by priority_score descending
    """
    # Extract files below threshold from baseline
    files_below_threshold = baseline_data.get("files_below_threshold", [])

    # Build impact score lookup from all_files array
    impact_lookup = {}
    for file_data in impact_scores.get("all_files", []):
        file_path = file_data.get("file", "")
        tier = file_data.get("tier", "Low")
        impact_lookup[file_path] = tier

    # Tier to score mapping
    tier_scores = {
        "Critical": 10,
        "High": 7,
        "Medium": 5,
        "Low": 3,
    }

    # Calculate priority scores
    ranked_files = []
    for file_data in files_below_threshold:
        file_path = file_data.get("file", "")

        # Skip files above threshold
        coverage_pct = file_data.get("coverage_pct", 0.0)
        if coverage_pct >= min_coverage_threshold:
            continue

        # Get impact score
        tier = impact_lookup.get(file_path, "Low")
        impact_score = tier_scores.get(tier, 3)

        # Calculate priority score
        priority_score = calculate_priority_score(file_data, impact_score)

        # Estimate tests needed
        estimated_tests = estimate_tests_needed(file_data)

        # Build ranked file entry
        ranked_file = {
            "file": file_path,
            "coverage_pct": coverage_pct,
            "total_lines": file_data.get("total_lines", 0),
            "covered_lines": file_data.get("covered_lines", 0),
            "uncovered_lines": file_data.get("uncovered_lines", 0),
            "impact_score": impact_score,
            "tier": tier,
            "priority_score": priority_score,
            "estimated_tests": estimated_tests,
        }

        ranked_files.append(ranked_file)

    # Sort by priority_score descending
    ranked_files.sort(key=lambda x: x["priority_score"], reverse=True)

    return ranked_files


def identify_quick_wins(ranked_files: List[Dict[str, Any]], top_n: int = 20) -> List[Dict[str, Any]]:
    """
    Identify quick wins - files with 0% coverage and Critical/High tier.

    These are the "low hanging fruit" that will provide maximum coverage gain
    with minimal effort.

    Args:
        ranked_files: List of ranked files
        top_n: Maximum number of quick wins to return (default 20)

    Returns:
        List of quick win files, sorted by uncovered_lines descending
    """
    # Filter for 0% coverage and Critical/High tier
    quick_wins = [
        f for f in ranked_files
        if f["coverage_pct"] == 0.0 and f["tier"] in ["Critical", "High"]
    ]

    # Sort by uncovered_lines descending
    quick_wins.sort(key=lambda x: x["uncovered_lines"], reverse=True)

    return quick_wins[:top_n]


def group_by_phase(ranked_files: List[Dict[str, Any]]) -> Dict[str, List[Dict[str, Any]]]:
    """
    Group files by phase assignments for Phases 101-110.

    Phase assignments:
        - Phase 101 (Backend Core): Top 20 Critical + High tier files
        - Phase 102 (Backend API): Next 15 High + Medium tier API files
        - Phase 103 (Backend Property): Files with complex logic (engine, handler, coordinator)
        - Phase 104 (Backend Error): Files with error handling focus
        - Phases 105-109: Frontend files (placeholder for frontend coverage)

    Args:
        ranked_files: List of ranked files

    Returns:
        Dictionary mapping phase names to file lists
    """
    phases = {
        "101-backend-core": [],
        "102-backend-api": [],
        "103-backend-property": [],
        "104-backend-error": [],
        "105-frontend-core": [],  # Placeholder
        "106-frontend-api": [],  # Placeholder
        "107-frontend-components": [],  # Placeholder
        "108-frontend-hooks": [],  # Placeholder
        "109-frontend-integration": [],  # Placeholder
    }

    # Phase 101: Top 20 Critical + High tier files
    critical_high = [f for f in ranked_files if f["tier"] in ["Critical", "High"]]
    phases["101-backend-core"] = critical_high[:20]

    # Phase 102: Next 15 High + Medium tier API files
    remaining_after_101 = ranked_files[len(critical_high[:20]):]
    api_files = [f for f in remaining_after_101 if f["file"].startswith("api/")]
    phases["102-backend-api"] = api_files[:15]

    # Phase 103: Files with complex logic patterns
    complex_patterns = ["engine", "handler", "coordinator", "orchestrator", "workflow"]
    complex_files = [
        f for f in ranked_files
        if any(p in f["file"].lower() for p in complex_patterns)
        and f not in phases["101-backend-core"]
        and f not in phases["102-backend-api"]
    ]
    phases["103-backend-property"] = complex_files[:15]

    # Phase 104: Error handling focus
    error_patterns = ["error", "exception", "validation", "monitoring", "health"]
    error_files = [
        f for f in ranked_files
        if any(p in f["file"].lower() for p in error_patterns)
        and f not in phases["101-backend-core"]
        and f not in phases["102-backend-api"]
        and f not in phases["103-backend-property"]
    ]
    phases["104-backend-error"] = error_files[:15]

    # Remove files already assigned to backend phases
    assigned_files = set()
    for phase_files in phases.values():
        assigned_files.update(f["file"] for f in phase_files)

    remaining = [f for f in ranked_files if f["file"] not in assigned_files]

    # Remaining files go to frontend placeholder phases
    phases["105-frontend-core"] = remaining[:10]
    phases["106-frontend-api"] = remaining[10:20]
    phases["107-frontend-components"] = remaining[20:30]
    phases["108-frontend-hooks"] = remaining[30:40]
    phases["109-frontend-integration"] = remaining[40:50]

    return phases


def write_json_report(
    ranked_files: List[Dict[str, Any]],
    quick_wins: List[Dict[str, Any]],
    phase_assignments: Dict[str, List[Dict[str, Any]]],
    baseline_data: Dict[str, Any],
    output_path: Path,
) -> None:
    """
    Write JSON report with ranked files and metadata.

    Args:
        ranked_files: List of ranked files
        quick_wins: List of quick win files
        phase_assignments: Dictionary of phase assignments
        baseline_data: Original baseline data
        output_path: Output file path
    """
    # Calculate summary statistics
    total_files = len(ranked_files)
    total_uncovered = sum(f["uncovered_lines"] for f in ranked_files)

    tier_counts = defaultdict(int)
    tier_uncovered = defaultdict(int)
    for f in ranked_files:
        tier_counts[f["tier"]] += 1
        tier_uncovered[f["tier"]] += f["uncovered_lines"]

    # Build output JSON
    output = {
        "generated_at": baseline_data.get("timestamp", ""),
        "baseline_version": baseline_data.get("baseline_version", "v5.0"),
        "summary": {
            "total_files_below_80": total_files,
            "total_uncovered_lines": total_uncovered,
            "tier_counts": dict(tier_counts),
            "tier_uncovered_lines": dict(tier_uncovered),
            "quick_wins_count": len(quick_wins),
        },
        "ranked_files": ranked_files,
        "quick_wins": quick_wins,
        "phase_assignments": {
            phase: {
                "count": len(files),
                "files": [f["file"] for f in files],
            }
            for phase, files in phase_assignments.items()
        },
    }

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        json.dump(output, f, indent=2)

    print(f"✓ JSON report written to {output_path}")
    print(f"  Total files: {total_files}")
    print(f"  Total uncovered lines: {total_uncovered}")
    print(f"  Quick wins: {len(quick_wins)}")


def write_markdown_report(
    ranked_files: List[Dict[str, Any]],
    quick_wins: List[Dict[str, Any]],
    phase_assignments: Dict[str, List[Dict[str, Any]]],
    baseline_data: Dict[str, Any],
    output_path: Path,
) -> None:
    """
    Write markdown report with top 50 files and quick wins.

    Args:
        ranked_files: List of ranked files
        quick_wins: List of quick win files
        phase_assignments: Dictionary of phase assignments
        baseline_data: Original baseline data
        output_path: Output file path
    """
    lines = []

    # Header
    lines.append("# High-Impact File Prioritization v5.0")
    lines.append("")
    lines.append(f"**Generated**: {baseline_data.get('timestamp', '')}")
    lines.append("**Phase**: 100-03")
    lines.append("")

    # Executive Summary
    lines.append("## Executive Summary")
    lines.append("")
    total_files = len(ranked_files)
    total_uncovered = sum(f["uncovered_lines"] for f in ranked_files)

    tier_counts = defaultdict(int)
    tier_uncovered = defaultdict(int)
    for f in ranked_files:
        tier_counts[f["tier"]] += 1
        tier_uncovered[f["tier"]] += f["uncovered_lines"]

    lines.append(f"- **Total files below 80% coverage**: {total_files}")
    lines.append(f"- **Total uncovered lines**: {total_uncovered:,}")
    lines.append("")

    lines.append("### Distribution by Impact Tier")
    lines.append("")
    lines.append("| Tier | Files | Uncovered Lines | Description |")
    lines.append("|------|-------|-----------------|-------------|")
    lines.append(f"| Critical | {tier_counts['Critical']} | {tier_uncovered['Critical']:,} | Governance, LLM, security |")
    lines.append(f"| High | {tier_counts['High']} | {tier_uncovered['High']:,} | Memory, tools, training |")
    lines.append(f"| Medium | {tier_counts['Medium']} | {tier_uncovered['Medium']:,} | Supporting services |")
    lines.append(f"| Low | {tier_counts['Low']} | {tier_uncovered['Low']:,} | Utility code |")
    lines.append("")

    lines.append("### Top 3 Files by Priority Score")
    lines.append("")
    lines.append("| Rank | File | Coverage | Uncovered | Impact | Priority Score | Tier |")
    lines.append("|------|------|----------|-----------|--------|----------------|------|")
    for i, f in enumerate(ranked_files[:3], 1):
        lines.append(
            f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['uncovered_lines']} | "
            f"{f['impact_score']} | {f['priority_score']:.2f} | {f['tier']} |"
        )
    lines.append("")

    # Formula Explanation
    lines.append("## Priority Score Formula")
    lines.append("")
    lines.append("### Formula")
    lines.append("```")
    lines.append("priority_score = (uncovered_lines * impact_score) / (current_coverage_pct + 1)")
    lines.append("```")
    lines.append("")
    lines.append("### Why This Formula?")
    lines.append("")
    lines.append("- **uncovered_lines**: More uncovered lines = more potential coverage gain")
    lines.append("- **impact_score**: Higher business impact = more value per test")
    lines.append("- **current_coverage_pct + 1**: Lower current coverage = higher priority")
    lines.append("  - Adding 1 prevents division by zero for 0% coverage files")
    lines.append("  - This creates a \"quick wins\" bias towards files with very low coverage")
    lines.append("")

    lines.append("### Example Calculations")
    lines.append("")
    lines.append("| Scenario | Uncovered | Impact | Coverage | Priority Score | Interpretation |")
    lines.append("|----------|-----------|--------|----------|----------------|----------------|")
    lines.append("| A: Large gap, critical | 1000 | 10 | 5% | 952.38 | Very high priority - lots of critical code to test |")
    lines.append("| B: Small gap, critical | 100 | 10 | 20% | 47.62 | High priority - critical but small |")
    lines.append("| C: Large gap, medium | 1000 | 5 | 5% | 476.19 | Medium-high priority - lots of code |")
    lines.append("| D: Small gap, low | 100 | 3 | 50% | 6.00 | Low priority - small, low impact |")
    lines.append("| E: Zero coverage, high | 200 | 7 | 0% | 1400.00 | Quick win - no coverage exists yet |")
    lines.append("")

    # Top 50 Ranked Files
    lines.append("## Top 50 Ranked Files")
    lines.append("")
    lines.append("| Rank | File | Coverage | Uncovered | Impact | Priority | Est. Tests | Tier |")
    lines.append("|------|------|----------|-----------|--------|----------|------------|------|")

    for i, f in enumerate(ranked_files[:50], 1):
        lines.append(
            f"| {i} | {f['file']} | {f['coverage_pct']:.2f}% | {f['uncovered_lines']} | "
            f"{f['impact_score']} | {f['priority_score']:.2f} | {f['estimated_tests']} | {f['tier']} |"
        )
    lines.append("")

    # Quick Wins
    lines.append("## Quick Wins (0% Coverage, Critical/High Impact)")
    lines.append("")
    lines.append(f"These {len(quick_wins)} files have **zero coverage** but high business impact.")
    lines.append("They are the \"low hanging fruit\" for Phase 101.")
    lines.append("")
    lines.append("| Rank | File | Uncovered Lines | Impact | Tier | Est. Tests |")
    lines.append("|------|------|-----------------|--------|------|------------|")

    for i, f in enumerate(quick_wins, 1):
        lines.append(
            f"| {i} | {f['file']} | {f['uncovered_lines']} | "
            f"{f['impact_score']} | {f['tier']} | {f['estimated_tests']} |"
        )
    lines.append("")

    # Phase Assignments
    lines.append("## Phase Assignments (101-110)")
    lines.append("")

    for phase_name, phase_files in sorted(phase_assignments.items()):
        if not phase_files:
            continue

        phase_num = phase_name.split("-")[0]
        phase_title = phase_name.split("-", 1)[1].replace("-", " ").title()

        lines.append(f"### Phase {phase_num}: {phase_title}")
        lines.append("")
        lines.append(f"**Files**: {len(phase_files)}")
        lines.append("")

        for f in phase_files[:10]:  # Show first 10
            lines.append(f"- {f['file']} (Priority: {f['priority_score']:.2f})")

        if len(phase_files) > 10:
            lines.append(f"- ... and {len(phase_files) - 10} more")

        lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by prioritize_high_impact_files.py*")
    lines.append("*Phase: 100-03*")
    lines.append(f"*Timestamp: {baseline_data.get('timestamp', '')}*")

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"✓ Markdown report written to {output_path}")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Prioritize files by coverage impact using (uncovered * impact / coverage) formula"
    )
    parser.add_argument(
        "--baseline",
        type=Path,
        required=True,
        help="Path to coverage_baseline.json",
    )
    parser.add_argument(
        "--impact",
        type=Path,
        required=True,
        help="Path to business_impact_scores.json",
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=Path("tests/coverage_reports/metrics/prioritized_files_v5.0.json"),
        help="Output path for ranked files JSON",
    )
    parser.add_argument(
        "--report",
        type=Path,
        default=Path("tests/coverage_reports/HIGH_IMPACT_PRIORITIZATION.md"),
        help="Output path for markdown report",
    )
    parser.add_argument(
        "--min-coverage",
        type=float,
        default=80.0,
        help="Minimum coverage threshold (default: 80%%)",
    )
    parser.add_argument(
        "--quick-wins",
        type=int,
        default=20,
        help="Number of quick wins to identify (default: 20)",
    )

    args = parser.parse_args()

    # Load baseline data
    print(f"Loading baseline data from {args.baseline}...")
    try:
        with open(args.baseline, "r") as f:
            baseline_data = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Baseline file not found: {args.baseline}")
        sys.exit(1)

    # Load impact scores
    print(f"Loading impact scores from {args.impact}...")
    try:
        with open(args.impact, "r") as f:
            impact_scores = json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Impact scores file not found: {args.impact}")
        sys.exit(1)

    # Rank files
    print("Ranking files by priority score...")
    ranked_files = rank_files(baseline_data, impact_scores, args.min_coverage)

    print(f"  Ranked {len(ranked_files)} files below {args.min_coverage}% coverage")

    # Identify quick wins
    print("Identifying quick wins...")
    quick_wins = identify_quick_wins(ranked_files, args.quick_wins)

    print(f"  Found {len(quick_wins)} quick wins (0% coverage, Critical/High tier)")

    # Group by phase
    print("Grouping files by phase...")
    phase_assignments = group_by_phase(ranked_files)

    for phase, files in phase_assignments.items():
        if files:
            print(f"  Phase {phase}: {len(files)} files")

    # Write JSON report
    print("\nWriting reports...")
    write_json_report(
        ranked_files,
        quick_wins,
        phase_assignments,
        baseline_data,
        args.output,
    )

    # Write markdown report
    write_markdown_report(
        ranked_files,
        quick_wins,
        phase_assignments,
        baseline_data,
        args.report,
    )

    print("\n✓ Prioritization complete!")
    print(f"\nNext steps:")
    print(f"  1. Review {args.report} for top priorities")
    print(f"  2. Use {args.output} for automated planning")
    print(f"  3. Start with Phase 101 (Backend Core Services)")


if __name__ == "__main__":
    main()
