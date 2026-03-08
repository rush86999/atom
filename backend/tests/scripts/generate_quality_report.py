#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Comprehensive Quality Metrics Report Generator

Purpose: Consolidate coverage trends, flaky tests, complexity hotspots, and slow tests
into a single markdown report for PR comments, preventing comment spam and providing
unified quality feedback to developers.

Usage:
    python generate_quality_report.py \\
        --trending-file tests/coverage_reports/metrics/cross_platform_trend.json \\
        --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \\
        --complexity-file tests/coverage_reports/metrics/complexity_hotspots.json \\
        --durations-file tests/coverage_reports/metrics/slow_tests.json \\
        --platform backend \\
        --output quality_metrics_report.md

Exit Codes:
    0: All quality metrics passing (no issues found)
    1: Issues found (flaky tests, complexity hotspots, or slow tests)
    2: Error (missing files, invalid JSON, etc.)
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, List, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Default paths
TREND_FILE = Path("tests/coverage_reports/metrics/cross_platform_trend.json")
QUARANTINE_DB = Path("tests/coverage_reports/metrics/flaky_tests.db")
COMPLEXITY_FILE = Path("tests/coverage_reports/metrics/complexity_hotspots.json")
DURATIONS_FILE = Path("tests/coverage_reports/metrics/slow_tests.json")
OUTPUT_FILE = Path("quality_metrics_report.md")

# Thresholds
MIN_HISTORY_ENTRIES = 2
WARNING_THRESHOLD = -1.0  # 1% decrease triggers warning
CRITICAL_THRESHOLD = -5.0  # 5% decrease triggers critical


def load_flaky_tests(db_path: Path, platform: str) -> List[Dict]:
    """Load flaky tests from quarantine database.

    Args:
        db_path: Path to flaky_tests.db
        platform: Platform filter (backend/frontend/mobile/desktop)

    Returns:
        List of flaky test records sorted by flaky rate (descending)

    Raises:
        SystemExit: If database not found or error loading
    """
    try:
        # Import FlakyTestTracker
        from tests.scripts.flaky_test_tracker import FlakyTestTracker

        tracker = FlakyTestTracker(db_path)
        flaky_tests = tracker.get_quarantined_tests(platform=platform)
        tracker.close()

        return flaky_tests
    except ImportError as e:
        logger.error(f"Failed to import FlakyTestTracker: {e}")
        sys.exit(2)
    except Exception as e:
        logger.error(f"Error loading flaky tests: {e}")
        sys.exit(2)


def load_complexity_hotspots(complexity_file: Path) -> List[Dict]:
    """Load complexity hotspots from JSON file.

    Args:
        complexity_file: Path to complexity_hotspots.json

    Returns:
        List of complexity hotspot records sorted by complexity (descending)

    Raises:
        SystemExit: If file not found or invalid JSON
    """
    if not complexity_file.exists():
        logger.warning(f"Complexity file not found: {complexity_file}")
        return []

    try:
        with open(complexity_file, 'r') as f:
            data = json.load(f)

        hotspots = data.get("hotspots", [])

        # Sort by complexity (descending)
        hotspots.sort(key=lambda x: x.get("complexity", 0), reverse=True)

        return hotspots
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading complexity hotspots: {e}")
        sys.exit(2)


def load_slow_tests(durations_file: Path, db_path: Path, platform: str, min_time: float = 10.0) -> List[Dict]:
    """Load slow tests from durations file or flaky test database.

    Args:
        durations_file: Path to slow_tests.json (optional)
        db_path: Path to flaky_tests.db
        platform: Platform filter
        min_time: Minimum execution time threshold (default: 10s)

    Returns:
        List of slow test records sorted by max_execution_time (descending)
    """
    # First, try to load from durations file (JSON output from track_execution_times.py)
    if durations_file and durations_file.exists():
        try:
            with open(durations_file, 'r') as f:
                data = json.load(f)

            slow_tests = data.get("slow_tests", [])

            # Sort by max_execution_time (descending)
            slow_tests.sort(key=lambda x: x.get("max_execution_time", 0), reverse=True)

            return slow_tests
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading slow tests from durations file: {e}")

    # Fallback: query from flaky test database
    try:
        from tests.scripts.flaky_test_tracker import FlakyTestTracker

        tracker = FlakyTestTracker(db_path)
        slow_tests = tracker.get_slow_tests(min_time=min_time, platform=platform, limit=50)
        tracker.close()

        return slow_tests
    except Exception as e:
        logger.warning(f"Error loading slow tests from database: {e}")
        return []


