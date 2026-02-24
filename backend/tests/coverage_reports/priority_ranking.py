#!/usr/bin/env python3
"""
Priority Ranking Script for High-Impact Files

Identifies and prioritizes files for test coverage expansion based on:
- Lines of code (size)
- Current coverage percentage (opportunity)
- Business criticality (impact)

Purpose: Focus testing efforts on files that provide maximum coverage gain per test added.

Usage:
    python tests/coverage_reports/priority_ranking.py

Output:
    - backend/tests/coverage_reports/metrics/high_impact_files.json
    - backend/tests/coverage_reports/HIGH_IMPACT_FILES.md
"""

from __future__ import annotations

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List


# Business criticality scoring (1-10 scale)
# Higher scores = more important to business operations
CRITICALITY_MAP = {
    # P0 - Governance & Safety (highest priority)
    "agent_governance_service": 10,
    "governance_cache": 10,
    "trigger_interceptor": 10,
    "agent_context_resolver": 9,
    "supervision_service": 9,

    # P0 - LLM Integration (core functionality)
    "byok_handler": 10,
    "atom_agent_endpoints": 9,
    "streaming_handler": 8,

    # P1 - Episodic Memory (learning system)
    "episode_segmentation_service": 9,
    "episode_retrieval_service": 8,
    "episode_lifecycle_service": 8,
    "agent_graduation_service": 8,

    # P1 - Tools & Devices
    "canvas_tool": 7,
    "browser_tool": 7,
    "device_tool": 7,

    # P1 - Training & Graduation
    "student_training_service": 8,
    "proposal_service": 7,

    # P2 - Supporting services
    "workflow_engine": 6,
    "lancedb_handler": 5,
    "embedding_service": 5,
}


def extract_module_name(file_path: str) -> str:
    """
    Extract module name from file path for criticality lookup.

    Examples:
        core/agent_governance_service.py -> agent_governance_service
        tools/canvas_tool.py -> canvas_tool
    """
    # Get filename without path and extension
    filename = Path(file_path).name
    # Remove .py extension
    module_name = filename.replace(".py", "")
    return module_name


def calculate_priority_score(
    file_path: str,
    coverage_data: Dict[str, Any],
    criticality_map: Dict[str, int]
) -> Dict[str, Any]:
    """
    Calculate priority score for a single file.

    Priority score formula: (uncovered_lines / 100) * criticality

    This weights:
    - Size of opportunity (uncovered lines)
    - Business impact (criticality score)

    Args:
        file_path: Path to the Python file
        coverage_data: Coverage data from coverage.json
        criticality_map: Mapping of module names to criticality scores

    Returns:
        Dictionary with priority score and metadata
    """
    summary = coverage_data["summary"]
    line_count = summary["num_statements"]
    covered = summary["covered_lines"]

    # Calculate coverage percentage
    coverage_pct = (covered / line_count * 100) if line_count > 0 else 0

    # Get business criticality (default 3 for unknown files)
    module_name = extract_module_name(file_path)
    criticality = criticality_map.get(module_name, 3)

    # Calculate uncovered lines
    uncovered = line_count - covered

    # Priority score: (uncovered_lines / 100) * criticality
    # This gives higher priority to:
    # - Files with more uncovered lines (opportunity)
    # - Files with higher business criticality (impact)
    priority_score = (uncovered / 100) * criticality

    # Determine tier based on criticality
    if criticality >= 9:
        tier = "P0"
    elif criticality >= 7:
        tier = "P1"
    elif criticality >= 5:
        tier = "P2"
    else:
        tier = "P3"

    return {
        "file": file_path,
        "line_count": line_count,
        "covered": covered,
        "coverage_pct": round(coverage_pct, 2),
        "uncovered": uncovered,
        "criticality": criticality,
        "priority_score": round(priority_score, 2),
        "tier": tier,
        "module_name": module_name,
    }


def filter_high_impact(
    coverage_json_path: str,
    min_lines: int = 200,
    max_coverage: int = 30
) -> List[Dict[str, Any]]:
    """
    Filter and rank high-impact files from coverage data.

    Args:
        coverage_json_path: Path to coverage.json
        min_lines: Minimum number of lines to be considered high-impact
        max_coverage: Maximum coverage percentage to be considered high-impact

    Returns:
        List of high-impact files sorted by priority_score descending
    """
    # Load coverage.json
    with open(coverage_json_path, "r") as f:
        coverage_data = json.load(f)

    files_data = coverage_data.get("files", {})
    ranked_files = []

    # Filter and calculate priority scores
    for file_path, file_coverage in files_data.items():
        summary = file_coverage["summary"]
        line_count = summary["num_statements"]
        coverage_pct = summary["percent_covered"]

        # Filter: must have min_lines AND max_coverage or less
        if line_count >= min_lines and coverage_pct <= max_coverage:
            priority_data = calculate_priority_score(file_path, file_coverage, CRITICALITY_MAP)
            ranked_files.append(priority_data)

    # Sort by priority_score descending
    ranked_files.sort(key=lambda x: x["priority_score"], reverse=True)

    return ranked_files


