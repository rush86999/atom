#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
Coverage Trend Analyzer Script

Purpose: Detect significant coverage regressions (>1% threshold), validate historical
data integrity, and log regression events for CI/CD alerting.

Usage:
    python coverage_trend_analyzer.py [options]

Options:
    --trending-file PATH        Path to cross_platform_trend.json (default: relative path)
    --regression-threshold FLOAT    Regression threshold in percentage (default: 1.0)
    --output PATH               Path to coverage_regressions.json (default: relative path)
    --periods N                 Number of periods to compare for trend (default: 7)
    --format FORMAT             Output format: text|json|markdown (default: text)

Example:
    python coverage_trend_analyzer.py --trending-file tests/coverage_reports/metrics/cross_platform_trend.json
    python coverage_trend_analyzer.py --regression-threshold 2.0 --format markdown
"""

import argparse
import json
import logging
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Optional

# Import from existing trending script
try:
    # Add parent directory to path for import
    sys.path.insert(0, str(Path(__file__).parent))
    from update_cross_platform_trending import TrendDelta, compute_trend_delta
except ImportError:
    # Fallback: define compute_trend_delta inline
    TrendDelta = None

    def compute_trend_delta(trending_data, platform, periods=1):
        """Fallback implementation if import fails."""
        history = trending_data.get("history", [])

        if len(history) < 2:
            return None

        # Get current coverage from latest entry
        latest_entry = history[-1]
        current_coverage = latest_entry.get("platforms", {}).get(platform, 0.0)

        # Get previous coverage from N periods ago
        previous_index = len(history) - 1 - periods
        if previous_index < 0:
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

        # Return simple dict instead of TrendDelta if class not available
        return {
            "platform": platform,
            "current": current_coverage,
            "previous": previous_coverage,
            "delta": round(delta, 2),
            "trend": trend,
            "periods": periods
        }

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(levelname)s: %(message)s'
)
logger = logging.getLogger(__name__)

# Default paths
TREND_FILE = Path("tests/coverage_reports/metrics/cross_platform_trend.json")
REGRESSION_OUTPUT = Path("tests/coverage_reports/metrics/coverage_regressions.json")

# Thresholds
REGRESSION_THRESHOLD = 1.0  # 1% change triggers alert
CRITICAL_THRESHOLD = 5.0     # 5% drop is critical
MIN_HISTORY_ENTRIES = 2      # Need at least 2 entries for comparison

# Retention settings
REGRESSION_RETENTION_DAYS = 90


# JSON Schema for cross_platform_trend.json validation
TREND_DATA_SCHEMA = {
    "type": "object",
    "required": ["history", "latest", "platform_trends", "computed_weights"],
    "properties": {
        "history": {
            "type": "array",
            "items": {
                "type": "object",
                "required": ["timestamp", "overall_coverage", "platforms", "thresholds"],
                "properties": {
                    "timestamp": {"type": "string"},
                    "overall_coverage": {"type": "number"},
                    "platforms": {
                        "type": "object",
                        "properties": {
                            "backend": {"type": "number"},
                            "frontend": {"type": "number"},
                            "mobile": {"type": "number"},
                            "desktop": {"type": "number"}
                        }
                    },
                    "thresholds": {
                        "type": "object",
                        "properties": {
                            "backend": {"type": "number"},
                            "frontend": {"type": "number"},
                            "mobile": {"type": "number"},
                            "desktop": {"type": "number"}
                        }
                    },
                    "commit_sha": {"type": "string"},
                    "branch": {"type": "string"}
                }
            }
        },
        "latest": {
            "type": "object",
            "required": ["timestamp", "overall_coverage", "platforms", "thresholds"]
        },
        "platform_trends": {
            "type": "object"
        },
        "computed_weights": {
            "type": "object",
            "properties": {
                "backend": {"type": "number"},
                "frontend": {"type": "number"},
                "mobile": {"type": "number"},
                "desktop": {"type": "number"}
            }
        }
    }
}


def load_trending_data(trend_file: Path) -> Dict:
    """
    Load trending data from cross_platform_trend.json.

    Validates structure and initializes empty structure if file doesn't exist.

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
        logger.warning(f"Trending file not found: {trend_file}, initializing empty structure")
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


def validate_trend_data(trending_data: Dict) -> bool:
    """
    Validate trending data structure using jsonschema.

    Args:
        trending_data: Trending data dict to validate

    Returns:
        True if valid, False if validation fails
    """
    try:
        from jsonschema import validate, ValidationError

        try:
            validate(instance=trending_data, schema=TREND_DATA_SCHEMA)
            logger.info("Trending data validation: PASSED")
            return True
        except ValidationError as e:
            logger.warning(f"Trending data validation failed: {e.message}")
            logger.warning(f"Path: {' -> '.join(str(p) for p in e.path)}")
            return False

    except ImportError:
        logger.warning("jsonschema not installed, skipping validation")
        # Basic validation without jsonschema
        if "history" not in trending_data:
            logger.error("Missing 'history' key in trending data")
            return False
        if not isinstance(trending_data["history"], list):
            logger.error("'history' must be a list")
            return False
        logger.info("Basic trending data validation: PASSED")
        return True


