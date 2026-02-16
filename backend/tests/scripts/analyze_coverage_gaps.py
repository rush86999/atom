#!/usr/bin/env python3
"""
Coverage Gap Analysis Script

Analyzes pytest coverage reports to identify high-impact testing opportunities.
Categorizes files by size, calculates coverage gaps, and prioritizes files for
maximum coverage improvement.

Usage:
    python3 tests/scripts/analyze_coverage_gaps.py --format all --output-dir tests/coverage_reports/metrics/
    python3 tests/scripts/analyze_coverage_gaps.py --format json --output-dir /path/to/output
    python3 tests/scripts/analyze_coverage_gaps.py --format markdown --output-dir reports/

Output Files:
    - coverage_summary.json: Module-level aggregations and file tiers
    - priority_files_for_phases_12_13.json: Ranked file list for test planning
    - zero_coverage_analysis.json: Files with 0% coverage >100 lines
    - PHASE_11_COVERAGE_ANALYSIS_REPORT.md: Comprehensive markdown report

Requirements:
    - Python 3.11+
    - coverage.json from pytest-cov

Author: Phase 11 Coverage Analysis
Generated: 2026-02-15
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Tuple


def load_coverage_data(coverage_path: str) -> Dict[str, Any]:
    """
    Load coverage.json from pytest-cov.

    Args:
        coverage_path: Path to coverage.json file

    Returns:
        Coverage data dictionary

    Raises:
        FileNotFoundError: If coverage.json doesn't exist
        json.JSONDecodeError: If coverage.json is invalid
    """
    path = Path(coverage_path)
    if not path.exists():
        raise FileNotFoundError(
            f"Coverage file not found: {coverage_path}\n"
            f"Run tests with coverage first: pytest --cov=backend --cov-report=json"
        )

    with open(path, 'r') as f:
        return json.load(f)


def categorize_file_by_size(lines: int) -> str:
    """
    Categorize file by total lines of code.

    Args:
        lines: Total number of lines (statements)

    Returns:
        Tier category (Tier 1-5)
    """
    if lines >= 500:
        return "Tier 1"  # Highest impact
    elif lines >= 300:
        return "Tier 2"  # High impact
    elif lines >= 200:
        return "Tier 3"  # Medium impact
    elif lines >= 100:
        return "Tier 4"  # Low impact
    else:
        return "Tier 5"  # Minimal impact


def calculate_metrics(filedata: Dict[str, Any]) -> Dict[str, float]:
    """
    Calculate coverage metrics for a single file.

    Args:
        filedata: File coverage data from coverage.json

    Returns:
        Dictionary with calculated metrics
    """
    total_lines = filedata['summary']['num_statements']
    covered_lines = filedata['summary']['covered_lines']
    coverage_pct = filedata['summary']['percent_covered']

    # Coverage gap: lines that are NOT covered
    coverage_gap = total_lines - covered_lines

    # Potential gain: assuming 50% achievable coverage (Phase 8.6 proven target)
    potential_gain = coverage_gap * 0.5

    # Priority score: uncovered ratio (higher = more priority)
    priority_score = coverage_gap / total_lines if total_lines > 0 else 0

    return {
        'total_lines': total_lines,
        'covered_lines': covered_lines,
        'coverage_pct': coverage_pct,
        'coverage_gap': coverage_gap,
        'potential_gain': potential_gain,
        'priority_score': priority_score
    }


def analyze_files(coverage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Analyze all files in coverage report and calculate metrics.

    Args:
        coverage_data: Full coverage data dictionary

    Returns:
        List of file analysis results with metrics
    """
    files_analysis = []

    for filepath, filedata in coverage_data['files'].items():
        metrics = calculate_metrics(filedata)
        tier = categorize_file_by_size(metrics['total_lines'])

        files_analysis.append({
            'file': filepath,
            'tier': tier,
            **metrics
        })

    return files_analysis


