#!/usr/bin/env python3
"""
Coverage Dashboard Generator - Unified Phase 100 Dashboard + Trend Dashboard

Combines all Phase 100 artifacts into a unified coverage gap dashboard:
- Coverage baseline (Plan 01)
- Business impact scores (Plan 02)
- Prioritized files (Plan 03)
- Coverage trend (Plan 04)

Extended for Phase 110 Plan 03:
- Trend dashboard with ASCII historical graphs
- Per-module breakdown charts
- Forecast to 80% target

Usage:
    # Generate unified dashboard (Phase 100)
    python3 tests/scripts/generate_coverage_dashboard.py \
        --metrics-dir tests/coverage_reports/metrics \
        --output tests/coverage_reports/COVERAGE_DASHBOARD_v5.0.md

    # Generate trend dashboard (Phase 110)
    python3 tests/scripts/generate_coverage_dashboard.py \
        --trend-file tests/coverage_reports/metrics/coverage_trend_v5.0.json \
        --output tests/coverage_reports/dashboards/COVERAGE_TREND_v5.0.md \
        --mode trend
"""

import argparse
import json
import os
import sys
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


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


def load_trend_data(trend_file: Path) -> Optional[Dict[str, Any]]:
    """
    Load trend data from JSON file.

    Args:
        trend_file: Path to coverage_trend_v5.0.json

    Returns:
        Trend data dict or None if not found
    """
    try:
        with open(trend_file, 'r') as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"⚠️  WARNING: {trend_file} not found")
        return None
    except json.JSONDecodeError as e:
        print(f"⚠️  WARNING: {trend_file} has invalid JSON: {e}")
        return None


def generate_trend_dashboard(trend_data: Dict[str, Any], width: int = 70) -> str:
    """
    Generate markdown dashboard with ASCII trend charts.

    Args:
        trend_data: Trend data with history from coverage_trend_v5.0.json
        width: Chart width in characters

    Returns:
        Markdown content for trend dashboard
    """
    current = trend_data.get("current", {})
    baseline = trend_data.get("baseline", {})
    history = trend_data.get("history", [])
    metadata = trend_data.get("metadata", {})

    # Extract coverage values
    current_pct = current.get("overall_coverage", 0)
    baseline_pct = baseline.get("overall_coverage", 0)

    # Calculate remaining to 80% target
    target_pct = 80.0
    remaining_pct = target_pct - current_pct
    progress_pct = (current_pct / target_pct) * 100 if target_pct > 0 else 0

    # Generate progress bar
    filled = int(progress_pct / 5)  # 20 chars = 100%
    bar = "█" * filled + "░" * (20 - filled)

    # Calculate statistics
    total_snapshots = len(history)
    first_date = history[0].get("timestamp", "") if history else ""
    last_date = history[-1].get("timestamp", "") if history else ""

    dashboard = f"""# Coverage Trend Dashboard v5.0

**Generated:** {datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M:%S UTC')}
**Purpose:** Track progress toward 80% coverage goal with historical trends

## Executive Summary

| Metric | Value |
|--------|-------|
| **Current Coverage** | **{current_pct:.2f}%** |
| **Baseline** | {baseline_pct:.2f}% |
| **Target** | {target_pct:.2f}% |
| **Remaining** | {remaining_pct:.2f}% |
| **Progress** | {progress_pct:.1f}% |
| **Total Snapshots** | {total_snapshots} |
| **Date Range** | {first_date[:10] if first_date else 'N/A'} to {last_date[:10] if last_date else 'N/A'} |

### Visual Progress Bar

[{bar}] {progress_pct:.1f}%

### Coverage Statistics

- **Lines Covered:** {current.get('covered_lines', 0):,} / {current.get('total_lines', 0):,}
- **Branch Coverage:** {current.get('branch_coverage', 0):.2f}%
- **Covered Branches:** {current.get('covered_branches', 0):,} / {current.get('total_branches', 0):,}

---

## Overall Coverage Trend

```
{generate_ascii_trend_chart(history, width)}
```

### Trend Analysis

"""

    # Add trend analysis
    if len(history) >= 2:
        first_cov = history[0].get("overall_coverage", 0)
        last_cov = history[-1].get("overall_coverage", 0)
        delta = last_cov - first_cov

        if delta > 0:
            dashboard += f"- **Total Change:** +{delta:.2f}% (from {first_cov:.2f}% to {last_cov:.2f}%)\n"
            dashboard += f"- **Trend:** Increasing \u2191\n"
        elif delta < 0:
            dashboard += f"- **Total Change:** {delta:.2f}% (from {first_cov:.2f}% to {last_cov:.2f}%)\n"
            dashboard += f"- **Trend:** Decreasing \u2192\n"
        else:
            dashboard += f"- **Total Change:** 0.00% (stable at {last_cov:.2f}%)\n"
            dashboard += f"- **Trend:** Stable \u2192\n"

        # Calculate average rate
        if len(history) > 1:
            avg_rate = delta / (len(history) - 1)
            dashboard += f"- **Average Change:** {avg_rate:+.3f}% per snapshot\n"
    else:
        dashboard += "- **Insufficient data for trend analysis**\n"

    dashboard += "\n---\n\n"

    # Add module breakdown charts
    dashboard += generate_module_charts(trend_data)

    # Add detailed analysis
    dashboard += generate_analysis_section(trend_data)

    # Add forecast section
    dashboard += generate_forecast_section(trend_data, target_pct)

    # Add detailed snapshots table
    dashboard += generate_detailed_snapshots_table(history)

    # Add metadata section
    dashboard += generate_metadata_section(metadata)

    # Add user guide
    dashboard += generate_user_guide_section()

    # Add technical notes
    dashboard += generate_technical_notes_section()

    # Add changelog
    dashboard += generate_changelog_section()

    return dashboard