def calculate_platform_delta(current: float, previous: float) -> Tuple[str, str, float]:
    """Calculate trend indicator and severity for platform coverage change.

    Args:
        current: Current coverage percentage
        previous: Previous coverage percentage

    Returns:
        Tuple of (indicator, severity, delta)
        - indicator: ↑ (up), ↓ (down), → (stable)
        - severity: 🔴 CRITICAL, 🟡 WARNING, ✅ OK
        - delta: Coverage change in percentage points
    """
    delta = current - previous

    # Determine trend indicator
    if delta > 1.0:
        indicator = "↑"
    elif delta < -1.0:
        indicator = "↓"
    else:
        indicator = "→"

    # Determine severity
    if delta < CRITICAL_THRESHOLD:
        severity = "🔴"
    elif delta < WARNING_THRESHOLD:
        severity = "🟡"
    else:
        severity = "✅"

    return indicator, severity, delta


def generate_coverage_trends_section(trending_data: Dict) -> List[str]:
    """Generate coverage trends section with indicators and severity.

    Args:
        trending_data: Trending data dict with history list

    Returns:
        List of markdown lines
    """
    lines = []
    lines.append("### 📊 Coverage Trends")
    lines.append("")

    history = trending_data.get("history", [])

    if len(history) < MIN_HISTORY_ENTRIES:
        lines.append("*Insufficient historical data for trend analysis*")
        lines.append("")
        return lines

    # Get current and previous entries
    current_entry = history[-1]
    previous_entry = history[-2]

    # Extract platform coverage
    platforms = ["backend", "frontend", "mobile", "desktop"]
    current_platforms = current_entry.get("platforms", {})
    previous_platforms = previous_entry.get("platforms", {})

    # Build markdown table
    lines.append("| Platform | Previous | Current | Delta | Trend |")
    lines.append("|----------|----------|---------|-------|-------|")

    for platform in platforms:
        current_coverage = current_platforms.get(platform, 0.0)
        previous_coverage = previous_platforms.get(platform, 0.0)

        # Skip if both are 0 (no data)
        if current_coverage == 0.0 and previous_coverage == 0.0:
            continue

        indicator, severity, delta = calculate_platform_delta(current_coverage, previous_coverage)

        sign = "+" if delta >= 0 else ""
        lines.append(
            f"| {platform.capitalize():10s} | {previous_coverage:6.2f}% | "
            f"{current_coverage:6.2f}% | {sign}{delta:5.2f}% | {severity} {indicator} |"
        )

    lines.append("")

    # Legend
    lines.append("**Legend:**")
    lines.append("- ↑ Coverage increased (>1%)")
    lines.append("- → Coverage stable (±1%)")
    lines.append("- ↓ Coverage decreased (>1%)")
    lines.append("- 🔴 CRITICAL: >5% decrease (investigate required)")
    lines.append("- 🟡 WARNING: >1% decrease (monitor)")
    lines.append("- ✅ OK: Within normal variation")
    lines.append("")

    return lines


def generate_flaky_tests_section(flaky_tests: List[Dict]) -> List[str]:
    """Generate flaky tests section.

    Args:
        flaky_tests: List of flaky test records

    Returns:
        List of markdown lines
    """
    lines = []
    lines.append("### 🔄 Flaky Tests")
    lines.append("")

    if flaky_tests:
        lines.append(f"**{len(flaky_tests)} flaky tests detected**")
        lines.append("")
        lines.append("| Test | Flaky Rate | Platform |")
        lines.append("|------|------------|----------|")

        for test in flaky_tests[:5]:  # Show top 5
            name = test["test_path"].split("::")[-1]
            rate = test["flaky_rate"] * 100
            platform = test["platform"]
            lines.append(f"| {name} | {rate:.0f}% | {platform} |")

        if len(flaky_tests) > 5:
            lines.append(f"| ... and {len(flaky_tests) - 5} more | | |")
    else:
        lines.append("✅ No flaky tests detected")

    lines.append("")
    return lines


