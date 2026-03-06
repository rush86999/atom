#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Cross-Platform Coverage Trend Tracking Script

Purpose: Track coverage changes over time for each platform, identify regressions,
and show trend indicators in PR comments. Extends existing trending.json format
to include cross-platform breakdown while maintaining backward compatibility.

Usage:
    python update_cross_platform_trending.py [options]

Options:
    --summary PATH              Path to cross_platform_summary.json (required)
    --trending-file PATH        Path to cross_platform_trend.json (default: relative path)
    --periods N                 Number of periods to compare for trend (default: 1)
    --format FORMAT             Output format: text|json|markdown (default: text)
    --commit-sha SHA            Current commit SHA for tracking
    --branch BRANCH             Branch name for tracking
    --prune                     Remove entries older than MAX_HISTORY_DAYS (default: 30)

Example:
    python update_cross_platform_trending.py --summary cross_platform_summary.json
    python update_cross_platform_trending.py --summary cross_platform_summary.json --periods 7 --format markdown
"""

import argparse
import json
import logging
import sys
from dataclasses import dataclass
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Default paths
TREND_FILE = Path("tests/coverage_reports/metrics/cross_platform_trend.json")
BACKEND_TREND_FILE = Path("tests/coverage_reports/metrics/trending.json")

# Retention settings
MAX_HISTORY_DAYS = 30
MIN_HISTORY_ENTRIES = 2

# Platform mapping for backward compatibility
PLATFORM_MAPPING = {
    "python": "backend",
    "javascript": "frontend",
    "mobile": "mobile",
    "desktop": "desktop"
}


@dataclass
class TrendEntry:
    """Single trend entry with timestamp and platform coverage."""
    timestamp: str
    overall_coverage: float
    platforms: Dict[str, float]  # backend, frontend, mobile, desktop
    thresholds: Dict[str, float]  # Platform thresholds at time of recording
    commit_sha: Optional[str] = None
    branch: Optional[str] = None


@dataclass
class TrendDelta:
    """Trend delta information for a platform."""
    platform: str
    current: float
    previous: float
    delta: float  # Positive = improvement, Negative = regression
    trend: str  # "up", "down", "stable"
    periods: int  # Number of data points compared


def load_trending_data(trend_file: Path) -> Dict:
    """
    Load trending data from cross_platform_trend.json.

    Validates structure and initializes empty structure if file doesn't exist.

    Expected schema:
    {
        "history": [
            {
                "timestamp": "2026-03-06T12:00:00Z",
                "overall_coverage": 78.5,
                "platforms": {"backend": 75.0, "frontend": 82.0, ...},
                "thresholds": {"backend": 70.0, "frontend": 80.0, ...},
                "commit_sha": "abc123",
                "branch": "main"
            }
        ],
        "latest": {
            "timestamp": "...",
            "overall_coverage": 78.5,
            "platforms": {...},
            "thresholds": {...}
        },
        "platform_trends": {
            "backend": {"trend": "up", "delta": 2.5, "periods": 1},
            "frontend": {"trend": "stable", "delta": 0.3, "periods": 1}
        },
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }

    Args:
        trend_file: Path to cross_platform_trend.json

    Returns:
        Dict with history list, latest entry, platform-specific trends
    """
    # Default empty structure
    default_structure = {
        "history": [],
        "latest": {},
        "platform_trends": {},
        "computed_weights": {
            "backend": 0.35,
            "frontend": 0.40,
            "mobile": 0.15,
            "desktop": 0.10
        }
    }

    if not trend_file.exists():
        logger.info(f"Trending file not found: {trend_file}, initializing empty structure")
        return default_structure

    try:
        with open(trend_file, 'r') as f:
            trending_data = json.load(f)

        # Validate structure
        required_keys = ["history", "latest", "platform_trends"]
        for key in required_keys:
            if key not in trending_data:
                logger.warning(f"Missing key '{key}' in trending data, initializing with default")
                trending_data[key] = default_structure[key]

        return trending_data

    except (json.JSONDecodeError, IOError) as e:
        logger.error(f"Error loading trending data: {e}")
        return default_structure


def update_trending_data(
    summary_file: Path,
    trend_file: Path,
    commit_sha: str = "",
    branch: str = ""
) -> Dict:
    """
    Update trending data with new coverage summary.

    Loads cross_platform_summary.json from Plan 01/02, creates new TrendEntry,
    appends to history, prunes old entries, updates latest entry, and saves.

    Args:
        summary_file: Path to cross_platform_summary.json
        trend_file: Path to cross_platform_trend.json
        commit_sha: Current commit SHA for tracking
        branch: Branch name for tracking

    Returns:
        Updated trending data dict
    """
    # Load summary data
    if not summary_file.exists():
        logger.error(f"Summary file not found: {summary_file}")
        sys.exit(1)

    with open(summary_file, 'r') as f:
        summary_data = json.load(f)

    # Load existing trending data
    trending_data = load_trending_data(trend_file)

    # Extract platform coverage from summary
    # Summary format: {"platforms": {"backend": {"coverage_pct": 75.0}, ...}, ...}
    platforms_coverage = {}
    thresholds = {}

    for platform_name, platform_data in summary_data.get("platforms", {}).items():
        platforms_coverage[platform_name] = platform_data.get("coverage_pct", 0.0)

    # Extract thresholds from summary
    thresholds = summary_data.get("thresholds", {})

    # Extract overall coverage
    overall_coverage = summary_data.get("weighted", {}).get("overall_pct", 0.0)

    # Extract commit SHA and branch
    timestamp = summary_data.get("timestamp", datetime.now().isoformat() + "Z")

    # Create new trend entry
    new_entry = {
        "timestamp": timestamp,
        "overall_coverage": round(overall_coverage, 2),
        "platforms": {k: round(v, 2) for k, v in platforms_coverage.items()},
        "thresholds": thresholds,
        "commit_sha": commit_sha,
        "branch": branch
    }

    # Append to history
    trending_data["history"].append(new_entry)

    # Prune old entries (older than MAX_HISTORY_DAYS)
    cutoff_time = datetime.now() - timedelta(days=MAX_HISTORY_DAYS)
    pruned_history = []

    for entry in trending_data["history"]:
        try:
            # Parse timestamp and make it offset-naive for comparison
            ts = entry["timestamp"].replace("Z", "").replace("+00:00", "")
            entry_time = datetime.fromisoformat(ts)
            if entry_time >= cutoff_time:
                pruned_history.append(entry)
        except (ValueError, KeyError):
            # Keep entries with invalid timestamps
            pruned_history.append(entry)

    trending_data["history"] = pruned_history

    # Update latest entry
    trending_data["latest"] = {
        "timestamp": new_entry["timestamp"],
        "overall_coverage": new_entry["overall_coverage"],
        "platforms": new_entry["platforms"],
        "thresholds": new_entry["thresholds"]
    }

    # Save updated trending data
    trend_file.parent.mkdir(parents=True, exist_ok=True)
    with open(trend_file, 'w') as f:
        json.dump(trending_data, f, indent=2)

    logger.info(f"Updated trending data: {trend_file}")
    logger.info(f"  History entries: {len(trending_data['history'])}")
    logger.info(f"  Overall coverage: {overall_coverage:.2f}%")

    return trending_data


def compute_trend_delta(
    trending_data: Dict,
    platform: str,
    periods: int = 1
) -> Optional[TrendDelta]:
    """
    Compute trend delta for a platform over N periods.

    Args:
        trending_data: Trending data dict with history
        platform: Platform name (backend, frontend, mobile, desktop)
        periods: Number of periods to compare (default: 1)

    Returns:
        TrendDelta or None if insufficient history
    """
    history = trending_data.get("history", [])

    if len(history) < MIN_HISTORY_ENTRIES:
        logger.debug(f"Insufficient history for trend computation (need {MIN_HISTORY_ENTRIES}, have {len(history)})")
        return None

    # Get current coverage from latest entry
    latest_entry = history[-1]
    current_coverage = latest_entry.get("platforms", {}).get(platform, 0.0)

    # Get previous coverage from N periods ago
    previous_index = len(history) - 1 - periods
    if previous_index < 0:
        logger.debug(f"Cannot compare {periods} periods ago (only {len(history)} entries)")
        return None

    previous_entry = history[previous_index]
    previous_coverage = previous_entry.get("platforms", {}).get(platform, 0.0)

    # Calculate delta (positive = improvement, negative = regression)
    delta = current_coverage - previous_coverage

    # Determine trend
    if delta > 1.0:
        trend = "up"
    elif delta < -1.0:
        trend = "down"
    else:
        trend = "stable"

    return TrendDelta(
        platform=platform,
        current=current_coverage,
        previous=previous_coverage,
        delta=round(delta, 2),
        trend=trend,
        periods=periods
    )


def generate_trend_report(trending_data: Dict, format: str = "text") -> str:
    """
    Generate trend report in specified format.

    Args:
        trending_data: Trending data dict
        format: Output format (text|json|markdown)

    Returns:
        Formatted report string
    """
    history = trending_data.get("history", [])

    if len(history) < MIN_HISTORY_ENTRIES:
        return "Insufficient history for trend report"

    # Compute deltas for each platform
    platforms = ["backend", "frontend", "mobile", "desktop"]
    deltas_1_period = {}
    deltas_7_period = {}

    for platform in platforms:
        delta_1 = compute_trend_delta(trending_data, platform, periods=1)
        if delta_1:
            deltas_1_period[platform] = delta_1

        delta_7 = compute_trend_delta(trending_data, platform, periods=7)
        if delta_7:
            deltas_7_period[platform] = delta_7

    # Generate report based on format
    if format == "text":
        return _generate_text_report(deltas_1_period, deltas_7_period)
    elif format == "json":
        return _generate_json_report(deltas_1_period, deltas_7_period)
    elif format == "markdown":
        return _generate_markdown_report(deltas_1_period, deltas_7_period)
    else:
        raise ValueError(f"Unknown format: {format}")


def _get_trend_indicator(trend: str) -> str:
    """Get trend indicator symbol."""
    if trend == "up":
        return "↑"
    elif trend == "down":
        return "↓"
    else:
        return "→"


def _generate_text_report(
    deltas_1_period: Dict[str, TrendDelta],
    deltas_7_period: Dict[str, TrendDelta]
) -> str:
    """Generate human-readable text report."""
    lines = []
    lines.append("=" * 70)
    lines.append("Cross-Platform Coverage Trend Report")
    lines.append("=" * 70)
    lines.append("")

    # 1-period trends
    lines.append("Trend (1 period):")
    for platform, delta in deltas_1_period.items():
        indicator = _get_trend_indicator(delta.trend)
        sign = "+" if delta.delta > 0 else ""
        lines.append(f"  {platform.capitalize():10s}: {delta.current:.2f}% ({indicator} {sign}{delta.delta:.2f}%)")

    lines.append("")

    # 7-period trends (week-over-week)
    if deltas_7_period:
        lines.append("Trend (7 periods - week over week):")
        for platform, delta in deltas_7_period.items():
            indicator = _get_trend_indicator(delta.trend)
            sign = "+" if delta.delta > 0 else ""
            lines.append(f"  {platform.capitalize():10s}: {delta.current:.2f}% ({indicator} {sign}{delta.delta:.2f}%)")

        lines.append("")

    lines.append("=" * 70)

    return "\n".join(lines)


def _generate_json_report(
    deltas_1_period: Dict[str, TrendDelta],
    deltas_7_period: Dict[str, TrendDelta]
) -> str:
    """Generate machine-readable JSON report."""
    report = {
        "trends_1_period": {},
        "trends_7_period": {}
    }

    for platform, delta in deltas_1_period.items():
        report["trends_1_period"][platform] = {
            "current": delta.current,
            "previous": delta.previous,
            "delta": delta.delta,
            "trend": delta.trend,
            "periods": delta.periods
        }

    for platform, delta in deltas_7_period.items():
        report["trends_7_period"][platform] = {
            "current": delta.current,
            "previous": delta.previous,
            "delta": delta.delta,
            "trend": delta.trend,
            "periods": delta.periods
        }

    return json.dumps(report, indent=2)


def _generate_markdown_report(
    deltas_1_period: Dict[str, TrendDelta],
    deltas_7_period: Dict[str, TrendDelta]
) -> str:
    """Generate markdown report (PR comment format)."""
    lines = []
    lines.append("### Coverage Trends")
    lines.append("")

    # 1-period trends
    lines.append("| Platform | Coverage | Trend (1) |")
    lines.append("|----------|----------|-----------|")

    for platform, delta in deltas_1_period.items():
        indicator = _get_trend_indicator(delta.trend)
        sign = "+" if delta.delta > 0 else ""
        lines.append(f"| {platform.capitalize()} | {delta.current:.2f}% | {indicator} {sign}{delta.delta:.2f}% |")

    lines.append("")

    # 7-period trends
    if deltas_7_period:
        lines.append("| Platform | Trend (7) |")
        lines.append("|----------|-----------|")

        for platform, delta in deltas_7_period.items():
            indicator = _get_trend_indicator(delta.trend)
            sign = "+" if delta.delta > 0 else ""
            lines.append(f"| {platform.capitalize()} | {indicator} {sign}{delta.delta:.2f}% |")

        lines.append("")

    # Legend
    lines.append("**Legend:**")
    lines.append("- ↑ Improved (>1% increase)")
    lines.append("- ↓ Regressed (>1% decrease)")
    lines.append("- → Stable (within ±1%)")

    return "\n".join(lines)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Cross-platform coverage trend tracking with historical data"
    )

    parser.add_argument(
        "--summary",
        type=Path,
        required=True,
        help="Path to cross_platform_summary.json"
    )

    parser.add_argument(
        "--trending-file",
        type=Path,
        default=TREND_FILE,
        help="Path to cross_platform_trend.json"
    )

    parser.add_argument(
        "--periods",
        type=int,
        default=1,
        help="Number of periods to compare for trend (default: 1)"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format"
    )

    parser.add_argument(
        "--commit-sha",
        type=str,
        default="",
        help="Current commit SHA for tracking"
    )

    parser.add_argument(
        "--branch",
        type=str,
        default="",
        help="Branch name for tracking"
    )

    parser.add_argument(
        "--prune",
        action="store_true",
        help="Remove entries older than MAX_HISTORY_DAYS"
    )

    args = parser.parse_args()

    # Update trending data
    trending_data = update_trending_data(
        args.summary,
        args.trending_file,
        args.commit_sha,
        args.branch
    )

    # Generate and print trend report
    report = generate_trend_report(trending_data, args.format)
    print(report)

    return 0


if __name__ == "__main__":
    sys.exit(main())
