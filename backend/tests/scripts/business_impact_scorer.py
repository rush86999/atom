#!/usr/bin/env python3
"""
Business Impact Scorer v1.0

Assigns business impact scores to source files for coverage prioritization.

Purpose: Not all uncovered lines are equally important. A governance bug is 10x more
critical than a UI utility bug. Business impact scoring weights coverage gaps by
business criticality so we prioritize testing where it matters most.

This enables the COVR-02 requirement: "rank files by (lines * impact / current_coverage)".

Usage:
    python3 tests/scripts/business_impact_scorer.py --help
    python3 tests/scripts/business_impact_scorer.py --coverage-file tests/coverage_reports/metrics/coverage_baseline.json
    python3 tests/scripts/business_impact_scorer.py --validate

Output:
    - business_impact_scores.json: File-to-impact-score mapping
    - BUSINESS_IMPACT_SCORING.md: Methodology documentation

Generated: 2026-02-27
Phase: 100-02
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


# =============================================================================
# IMPACT TIER DEFINITIONS
# =============================================================================

# Critical (score=10): Governance, LLM, episodic memory, constitutional safety
# These are the core business logic that keeps Atom running safely and effectively
CRITICAL_PATTERNS = {
    # Agent Governance & Safety
    'agent_governance',
    'governance_cache',
    'agent_context_resolver',
    'trigger_interceptor',
    'supervision_service',
    'proposal_service',
    'constitutional_validator',
    'constitutional',

    # LLM Integration & BYOK
    'byok_handler',
    'llm',
    'cognitive_tier',

    # Episodic Memory & Graduation
    'episode_segmentation',
    'episode_retrieval',
    'episode_lifecycle',
    'agent_graduation',

    # Canvas Presentations
    'canvas_tool',
    'canvas_state',

    # Student Agent Training
    'student_training',
    'meta_agent_training',

    # Browser Automation (Critical business impact)
    'browser',
}

# High (score=7): Tools, device, browser, package governance, skills, security
# These are important operational features with significant business impact
HIGH_PATTERNS = {
    # Tools & Device Capabilities
    'browser_tool',
    'device_tool',
    'device_capabilities',

    # Package Governance & Skills
    'package_governance',
    'package_dependency',
    'package_installer',
    'skill_adapter',
    'hazard_sandbox',
    'skill_security',
    'skill_registry',

    # Security & Auth
    'security',
    'auth',
    'permission',

    # World Model & Business Facts
    'world_model',
    'policy_fact',
    'business_fact',
}

# Medium (score=5): Supporting services, integrations, infrastructure
# These are important but less critical than core business logic
MEDIUM_PATTERNS = {
    # Workflow & Integration
    'workflow',
    'integration',

    # Analytics & Monitoring
    'dashboard',
    'analytics',
    'feedback',
    'monitoring',
    'health',

    # Deep Links & Navigation
    'deeplink',

    # Vector & Embedding
    'embedding',
    'lancedb',
    'vector',

    # Formula & Extraction
    'formula',
    'extractor',

    # Canvas Guidance (not core canvas_tool)
    'canvas_guidance',
    'agent_guidance',
}

# Low (score=3): Utilities, helpers, generated code, non-core features
# These are supporting code with minimal business impact
LOW_PATTERNS = {
    'util',
    'helper',
    'constant',
    'config',
    'mock',
    'fixture',
    'test',
    'example',
    'deprecated',
}


# =============================================================================
# VALIDATION FILE LISTS
# =============================================================================

# Known critical files from critical_path_mapper.py
# These MUST score as Critical (score=10)
KNOWN_CRITICAL_FILES = [
    'core/agent_governance_service.py',
    'core/llm/byok_handler.py',
    'core/episode_segmentation_service.py',
    'core/episode_retrieval_service.py',
    'core/agent_graduation_service.py',
    'tools/canvas_tool.py',
    'tools/browser_tool.py',
    'core/trigger_interceptor.py',
    'core/supervision_service.py',
]

# Known high-impact files
# These MUST score as High (score=7)
KNOWN_HIGH_FILES = [
    'tools/device_tool.py',
    'core/package_governance_service.py',
    'core/skill_adapter.py',
    # Note: hazard_sandbox.py may not exist in coverage data yet
]


# =============================================================================
# SCORING LOGIC
# =============================================================================

def score_file(filepath: str, coverage_data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Assign business impact score to a single file.

    Scoring priority: Critical (10) > High (7) > Medium (5) > Low (3)

    Args:
        filepath: Path to file (e.g., "core/agent_governance_service.py")
        coverage_data: Optional coverage data to extract coverage metrics

    Returns:
        Dictionary with tier, score, and coverage info
    """
    # Check patterns in priority order (critical -> high -> medium -> low)
    tier = None
    score = 0

    # Normalize filepath for pattern matching
    filepath_lower = filepath.lower()

    # Check Critical patterns first
    for pattern in CRITICAL_PATTERNS:
        if pattern in filepath_lower:
            tier = "Critical"
            score = 10
            break

    # If not Critical, check High patterns
    if tier is None:
        for pattern in HIGH_PATTERNS:
            if pattern in filepath_lower:
                tier = "High"
                score = 7
                break

    # If not High, check Medium patterns
    if tier is None:
        for pattern in MEDIUM_PATTERNS:
            if pattern in filepath_lower:
                tier = "Medium"
                score = 5
                break

    # If not Medium, check Low patterns
    if tier is None:
        for pattern in LOW_PATTERNS:
            if pattern in filepath_lower:
                tier = "Low"
                score = 3
                break

    # Default to Medium if no pattern matches
    if tier is None:
        tier = "Medium"
        score = 5

    # Extract coverage data if provided
    coverage_pct = 0.0
    uncovered_lines = 0
    total_lines = 0

    if coverage_data and filepath in coverage_data.get('files', {}):
        file_data = coverage_data['files'][filepath]
        summary = file_data.get('summary', {})
        coverage_pct = summary.get('percent_covered', 0.0)
        total_lines = summary.get('num_statements', 0)
        covered_lines = summary.get('covered_lines', 0)
        uncovered_lines = total_lines - covered_lines

    return {
        'file': filepath,
        'tier': tier,
        'score': score,
        'coverage_pct': round(coverage_pct, 2),
        'total_lines': total_lines,
        'uncovered_lines': uncovered_lines,
    }