def create_module_aggregation(files_analysis: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Aggregate metrics by module (core/, api/, tools/, etc.).

    Args:
        files_analysis: List of file analysis results

    Returns:
        Module-level aggregated metrics
    """
    modules = {}

    for file_data in files_analysis:
        # Extract module from filepath (e.g., "core/workflow_engine.py" -> "core")
        parts = file_data['file'].split('/')
        module = parts[0] if len(parts) > 1 else 'other'

        if module not in modules:
            modules[module] = {
                'total_lines': 0,
                'covered_lines': 0,
                'files': []
            }

        modules[module]['total_lines'] += file_data['total_lines']
        modules[module]['covered_lines'] += file_data['covered_lines']
        modules[module]['files'].append(file_data)

    # Calculate module percentages
    for module in modules.values():
        module['coverage_pct'] = (
            module['covered_lines'] / module['total_lines'] * 100
            if module['total_lines'] > 0 else 0
        )
        module['coverage_gap'] = module['total_lines'] - module['covered_lines']

    return modules


def get_high_priority_files(files_analysis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get high-priority files for testing (Tier 1-3, sorted by coverage gap).

    Args:
        files_analysis: List of file analysis results

    Returns:
        Sorted list of high-priority files
    """
    # Filter to Tier 1-3 (files >= 200 lines)
    high_priority = [f for f in files_analysis if f['tier'] in ['Tier 1', 'Tier 2', 'Tier 3']]

    # Sort by coverage gap (largest gap first)
    high_priority.sort(key=lambda x: x['coverage_gap'], reverse=True)

    return high_priority


def get_zero_coverage_files(files_analysis: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
    """
    Get files with 0% coverage and >100 lines.

    Args:
        files_analysis: List of file analysis results

    Returns:
        List of zero-coverage files
    """
    zero_coverage = [
        f for f in files_analysis
        if f['coverage_pct'] == 0 and f['total_lines'] >= 100
    ]

    # Sort by file size (largest first)
    zero_coverage.sort(key=lambda x: x['total_lines'], reverse=True)

    return zero_coverage


def estimate_test_complexity(file_data: Dict[str, Any]) -> str:
    """
    Estimate test complexity based on file size and coverage.

    Args:
        file_data: File analysis data

    Returns:
        Complexity level (low, medium, high)
    """
    lines = file_data['total_lines']

    if lines < 150:
        return "low"  # <30 tests
    elif lines < 400:
        return "medium"  # 30-60 tests
    else:
        return "high"  # >60 tests


def recommend_test_type(filepath: str) -> str:
    """
    Recommend test type based on file characteristics.

    Args:
        filepath: File path

    Returns:
        Recommended test type (unit, integration, property, e2e)
    """
    # Property tests for stateful logic
    if any(keyword in filepath for keyword in [
        'workflow', 'engine', 'handler', 'coordinator', 'executor'
    ]):
        return "property"

    # Integration tests for API endpoints
    if any(keyword in filepath for keyword in [
        'endpoint', 'route', 'api'
    ]):
        return "integration"

    # Unit tests for isolated logic
    if any(keyword in filepath for keyword in [
        'service', 'util', 'helper', 'manager'
    ]):
        return "unit"

    # Default to unit tests
    return "unit"


def create_coverage_summary(
    files_analysis: List[Dict[str, Any]],
    modules: Dict[str, Any]
) -> Dict[str, Any]:
    """
    Create coverage summary JSON output.

    Args:
        files_analysis: List of file analysis results
        modules: Module-level aggregated metrics

    Returns:
        Coverage summary dictionary
    """
    # Calculate overall metrics
    total_lines = sum(f['total_lines'] for f in files_analysis)
    total_covered = sum(f['covered_lines'] for f in files_analysis)
    overall_pct = (total_covered / total_lines * 100) if total_lines > 0 else 0

    # Get high-priority files
    high_priority = get_high_priority_files(files_analysis)
    zero_coverage = get_zero_coverage_files(files_analysis)

    # Organize by tier
    files_by_tier = {
        'Tier 1': [f for f in files_analysis if f['tier'] == 'Tier 1'],
        'Tier 2': [f for f in files_analysis if f['tier'] == 'Tier 2'],
        'Tier 3': [f for f in files_analysis if f['tier'] == 'Tier 3'],
        'Tier 4': [f for f in files_analysis if f['tier'] == 'Tier 4'],
        'Tier 5': [f for f in files_analysis if f['tier'] == 'Tier 5'],
    }

    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'overall': {
            'percent_covered': round(overall_pct, 2),
            'covered_lines': total_covered,
            'total_lines': total_lines,
            'coverage_gap': total_lines - total_covered
        },
        'modules': {
            module: {
                'percent_covered': round(data['coverage_pct'], 2),
                'covered_lines': data['covered_lines'],
                'total_lines': data['total_lines'],
                'coverage_gap': data['coverage_gap'],
                'file_count': len(data['files'])
            }
            for module, data in modules.items()
        },
        'files_by_size': {
            tier: {
                'file_count': len(files),
                'total_lines': sum(f['total_lines'] for f in files),
                'covered_lines': sum(f['covered_lines'] for f in files),
                'avg_coverage_pct': round(
                    sum(f['covered_lines'] for f in files) /
                    sum(f['total_lines'] for f in files) * 100
                    if sum(f['total_lines'] for f in files) > 0 else 0,
                    2
                )
            }
            for tier, files in files_by_tier.items()
        },
        'high_priority_files': [
            {
                'file': f['file'],
                'lines': f['total_lines'],
                'coverage_pct': round(f['coverage_pct'], 2),
                'uncovered_lines': f['coverage_gap'],
                'potential_gain': round(f['potential_gain']),
                'priority_score': round(f['priority_score'], 3)
            }
            for f in high_priority[:50]  # Top 50
        ],
        'zero_coverage_files': [
            {
                'file': f['file'],
                'lines': f['total_lines'],
                'estimated_gain_lines': round(f['total_lines'] * 0.5)
            }
            for f in zero_coverage
        ]
    }


def create_priority_files_list(
    high_priority: List[Dict[str, Any]],
    zero_coverage: List[Dict[str, Any]]
) -> Dict[str, Any]:
    """
    Create prioritized file list for Phases 12-13.

    Args:
        high_priority: List of high-priority files
        zero_coverage: List of zero-coverage files

    Returns:
        Priority files dictionary
    """
    # Calculate overall metrics
    total_lines = sum(f['total_lines'] for f in high_priority)
    total_covered = sum(f['covered_lines'] for f in high_priority)
    overall_pct = (total_covered / total_lines * 100) if total_lines > 0 else 0

    # Split into Phase 12 (Tier 1, <20% coverage) and Phase 13 (Tier 2-3, <30%)
    phase_12_files = [
        f for f in high_priority
        if f['tier'] == 'Tier 1' and f['coverage_pct'] < 20
    ][:20]  # Top 20 files

    phase_13_files = [
        f for f in high_priority
        if f not in phase_12_files and f['coverage_pct'] < 30
    ][:20]  # Next 20 files

    # Add zero-coverage files to Phase 13
    phase_13_files.extend(zero_coverage[:10])

    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'current_coverage': {
            'percent': round(overall_pct, 2),
            'covered_lines': total_covered,
            'total_lines': total_lines
        },
        'target_coverage': {
            'percent': 80,
            'required_lines': int(total_lines * 0.8),
            'gap_lines': total_lines - int(total_lines * 0.8)
        },
        'phases': {
            '12': {
                'target_percent': 28,
                'target_gain': 5.2,
                'files': [
                    {
                        'rank': i + 1,
                        'file': f['file'],
                        'lines': f['total_lines'],
                        'current_percent': round(f['coverage_pct'], 2),
                        'uncovered_lines': f['coverage_gap'],
                        'estimated_tests_needed': max(30, int(f['total_lines'] / 20)),
                        'recommended_test_type': recommend_test_type(f['file']),
                        'coverage_complexity': estimate_test_complexity(f),
                        'tier': f['tier']
                    }
                    for i, f in enumerate(phase_12_files)
                ]
            },
            '13': {
                'target_percent': 35,
                'target_gain': 7.0,
                'files': [
                    {
                        'rank': i + 1,
                        'file': f['file'],
                        'lines': f['total_lines'],
                        'current_percent': round(f['coverage_pct'], 2),
                        'uncovered_lines': f['coverage_gap'],
                        'estimated_tests_needed': max(30, int(f['total_lines'] / 20)),
                        'recommended_test_type': recommend_test_type(f['file']),
                        'coverage_complexity': estimate_test_complexity(f),
                        'tier': f['tier']
                    }
                    for i, f in enumerate(phase_13_files)
                ]
            }
        },
        'zero_coverage_quick_wins': [
            {
                'file': f['file'],
                'lines': f['total_lines'],
                'estimated_gain_lines': round(f['total_lines'] * 0.5),
                'recommended_test_type': recommend_test_type(f['file'])
            }
            for f in zero_coverage[:30]  # Top 30
        ]
    }