def generate_changelog_section() -> str:
    """
    Generate changelog section for dashboard updates.

    Returns:
        Markdown changelog section
    """
    section = "## Dashboard Changelog\n\n"

    section += "### v5.0 (2026-03-01)\n"
    section += "- Initial trend dashboard creation\n"
    section += "- ASCII visualization for terminal display\n"
    section += "- Per-module breakdown (core, api, tools)\n"
    section += "- Forecast scenarios (optimistic, realistic, pessimistic)\n"
    section += "- Detailed snapshot history with commit messages\n"
    section += "- Coverage momentum and velocity tracking\n"
    section += "- Module performance comparison\n"
    section += "- Comprehensive user guide and technical notes\n\n"

    section += "### Planned Enhancements\n"
    section += "- [ ] Integration with frontend/mobile coverage data\n"
    section += "- [ ] Automated PR comment generation\n"
    section += "- [ ] Email alerts on regression detection\n"
    section += "- [ ] Historical trend comparison by phase\n"
    section += "- [ ] Coverage heatmaps by file/directory\n\n"

    section += "---\n\n"
    section += "*For questions or issues, see: `backend/tests/scripts/generate_coverage_dashboard.py`*\n"
    section += "*Coverage data source: `backend/tests/coverage_reports/metrics/coverage_trend_v5.0.json`*\n\n"

    return section