def detect_regressions(trending_data: Dict, threshold: float = REGRESSION_THRESHOLD) -> List[Dict]:
    """
    Detect coverage regressions by comparing current vs previous coverage.

    Args:
        trending_data: Trending data dict with history
        threshold: Regression threshold in percentage points (default: 1.0)

    Returns:
        List of regression dicts with platform, current_coverage, previous_coverage,
        delta, severity, timestamps, and commit_sha
    """
    history = trending_data.get("history", [])

    if len(history) < MIN_HISTORY_ENTRIES:
        logger.info(f"Insufficient history for regression detection (need {MIN_HISTORY_ENTRIES}, have {len(history)})")
        return []

    regressions = []
    platforms = ["backend", "frontend", "mobile", "desktop"]

    # Get current and previous entries
    current_entry = history[-1]
    previous_entry = history[-2]

    for platform in platforms:
        # Get current and previous coverage
        current_coverage = current_entry.get("platforms", {}).get(platform)
        previous_coverage = previous_entry.get("platforms", {}).get(platform)

        # Skip if coverage data missing
        if current_coverage is None or previous_coverage is None:
            logger.debug(f"Skipping {platform}: missing coverage data")
            continue

        # Skip if coverage is 0% (likely failed job)
        if current_coverage == 0.0 or previous_coverage == 0.0:
            logger.warning(f"Skipping {platform}: coverage is 0% (likely failed job)")
            continue

        # Calculate delta
        delta = current_coverage - previous_coverage

        # Check if regression (negative delta exceeding threshold)
        if delta < -threshold:
            # Determine severity
            if delta < -CRITICAL_THRESHOLD:
                severity = "critical"
            else:
                severity = "warning"

            regression = {
                "platform": platform,
                "current_coverage": round(current_coverage, 2),
                "previous_coverage": round(previous_coverage, 2),
                "delta": round(delta, 2),
                "severity": severity,
                "timestamp_current": current_entry.get("timestamp", ""),
                "timestamp_previous": previous_entry.get("timestamp", ""),
                "commit_sha": current_entry.get("commit_sha", ""),
                "branch": current_entry.get("branch", ""),
                "detected_at": datetime.now().isoformat() + "Z"
            }

            regressions.append(regression)
            logger.info(f"Regression detected: {platform} {previous_coverage:.2f}% -> {current_coverage:.2f}% ({delta:+.2f}%, {severity})")

    return regressions


def calculate_moving_average(trending_data: Dict, platform: str, periods: int = 3) -> Optional[float]:
    """
    Calculate moving average for a platform over N periods.

    Args:
        trending_data: Trending data dict with history
        platform: Platform name (backend, frontend, mobile, desktop)
        periods: Number of periods for moving average (default: 3)

    Returns:
        Moving average as float, or None if insufficient history
    """
    history = trending_data.get("history", [])

    if len(history) < periods:
        return None

    # Get last N entries
    recent_entries = history[-periods:]

    # Calculate average
    total = 0.0
    count = 0

    for entry in recent_entries:
        coverage = entry.get("platforms", {}).get(platform)
        if coverage is not None and coverage > 0:
            total += coverage
            count += 1

    if count == 0:
        return None

    return round(total / count, 2)


def analyze_trends(trending_data: Dict, periods: int = 7) -> Dict:
    """
    Analyze coverage trends with moving averages and trend identification.

    Args:
        trending_data: Trending data dict with history
        periods: Number of periods for trend comparison (default: 7)

    Returns:
        Dict with platform_trends, regression_count, improvement_count
    """
    history = trending_data.get("history", [])

    if len(history) < MIN_HISTORY_ENTRIES:
        return {
            "platform_trends": {},
            "regression_count": 0,
            "improvement_count": 0
        }

    platforms = ["backend", "frontend", "mobile", "desktop"]
    platform_trends = {}
    regression_count = 0
    improvement_count = 0

    for platform in platforms:
        # Get trend delta from existing function
        delta_info = compute_trend_delta(trending_data, platform, periods=periods)

        if delta_info is None:
            continue

        # Calculate moving average
        moving_avg = calculate_moving_average(trending_data, platform, periods=3)

        # Determine trend classification
        if delta_info.delta > 1.0:
            trend_classification = "improving"
            improvement_count += 1
        elif delta_info.delta < -1.0:
            trend_classification = "declining"
            regression_count += 1
        else:
            trend_classification = "stable"

        platform_trends[platform] = {
            "trend": delta_info.trend,
            "delta": delta_info.delta,
            "current": delta_info.current,
            "previous": delta_info.previous,
            "moving_avg": moving_avg,
            "classification": trend_classification
        }

    return {
        "platform_trends": platform_trends,
        "regression_count": regression_count,
        "improvement_count": improvement_count
    }


