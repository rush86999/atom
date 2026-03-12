#!/usr/bin/env python3
"""
Phase 171 Coverage Gap Analysis Script

Analyzes Phase 171 baseline coverage data to create a realistic roadmap
for achieving 80% backend coverage based on historical performance.

Author: Phase 171 Plan 04A
Date: 2026-03-12
"""

import json
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def load_coverage_data() -> Dict[str, Any]:
    """Load Phase 171 overall coverage data."""
    coverage_path = Path("tests/coverage_reports/backend_phase_171_overall.json")
    with open(coverage_path) as f:
        return json.load(f)


def load_zero_coverage_analysis() -> Dict[str, Any]:
    """Load zero coverage analysis data."""
    zero_cov_path = Path("tests/coverage_reports/metrics/zero_coverage_analysis.json")
    with open(zero_cov_path) as f:
        return json.load(f)


def categorize_files_by_tier(coverage_data: Dict[str, Any]) -> Dict[str, List[Dict]]:
    """
    Categorize files by coverage tier.

    Tier 1: Zero coverage (highest priority)
    Tier 2: < 20% coverage
    Tier 3: 20-50% coverage
    Tier 4: > 50% coverage (lowest priority)
    """
    tier1_critical = []  # Zero coverage
    tier2_high = []      # < 20%
    tier3_medium = []    # 20-50%
    tier4_low = []       # > 50%

    for file_info in coverage_data['files']:
        cov = file_info['line_coverage']

        if cov == 0.0:
            tier1_critical.append(file_info)
        elif cov < 20.0:
            tier2_high.append(file_info)
        elif cov < 50.0:
            tier3_medium.append(file_info)
        else:
            tier4_low.append(file_info)

    return {
        'tier1_critical': tier1_critical,
        'tier2_high': tier2_high,
        'tier3_medium': tier3_medium,
        'tier4_low': tier4_low
    }


def calculate_historical_performance() -> Dict[str, Any]:
    """
    Calculate historical performance from Phases 165-170.

    Returns:
        Dict with avg_gain_per_phase, avg_duration_min, avg_lines_per_phase
    """
    historical_phases = {
        'Phase 165': {'gain': 4.0, 'duration_min': 5, 'notes': 'Governance & LLM (isolated)'},
        'Phase 166': {'gain': 0.0, 'duration_min': 5, 'notes': 'Episodic Memory (blocked)'},
        'Phase 167': {'gain': 3.5, 'duration_min': 7, 'notes': 'API Routes'},
        'Phase 168': {'gain': 5.0, 'duration_min': 5, 'notes': 'Database Layer'},
        'Phase 169': {'gain': 4.5, 'duration_min': 25, 'notes': 'Tools & Integrations'},
        'Phase 170': {'gain': 3.0, 'duration_min': 8, 'notes': 'LanceDB, WebSocket, HTTP'}
    }

    total_gain = sum(p['gain'] for p in historical_phases.values())
    total_duration = sum(p['duration_min'] for p in historical_phases.values())
    num_phases = len(historical_phases)

    return {
        'phases_analyzed': num_phases,
        'avg_gain_per_phase': total_gain / num_phases,
        'avg_duration_min': total_duration / num_phases,
        'historical_data': historical_phases
    }


def calculate_roadmap_metrics(
    coverage_data: Dict[str, Any],
    historical_perf: Dict[str, Any]
) -> Dict[str, Any]:
    """Calculate roadmap metrics for reaching 80% coverage."""
    current_coverage = coverage_data['line_coverage']
    lines_covered = coverage_data['lines_covered']
    lines_total = coverage_data['lines_total']

    target_coverage = 80.0
    gap_percent = target_coverage - current_coverage
    lines_needed = int((target_coverage / 100) * lines_total) - lines_covered

    avg_gain_per_phase = historical_perf['avg_gain_per_phase']
    avg_duration_min = historical_perf['avg_duration_min']

    phases_needed = int(gap_percent / avg_gain_per_phase) + 1
    estimated_weeks = phases_needed / 5  # Assuming 5 phases per week
    estimated_hours = (phases_needed * avg_duration_min) / 60

    return {
        'gap_percent': gap_percent,
        'lines_needed': lines_needed,
        'phases_needed': phases_needed,
        'estimated_weeks': estimated_weeks,
        'estimated_hours': estimated_hours
    }