def generate_ascii_trend_chart(history: List[Dict[str, Any]], width: int = 70) -> str:
    """
    Generate ASCII line chart showing last 30 snapshots.

    Args:
        history: List of snapshot dicts
        width: Chart width in characters

    Returns:
        ASCII chart string
    """
    if not history:
        return "No trend data available"

    # Use last 30 snapshots
    snapshots = history[-30:] if len(history) > 30 else history

    # Find min/max for scaling
    coverages = [s.get("overall_coverage", 0) for s in snapshots]
    min_cov = min(coverages)
    max_cov = max(coverages)

    # Include 80% target in scale
    target_pct = 80.0
    if min_cov < target_pct:
        max_cov = max(max_cov, target_pct)

    range_cov = max_cov - min_cov if max_cov > min_cov else 1.0

    # Chart dimensions
    chart_height = 15
    chart_width = min(width, len(snapshots))

    lines = []
    lines.append("Coverage Trend (last {} snapshots)".format(len(snapshots)))
    lines.append("=" * width)

    # Generate chart rows (top to bottom)
    for row in range(chart_height, -1, -1):
        value = min_cov + (range_cov * row / chart_height)

        # Y-axis label
        label = f"{value:5.1f}%"

        # Build chart row
        chart_row = label + " |"

        # Plot each snapshot
        for i in range(chart_width):
            if i < len(snapshots):
                snapshot = snapshots[i]
                cov = snapshot.get("overall_coverage", 0)

                # Check if value is close to this point
                if abs(cov - value) < (range_cov / chart_height):
                    # Mark special points
                    if i == 0:
                        chart_row += "B"  # Baseline
                    elif i == len(snapshots) - 1:
                        chart_row += "C"  # Current
                    else:
                        chart_row += "*"
                else:
                    chart_row += " "
            else:
                chart_row += " "

        chart_row += "|"

        # Mark target line
        if abs(target_pct - value) < (range_cov / chart_height):
            chart_row += " <-- 80% TARGET"

        lines.append(chart_row)

    # X-axis
    lines.append("       +" + "-" * chart_width + "+")
    lines.append("Legend: B = Baseline, C = Current, * = Historical snapshot")

    return "\n".join(lines)


def generate_module_charts(trend_data: Dict[str, Any]) -> str:
    """
    Generate per-module ASCII charts.

    Args:
        trend_data: Trend data with module breakdown

    Returns:
        Markdown section with module charts
    """
    history = trend_data.get("history", [])

    # Extract module histories
    modules = ["core", "api", "tools"]
    module_data = {m: [] for m in modules}

    for snapshot in history:
        module_breakdown = snapshot.get("module_breakdown", {})
        for module in modules:
            module_data[module].append(module_breakdown.get(module, 0))

    # Generate section
    section = "## Module Breakdown\n\n"

    for module in modules:
        current = module_data[module][-1] if module_data[module] else 0
        section += f"### {module.capitalize()} Module ({current:.2f}%)\n\n"

        # Add statistics
        if module_data[module]:
            min_cov = min(module_data[module])
            max_cov = max(module_data[module])
            avg_cov = sum(module_data[module]) / len(module_data[module])

            section += f"- **Current:** {current:.2f}%\n"
            section += f"- **Average:** {avg_cov:.2f}%\n"
            section += f"- **Range:** {min_cov:.2f}% - {max_cov:.2f}%\n"
            section += f"- **Snapshots:** {len(module_data[module])}\n\n"

            # Calculate progress to 80%
            remaining = 80.0 - current
            progress_pct = (current / 80.0) * 100
            filled = int(progress_pct / 5)
            bar = "█" * filled + "░" * (20 - filled)

            section += f"Progress to 80%: [{bar}] {progress_pct:.1f}% ({remaining:.2f}% remaining)\n\n"

        section += "```\n"
        section += generate_small_module_chart(module_data[module])
        section += "\n```\n\n"

        # Add module trend analysis
        if len(module_data[module]) >= 2:
            first = module_data[module][0]
            last = module_data[module][-1]
            delta = last - first

            if delta > 0.5:
                trend_icon = "\u2191"  # Up arrow
                trend_text = "Increasing"
            elif delta < -0.5:
                trend_icon = "\u2193"  # Down arrow
                trend_text = "Decreasing"
            else:
                trend_icon = "\u2192"  # Right arrow
                trend_text = "Stable"

            section += f"**Trend:** {trend_text} {trend_icon} ({delta:+.2f}% from baseline)\n\n"

        section += "---\n\n"

    return section