def log_regressions(regressions: List[Dict], output_file: Path) -> None:
    """
    Log regressions to coverage_regressions.json with retention pruning.

    Args:
        regressions: List of regression dicts
        output_file: Path to coverage_regressions.json
    """
    # Create output directory if needed
    output_file.parent.mkdir(parents=True, exist_ok=True)

    # Load existing regressions
    existing_data = {
        "regressions": [],
        "metadata": {
            "created_at": datetime.now().isoformat() + "Z",
            "regression_threshold": REGRESSION_THRESHOLD,
            "retention_days": REGRESSION_RETENTION_DAYS
        }
    }

    if output_file.exists():
        try:
            with open(output_file, 'r') as f:
                existing_data = json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            logger.warning(f"Error loading existing regressions: {e}, creating new file")

    # Append new regressions
    existing_data["regressions"].extend(regressions)

    # Prune old entries (older than RETENTION_DAYS)
    cutoff_time = datetime.now() - timedelta(days=REGRESSION_RETENTION_DAYS)
    pruned_regressions = []

    for regression in existing_data["regressions"]:
        try:
            detected_at = regression.get("detected_at", "")
            if detected_at:
                # Parse timestamp
                ts = detected_at.replace("Z", "").replace("+00:00", "")
                regression_time = datetime.fromisoformat(ts)

                if regression_time >= cutoff_time:
                    pruned_regressions.append(regression)
            else:
                # Keep entries without timestamp
                pruned_regressions.append(regression)
        except (ValueError, KeyError):
            # Keep entries with invalid timestamps
            pruned_regressions.append(regression)

    existing_data["regressions"] = pruned_regressions

    # Write updated regressions
    with open(output_file, 'w') as f:
        json.dump(existing_data, f, indent=2)

    logger.info(f"Logged {len(regressions)} regressions to {output_file}")
    logger.info(f"Total regressions in file: {len(existing_data['regressions'])} (pruned to {REGRESSION_RETENTION_DAYS} days)")


def generate_text_report(regressions: List[Dict], trends: Dict) -> str:
    """
    Generate human-readable text report.

    Args:
        regressions: List of regression dicts
        trends: Trend analysis dict

    Returns:
        Formatted text report
    """
    lines = []
    lines.append("=" * 70)
    lines.append("Coverage Trend Analysis Report")
    lines.append("=" * 70)
    lines.append("")

    # Regression count
    if regressions:
        lines.append(f"Regressions Detected: {len(regressions)}")
        lines.append("")

        # Severity breakdown
        critical_count = sum(1 for r in regressions if r["severity"] == "critical")
        warning_count = sum(1 for r in regressions if r["severity"] == "warning")

        lines.append(f"  Critical: {critical_count}")
        lines.append(f"  Warning:  {warning_count}")
        lines.append("")

        # Platform breakdown
        lines.append("Affected Platforms:")
        for regression in regressions:
            platform = regression["platform"].capitalize()
            current = regression["current_coverage"]
            previous = regression["previous_coverage"]
            delta = regression["delta"]
            severity = regression["severity"].upper()

            lines.append(f"  {platform}: {previous:.2f}% -> {current:.2f}% ({delta:+.2f}%, {severity})")

        lines.append("")
    else:
        lines.append("No Regressions Detected")
        lines.append("")

    # Platform trends
    platform_trends = trends.get("platform_trends", {})
    if platform_trends:
        lines.append("Platform Trends:")
        for platform, trend_info in platform_trends.items():
            classification = trend_info.get("classification", "stable").capitalize()
            delta = trend_info.get("delta", 0.0)
            moving_avg = trend_info.get("moving_avg")

            sign = "+" if delta > 0 else ""
            moving_avg_str = f", MA: {moving_avg:.2f}%" if moving_avg else ""
            lines.append(f"  {platform.capitalize():10s}: {classification} ({sign}{delta:.2f}%{moving_avg_str})")

        lines.append("")

    # Summary
    regression_count = trends.get("regression_count", 0)
    improvement_count = trends.get("improvement_count", 0)

    lines.append(f"Summary: {improvement_count} improving, {regression_count} declining")
    lines.append("=" * 70)

    return "\n".join(lines)


def generate_json_report(regressions: List[Dict], trends: Dict) -> str:
    """
    Generate machine-readable JSON report.

    Args:
        regressions: List of regression dicts
        trends: Trend analysis dict

    Returns:
        JSON string
    """
    report = {
        "regressions": regressions,
        "trends": trends,
        "generated_at": datetime.now().isoformat() + "Z"
    }

    return json.dumps(report, indent=2)