def generate_complexity_hotspots_section(complexity_hotspots: List[Dict]) -> List[str]:
    """Generate complexity hotspots section.

    Args:
        complexity_hotspots: List of complexity hotspot records

    Returns:
        List of markdown lines
    """
    lines = []
    lines.append("### 🔥 Complexity Hotspots")
    lines.append("")

    if complexity_hotspots:
        lines.append(f"**{len(complexity_hotspots)} high-complexity, low-coverage functions**")
        lines.append("")
        lines.append("| Function | Complexity | Coverage | Priority |")
        lines.append("|----------|------------|----------|----------|")

        for spot in complexity_hotspots[:5]:  # Show top 5
            func = f"{spot['function']}()"
            complexity = spot["complexity"]
            coverage = spot["coverage"]
            priority = spot["priority"].upper()
            lines.append(f"| {func} | {complexity} | {coverage:.1f}% | {priority} |")

        if len(complexity_hotspots) > 5:
            lines.append(f"| ... and {len(complexity_hotspots) - 5} more | | | |")
    else:
        lines.append("✅ No complexity hotspots")

    lines.append("")
    return lines


def generate_slow_tests_section(slow_tests: List[Dict]) -> List[str]:
    """Generate slow tests section.

    Args:
        slow_tests: List of slow test records

    Returns:
        List of markdown lines
    """
    lines = []
    lines.append("### ⏱️ Slow Tests (>10s)")
    lines.append("")

    if slow_tests:
        lines.append(f"**{len(slow_tests)} slow tests detected**")
        lines.append("")
        lines.append("| Test | Avg Time | Max Time | Platform |")
        lines.append("|------|----------|----------|----------|")

        for test in slow_tests[:5]:  # Show top 5
            name = test["test_path"].split("::")[-1]
            avg = test.get("avg_execution_time", 0)
            max_time = test.get("max_execution_time", 0)
            platform = test["platform"]
            lines.append(f"| {name} | {avg:.1f}s | {max_time:.1f}s | {platform} |")

        if len(slow_tests) > 5:
            lines.append(f"| ... and {len(slow_tests) - 5} more | | | |")
    else:
        lines.append("✅ All tests under 10s")

    lines.append("")
    return lines


def generate_summary_section(
    flaky_tests: List[Dict],
    complexity_hotspots: List[Dict],
    slow_tests: List[Dict]
) -> List[str]:
    """Generate summary section with actionable recommendations.

    Args:
        flaky_tests: List of flaky test records
        complexity_hotspots: List of complexity hotspot records
        slow_tests: List of slow test records

    Returns:
        List of markdown lines
    """
    lines = []
    lines.append("### 📋 Summary")
    lines.append("")

    issues = []

    if flaky_tests:
        issues.append(f"Fix {len(flaky_tests)} flaky tests")

    if complexity_hotspots:
        issues.append(f"Refactor {len(complexity_hotspots)} high-complexity functions")

    if slow_tests:
        issues.append(f"Optimize {len(slow_tests)} slow tests")

    if issues:
        lines.append("**Action Required:**")
        for issue in issues:
            lines.append(f"- {issue}")
        lines.append("")
        lines.append("Please address these issues to maintain test suite health.")
    else:
        lines.append("✅ All quality metrics passing")

    lines.append("")
    return lines


def generate_quality_report(
    trending_data: Dict,
    flaky_tests: List[Dict],
    complexity_hotspots: List[Dict],
    slow_tests: List[Dict]
) -> str:
    """Generate comprehensive quality metrics markdown report.

    Args:
        trending_data: Trending data dict with history list
        flaky_tests: List of flaky test records
        complexity_hotspots: List of complexity hotspot records
        slow_tests: List of slow test records

    Returns:
        Markdown string formatted for PR comment
    """
    lines = []
    lines.append("## Test Quality Metrics Report")
    lines.append("")

    # Section 1: Coverage Trends
    lines.extend(generate_coverage_trends_section(trending_data))

    # Section 2: Flaky Tests
    lines.extend(generate_flaky_tests_section(flaky_tests))

    # Section 3: Complexity Hotspots
    lines.extend(generate_complexity_hotspots_section(complexity_hotspots))

    # Section 4: Slow Tests
    lines.extend(generate_slow_tests_section(slow_tests))

    # Section 5: Summary
    lines.extend(generate_summary_section(flaky_tests, complexity_hotspots, slow_tests))

    return "\n".join(lines)


