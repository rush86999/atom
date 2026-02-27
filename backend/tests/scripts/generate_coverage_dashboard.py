#!/usr/bin/env python3
"""
Coverage Dashboard Generator - Unified Phase 100 Dashboard

Combines all Phase 100 artifacts into a unified coverage gap dashboard:
- Coverage baseline (Plan 01)
- Business impact scores (Plan 02)
- Prioritized files (Plan 03)
- Coverage trend (Plan 04)

Usage:
    python3 tests/scripts/generate_coverage_dashboard.py \
        --metrics-dir tests/coverage_reports/metrics \
        --output tests/coverage_reports/COVERAGE_DASHBOARD_v5.0.md
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional


def load_json_file(filepath: Path) -> Optional[Dict[str, Any]]:
    """Load JSON file with error handling."""
    try:
        with open(filepath, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  WARNING: {filepath.name} not found, skipping...")
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️  WARNING: {filepath.name} has invalid JSON: {e}")
        return None


def load_all_artifacts(metrics_dir: Path) -> Dict[str, Any]:
    """
    Load all Phase 100 artifacts from metrics directory.

    Returns:
        Dictionary with keys: baseline, impact_scores, prioritized_files, trend
    """
    artifacts = {
        "baseline": None,
        "impact_scores": None,
        "prioritized_files": None,
        "trend": None
    }

    # Load coverage_baseline.json (Plan 01)
    baseline_path = metrics_dir / "coverage_baseline.json"
    artifacts["baseline"] = load_json_file(baseline_path)

    # Load business_impact_scores.json (Plan 02)
    impact_path = metrics_dir / "business_impact_scores.json"
    artifacts["impact_scores"] = load_json_file(impact_path)

    # Load prioritized_files_v5.0.json (Plan 03)
    prioritized_path = metrics_dir / "prioritized_files_v5.0.json"
    artifacts["prioritized_files"] = load_json_file(prioritized_path)

    # Load coverage_trend_v5.0.json (Plan 04)
    trend_path = metrics_dir / "coverage_trend_v5.0.json"
    artifacts["trend"] = load_json_file(trend_path)

    return artifacts


def generate_executive_summary(artifacts: Dict[str, Any]) -> str:
    """Generate Executive Summary section."""
    baseline = artifacts.get("baseline", {})
    overall = baseline.get("overall", {})
    files_below = baseline.get("files_below_threshold", [])
    modules = baseline.get("modules", {})

    # Extract coverage percentages
    overall_pct = overall.get("percent_covered", "N/A")
    coverage_gap = overall.get("coverage_gap", 0)

    # Get module breakdown
    core_module = modules.get("core", {})
    api_module = modules.get("api", {})
    tools_module = modules.get("tools", {})

    core_pct = core_module.get("percent", "N/A")
    api_pct = api_module.get("percent", "N/A")
    tools_pct = tools_module.get("percent", "N/A")

    # Calculate distance to 80% target
    try:
        overall_float = float(overall_pct) if overall_pct != "N/A" else 0
        distance_to_target = 80.0 - overall_float
    except (ValueError, TypeError):
        distance_to_target = "N/A"

    section = f"""## Executive Summary

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}

### Current Coverage State

| Metric | Value | Target | Gap |
|--------|-------|--------|-----|
| **Overall Coverage** | **{overall_pct}%** | 80% | {distance_to_target if isinstance(distance_to_target, str) else f"{distance_to_target:.1f}%" } |
| Core Module | {core_pct}% | 80% | {80 - float(core_pct) if isinstance(core_pct, (int, float)) else "N/A"}% |
| API Module | {api_pct}% | 80% | {80 - float(api_pct) if isinstance(api_pct, (int, float)) else "N/A"}% |
| Tools Module | {tools_pct}% | 80% | {80 - float(tools_pct) if isinstance(tools_pct, (int, float)) else "N/A"}% |

### Files Below 80% Threshold

