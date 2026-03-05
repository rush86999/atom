#!/usr/bin/env python3
"""
Coverage Gap Analysis Script for Phase 121

Analyzes coverage JSON to identify gaps and prioritize tests.
"""

import json
import sys
from typing import List, Dict, Any

def parse_coverage_data(filepath: str) -> Dict[str, Any]:
    """Parse coverage JSON file."""
    with open(filepath) as f:
        return json.load(f)

def analyze_file_coverage(data: Dict[str, Any], file_path: str) -> Dict[str, Any]:
    """Analyze coverage for a single file."""
    file_data = data['files'].get(file_path, {})
    summary = file_data.get('summary', {})
    missing_lines = file_data.get('missing_lines', [])
    executed_lines = file_data.get('executed_lines', [])

    return {
        'file_path': file_path,
        'covered': summary.get('covered_lines', 0),
        'total': summary.get('num_statements', 0),
        'percent': summary.get('percent_covered', 0),
        'missing_lines': missing_lines,
        'executed_lines': executed_lines,
    }

def analyze_function_coverage(
    coverage_data: Dict[str, Any],
    func_name: str,
    start_line: int,
    end_line: int
) -> Dict[str, Any]:
    """Analyze coverage for a specific function."""
    missing_lines = coverage_data['missing_lines']
    func_missing = [l for l in missing_lines if start_line <= l <= end_line]
    func_total = end_line - start_line + 1
    func_covered = func_total - len(func_missing)
    func_pct = (func_covered / func_total * 100) if func_total > 0 else 0

    # Determine impact
    if len(func_missing) == 0:
        impact = "NONE"
    elif func_pct < 30:
        impact = "HIGH"
    elif func_pct < 60:
        impact = "MEDIUM"
    else:
        impact = "LOW"

    return {
        'name': func_name,
        'start': start_line,
        'end': end_line,
        'covered': func_covered,
        'total': func_total,
        'percent': func_pct,
        'missing_lines': func_missing,
        'impact': impact,
    }

def calculate_tests_needed(current_coverage: float, target_coverage: float = 60.0) -> int:
    """Estimate tests needed to reach target coverage."""
    gap = target_coverage - current_coverage
    if gap <= 0:
        return 0

    # Estimate: ~1 test per 1-2% coverage improvement
    tests_per_pct = 1.5
    return int(gap * tests_per_pct)

def main():
    # Load coverage data
    data = parse_coverage_data('backend/tests/coverage_reports/metrics/phase_121_health_coverage_baseline.json')

    # Analyze both files
    health_routes = analyze_file_coverage(data, 'api/health_routes.py')
    monitoring = analyze_file_coverage(data, 'core/monitoring.py')

    print("# Health Monitoring Coverage Gap Analysis\n")
    print("## Executive Summary\n")
    print(f"**Combined Coverage**: {(health_routes['percent'] + monitoring['percent']) / 2:.2f}%\n")
    print(f"- api/health_routes.py: {health_routes['percent']:.2f}% ({health_routes['covered']}/{health_routes['total']} lines)")
    print(f"- core/monitoring.py: {monitoring['percent']:.2f}% ({monitoring['covered']}/{monitoring['total']} lines)\n")

    # Health routes functions
    print("## api/health_routes.py - Coverage by Function\n")
    health_functions = [
        ('liveness_probe', 65, 81),
        ('readiness_probe', 142, 185),
        ('_check_database', 188, 234),
        ('_execute_db_query', 237, 246),
        ('check_database_connectivity', 304, 371),
        ('_check_disk_space', 374, 406),
        ('prometheus_metrics', 435, 447),
        ('sync_health_probe', 517, 556),
        ('sync_prometheus_metrics', 586, 609),
    ]

    health_gaps = []
    for func_name, start, end in health_functions:
        func_data = analyze_function_coverage(health_routes, func_name, start, end)
        if func_data['percent'] < 100:
            print(f"### {func_name}() - Lines {start}-{end}")
            print(f"- **Coverage**: {func_data['percent']:.1f}% ({func_data['covered']}/{func_data['total']} lines)")
            print(f"- **Impact**: {func_data['impact']}")
            if func_data['missing_lines']:
                print(f"- **Missing lines**: {func_data['missing_lines']}")
            print()
            health_gaps.append(func_data)

    # Monitoring functions
    print("\n## core/monitoring.py - Coverage by Function\n")
    monitoring_functions = [
        ('add_log_level', 170, 175),
        ('add_logger_name', 178, 183),
        ('configure_structlog', 186, 240),
        ('get_logger', 243, 257),
        ('RequestContext.__init__', 270, 273),
        ('RequestContext.__enter__', 275, 280),
        ('RequestContext.__exit__', 282, 285),
        ('track_http_request', 293, 312),
        ('track_agent_execution', 315, 331),
        ('track_skill_execution', 334, 350),
        ('track_db_query', 353, 363),
        ('set_active_agents', 366, 373),
        ('set_db_connections', 376, 385),
        ('track_deployment', 393, 415),
        ('track_smoke_test', 418, 440),
        ('record_rollback', 443, 451),
        ('update_canary_traffic', 454, 466),
        ('record_prometheus_query', 469, 480),
        ('initialize_metrics', 483, 496),
    ]

    monitoring_gaps = []
    for func_name, start, end in monitoring_functions:
        func_data = analyze_function_coverage(monitoring, func_name, start, end)
        if func_data['percent'] < 100:
            print(f"### {func_name}() - Lines {start}-{end}")
            print(f"- **Coverage**: {func_data['percent']:.1f}% ({func_data['covered']}/{func_data['total']} lines)")
            print(f"- **Impact**: {func_data['impact']}")
            if func_data['missing_lines']:
                print(f"- **Missing lines**: {func_data['missing_lines']}")
            print()
            monitoring_gaps.append(func_data)

    # Calculate tests needed
    print("\n## Test Count Estimate\n")
    health_tests = calculate_tests_needed(health_routes['percent'])
    monitoring_tests = calculate_tests_needed(monitoring['percent'])
    total_tests = health_tests + monitoring_tests

    print(f"**Target**: 60% coverage per file\n")
    print(f"- api/health_routes.py: {health_routes['percent']:.2f}% → 60% (need ~{health_tests} tests)")
    print(f"- core/monitoring.py: {monitoring['percent']:.2f}% → 60% (already exceeds target)")
    print(f"- **Total tests needed**: ~{health_tests} tests (health_routes.py only)\n")

    # Prioritized test list
    print("\n## Prioritized Test List (Highest ROI)\n")

    # Sort gaps by impact and missing lines
    all_gaps = sorted(
        [g for g in health_gaps if g['impact'] in ['HIGH', 'MEDIUM']],
        key=lambda x: (x['impact'] == 'HIGH', len(x['missing_lines'])),
        reverse=True
    )

    for i, gap in enumerate(all_gaps[:10], 1):
        print(f"### Gap {i}: {gap['name']}() - {gap['percent']:.1f}% coverage")
        print(f"- **File**: api/health_routes.py")
        print(f"- **Lines**: {gap['start']}-{gap['end']}")
        print(f"- **Impact**: {gap['impact']}")
        print(f"- **Tests Needed**:")
        print(f"  1. Test successful execution path")
        if gap['percent'] < 50:
            print(f"  2. Test error/exception paths")
            print(f"  3. Test edge cases (timeouts, failures)")
        print()

if __name__ == '__main__':
    main()