def create_zero_coverage_analysis(zero_coverage: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Create zero coverage analysis JSON.

    Args:
        zero_coverage: List of zero-coverage files

    Returns:
        Zero coverage analysis dictionary
    """
    return {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'total_zero_coverage_files': len(zero_coverage),
        'total_lines_uncovered': sum(f['total_lines'] for f in zero_coverage),
        'estimated_total_gain': sum(f['total_lines'] * 0.5 for f in zero_coverage),
        'files': [
            {
                'file': f['file'],
                'lines': f['total_lines'],
                'estimated_gain_lines': round(f['total_lines'] * 0.5),
                'recommended_test_type': recommend_test_type(f['file']),
                'complexity': estimate_test_complexity(f)
            }
            for f in zero_coverage
        ]
    }


def generate_markdown_report(
    coverage_summary: Dict[str, Any],
    priority_files: Dict[str, Any],
    modules: Dict[str, Any]
) -> str:
    """
    Generate comprehensive markdown report.

    Args:
        coverage_summary: Coverage summary data
        priority_files: Priority files data
        modules: Module aggregated data

    Returns:
        Markdown report content
    """
    overall = coverage_summary['overall']

    md = f"""# Phase 11 Coverage Analysis Report

**Generated:** {coverage_summary['generated_at']}
**Purpose:** Identify highest-impact testing opportunities for Phases 12-13

---

## Executive Summary

### Current Coverage Status

| Metric | Value |
|--------|-------|
| Overall Coverage | {overall['percent_covered']}% |
| Covered Lines | {overall['covered_lines']:,} |
| Total Lines | {overall['total_lines']:,} |
| Coverage Gap | {overall['coverage_gap']:,} lines |
| Target Coverage (80%) | {int(overall['total_lines'] * 0.8):,} lines |
| Remaining Gap | {int(overall['total_lines'] * 0.8) - overall['covered_lines']:,} lines |

### File Distribution by Size

| Tier | Size Range | File Count | Total Lines | Avg Coverage |
|------|------------|------------|-------------|--------------|
| Tier 1 | ≥500 lines | {coverage_summary['files_by_size']['Tier 1']['file_count']} | {coverage_summary['files_by_size']['Tier 1']['total_lines']:,} | {coverage_summary['files_by_size']['Tier 1']['avg_coverage_pct']}% |
| Tier 2 | 300-499 lines | {coverage_summary['files_by_size']['Tier 2']['file_count']} | {coverage_summary['files_by_size']['Tier 2']['total_lines']:,} | {coverage_summary['files_by_size']['Tier 2']['avg_coverage_pct']}% |
| Tier 3 | 200-299 lines | {coverage_summary['files_by_size']['Tier 3']['file_count']} | {coverage_summary['files_by_size']['Tier 3']['total_lines']:,} | {coverage_summary['files_by_size']['Tier 3']['avg_coverage_pct']}% |
| Tier 4 | 100-199 lines | {coverage_summary['files_by_size']['Tier 4']['file_count']} | {coverage_summary['files_by_size']['Tier 4']['total_lines']:,} | {coverage_summary['files_by_size']['Tier 4']['avg_coverage_pct']}% |
| Tier 5 | <100 lines | {coverage_summary['files_by_size']['Tier 5']['file_count']} | {coverage_summary['files_by_size']['Tier 5']['total_lines']:,} | {coverage_summary['files_by_size']['Tier 5']['avg_coverage_pct']}% |

---

## Top 20 High-Impact Files

Ranked by coverage gap (uncovered lines). **Target: 50% coverage per file** (Phase 8.6 proven sustainable).

| Rank | File | Lines | Current % | Uncovered | Priority | Tier | Test Type | Complexity |
|------|------|-------|-----------|-----------|----------|------|-----------|------------|
"""

    for i, file_data in enumerate(coverage_summary['high_priority_files'][:20], 1):
        filepath = file_data['file']
        lines = file_data['lines']
        pct = file_data['coverage_pct']
        uncovered = file_data['uncovered_lines']
        priority = file_data['priority_score']

        # Determine tier and test type
        tier = "Tier 1" if lines >= 500 else "Tier 2" if lines >= 300 else "Tier 3"
        test_type = recommend_test_type(filepath)
        complexity = "high" if lines >= 400 else "medium" if lines >= 150 else "low"

        md += f"| {i} | {filepath} | {lines} | {pct}% | {uncovered} | {priority:.3f} | {tier} | {test_type} | {complexity} |\n"

    md += f"""

---

## Zero Coverage Quick Wins

Files with **0% coverage** and >100 lines. Testing these to 50% coverage provides fast wins.

**Total zero-coverage files >100 lines:** {len(coverage_summary['zero_coverage_files'])}

| File | Lines | Est. Gain (50%) | Test Type | Complexity |
|------|-------|-----------------|-----------|------------|
"""

    for file_data in coverage_summary['zero_coverage_files'][:25]:
        filepath = file_data['file']
        lines = file_data['lines']
        gain = file_data['estimated_gain_lines']
        test_type = recommend_test_type(filepath)
        complexity = "high" if lines >= 400 else "medium" if lines >= 150 else "low"

        md += f"| {filepath} | {lines} | {gain} | {test_type} | {complexity} |\n"

    md += f"""

---

## Module Breakdown

### Core Module

**Files:** {len(modules.get('core', {}).get('files', []))}

| Metric | Value |
|--------|-------|
| Coverage | {modules.get('core', {}).get('coverage_pct', 0):.1f}% |
| Covered Lines | {modules.get('core', {}).get('covered_lines', 0):,} |
| Total Lines | {modules.get('core', {}).get('total_lines', 0):,} |
| Coverage Gap | {modules.get('core', {}).get('coverage_gap', 0):,} |

**Top 5 Gaps in core/:**
"""

    core_files = sorted(
        modules.get('core', {}).get('files', []),
        key=lambda x: x['coverage_gap'],
        reverse=True
    )[:5]

    for i, f in enumerate(core_files, 1):
        md += f"{i}. {f['file']}: {f['coverage_gap']} lines uncovered ({f['coverage_pct']:.1f}%)\n"

    md += f"""

### API Module

**Files:** {len(modules.get('api', {}).get('files', []))}

| Metric | Value |
|--------|-------|
| Coverage | {modules.get('api', {}).get('coverage_pct', 0):.1f}% |
| Covered Lines | {modules.get('api', {}).get('covered_lines', 0):,} |
| Total Lines | {modules.get('api', {}).get('total_lines', 0):,} |
| Coverage Gap | {modules.get('api', {}).get('coverage_gap', 0):,} |

**Top 5 Gaps in api/:**
"""

    api_files = sorted(
        modules.get('api', {}).get('files', []),
        key=lambda x: x['coverage_gap'],
        reverse=True
    )[:5]

    for i, f in enumerate(api_files, 1):
        md += f"{i}. {f['file']}: {f['coverage_gap']} lines uncovered ({f['coverage_pct']:.1f}%)\n"

    md += f"""

### Tools Module

**Files:** {len(modules.get('tools', {}).get('files', []))}

| Metric | Value |
|--------|-------|
| Coverage | {modules.get('tools', {}).get('coverage_pct', 0):.1f}% |
| Covered Lines | {modules.get('tools', {}).get('covered_lines', 0):,} |
| Total Lines | {modules.get('tools', {}).get('total_lines', 0):,} |
| Coverage Gap | {modules.get('tools', {}).get('coverage_gap', 0):,} |

**Top 5 Gaps in tools/:**
"""

    tools_files = sorted(
        modules.get('tools', {}).get('files', []),
        key=lambda x: x['coverage_gap'],
        reverse=True
    )[:5]

    for i, f in enumerate(tools_files, 1):
        md += f"{i}. {f['file']}: {f['coverage_gap']} lines uncovered ({f['coverage_pct']:.1f}%)\n"

    md += f"""

---

## Phase 12-13 Testing Strategy

### Strategy Overview

Based on Phase 8.6 validation (3.38x velocity acceleration), this analysis prioritizes **high-impact files** for maximum coverage gain.

**Key Principles:**
- Target 50% average coverage per file (proven sustainable)
- Prioritize largest files first (Tier 1 > Tier 2 > Tier 3)
- Use appropriate test types (property, integration, unit)
- 3-4 files per plan for focused execution

### Phase 12: Tier 1 Files

**Target:** {priority_files['phases']['12']['target_percent']}% coverage (+{priority_files['phases']['12']['target_gain']} percentage points)
**Focus:** Files ≥500 lines with <20% coverage
**Estimated Plans:** 4-5 plans
**Estimated Velocity:** +1.3-1.5% per plan

**Files:** {len(priority_files['phases']['12']['files'])} files

### Phase 13: Tier 2-3 + Zero Coverage

**Target:** {priority_files['phases']['13']['target_percent']}% coverage (+{priority_files['phases']['13']['target_gain']} percentage points)
**Focus:** Files 300-500 lines, <30% coverage + zero-coverage quick wins
**Estimated Plans:** 5-6 plans
**Estimated Velocity:** +1.2-1.4% per plan

**Files:** {len(priority_files['phases']['13']['files'])} files

### Test Type Recommendations

| Test Type | When to Use | Examples |
|-----------|-------------|----------|
| **Property Tests** | Stateful logic, workflows, handlers | workflow_engine, byok_handler, coordinators |
| **Integration Tests** | API endpoints, routes | atom_agent_endpoints, workflow_endpoints, API routes |
| **Unit Tests** | Isolated logic, services, utilities | lancedb_handler, auto_document_ingestion, services |

### Execution Plan

**Files Per Plan:** 3-4 high-impact files
**Target Coverage Per File:** 50% (Phase 8.6 proven sustainable)
**Estimated Velocity:** +1.5% per plan (maintaining Phase 8.6 acceleration)
**Estimated Duration:** 4-6 hours per plan

**Total Estimated Impact:**
- Phase 12: +{priority_files['phases']['12']['target_gain']} percentage points
- Phase 13: +{priority_files['phases']['13']['target_gain']} percentage points
- Combined: +{priority_files['phases']['12']['target_gain'] + priority_files['phases']['13']['target_gain']} percentage points

---

## Recommendations

1. **Start with Tier 1 files** (Phase 12) - Highest ROI with 3.38x velocity acceleration
2. **Target 50% coverage per file** - Proven sustainable from Phase 8.6
3. **Use appropriate test types** - Property tests for stateful logic, integration for APIs
4. **3-4 files per plan** - Focused execution without overwhelming complexity
5. **Leverage existing test infrastructure** - Property test patterns, AsyncMock, FastAPI TestClient

---

## Appendix: Data Sources

- **Coverage Data:** `tests/coverage_reports/metrics/coverage.json`
- **Analysis Script:** `tests/scripts/analyze_coverage_gaps.py`
- **Priority Files:** `tests/coverage_reports/priority_files_for_phases_12_13.json`

*Generated by Phase 11 Coverage Analysis - {datetime.utcnow().strftime('%Y-%m-%d')}*
"""

    return md


def main():
    """Main entry point for coverage analysis script."""
    parser = argparse.ArgumentParser(
        description='Analyze coverage gaps and prioritize testing opportunities',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--coverage-file',
        default='backend/tests/coverage_reports/metrics/coverage.json',
        help='Path to coverage.json (default: backend/tests/coverage_reports/metrics/coverage.json)'
    )
    parser.add_argument(
        '--format',
        choices=['json', 'markdown', 'all'],
        default='all',
        help='Output format (default: all)'
    )
    parser.add_argument(
        '--output-dir',
        default='backend/tests/coverage_reports/metrics/',
        help='Output directory for generated files (default: backend/tests/coverage_reports/metrics/)'
    )

    args = parser.parse_args()

    try:
        # Load coverage data
        print(f"Loading coverage data from {args.coverage_file}...")
        coverage_data = load_coverage_data(args.coverage_file)
        print(f"Found {len(coverage_data['files'])} files")

        # Analyze files
        print("Analyzing coverage gaps...")
        files_analysis = analyze_files(coverage_data)
        modules = create_module_aggregation(files_analysis)
        high_priority = get_high_priority_files(files_analysis)
        zero_coverage = get_zero_coverage_files(files_analysis)

        # Create output directory
        output_dir = Path(args.output_dir)
        output_dir.mkdir(parents=True, exist_ok=True)

        # Generate outputs based on format
        if args.format in ['json', 'all']:
            print("Generating JSON files...")

            # Coverage summary
            coverage_summary = create_coverage_summary(files_analysis, modules)
            summary_path = output_dir / 'coverage_summary.json'
            with open(summary_path, 'w') as f:
                json.dump(coverage_summary, f, indent=2)
            print(f"  Created: {summary_path}")

            # Priority files for Phases 12-13
            priority_files = create_priority_files_list(high_priority, zero_coverage)
            priority_path = output_dir / 'priority_files_for_phases_12_13.json'
            with open(priority_path, 'w') as f:
                json.dump(priority_files, f, indent=2)
            print(f"  Created: {priority_path}")

            # Zero coverage analysis
            zero_analysis = create_zero_coverage_analysis(zero_coverage)
            zero_path = output_dir / 'zero_coverage_analysis.json'
            with open(zero_path, 'w') as f:
                json.dump(zero_analysis, f, indent=2)
            print(f"  Created: {zero_path}")

        if args.format in ['markdown', 'all']:
            print("Generating markdown report...")

            # Generate markdown report
            markdown_report = generate_markdown_report(
                coverage_summary if args.format in ['json', 'all'] else create_coverage_summary(files_analysis, modules),
                priority_files if args.format in ['json', 'all'] else create_priority_files_list(high_priority, zero_coverage),
                modules
            )

            report_path = output_dir / 'PHASE_11_COVERAGE_ANALYSIS_REPORT.md'
            with open(report_path, 'w') as f:
                f.write(markdown_report)
            print(f"  Created: {report_path}")

        print("\nAnalysis complete!")
        print(f"High-priority files identified: {len(high_priority)}")
        print(f"Zero-coverage files (>100 lines): {len(zero_coverage)}")

        return 0

    except FileNotFoundError as e:
        print(f"Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"Error: Invalid JSON in coverage file: {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"Unexpected error: {e}", file=sys.stderr)
        import traceback
        traceback.print_exc()
        return 1


if __name__ == '__main__':
    sys.exit(main())