def score_all_files(coverage_data: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Score all files in coverage report.

    Args:
        coverage_data: Full coverage report JSON

    Returns:
        List of scored files with tier, score, coverage metrics
    """
    scored_files = []

    for filepath in coverage_data.get('files', {}).keys():
        scored = score_file(filepath, coverage_data)
        scored_files.append(scored)

    # Sort by score (highest first), then by uncovered lines (most gaps first)
    scored_files.sort(key=lambda x: (-x['score'], -x['uncovered_lines']))

    return scored_files


def generate_scoring_report(scored_files: List[Dict[str, Any]]) -> Dict[str, Any]:
    """
    Generate aggregate statistics by impact tier.

    Args:
        scored_files: List of scored files

    Returns:
        Summary statistics with tier counts and uncovered line totals
    """
    # Aggregate by tier
    tier_stats = {
        'Critical': {'count': 0, 'uncovered_lines': 0, 'total_lines': 0},
        'High': {'count': 0, 'uncovered_lines': 0, 'total_lines': 0},
        'Medium': {'count': 0, 'uncovered_lines': 0, 'total_lines': 0},
        'Low': {'count': 0, 'uncovered_lines': 0, 'total_lines': 0},
    }

    for file_data in scored_files:
        tier = file_data['tier']
        tier_stats[tier]['count'] += 1
        tier_stats[tier]['uncovered_lines'] += file_data['uncovered_lines']
        tier_stats[tier]['total_lines'] += file_data['total_lines']

    # Calculate overall totals
    total_files = len(scored_files)
    total_uncovered = sum(f['uncovered_lines'] for f in scored_files)
    total_lines = sum(f['total_lines'] for f in scored_files)

    # Identify top gaps per tier
    top_gaps_by_tier = {}
    for tier in ['Critical', 'High', 'Medium', 'Low']:
        tier_files = [f for f in scored_files if f['tier'] == tier]
        top_gaps_by_tier[tier] = tier_files[:5]  # Top 5 gaps per tier

    return {
        'total_files': total_files,
        'total_uncovered_lines': total_uncovered,
        'total_lines': total_lines,
        'tier_counts': {
            tier: tier_stats[tier]['count']
            for tier in ['Critical', 'High', 'Medium', 'Low']
        },
        'tier_uncovered_lines': {
            tier: tier_stats[tier]['uncovered_lines']
            for tier in ['Critical', 'High', 'Medium', 'Low']
        },
        'top_gaps_by_tier': top_gaps_by_tier,
    }


def write_json_output(
    scored_files: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_path: str
):
    """
    Write business impact scores to JSON file.

    Args:
        scored_files: List of scored files
        summary: Summary statistics
        output_path: Path to output JSON file
    """
    # Group files by tier for structured output
    files_by_tier = {
        'Critical': [f for f in scored_files if f['tier'] == 'Critical'],
        'High': [f for f in scored_files if f['tier'] == 'High'],
        'Medium': [f for f in scored_files if f['tier'] == 'Medium'],
        'Low': [f for f in scored_files if f['tier'] == 'Low'],
    }

    output_data = {
        'generated_at': datetime.utcnow().isoformat() + 'Z',
        'scoring_rules': {
            'critical_score': 10,
            'high_score': 7,
            'medium_score': 5,
            'low_score': 3,
        },
        'summary': summary,
        'files_by_tier': files_by_tier,
        'all_files': scored_files,
    }

    with open(output_path, 'w') as f:
        json.dump(output_data, f, indent=2)

    print(f"Created: {output_path}")


def write_markdown_report(
    scored_files: List[Dict[str, Any]],
    summary: Dict[str, Any],
    output_path: str
):
    """
    Write methodology documentation to markdown file.

    Args:
        scored_files: List of scored files
        summary: Summary statistics
        output_path: Path to output markdown file
    """
    md = f"""# Business Impact Scoring Methodology

**Generated:** {datetime.utcnow().isoformat() + 'Z'}
**Phase:** 100-02
**Purpose:** Assign business impact scores to source files for coverage prioritization

---

## Overview

Not all uncovered lines are equally important. A governance bug is 10x more critical than a UI utility bug. Business impact scoring weights coverage gaps by business criticality so we prioritize testing where it matters most.

This enables the COVR-02 requirement: **"rank files by (lines * impact / current_coverage)"**.

---

## Impact Tiers

### Critical (Score: 10)

**Definition:** Core business logic that keeps Atom running safely and effectively.

**Patterns:**
"""

    for pattern in sorted(CRITICAL_PATTERNS):
        md += f"- `{pattern}`\n"

    md += f"""
**Examples:**
- `agent_governance_service.py` - Agent permission checks
- `byok_handler.py` - LLM provider routing
- `episode_segmentation_service.py` - Memory creation
- `canvas_tool.py` - Canvas presentations

**Impact:** Bugs here can cause security breaches, data loss, or system failure.

---

### High (Score: 7)

**Definition:** Important operational features with significant business impact.

**Patterns:**
"""

    for pattern in sorted(HIGH_PATTERNS):
        md += f"- `{pattern}`\n"

    md += f"""
**Examples:**
- `browser_tool.py` - Web automation
- `device_tool.py` - Device capabilities
- `package_governance_service.py` - Package security

**Impact:** Bugs here can cause feature failures or degraded user experience.

---

### Medium (Score: 5)

**Definition:** Supporting services and infrastructure.

**Patterns:**
"""

    for pattern in sorted(MEDIUM_PATTERNS):
        md += f"- `{pattern}`\n"

    md += f"""
**Examples:**
- Workflow orchestration
- Analytics and monitoring
- Integration adapters

**Impact:** Bugs here can cause minor disruptions or dashboard errors.

---

### Low (Score: 3)

**Definition:** Utilities, helpers, and non-core features.

**Patterns:**
"""

    for pattern in sorted(LOW_PATTERNS):
        md += f"- `{pattern}`\n"

    md += f"""
**Examples:**
- Utility functions
- Test fixtures
- Configuration loaders

**Impact:** Bugs here have minimal impact on core operations.

---

## Scoring Distribution

### Summary Statistics

| Metric | Count |
|--------|-------|
| Total Files | {summary['total_files']} |
| Total Lines | {summary['total_lines']:,} |
| Uncovered Lines | {summary['total_uncovered_lines']:,} |

### Files by Tier

| Tier | Score | File Count | Uncovered Lines |
|------|-------|------------|-----------------|
| Critical | 10 | {summary['tier_counts']['Critical']} | {summary['tier_uncovered_lines']['Critical']:,} |
| High | 7 | {summary['tier_counts']['High']} | {summary['tier_uncovered_lines']['High']:,} |
| Medium | 5 | {summary['tier_counts']['Medium']} | {summary['tier_uncovered_lines']['Medium']:,} |
| Low | 3 | {summary['tier_counts']['Low']} | {summary['tier_uncovered_lines']['Low']:,} |

---

## Top Gaps by Tier

### Critical Tier (Score: 10)

| File | Coverage | Uncovered Lines |
|------|----------|-----------------|
"""

    for f in summary['top_gaps_by_tier']['Critical'][:10]:
        md += f"| {f['file']} | {f['coverage_pct']}% | {f['uncovered_lines']} |\n"

    md += """
### High Tier (Score: 7)

| File | Coverage | Uncovered Lines |
|------|----------|-----------------|
"""

    for f in summary['top_gaps_by_tier']['High'][:10]:
        md += f"| {f['file']} | {f['coverage_pct']}% | {f['uncovered_lines']} |\n"

    md += """
---

## Usage

### Prioritization Formula

Rank files for testing using:

```
priority_score = (uncovered_lines * impact_score) / current_coverage
```

**Example:**
- File A: 100 uncovered lines, Critical (score=10), 0% coverage
  - Priority: (100 * 10) / 1 = 1000
- File B: 100 uncovered lines, High (score=7), 50% coverage
  - Priority: (100 * 7) / 0.5 = 1400
- File C: 100 uncovered lines, Low (score=3), 20% coverage
  - Priority: (100 * 3) / 0.2 = 1500

**Result:** File C (Low tier, poor coverage) ranks higher than File A (Critical tier, no tests) because it has lower existing coverage.

### Quick Wins Strategy

1. **Critical tier files with 0% coverage** - Highest priority
2. **High tier files with <20% coverage** - Quick wins
3. **Large files (500+ lines) with low coverage** - Maximum coverage gain

---

## Data Sources

- **Coverage Baseline:** `tests/coverage_reports/metrics/coverage_baseline.json`
- **Impact Scores:** `tests/coverage_reports/metrics/business_impact_scores.json`
- **Critical Paths:** `tests/coverage_reports/critical_path_mapper.py`

---

*Generated by Phase 100-02 Business Impact Scoring*
*Timestamp: {datetime.utcnow().isoformat() + 'Z'}*
"""

    with open(output_path, 'w') as f:
        f.write(md)

    print(f"Created: {output_path}")


# =============================================================================
# VALIDATION
# =============================================================================

def validate_known_critical_files(scored_files: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate that known critical files are scored as Critical (score=10).

    Args:
        scored_files: List of scored files

    Returns:
        Tuple of (all_passed, error_messages)
    """
    errors = []

    # Create lookup map
    file_scores = {f['file']: f for f in scored_files}

    for expected_file in KNOWN_CRITICAL_FILES:
        if expected_file not in file_scores:
            errors.append(f"MISSING: {expected_file} not found in coverage data")
            continue

        file_data = file_scores[expected_file]
        if file_data['tier'] != 'Critical' or file_data['score'] != 10:
            errors.append(
                f"WRONG_TIER: {expected_file} has tier={file_data['tier']}, score={file_data['score']} "
                f"(expected: Critical, 10)"
            )

    return len(errors) == 0, errors


def validate_known_high_files(scored_files: List[Dict[str, Any]]) -> Tuple[bool, List[str]]:
    """
    Validate that known high-impact files are scored as High (score=7).

    Args:
        scored_files: List of scored files

    Returns:
        Tuple of (all_passed, error_messages)
    """
    errors = []

    # Create lookup map
    file_scores = {f['file']: f for f in scored_files}

    for expected_file in KNOWN_HIGH_FILES:
        if expected_file not in file_scores:
            errors.append(f"MISSING: {expected_file} not found in coverage data")
            continue

        file_data = file_scores[expected_file]
        if file_data['tier'] != 'High' or file_data['score'] != 7:
            errors.append(
                f"WRONG_TIER: {expected_file} has tier={file_data['tier']}, score={file_data['score']} "
                f"(expected: High, 7)"
            )

    return len(errors) == 0, errors


def run_validation(scored_files: List[Dict[str, Any]]) -> bool:
    """
    Run all validation checks and print results.

    Args:
        scored_files: List of scored files

    Returns:
        True if all validations pass
    """
    print("\n" + "="*60)
    print("BUSINESS IMPACT SCORING VALIDATION")
    print("="*60)

    all_passed = True

    # Validate critical files
    print("\nValidating Critical files (score=10)...")
    critical_passed, critical_errors = validate_known_critical_files(scored_files)
    if critical_passed:
        print(f"  ✓ All {len(KNOWN_CRITICAL_FILES)} critical files correctly scored")
    else:
        print(f"  ✗ Found {len(critical_errors)} errors:")
        for error in critical_errors:
            print(f"    - {error}")
        all_passed = False

    # Validate high files
    print("\nValidating High files (score=7)...")
    high_passed, high_errors = validate_known_high_files(scored_files)
    if high_passed:
        print(f"  ✓ All {len(KNOWN_HIGH_FILES)} high files correctly scored")
    else:
        print(f"  ✗ Found {len(high_errors)} errors:")
        for error in high_errors:
            print(f"    - {error}")
        all_passed = False

    print("\n" + "="*60)
    if all_passed:
        print("VALIDATION PASSED ✓")
    else:
        print("VALIDATION FAILED ✗")
    print("="*60 + "\n")

    return all_passed


# =============================================================================
# MAIN ENTRY POINT
# =============================================================================

def main():
    """Main entry point for business impact scoring."""
    parser = argparse.ArgumentParser(
        description='Assign business impact scores to source files for coverage prioritization',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog=__doc__
    )
    parser.add_argument(
        '--coverage-file',
        default='backend/tests/coverage_reports/metrics/coverage_baseline.json',
        help='Path to coverage_baseline.json from Phase 100-01'
    )
    parser.add_argument(
        '--output',
        default='backend/tests/coverage_reports/metrics/business_impact_scores.json',
        help='Path to output JSON file'
    )
    parser.add_argument(
        '--report',
        default='backend/tests/coverage_reports/BUSINESS_IMPACT_SCORING.md',
        help='Path to methodology documentation'
    )
    parser.add_argument(
        '--validate',
        action='store_true',
        help='Run validation and exit'
    )

    args = parser.parse_args()

    try:
        # Load coverage baseline
        print(f"Loading coverage data from {args.coverage_file}...")
        with open(args.coverage_file, 'r') as f:
            coverage_data = json.load(f)

        print(f"Found {len(coverage_data.get('files', {}))} files")

        # Score all files
        print("Scoring files by business impact...")
        scored_files = score_all_files(coverage_data)

        # Generate summary
        summary = generate_scoring_report(scored_files)

        print(f"\nScoring complete!")
        print(f"  Total files: {summary['total_files']}")
        print(f"  Critical: {summary['tier_counts']['Critical']} files")
        print(f"  High: {summary['tier_counts']['High']} files")
        print(f"  Medium: {summary['tier_counts']['Medium']} files")
        print(f"  Low: {summary['tier_counts']['Low']} files")
        print(f"  Total uncovered lines: {summary['total_uncovered_lines']:,}")

        # Run validation if requested
        if args.validate:
            validation_passed = run_validation(scored_files)
            return 0 if validation_passed else 1

        # Write JSON output
        print("\nWriting output files...")
        write_json_output(scored_files, summary, args.output)

        # Write markdown report
        write_markdown_report(scored_files, summary, args.report)

        # Run validation after scoring
        validation_passed = run_validation(scored_files)

        if not validation_passed:
            print("\nWARNING: Validation failed. Please review scoring patterns.")
            return 1

        print("\nBusiness impact scoring complete!")
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