def print_analysis_summary(
    coverage_data: Dict[str, Any],
    zero_cov_data: Dict[str, Any],
    tiers: Dict[str, List[Dict]],
    historical_perf: Dict[str, Any],
    roadmap_metrics: Dict[str, Any]
) -> None:
    """Print comprehensive analysis summary."""
    current_coverage = coverage_data['line_coverage']
    lines_covered = coverage_data['lines_covered']
    lines_total = coverage_data['lines_total']

    print("=" * 80)
    print("PHASE 171 COVERAGE GAP ANALYSIS")
    print("=" * 80)
    print()

    print("CURRENT COVERAGE (Phase 171 Baseline):")
    print(f"  Line Coverage: {current_coverage:.2f}%")
    print(f"  Lines Covered: {lines_covered:,}")
    print(f"  Total Lines: {lines_total:,}")
    print()

    print("GAP TO 80% TARGET:")
    print(f"  Gap: {roadmap_metrics['gap_percent']:.2f} percentage points")
    print(f"  Lines Needed: {roadmap_metrics['lines_needed']:,}")
    print()

    print("FILE INVENTORY:")
    print(f"  Total Files: {len(coverage_data['files']):,}")
    print(f"  Zero Coverage Files: {zero_cov_data['total_zero_coverage_files']:,}")
    print(f"  Zero Coverage Lines: {zero_cov_data['total_lines_uncovered']:,}")
    below_80 = len([f for f in coverage_data['files'] if f['line_coverage'] < 80])
    print(f"  Below 80%: {below_80:,} files")
    print()

    print("HISTORICAL PERFORMANCE (Phases 165-170):")
    for phase, data in historical_perf['historical_data'].items():
        print(f"  {phase}: +{data['gain']:.1f}% (~{data['duration_min']} min) - {data['notes']}")
    print(f"  AVERAGE: +{historical_perf['avg_gain_per_phase']:.2f}% per phase "
          f"(~{historical_perf['avg_duration_min']:.1f} min)")
    print()

    print("ROADMAP CALCULATION:")
    print(f"  Recommended phases to reach 80%: {roadmap_metrics['phases_needed']} phases")
    print(f"  Estimated duration: {roadmap_metrics['estimated_weeks']:.1f} weeks")
    print(f"  Estimated effort: {roadmap_metrics['estimated_hours']:.1f} hours")
    print()

    print("FILE TIER BREAKDOWN:")
    print(f"  Tier 1 (Critical - Zero Coverage): {len(tiers['tier1_critical']):,} files")
    print(f"  Tier 2 (High - < 20% Coverage): {len(tiers['tier2_high']):,} files")
    print(f"  Tier 3 (Medium - 20-50% Coverage): {len(tiers['tier3_medium']):,} files")
    print(f"  Tier 4 (Low - > 50% Coverage): {len(tiers['tier4_low']):,} files")
    print()


def main():
    """Main execution function."""
    print("Loading coverage data...")
    coverage_data = load_coverage_data()
    zero_cov_data = load_zero_coverage_analysis()

    print("Categorizing files by tier...")
    tiers = categorize_files_by_tier(coverage_data)

    print("Calculating historical performance...")
    historical_perf = calculate_historical_performance()

    print("Calculating roadmap metrics...")
    roadmap_metrics = calculate_roadmap_metrics(coverage_data, historical_perf)

    print()
    print_analysis_summary(
        coverage_data,
        zero_cov_data,
        tiers,
        historical_perf,
        roadmap_metrics
    )

    print("Analysis complete.")
    print(f"Generated at: {datetime.utcnow().isoformat()}Z")


if __name__ == "__main__":
    main()
