#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
PR Trend Comment Generator Script

Purpose: Generate markdown PR comments with coverage trend indicators (↑↓→)
showing regression alerts and historical context for developers.

Usage:
    python generate_pr_trend_comment.py [options]

Options:
    --trending-file PATH        Path to cross_platform_trend.json (default: relative path)
    --output PATH               Path to output markdown file (default: pr_comment.md)

Example:
    python generate_pr_trend_comment.py --trending-file tests/coverage_reports/metrics/cross_platform_trend.json
    python generate_pr_trend_comment.py --output /tmp/pr_comment.md
"""

import argparse
import json
import logging
import sys
from pathlib import Path
from typing import Dict, Optional, Tuple

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Default paths
TREND_FILE = Path("tests/coverage_reports/metrics/cross_platform_trend.json")
OUTPUT_FILE = Path("pr_comment.md")

# Thresholds
MIN_HISTORY_ENTRIES = 2
WARNING_THRESHOLD = -1.0  # 1% decrease triggers warning
CRITICAL_THRESHOLD = -5.0  # 5% decrease triggers critical


def calculate_platform_delta(current: float, previous: float) -> Tuple[str, str, float]:
    """
    Calculate trend indicator and severity for platform coverage change.

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
        severity = "🔴 CRITICAL"
    elif delta < WARNING_THRESHOLD:
        severity = "🟡 WARNING"
    else:
        severity = "✅ OK"

    return indicator, severity, delta


def generate_pr_comment(trending_data: Dict) -> str:
    """
    Generate markdown PR comment with trend indicators and historical context.

    Args:
        trending_data: Trending data dict with history list

    Returns:
        Markdown string formatted for PR comment

    Raises:
        ValueError: If insufficient historical data (need at least 2 entries)
    """
    history = trending_data.get("history", [])

    if len(history) < MIN_HISTORY_ENTRIES:
        raise ValueError(f"Insufficient historical data for trend analysis (need {MIN_HISTORY_ENTRIES}, have {len(history)})")

    # Get current and previous entries
    current_entry = history[-1]
    previous_entry = history[-2]

    # Extract platform coverage
    platforms = ["backend", "frontend", "mobile", "desktop"]
    current_platforms = current_entry.get("platforms", {})
    previous_platforms = previous_entry.get("platforms", {})

    # Extract historical context
    latest = trending_data.get("latest", {})
    overall_coverage = latest.get("overall_coverage", 0.0)

    # Calculate target coverage (80% goal)
    target_coverage = 80.0
    remaining = max(0.0, target_coverage - overall_coverage)

    # Find baseline (first entry in history)
    baseline_entry = history[0]
    baseline_coverage = baseline_entry.get("overall_coverage", 0.0)

    # Build markdown
    lines = []
    lines.append("### Coverage Trend Analysis")
    lines.append("")

    # Platform trends table
    lines.append("| Platform | Previous | Current | Delta | Status |")
    lines.append("|----------|----------|---------|-------|--------|")

    for platform in platforms:
        current_coverage = current_platforms.get(platform, 0.0)
        previous_coverage = previous_platforms.get(platform, 0.0)

        # Skip if both are 0 (no data)
        if current_coverage == 0.0 and previous_coverage == 0.0:
            continue

        indicator, severity, delta = calculate_platform_delta(current_coverage, previous_coverage)

        sign = "+" if delta >= 0 else ""
        lines.append(f"| {platform.capitalize():10s} | {previous_coverage:6.2f}% | {current_coverage:6.2f}% | {indicator} {sign}{delta:5.2f}% | {severity:12s} |")

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

    # Historical context
    lines.append("**Historical Context:**")
    lines.append(f"- Baseline: {baseline_coverage:.2f}%")
    lines.append(f"- Current: {overall_coverage:.2f}%")
    lines.append(f"- Target: {target_coverage:.2f}%")
    lines.append(f"- Remaining: {remaining:.2f}%")
    lines.append("")

    return "\n".join(lines)


def load_trending_data(trend_file: Path) -> Dict:
    """
    Load trending data from cross_platform_trend.json.

    Args:
        trend_file: Path to cross_platform_trend.json

    Returns:
        Trending data dict

    Raises:
        SystemExit: If file not found or invalid JSON
    """
    if not trend_file.exists():
        logger.error(f"Trending file not found: {trend_file}")
        sys.exit(1)

    try:
        with open(trend_file, 'r') as f:
            trending_data = json.load(f)
        return trending_data
    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading trending data: {e}")
        sys.exit(1)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Generate PR trend comments with coverage indicators"
    )

    parser.add_argument(
        "--trending-file",
        type=Path,
        default=TREND_FILE,
        help="Path to cross_platform_trend.json"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=OUTPUT_FILE,
        help="Path to output markdown file"
    )

    args = parser.parse_args()

    # Load trending data
    logger.info(f"Loading trending data from: {args.trending_file}")
    trending_data = load_trending_data(args.trending_file)

    # Generate PR comment
    try:
        pr_comment = generate_pr_comment(trending_data)
    except ValueError as e:
        logger.error(str(e))
        sys.exit(1)

    # Write to output file
    args.output.parent.mkdir(parents=True, exist_ok=True)
    with open(args.output, 'w') as f:
        f.write(pr_comment)

    logger.info(f"PR comment written to: {args.output}")

    # Print to stdout for GitHub Action consumption
    print("")
    print(pr_comment)

    return 0


if __name__ == "__main__":
    sys.exit(main())