def generate_priority_report(
    ranked_files: List[Dict[str, Any]],
    filters: Dict[str, Any],
    output_path: str
) -> None:
    """
    Generate markdown priority ranking report.

    Args:
        ranked_files: List of ranked high-impact files
        filters: Filter criteria used (min_lines, max_coverage)
        output_path: Path to save markdown report
    """
    # Calculate summary statistics
    total_files = len(ranked_files)
    total_uncovered = sum(f["uncovered"] for f in ranked_files)
    total_lines = sum(f["line_count"] for f in ranked_files)

    # Count by tier
    tier_counts = {"P0": 0, "P1": 0, "P2": 0, "P3": 0}
    for f in ranked_files:
        tier_counts[f["tier"]] = tier_counts.get(f["tier"], 0) + 1

    # Get top 5 files
    top_5 = ranked_files[:5]

    # Generate markdown
    lines = []
    lines.append("# High-Impact Files for Test Coverage Expansion v3.2")
    lines.append("")
    lines.append(f"**Generated**: {datetime.now().strftime('%Y-%m-%d %H:%M:%S UTC')}")
    lines.append("**Phase**: 81-02")
    lines.append("")

    # Summary
    lines.append("## Summary")
    lines.append("")
    lines.append(f"- **Total high-impact files identified**: {total_files}")
    lines.append(f"- **Combined uncovered lines**: {total_uncovered:,}")
    lines.append(f"- **Total lines of code**: {total_lines:,}")
    lines.append(f"- **Average coverage**: {sum(f['coverage_pct'] for f in ranked_files) / total_files:.1f}%")
    lines.append(f"- **Filter criteria**: >{filters['min_lines']} lines, <{filters['max_coverage']}% coverage")
    lines.append("")

    # Tier distribution
    lines.append("### Distribution by Priority Tier")
    lines.append("")
    lines.append("| Tier | Files | Description |")
    lines.append("|------|-------|-------------|")
    lines.append("| P0 | {} | Governance, safety, LLM integration |".format(tier_counts["P0"]))
    lines.append("| P1 | {} | Memory system, tools, training |".format(tier_counts["P1"]))
    lines.append("| P2 | {} | Supporting services, infrastructure |".format(tier_counts["P2"]))
    lines.append("| P3 | {} | Utility code, low-risk modules |".format(tier_counts["P3"]))
    lines.append("")

    # Top 5 files
    lines.append("### Top 5 Files by Priority Score")
    lines.append("")
    lines.append("| Rank | File | Lines | Coverage | Uncovered | Criticality | Priority Score | Tier |")
    lines.append("|------|------|-------|----------|-----------|-------------|----------------|------|")
    for i, f in enumerate(top_5, 1):
        lines.append(
            f"| {i} | {f['file']} | {f['line_count']} | {f['coverage_pct']}% | "
            f"{f['uncovered']} | {f['criticality']} | {f['priority_score']} | {f['tier']} |"
        )
    lines.append("")

    # Priority tiers explanation
    lines.append("## Priority Tiers")
    lines.append("")
    lines.append("| Tier | Criticality | Description |")
    lines.append("|------|-------------|-------------|")
    lines.append("| P0 | 9-10 | Governance, safety, LLM integration |")
    lines.append("| P1 | 7-8 | Memory system, tools, training |")
    lines.append("| P2 | 5-6 | Supporting services, infrastructure |")
    lines.append("| P3 | 3-4 | Utility code, low-risk modules |")
    lines.append("")

    # All high-impact files table
    lines.append("## Priority Ranking - All High-Impact Files")
    lines.append("")
    lines.append("| Rank | File | Lines | Coverage | Uncovered | Criticality | Priority Score | Tier |")
    lines.append("|------|------|-------|----------|-----------|-------------|----------------|------|")
    for i, f in enumerate(ranked_files, 1):
        lines.append(
            f"| {i} | {f['file']} | {f['line_count']} | {f['coverage_pct']}% | "
            f"{f['uncovered']} | {f['criticality']} | {f['priority_score']} | {f['tier']} |"
        )
    lines.append("")

    # Recommendations
    lines.append("## Recommendations")
    lines.append("")
    lines.append("### Test Development Strategy")
    lines.append("")
    lines.append("1. **Start with P0 files** (governance, LLM, episodes)")
    lines.append("   - These represent core business functionality")
    lines.append("   - Highest risk if bugs exist")
    lines.append("   - Maximum impact on system reliability")
    lines.append("")
    lines.append("2. **Target 80% coverage on P0 files before moving to P1**")
    lines.append("   - Each 10% coverage improvement on P0 files = significant overall gain")
    lines.append("   - Focus on critical paths first")
    lines.append("")
    lines.append("3. **Use property-based tests for complex logic**")
    lines.append("   - Hypothesis for edge case discovery")
    lines.append("   - Especially useful for governance and LLM routing logic")
    lines.append("")
    lines.append("4. **Prioritize by priority_score within each tier**")
    lines.append("   - Higher score = more uncovered lines * business impact")
    lines.append("   - Maximum coverage gain per test added")
    lines.append("")

    # Next steps
    lines.append("## Next Steps")
    lines.append("")
    lines.append("1. **Phase 82: Core Services Unit Testing**")
    lines.append("   - Focus on P0 tier files (governance, LLM, episodes)")
    lines.append("   - Unit tests with >80% coverage target")
    lines.append("")
    lines.append("2. **Phase 86: Property-Based Testing**")
    lines.append("   - Hypothesis tests for complex business logic")
    lines.append("   - Edge case discovery in governance and routing")
    lines.append("")
    lines.append("3. **Continuous Tracking**")
    lines.append("   - Re-run priority ranking after each phase")
    lines.append("   - Track progress against baseline (15.23% overall)")
    lines.append("   - Adjust strategy based on coverage improvements")
    lines.append("")

    # Metadata
    lines.append("---")
    lines.append("")
    lines.append("*Generated by priority_ranking.py*")
    lines.append(f"*Phase: 81-02*")
    lines.append(f"*Timestamp: {datetime.now().isoformat()}*")

    # Write to file
    with open(output_path, "w") as f:
        f.write("\n".join(lines))

    print(f"✓ Generated priority report: {output_path}")