def generate_markdown_report(regressions: List[Dict], trends: Dict) -> str:
    """
    Generate markdown report (PR comment format).

    Args:
        regressions: List of regression dicts
        trends: Trend analysis dict

    Returns:
        Formatted markdown report
    """
    lines = []
    lines.append("### Coverage Trend Analysis")
    lines.append("")

    # Regressions section
    if regressions:
        lines.append("#### Regressions Detected")
        lines.append("")
        lines.append("| Platform | Previous | Current | Delta | Severity |")
        lines.append("|----------|----------|---------|-------|----------|")

        for regression in regressions:
            platform = regression["platform"].capitalize()
            previous = regression["previous_coverage"]
            current = regression["current_coverage"]
            delta = regression["delta"]
            severity = regression["severity"].capitalize()

            sign = "+" if delta > 0 else ""
            lines.append(f"| {platform} | {previous:.2f}% | {current:.2f}% | {sign}{delta:.2f}% | {severity} |")

        lines.append("")
    else:
        lines.append("**No regressions detected**")
        lines.append("")

    # Platform trends section
    platform_trends = trends.get("platform_trends", {})
    if platform_trends:
        lines.append("#### Platform Trends")
        lines.append("")
        lines.append("| Platform | Classification | Delta | Moving Avg |")
        lines.append("|----------|----------------|-------|------------|")

        for platform, trend_info in platform_trends.items():
            classification = trend_info.get("classification", "stable").capitalize()
            delta = trend_info.get("delta", 0.0)
            moving_avg = trend_info.get("moving_avg")

            # Add trend indicator
            if delta > 1.0:
                indicator = "↑"
            elif delta < -1.0:
                indicator = "↓"
            else:
                indicator = "→"

            sign = "+" if delta > 0 else ""
            moving_avg_str = f"{moving_avg:.2f}%" if moving_avg else "N/A"

            lines.append(f"| {platform.capitalize()} | {indicator} {classification} | {sign}{delta:.2f}% | {moving_avg_str} |")

        lines.append("")

    # Summary
    regression_count = trends.get("regression_count", 0)
    improvement_count = trends.get("improvement_count", 0)

    lines.append(f"**Summary:** {improvement_count} platforms improving, {regression_count} platforms declining")
    lines.append("")

    return "\n".join(lines)


def main():
    """Main execution function."""
    parser = argparse.ArgumentParser(
        description="Coverage trend analyzer with regression detection"
    )

    parser.add_argument(
        "--trending-file",
        type=Path,
        default=TREND_FILE,
        help="Path to cross_platform_trend.json"
    )

    parser.add_argument(
        "--regression-threshold",
        type=float,
        default=REGRESSION_THRESHOLD,
        help="Regression threshold in percentage points (default: 1.0)"
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=REGRESSION_OUTPUT,
        help="Path to coverage_regressions.json"
    )

    parser.add_argument(
        "--periods",
        type=int,
        default=7,
        help="Number of periods to compare for trend (default: 7)"
    )

    parser.add_argument(
        "--format",
        type=str,
        choices=["text", "json", "markdown"],
        default="text",
        help="Output format"
    )

    args = parser.parse_args()

    # Load trending data
    logger.info(f"Loading trending data from: {args.trending_file}")
    trending_data = load_trending_data(args.trending_file)

    # Validate data structure
    logger.info("Validating trending data structure...")
    is_valid = validate_trend_data(trending_data)

    if not is_valid:
        logger.warning("Trending data validation failed, proceeding with caution")

    # Detect regressions
    logger.info(f"Detecting regressions (threshold: {args.regression_threshold}%)...")
    regressions = detect_regressions(trending_data, threshold=args.regression_threshold)

    # Analyze trends
    logger.info(f"Analyzing trends ({args.periods} periods)...")
    trends = analyze_trends(trending_data, periods=args.periods)

    # Log regressions
    if regressions:
        logger.info(f"Logging {len(regressions)} regressions to: {args.output}")
        log_regressions(regressions, args.output)

    # Generate report
    logger.info(f"Generating report (format: {args.format})...")

    if args.format == "text":
        report = generate_text_report(regressions, trends)
    elif args.format == "json":
        report = generate_json_report(regressions, trends)
    elif args.format == "markdown":
        report = generate_markdown_report(regressions, trends)
    else:
        logger.error(f"Unknown format: {args.format}")
        return 1

    print("")
    print(report)

    # Exit with error if critical regressions detected
    critical_count = sum(1 for r in regressions if r["severity"] == "critical")
    if critical_count > 0:
        logger.error(f"Critical regressions detected: {critical_count}")
        return 1

    return 0


if __name__ == "__main__":
    sys.exit(main())