def generate_small_module_chart(module_history: List[float], width: int = 40) -> str:
    """
    Generate small ASCII chart for a single module.

    Args:
        module_history: List of coverage values
        width: Chart width

    Returns:
        ASCII chart string
    """
    if not module_history:
        return "No data"

    # Scale to fit width
    values = module_history[-width:] if len(module_history) > width else module_history

    min_val = min(values)
    max_val = max(values)
    range_val = max_val - min_val if max_val > min_val else 1.0

    # If all values are the same, show flat line
    if range_val < 0.01:
        lines = []
        current_val = values[0] if values else 0
        lines.append(f"Coverage: {current_val:.2f}% (stable across {len(values)} snapshots)")
        lines.append("")
        lines.append(" " * 10 + "*" * min(len(values), width))
        lines.append(" " * 10 + "^" if len(values) <= width else " " * 10 + "^" + " " * (width - 1) + "^")
        return "\n".join(lines)

    # Normal chart with variation
    lines = []

    # Create 3-row chart (high, mid, low)
    for threshold_pct in [0.75, 0.5, 0.25]:
        threshold = min_val + (range_val * threshold_pct)
        row_label = f"{max_val:.1f}%" if threshold_pct == 0.75 else f"{min_val + range_val * 0.5:.1f}%" if threshold_pct == 0.5 else f"{min_val:.1f}%"

        chart_row = f"{row_label:>6} |"
        for v in values:
            if v >= threshold:
                chart_row += "*"
            else:
                chart_row += " "
        chart_row += "|"

        lines.append(chart_row)

    # X-axis
    lines.append("       +" + "-" * min(len(values), width) + "+")

    return "\n".join(lines)


def calculate_forecast_to_target(trend_data: Dict[str, Any], target: float = 80.0) -> Dict[str, Any]:
    """
    Calculate timeline estimation to reach target coverage.

    Args:
        trend_data: Trend data with history
        target: Target coverage percentage

    Returns:
        Dict with optimistic, realistic, pessimistic estimates
    """
    history = trend_data.get("history", [])

    if len(history) < 3:
        return {
            "optimistic": "Insufficient data",
            "realistic": "Insufficient data",
            "pessimistic": "Insufficient data"
        }

    current = trend_data["current"]["overall_coverage"]

    if current >= target:
        return {
            "optimistic": "Target reached",
            "realistic": "Target reached",
            "pessimistic": "Target reached"
        }

    # Calculate average gain per snapshot (last 5)
    recent = history[-5:]
    increases = []
    for i in range(1, len(recent)):
        delta = recent[i]["overall_coverage"] - recent[i - 1]["overall_coverage"]
        increases.append(delta)

    avg_gain = sum(increases) / len(increases) if increases else 0

    if avg_gain <= 0:
        return {
            "optimistic": "Cannot forecast",
            "realistic": "Cannot forecast",
            "pessimistic": "Cannot forecast"
        }

    # Calculate snapshots needed
    remaining = target - current
    snapshots_needed = int(remaining / avg_gain) + 1

    # Estimate timeline based on snapshot frequency
    first_snapshot = datetime.fromisoformat(history[0]["timestamp"].replace("Z", "+00:00"))
    last_snapshot = datetime.fromisoformat(trend_data["current"]["timestamp"].replace("Z", "+00:00"))
    days_span = (last_snapshot - first_snapshot).days
    days_per_snapshot = days_span / (len(history) - 1) if len(history) > 1 else 1

    estimated_days = int(snapshots_needed * days_per_snapshot)

    # Generate scenarios
    optimistic_days = int(estimated_days * 0.7)  # 130% rate
    pessimistic_days = int(estimated_days * 1.3)  # 70% rate

    return {
        "optimistic_days": optimistic_days,
        "realistic_days": estimated_days,
        "pessimistic_days": pessimistic_days,
        "snapshots_needed": snapshots_needed,
        "avg_gain_per_snapshot": avg_gain
    }