def load_trending_data(trend_file: Path) -> Dict:
    """Load trending data from cross_platform_trend.json.

    Args:
        trend_file: Path to cross_platform_trend.json

    Returns:
        Trending data dict

    Raises:
        SystemExit: If file not found or invalid JSON
    """
    if not trend_file.exists():
        logger.error(f"Trending file not found: {trend_file}")
        sys.exit(2)

    try:
        with open(trend_file, 'r') as f:
            trending_data = json.load(f)
        return trending_data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading trending data: {e}")
        sys.exit(2)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate comprehensive quality metrics report",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Basic usage
  python generate_quality_report.py \\
    --trending-file tests/coverage_reports/metrics/cross_platform_trend.json \\
    --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \\
    --complexity-file tests/coverage_reports/metrics/complexity_hotspots.json \\
    --platform backend

  # With slow tests
  python generate_quality_report.py \\
    --trending-file tests/coverage_reports/metrics/cross_platform_trend.json \\
    --quarantine-db tests/coverage_reports/metrics/flaky_tests.db \\
    --complexity-file tests/coverage_reports/metrics/complexity_hotspots.json \\
    --durations-file tests/coverage_reports/metrics/slow_tests.json \\
    --platform backend \\
    --output quality_metrics_report.md
        """
    )

    parser.add_argument(
        "--trending-file",
        type=Path,
        default=TREND_FILE,
        help="Path to cross_platform_trend.json"
    )

    parser.add_argument(
        "--quarantine-db",
        type=Path,
        default=QUARANTINE_DB,
        help="Path to flaky_tests.db"
    )

    parser.add_argument(
        "--complexity-file",
        type=Path,
        default=COMPLEXITY_FILE,
        help="Path to complexity_hotspots.json"
    )

    parser.add_argument(
        "--durations-file",
        type=Path,
        default=DURATIONS_FILE,
        help="Path to slow_tests.json (optional)"
    )

    parser.add_argument(
        "--platform",
        type=str,
        required=True,
        choices=["backend", "frontend", "mobile", "desktop"],
        help="Platform name (backend/frontend/mobile/desktop)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help="Path to output markdown file"
    )

    parser.add_argument(
        "--min-time",
        type=float,
        default=10.0,
        help="Slow test threshold in seconds (default: 10.0)"
    )

    args = parser.parse_args()

    # Load trending data
    logger.info(f"Loading trending data from: {args.trending_file}")
    trending_data = load_trending_data(args.trending_file)

    # Load flaky tests
    logger.info(f"Loading flaky tests from: {args.quarantine_db}")
    flaky_tests = load_flaky_tests(args.quarantine_db, args.platform)

    # Load complexity hotspots
    logger.info(f"Loading complexity hotspots from: {args.complexity_file}")
    complexity_hotspots = load_complexity_hotspots(args.complexity_file)

    # Load slow tests
    if args.durations_file and args.durations_file.exists():
        logger.info(f"Loading slow tests from: {args.durations_file}")
        slow_tests = load_slow_tests(args.durations_file, args.quarantine_db, args.platform, args.min_time)
    else:
        logger.info("No slow tests file provided, querying from database")
        slow_tests = load_slow_tests(None, args.quarantine_db, args.platform, args.min_time)

    # Generate report
    logger.info("Generating quality metrics report...")
    report = generate_quality_report(
        trending_data,
        flaky_tests,
        complexity_hotspots,
        slow_tests
    )

    # Write to output file
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        f.write(report)

    logger.info(f"Quality report written to: {args.output}")

    # Print to stdout for GitHub Action consumption
    print("")
    print(report)

    # Exit code: 0 if no issues, 1 if issues found
    has_issues = bool(flaky_tests or complexity_hotspots or slow_tests)
    return 0 if not has_issues else 1


if __name__ == "__main__":
    sys.exit(main())