- **Total files:** {len(files_below)} files below 80% coverage (top 50 shown)
- **Uncovered lines:** {coverage_gap:,} lines
- **Priority files:** Top 50 files account for {sum(f.get('uncovered_lines', 0) for f in files_below[:50]):,} uncovered lines

### Gap Analysis

The codebase currently has **{distance_to_target if isinstance(distance_to_target, str) else f'{distance_to_target:.1f}%'}** overall coverage gap to reach the 80% target.

**Quick Wins:** {len([f for f in files_below if f.get('percent_covered', 0) == 0])} files have 0% coverage and are prime candidates for rapid improvement.

---

"""
    return section


def generate_impact_breakdown(artifacts: Dict[str, Any]) -> str:
    """Generate Impact Breakdown section."""
    impact_scores = artifacts.get("impact_scores", {})
    summary = impact_scores.get("summary", {})

    # Use summary data for tier counts and uncovered lines
    tier_counts = summary.get("tier_counts", {})
    tier_uncovered = summary.get("tier_uncovered_lines", {})

    # Get top files by (uncovered * impact)
    prioritized = artifacts.get("prioritized_files", {})
    top_files = prioritized.get("ranked_files", [])[:5]

    section = f"""## Impact Breakdown

### Files by Business Impact Tier

| Tier | Score | Files | Uncovered Lines |
|------|-------|-------|-----------------|
| **Critical** | 10 | {tier_counts.get('Critical', 0):,} | {tier_uncovered.get('Critical', 0):,} |
| **High** | 7 | {tier_counts.get('High', 0):,} | {tier_uncovered.get('High', 0):,} |
| **Medium** | 5 | {tier_counts.get('Medium', 0):,} | {tier_uncovered.get('Medium', 0):,} |
| **Low** | 3 | {tier_counts.get('Low', 0):,} | {tier_uncovered.get('Low', 0):,} |

### Top 5 Files by Priority Score

Priority formula: `(uncovered_lines × impact_score) / (coverage_pct + 1)`

| Rank | File | Coverage | Uncovered | Tier | Priority Score |
|------|------|----------|-----------|------|----------------|
"""

    for i, file_data in enumerate(top_files, 1):
        filepath = file_data.get("file", "Unknown")
        coverage = file_data.get("coverage_pct", 0)
        uncovered = file_data.get("uncovered_lines", 0)
        tier = file_data.get("tier", "Unknown")
        score = file_data.get("priority_score", 0)

        # Shorten filepath for display
        short_path = filepath.replace("backend/", "") if filepath.startswith("backend/") else filepath

        section += f"| {i} | `{short_path}` | {coverage:.1f}% | {uncovered:,} | {tier} | {score:,.0f} |\n"

    section += "\n---\n\n"
    return section


def generate_prioritized_list(artifacts: Dict[str, Any]) -> str:
    """Generate Prioritized Files section."""
    prioritized = artifacts.get("prioritized_files", {})
    all_files = prioritized.get("ranked_files", [])

    # Top 20 files
    top_20 = all_files[:20]

    # Quick wins (0% coverage AND Critical/High tier)
    quick_wins = [f for f in all_files if f.get("coverage_pct", 0) == 0 and f.get("tier") in ["Critical", "High"]]

    section = f"""## Prioritized Files

### Top 20 Files for Phase 101 (Backend Core Services)

| Rank | File | Coverage | Uncovered | Tier | Priority |
|------|------|----------|-----------|------|----------|
"""

    for i, file_data in enumerate(top_20, 1):
        filepath = file_data.get("file", "Unknown")
        coverage = file_data.get("coverage_pct", 0)
        uncovered = file_data.get("uncovered_lines", 0)
        tier = file_data.get("tier", "Unknown")
        score = file_data.get("priority_score", 0)

        # Shorten filepath
        short_path = filepath.replace("backend/", "") if filepath.startswith("backend/") else filepath

        section += f"| {i} | `{short_path}` | {coverage:.1f}% | {uncovered:,} | {tier} | {score:,.0f} |\n"

    section += f"""
### Quick Wins (0% Coverage, High Impact)

**{len(quick_wins)} files** with 0% coverage in Critical/High tiers:

"""

    for i, file_data in enumerate(quick_wins[:10], 1):
        filepath = file_data.get("file", "Unknown")
        tier = file_data.get("tier", "Unknown")
        uncovered = file_data.get("uncovered_lines", 0)

        # Shorten filepath
        short_path = filepath.replace("backend/", "") if filepath.startswith("backend/") else filepath

        section += f"{i}. `{short_path}` ({tier}, {uncovered:,} uncovered lines)\n"

    section += f"""

### Phase 101 Recommendations

**Focus:** Backend Core Services Unit Tests

**Priority Files:**
- Top {len(top_20)} files from prioritized list
- Estimated uncovered lines: {sum(f.get('uncovered_lines', 0) for f in top_20):,}
- Target coverage gain: +10-15 percentage points

**Strategy:**
1. Start with 0% coverage files (quick wins)
2. Focus on Critical tier (security, data access, agent governance)
3. Write unit tests for core business logic
4. Use property tests for state machines and data transformations

---

"""
    return section


def generate_trend_section(artifacts: Dict[str, Any]) -> str:
    """Generate Trend Visualization section."""
    trend = artifacts.get("trend", {})
    current = trend.get("current", {})
    baseline = trend.get("baseline", {})
    history = trend.get("history", [])

    current_pct = current.get("overall_coverage", "N/A")
    baseline_pct = baseline.get("overall_coverage", "N/A")
    delta_pct = current.get("delta", {}).get("overall_coverage", "N/A")

    # Generate ASCII trend chart
    section = f"""## Coverage Trend

### Current Status

| Metric | Value |
|--------|-------|
| **Current Coverage** | **{current_pct}** |
| **Baseline** | {baseline_pct} |
| **Delta** | {delta_pct} |
| **Target** | 80% |
| **Snapshots Tracked** | {len(history)} |

### Trend Visualization

"""

    # ASCII chart from history
    if history:
        section += "```\n"
        section += "Coverage Trend (last 10 snapshots)\n"
        section += "=" * 50 + "\n"

        for snapshot in history[-10:]:
            timestamp = snapshot.get("timestamp", "")
            coverage = snapshot.get("overall_coverage", 0)
            date = timestamp.split("T")[0] if "T" in timestamp else timestamp

            # Create bar
            bar_length = int(coverage / 2)  # Scale: 1% = 2 chars
            bar = "█" * bar_length
            section += f"{date} | {coverage:5.1f}% {bar}\n"

        section += "=" * 50 + "\n"
        section += "```\n\n"

    # Forecast
    forecast = trend.get("forecast", {})
    if forecast:
        section += "### Forecast to 80% Target\n\n"
        section += f"- **Realistic Estimate:** {forecast.get('realistic', 'N/A')} days\n"
        section += f"- **Optimistic:** {forecast.get('optimistic', 'N/A')} days\n"
        section += f"- **Pessimistic:** {forecast.get('pessimistic', 'N/A')} days\n\n"

    section += "---\n\n"
    return section


def generate_next_steps(artifacts: Dict[str, Any]) -> str:
    """Generate Next Steps section."""
    prioritized = artifacts.get("prioritized_files", {})
    phase_assignments = prioritized.get("phase_assignments", {})

    # Extract phase counts from assignments
    phase_counts = {}
    for phase_key, phase_data in phase_assignments.items():
        # Extract phase number from key (e.g., "101-backend-core" -> "101")
        phase_num = phase_key.split("-")[0]
        phase_counts[phase_num] = phase_data.get("count", 0)

    section = f"""## Next Steps

### Phase 101: Backend Core Services

**Objective:** Unit tests for top 20 high-impact backend files

**Priority Files:** {phase_counts.get('101', 0)}

**Estimated Coverage Gain:** +10-15 percentage points

**Test Types:**
- Unit tests for business logic
- Property tests for state machines
- Error path testing for critical failures

### Phase 102: Backend API Integration

**Objective:** API endpoint integration tests

**Priority Files:** {phase_counts.get('102', 0)}