def generate_forecast_section(trend_data: Dict[str, Any], target: float = 80.0) -> str:
    """
    Generate forecast section with 3 scenarios.

    Args:
        trend_data: Trend data with history
        target: Target coverage percentage

    Returns:
        Markdown forecast section
    """
    forecast = calculate_forecast_to_target(trend_data, target)

    section = "## Forecast to 80%\n\n"

    if isinstance(forecast.get("realistic"), str):
        # Error or insufficient data
        section += f"**{forecast['realistic']}**\n\n"
    else:
        section += f"- **Optimistic:** {forecast['optimistic_days']} days (130% rate)\n"
        section += f"- **Realistic:** {forecast['realistic_days']} days (100% rate)\n"
        section += f"- **Pessimistic:** {forecast['pessimistic_days']} days (70% rate)\n\n"

        # Add context
        section += f"*Based on {forecast['snapshots_needed']} snapshots needed at {forecast['avg_gain_per_snapshot']:.3f}% gain per snapshot*\n\n"

    section += "---\n\n"

    return section


def generate_snapshots_table(history: List[Dict[str, Any]], limit: int = 10) -> str:
    """
    Generate markdown table of recent snapshots.

    Args:
        history: List of snapshot dicts
        limit: Number of recent snapshots to show

    Returns:
        Markdown table
    """
    recent = history[-limit:] if len(history) > limit else history

    section = "## Recent Snapshots\n\n"
    section += "| Date | Coverage | Delta | Commit |\n"
    section += "|------|----------|-------|--------|\n"

    for snapshot in reversed(recent):
        timestamp = snapshot.get("timestamp", "")
        coverage = snapshot.get("overall_coverage", 0)
        commit = snapshot.get("commit", "unknown")[:8]

        # Parse date
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d")
        except:
            date_str = timestamp.split("T")[0] if "T" in timestamp else timestamp

        # Get delta
        delta = snapshot.get("delta", {})
        delta_str = f"{delta.get('absolute_change', 0):+.2f}%" if delta else "N/A"

        section += f"| {date_str} | {coverage:.2f}% | {delta_str} | `{commit}` |\n"

    section += "\n---\n\n"

    return section


def generate_detailed_snapshots_table(history: List[Dict[str, Any]], limit: int = 30) -> str:
    """
    Generate detailed markdown table of snapshots with more information.

    Args:
        history: List of snapshot dicts
        limit: Number of snapshots to show (default: 30)

    Returns:
        Markdown table section
    """
    recent = history[-limit:] if len(history) > limit else history

    section = "## Detailed Snapshot History\n\n"
    section += f"Showing {len(recent)} most recent snapshots (oldest to newest):\n\n"
    section += "| # | Date | Coverage | Lines | Branch | Delta | Commit | Message |\n"
    section += "|---|------|----------|-------|--------|-------|--------|---------|\n"

    for i, snapshot in enumerate(recent, 1):
        timestamp = snapshot.get("timestamp", "")
        coverage = snapshot.get("overall_coverage", 0)
        covered_lines = snapshot.get("covered_lines", 0)
        total_lines = snapshot.get("total_lines", 0)
        branch_cov = snapshot.get("branch_coverage", 0)
        commit = snapshot.get("commit", "unknown")[:8]
        commit_msg = snapshot.get("commit_message", "")[:40]

        # Parse date
        try:
            dt = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
            date_str = dt.strftime("%Y-%m-%d %H:%M")
        except:
            date_str = timestamp[:16] if len(timestamp) > 16 else timestamp

        # Get delta
        delta = snapshot.get("delta", {})
        delta_str = f"{delta.get('absolute_change', 0):+.2f}%" if delta else "N/A"

        # Format commit message
        msg_short = commit_msg.replace("\n", " ") if commit_msg else "N/A"

        section += f"| {i} | {date_str} | {coverage:.2f}% | {covered_lines:,}/{total_lines:,} | {branch_cov:.1f}% | {delta_str} | `{commit}` | {msg_short} |\n"

    section += "\n---\n\n"

    return section