def save_high_impact_json(
    ranked_files: List[Dict[str, Any]],
    filters: Dict[str, Any],
    output_path: str
) -> None:
    """
    Save high-impact files as machine-readable JSON.

    Args:
        ranked_files: List of ranked high-impact files
        filters: Filter criteria used
        output_path: Path to save JSON output
    """
    output_data = {
        "generated_at": datetime.now().isoformat(),
        "filters": filters,
        "total_files": len(ranked_files),
        "total_uncovered_lines": sum(f["uncovered"] for f in ranked_files),
        "total_lines": sum(f["line_count"] for f in ranked_files),
        "files": ranked_files,
    }

    with open(output_path, "w") as f:
        json.dump(output_data, f, indent=2)

    print(f"✓ Saved high-impact files JSON: {output_path}")


def main():
    """Main entry point for priority ranking analysis."""
    # Set up paths
    backend_dir = Path(__file__).parent.parent.parent
    coverage_json_path = backend_dir / "tests" / "coverage_reports" / "metrics" / "coverage.json"
    high_impact_json_path = backend_dir / "tests" / "coverage_reports" / "metrics" / "high_impact_files.json"
    report_path = backend_dir / "tests" / "coverage_reports" / "HIGH_IMPACT_FILES.md"

    # Verify coverage.json exists
    if not coverage_json_path.exists():
        print(f"ERROR: Coverage file not found: {coverage_json_path}")
        print("Run 'pytest --cov=backend --cov-report=json --cov-report=term' first.")
        sys.exit(1)

    print("🔍 Analyzing coverage data for high-impact files...")
    print(f"   Coverage file: {coverage_json_path}")
    print(f"   Filters: >200 lines, <30% coverage")
    print()

    # Define filter criteria
    filters = {
        "min_lines": 200,
        "max_coverage": 30,
    }

    # Filter and rank high-impact files
    ranked_files = filter_high_impact(
        str(coverage_json_path),
        min_lines=filters["min_lines"],
        max_coverage=filters["max_coverage"]
    )

    if not ranked_files:
        print("⚠ No high-impact files found matching the criteria.")
        print("  Consider adjusting filter thresholds.")
        sys.exit(0)

    print(f"✓ Found {len(ranked_files)} high-impact files")
    print()

    # Save machine-readable JSON
    save_high_impact_json(ranked_files, filters, str(high_impact_json_path))

    # Generate markdown report
    generate_priority_report(ranked_files, filters, str(report_path))

    # Print summary
    print()
    print("📊 Analysis Complete")
    print("=" * 60)
    print(f"Total high-impact files: {len(ranked_files)}")
    print(f"Total uncovered lines: {sum(f['uncovered'] for f in ranked_files):,}")
    print(f"Total lines of code: {sum(f['line_count'] for f in ranked_files):,}")
    print()
    print("Top 5 files by priority score:")
    for i, f in enumerate(ranked_files[:5], 1):
        print(f"  {i}. {f['file']} ({f['tier']}) - Priority: {f['priority_score']}")
    print()
    print(f"✓ Report saved to: {report_path}")
    print(f"✓ JSON saved to: {high_impact_json_path}")


if __name__ == "__main__":
    main()