**Estimated Coverage Gain:** +5-8 percentage points

### Phase 103: Property-Based Testing

**Objective:** Property tests for state transformations

**Priority Files:** {phase_counts.get('103', 0)}

**Focus Areas:**
- Workflow engine state transitions
- Agent governance state machines
- Data transformation functions

### Phase 104: Error Path Testing

**Objective:** Error handling and edge cases

**Priority Files:** {phase_counts.get('104', 0)}

**Focus Areas:**
- Exception handling paths
- Boundary conditions
- Invalid input scenarios

### Phases 105-109: Frontend Coverage Expansion

**Focus:** Frontend component tests (React, Tauri)

**Current Frontend Coverage:** 3.45% (from baseline report)

**Estimated Coverage Gain:** +20-25 percentage points

### Phase 110: Quality Gates & Reporting

**Objective:** Enforce 80% coverage threshold in CI

**Deliverables:**
- Coverage quality gate in CI pipeline
- Regression detection alerts
- Automated coverage trend reporting

---

## Summary

**Phase 100 establishes the foundation for v5.0 Coverage Expansion:**

1. ✅ **Baseline Coverage:** {artifacts.get('baseline', {}).get('overall', {}).get('percent_covered', 'N/A')}% overall, {len(artifacts.get('baseline', {}).get('files_below_threshold', []))} files below 80%
2. ✅ **Business Impact Scoring:** 4-tier system (Critical/High/Medium/Low) for prioritization
3. ✅ **File Prioritization:** Top 50 files ranked by (uncovered × impact / coverage)
4. ✅ **Trend Tracking:** Baseline established, history tracking operational

**Next:** Proceed to Phase 101 (Backend Core Services Unit Tests) using prioritized file list.

---

*Dashboard generated by Phase 100 Plan 05*
*See: .planning/phases/100-coverage-analysis/100-VERIFICATION.md for full verification*
"""

    return section


def write_dashboard(artifacts: Dict[str, Any], output_path: Path) -> None:
    """Generate and write unified dashboard markdown file."""
    dashboard_content = f"""# Coverage Gap Dashboard v5.0

**Phase:** 100 (Coverage Analysis)
**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Purpose:** Unified view of coverage gaps, prioritization, and trends for Phases 101-110

---

"""

    # Generate all sections
    dashboard_content += generate_executive_summary(artifacts)
    dashboard_content += generate_impact_breakdown(artifacts)
    dashboard_content += generate_prioritized_list(artifacts)
    dashboard_content += generate_trend_section(artifacts)
    dashboard_content += generate_next_steps(artifacts)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(dashboard_content)

    print(f"✅ Dashboard generated: {output_path}")
    print(f"   Size: {len(dashboard_content):,} bytes")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate unified coverage dashboard from Phase 100 artifacts"
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="tests/coverage_reports/metrics",
        help="Path to metrics directory containing Phase 100 JSON files"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/coverage_reports/COVERAGE_DASHBOARD_v5.0.md",
        help="Output path for dashboard markdown file"
    )

    args = parser.parse_args()

    # Convert to Path objects
    metrics_dir = Path(args.metrics_dir)
    output_path = Path(args.output)

    # Validate metrics directory
    if not metrics_dir.exists():
        print(f"❌ ERROR: Metrics directory not found: {metrics_dir}")
        sys.exit(1)

    # Load all artifacts
    print("Loading Phase 100 artifacts...")
    artifacts = load_all_artifacts(metrics_dir)

    # Check what we loaded
    loaded_count = sum(1 for v in artifacts.values() if v is not None)
    print(f"✅ Loaded {loaded_count}/4 artifact files")

    if loaded_count == 0:
        print("❌ ERROR: No artifacts found. Check metrics directory.")
        sys.exit(1)

    # Generate dashboard
    print("Generating unified dashboard...")
    write_dashboard(artifacts, output_path)

    print("\n✅ Phase 100 Dashboard Generation Complete")
    print(f"   Output: {output_path}")


if __name__ == "__main__":
    main()