def generate_analysis_section(trend_data: Dict[str, Any]) -> str:
    """
    Generate comprehensive analysis section.

    Args:
        trend_data: Trend data with history and current stats

    Returns:
        Markdown analysis section
    """
    history = trend_data.get("history", [])
    current = trend_data.get("current", {})
    baseline = trend_data.get("baseline", {})

    section = "## Detailed Analysis\n\n"

    # Coverage momentum
    if len(history) >= 5:
        recent_5 = history[-5:]
        recent_changes = []
        for i in range(1, len(recent_5)):
            delta = recent_5[i]["overall_coverage"] - recent_5[i - 1]["overall_coverage"]
            recent_changes.append(delta)

        avg_recent_change = sum(recent_changes) / len(recent_changes) if recent_changes else 0

        section += "### Coverage Momentum (Last 5 Snapshots)\n\n"
        section += f"- **Average Change:** {avg_recent_change:+.3f}% per snapshot\n"

        if avg_recent_change > 0.1:
            momentum = "Positive"
            icon = "\U0001F7E2"  # Green circle
        elif avg_recent_change < -0.1:
            momentum = "Negative"
            icon = "\U0001F534"  # Red circle
        else:
            momentum = "Neutral"
            icon = "\U0001F7E1"  # Yellow circle

        section += f"- **Momentum:** {icon} {momentum}\n\n"

    # Module comparison
    section += "### Module Performance Comparison\n\n"
    current_modules = current.get("module_breakdown", {})
    baseline_modules = baseline.get("module_breakdown", {})

    section += "| Module | Current | Baseline | Change | Target | Gap |\n"
    section += "|--------|---------|----------|--------|--------|-----|\n"

    for module in ["core", "api", "tools"]:
        current_val = current_modules.get(module, 0)
        baseline_val = baseline_modules.get(module, 0)
        change = current_val - baseline_val
        target = 80.0
        gap = target - current_val

        change_str = f"{change:+.2f}%"
        gap_str = f"{gap:.2f}%"

        section += f"| {module.capitalize()} | {current_val:.2f}% | {baseline_val:.2f}% | {change_str} | {target:.2f}% | {gap_str} |\n"

    section += "\n"

    # Coverage velocity
    if len(history) >= 3:
        first_snapshot = history[0]
        last_snapshot = history[-1]

        first_date = datetime.fromisoformat(first_snapshot["timestamp"].replace("Z", "+00:00"))
        last_date = datetime.fromisoformat(last_snapshot["timestamp"].replace("Z", "+00:00"))

        days_elapsed = (last_date - first_date).days
        total_change = last_snapshot["overall_coverage"] - first_snapshot["overall_coverage"]

        if days_elapsed > 0 and total_change != 0:
            velocity_per_day = total_change / days_elapsed
            section += "### Coverage Velocity\n\n"
            section += f"- **Time Elapsed:** {days_elapsed} days\n"
            section += f"- **Total Change:** {total_change:+.2f}%\n"
            section += f"- **Velocity:** {velocity_per_day:+.3f}% per day\n\n"

    # Recommendations
    section += "### Recommendations\n\n"

    current_cov = current.get("overall_coverage", 0)
    remaining = 80.0 - current_cov

    if remaining > 50:
        section += "- \u26A0\uFE0F **Critical Gap:** More than 50% below target. Focus on high-impact files first.\n"
    elif remaining > 30:
        section += "- **Significant Gap:** 30-50% below target. Accelerate test creation.\n"
    elif remaining > 10:
        section += "- **Moderate Gap:** 10-30% below target. Maintain current momentum.\n"
    else:
        section += "- \u2705 **Almost There:** Less than 10% to target. Final push needed.\n"

    section += "\n---\n\n"

    return section


def generate_metadata_section(metadata: Dict[str, Any]) -> str:
    """
    Generate metadata section with trend tracking information.

    Args:
        metadata: Metadata dict from trend data

    Returns:
        Markdown section
    """
    section = "## Metadata\n\n"
    section += "| Property | Value |\n"
    section += "|----------|-------|\n"
    section += f"| **Version** | {metadata.get('version', 'N/A')} |\n"
    section += f"| **Target Coverage** | {metadata.get('target_coverage', 'N/A')}% |\n"
    section += f"| **Max History Entries** | {metadata.get('max_history_entries', 'N/A')} |\n"
    section += f"| **Total Snapshots** | {metadata.get('total_snapshots', 'N/A')} |\n"
    section += f"| **Created At** | {metadata.get('created_at', 'N/A')} |\n"
    section += f"| **Last Updated** | {metadata.get('last_updated', 'N/A')} |\n"

    section += "\n---\n\n"

    return section


def generate_user_guide_section() -> str:
    """
    Generate user guide section for interpreting the dashboard.

    Returns:
        Markdown guide section
    """
    section = "## How to Interpret This Dashboard\n\n"

    section += "### Understanding the Charts\n\n"
    section += "**Overall Coverage Trend:**\n"
    section += "- Shows coverage over time with the last 30 snapshots\n"
    section += "- `B` marks the baseline (first measurement)\n"
    section += "- `C` marks the current (latest measurement)\n"
    section += "- `*` marks historical snapshots\n"
    section += "- `80% TARGET` line shows the goal\n\n"

    section += "**Module Breakdown:**\n"
    section += "- Core: `backend/core/` - Business logic, governance, LLM integration\n"
    section += "- API: `backend/api/` - REST endpoints, routes, handlers\n"
    section += "- Tools: `backend/tools/` - Browser automation, device capabilities\n\n"

    section += "### Reading the Progress Bar\n\n"
    section += "The visual progress bar shows completion toward 80%:\n"
    section += "- `█` (filled blocks) = progress made\n"
    section += "- `░` (empty blocks) = remaining work\n"
    section += "- Total width = 20 characters (5% per character)\n\n"

    section += "Example: `[█████░░░░░░░░░░░░░░░]` = 25% progress\n\n"

    section += "### Forecast Scenarios\n\n"
    section += "- **Optimistic:** 130% of recent velocity (best case)\n"
    section += "- **Realistic:** 100% of recent velocity (expected case)\n"
    section += "- **Pessimistic:** 70% of recent velocity (worst case)\n\n"

    section += "Forecasts assume:\n"
    section += "- Consistent test writing pace\n"
    section += "- Linear coverage growth\n"
    section += "- No major refactoring that reduces coverage\n\n"

    section += "### Using This Data\n\n"
    section += "**For Developers:**\n"
    section += "- Focus on modules with largest gap to 80%\n"
    section += "- Prioritize files with 0% coverage for quick wins\n"
    section += "- Track impact of test additions in snapshot history\n"
    section += "- Verify coverage increases after writing tests\n\n"

    section += "**For Project Managers:**\n"
    section += "- Monitor velocity to estimate completion timeline\n"
    section += "- Use forecast scenarios for risk planning\n"
    section += "- Check trend direction (should be increasing)\n"
    section += "- Allocate resources based on module gaps\n\n"

    section += "**For QA Teams:**\n"
    section += "- Identify under-tested modules (low coverage %)\n"
    section += "- Track regression (sudden decreases in trend)\n"
    section += "- Validate test coverage after feature releases\n"
    section += "- Prioritize testing efforts by module risk\n\n"

    section += "### Updating This Dashboard\n\n"
    section += "This dashboard is automatically updated:\n"
    section += "- After each CI/CD pipeline run\n"
    section += "- When tests are executed locally with coverage tracking\n"
    section += "- Via manual update: `python tests/scripts/coverage_trend_tracker.py --commit <hash>`\n\n"

    section += "### Quick Reference\n\n"
    section += "**Good Coverage Trend:**\n"
    section += "- Increasing by 0.5-2% per snapshot\n"
    section += "- All modules showing upward momentum\n"
    section += "- Forecast timeline within 3-6 months\n\n"

    section += "**Warning Signs:**\n"
    section += "- Flat or decreasing trend (no progress)\n"
    section += "- One module stagnant while others improve\n"
    section += "- Large gaps between snapshots (infrequent testing)\n\n"

    section += "---\n\n"

    return section


def generate_technical_notes_section() -> str:
    """
    Generate technical notes section about data collection.

    Returns:
        Markdown notes section
    """
    section = "## Technical Notes\n\n"

    section += "### Data Collection Method\n\n"
    section += "- **Tool:** pytest with pytest-cov plugin\n"
    section += "- **Source:** `backend/tests/coverage_reports/metrics/coverage.json`\n"
    section += "- **Frequency:** Per commit, max 30 entries retained\n"
    section += "- **Format:** JSON with timestamps, git hashes, and commit messages\n\n"

    section += "### Coverage Calculation\n\n"
    section += "- **Statement Coverage:** Percentage of executed lines vs total lines\n"
    section += "- **Branch Coverage:** Percentage of executed branches vs total branches\n"
    section += "- **Module Breakdown:** Aggregated from file-level data\n"
    section += "- **Threshold:** 80% target for all modules\n\n"

    section += "### Data Files\n\n"
    section += "- `coverage_trend_v5.0.json`: Main trend tracking file\n"
    section += "- `trends/YYYY-MM-DD_coverage_trend.json`: Daily snapshots\n"
    section += "- `coverage.json`: Latest coverage report\n"
    section += "- `coverage_baseline.json`: Initial baseline from Phase 100\n\n"

    section += "### Visualization\n\n"
    section += "- **Format:** ASCII art (terminal-friendly, no dependencies)\n"
    section += "- **Width:** Configurable (default: 70 characters)\n"
    section += "- **Height:** Auto-scaled based on data range\n"
    section += "- **Rendering:** Monospace font required for proper alignment\n\n"

    section += "### Limitations\n\n"
    section += "- Tracks backend Python code only (not frontend/mobile/desktop)\n"
    section += "- Requires git repository for commit metadata\n"
    section += "- Limited to last 30 snapshots (older data archived)\n"
    section += "- Forecast assumes linear progression (may vary)\n\n"

    section += "---\n\n"

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


def write_trend_dashboard(trend_file: Path, output_path: Path, width: int = 70) -> None:
    """
    Generate and write trend dashboard markdown file.

    Args:
        trend_file: Path to coverage_trend_v5.0.json
        output_path: Output path for trend dashboard
        width: ASCII chart width
    """
    # Load trend data
    trend_data = load_trend_data(trend_file)

    if not trend_data:
        print(f"❌ ERROR: Could not load trend data from {trend_file}")
        sys.exit(1)

    # Generate dashboard
    dashboard_content = generate_trend_dashboard(trend_data, width)

    # Write to file
    output_path.parent.mkdir(parents=True, exist_ok=True)
    with open(output_path, 'w') as f:
        f.write(dashboard_content)

    print(f"✅ Trend dashboard generated: {output_path}")
    print(f"   Size: {len(dashboard_content):,} bytes")


def main():
    """Main entry point."""
    parser = argparse.ArgumentParser(
        description="Generate coverage dashboard from Phase 100 artifacts or trend data"
    )
    parser.add_argument(
        "--metrics-dir",
        type=str,
        default="tests/coverage_reports/metrics",
        help="Path to metrics directory containing Phase 100 JSON files"
    )
    parser.add_argument(
        "--trend-file",
        type=str,
        default=None,
        help="Path to coverage_trend_v5.0.json for trend dashboard mode"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="tests/coverage_reports/COVERAGE_DASHBOARD_v5.0.md",
        help="Output path for dashboard markdown file"
    )
    parser.add_argument(
        "--mode",
        type=str,
        choices=["unified", "trend"],
        default="unified",
        help="Dashboard mode: unified (Phase 100) or trend (Phase 110)"
    )
    parser.add_argument(
        "--width",
        type=int,
        default=70,
        help="ASCII chart width in characters (default: 70)"
    )

    args = parser.parse_args()

    # Trend dashboard mode
    if args.mode == "trend":
        if not args.trend_file:
            # Auto-detect trend file
            args.trend_file = str(Path(args.metrics_dir) / "coverage_trend_v5.0.json")

        trend_file = Path(args.trend_file)
        output_path = Path(args.output)

        if not trend_file.exists():
            print(f"❌ ERROR: Trend file not found: {trend_file}")
            sys.exit(1)

        write_trend_dashboard(trend_file, output_path, args.width)
        print("\n✅ Trend Dashboard Generation Complete")
        return

    # Unified dashboard mode (default)
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
