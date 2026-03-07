#!/usr/bin/env python3
"""
E2E Test Results Aggregator

Combines E2E test results from web (Playwright pytest), mobile (API-level pytest),
and desktop (Tauri cargo test) platforms into a unified report.

Usage:
    python e2e_aggregator.py --web results/web.json \
                             --mobile results/mobile.json \
                             --desktop results/desktop.json \
                             --output results/e2e_unified.json
"""
import argparse
import json
import os
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def parse_cargo_json_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single line of cargo test JSON output.

    Args:
        line: Single line from cargo test --format json output

    Returns:
        Parsed test dict if line is a test result, None otherwise
    """
    try:
        data = json.loads(line.strip())
        if data.get("type") == "test":
            return {
                "name": data.get("name", "unknown"),
                "passed": data.get("passed", False),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def extract_tauri_metrics(results: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """Extract metrics from Tauri cargo test JSON format.

    Args:
        results: Test results dict (may have stats from pre-processing or raw cargo data)
        platform: Platform name (desktop)

    Returns:
        Metrics dict matching Playwright pytest format
    """
    # If results already have stats key (pre-processed by CI), use that
    if "stats" in results:
        return {
            "platform": platform,
            "total": results["stats"].get("total", 0),
            "passed": results["stats"].get("passed", 0),
            "failed": results["stats"].get("failed", 0),
            "skipped": results["stats"].get("skipped", 0),
            "duration": results["stats"].get("duration", 0),
        }

    # Parse raw cargo test results
    if "testResults" in results:
        test_results = results.get("testResults", [])
        total = len(test_results)
        passed = sum(1 for r in test_results if r.get("passed", False))
        return {
            "platform": platform,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "skipped": 0,
            "duration": results.get("duration", 0),
        }

    # Unknown Tauri format
    return {
        "platform": platform,
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "error": "Unknown Tauri format",
    }


def extract_metrics(results: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """Extract key metrics from platform-specific results.

    Args:
        results: Platform-specific test results dict
        platform: Platform name (web, mobile, desktop)

    Returns:
        Metrics dict with total/passed/failed/skipped/duration fields
    """
    # Check for errors first
    if "error" in results:
        return {
            "platform": platform,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "error": results["error"],
        }

    # Playwright pytest format (used by both web E2E and mobile API tests)
    if "stats" in results:
        return {
            "platform": platform,
            "total": results["stats"].get("total", 0),
            "passed": results["stats"].get("passed", 0),
            "failed": results["stats"].get("failed", 0),
            "skipped": results["stats"].get("skipped", 0),
            "duration": results["stats"].get("duration", 0),
        }

    # Tauri cargo test format (desktop)
    # Note: Mobile API tests use pytest (same as Playwright), no separate Detox parser needed
    if "testResults" in results or "test_suites" in results:
        return extract_tauri_metrics(results, platform)

    # Unknown format
    return {
        "platform": platform,
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "error": f"Unknown format for {platform}: missing stats or testResults keys",
    }


def calculate_aggregate_metrics(platform_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics across all platforms."""
    total_tests = sum(m.get("total", 0) for m in platform_metrics)
    total_passed = sum(m.get("passed", 0) for m in platform_metrics)
    total_failed = sum(m.get("failed", 0) for m in platform_metrics)
    total_duration = sum(m.get("duration", 0) for m in platform_metrics)

    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(pass_rate, 2),
        "total_duration_seconds": total_duration,
        "platforms": len(platform_metrics),
    }


def load_trend_history(trend_file: str) -> List[Dict[str, Any]]:
    """Load historical trend data from JSON file.

    Args:
        trend_file: Path to trend JSON file

    Returns:
        List of historical entries (newest first), empty list if file doesn't exist
    """
    path = Path(trend_file)
    if not path.exists():
        return []

    try:
        history = json.loads(path.read_text())
        # Ensure sorted by timestamp descending (newest first)
        history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)
        return history
    except (json.JSONDecodeError, KeyError):
        return []


def save_trend_history(trend_file: str, history: List[Dict[str, Any]]) -> None:
    """Save historical trend data to JSON file.

    Args:
        trend_file: Path to trend JSON file
        history: List of historical entries to save
    """
    # Create directory if not exists
    Path(trend_file).parent.mkdir(parents=True, exist_ok=True)

    # Sort by timestamp descending before saving
    history.sort(key=lambda x: x.get("timestamp", ""), reverse=True)

    # Write to file
    Path(trend_file).write_text(json.dumps(history, indent=2))


def append_to_history(
    trend_file: str,
    aggregate: Dict[str, Any],
    platform_metrics: List[Dict[str, Any]],
    retention_days: int = 90,
) -> List[Dict[str, Any]]:
    """Append current run to history and enforce retention period.

    Args:
        trend_file: Path to trend JSON file
        aggregate: Current aggregate metrics
        platform_metrics: Current platform metrics
        retention_days: Number of days to keep history (default 90)

    Returns:
        Updated history list
    """
    # Load existing history
    history = load_trend_history(trend_file)

    # Create current run entry
    current_run = {
        "timestamp": datetime.now().isoformat(),
        "aggregate": {
            "total_tests": aggregate.get("total_tests", 0),
            "total_passed": aggregate.get("total_passed", 0),
            "total_failed": aggregate.get("total_failed", 0),
            "pass_rate": aggregate.get("pass_rate", 0),
        },
        "platforms": [
            {
                "platform": p.get("platform", "unknown"),
                "total": p.get("total", 0),
                "passed": p.get("passed", 0),
                "failed": p.get("failed", 0),
                "duration": p.get("duration", 0),
            }
            for p in platform_metrics
        ],
    }

    # Append to history
    history.append(current_run)

    # Enforce retention period (remove entries older than retention_days)
    cutoff_date = datetime.now() - timedelta(days=retention_days)
    history = [
        entry
        for entry in history
        if datetime.fromisoformat(entry["timestamp"]) > cutoff_date
    ]

    # Save updated history
    save_trend_history(trend_file, history)

    return history


def calculate_trend_metrics(
    aggregate: Dict[str, Any],
    platform_metrics: List[Dict[str, Any]],
    history: List[Dict[str, Any]],
) -> Dict[str, Any]:
    """Calculate trend metrics comparing current run to previous run.

    Args:
        aggregate: Current aggregate metrics
        platform_metrics: Current platform metrics
        history: Historical trend data

    Returns:
        Trend metrics dict with pass_rate_delta, test_count_delta, declining_platforms
    """
    if not history or len(history) < 2:
        return {
            "pass_rate_delta": 0,
            "test_count_delta": 0,
            "declining_platforms": [],
        }

    # Get previous run (second entry since history is sorted newest first)
    previous_run = history[1]
    previous_pass_rate = previous_run["aggregate"].get("pass_rate", 0)
    previous_test_count = previous_run["aggregate"].get("total_tests", 0)

    # Calculate pass rate delta
    current_pass_rate = aggregate.get("pass_rate", 0)
    pass_rate_delta = current_pass_rate - previous_pass_rate

    # Calculate test count delta
    current_test_count = aggregate.get("total_tests", 0)
    test_count_delta = current_test_count - previous_test_count

    # Identify platforms with declining pass rates (>5% decline)
    declining_platforms = []
    previous_platforms = {
        p["platform"]: p for p in previous_run.get("platforms", [])
    }

    for current_platform in platform_metrics:
        platform_name = current_platform.get("platform", "unknown")
        if platform_name in previous_platforms:
            prev_platform = previous_platforms[platform_name]
            prev_pass_rate = (
                (prev_platform["passed"] / prev_platform["total"] * 100)
                if prev_platform["total"] > 0
                else 0
            )
            curr_pass_rate = (
                (current_platform["passed"] / current_platform["total"] * 100)
                if current_platform["total"] > 0
                else 0
            )

            delta = curr_pass_rate - prev_pass_rate
            if delta < -5.0:  # More than 5% decline
                declining_platforms.append({
                    "platform": platform_name.upper(),
                    "delta": delta,
                })

    return {
        "pass_rate_delta": round(pass_rate_delta, 2),
        "test_count_delta": test_count_delta,
        "declining_platforms": declining_platforms,
    }


def generate_summary(
    aggregate: Dict[str, Any],
    platform_metrics: List[Dict[str, Any]],
    trend_metrics: Optional[Dict[str, Any]] = None,
) -> str:
    """Generate human-readable summary.

    Args:
        aggregate: Aggregate metrics across all platforms
        platform_metrics: List of per-platform metrics
        trend_metrics: Optional trend analysis (pass rate change, test count change)

    Returns:
        Markdown summary string
    """
    lines = [
        "# E2E Test Results Summary",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Aggregate Results",
        f"- Total Tests: {aggregate['total_tests']}",
        f"- Passed: {aggregate['total_passed']}",
        f"- Failed: {aggregate['total_failed']}",
        f"- Pass Rate: {aggregate['pass_rate']}%",
        f"- Duration: {aggregate['total_duration_seconds']}s",
        "",
        "## Platform Breakdown",
    ]

    for metrics in platform_metrics:
        platform = metrics["platform"].upper()
        lines.append(f"### {platform}")
        lines.append(f"- Tests: {metrics['total']}")
        lines.append(f"- Passed: {metrics['passed']}")
        lines.append(f"- Failed: {metrics['failed']}")
        lines.append(f"- Duration: {metrics['duration']}s")
        lines.append("")

    # Add trend analysis if available
    if trend_metrics:
        lines.append("## Trend Analysis")

        # Pass rate change
        pass_rate_delta = trend_metrics.get("pass_rate_delta", 0)
        delta_indicator = "↑" if pass_rate_delta > 0 else "↓" if pass_rate_delta < 0 else "→"
        lines.append(f"- Pass Rate Change: {delta_indicator} {abs(pass_rate_delta):.2f}% vs previous run")

        # Test count change
        test_count_delta = trend_metrics.get("test_count_delta", 0)
        if test_count_delta > 0:
            lines.append(f"- Test Count: +{test_count_delta} tests added")
        elif test_count_delta < 0:
            lines.append(f"- Test Count: {test_count_delta} tests removed")
        else:
            lines.append("- Test Count: No change")

        # Platform-specific trends
        declining_platforms = trend_metrics.get("declining_platforms", [])
        if declining_platforms:
            lines.append("- Platforms with Declining Pass Rates:")
            for platform in declining_platforms:
                lines.append(f"  - {platform['platform']}: {platform['delta']:.2f}% decline")
        else:
            lines.append("- All platforms stable or improving")

        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(
        description="Aggregate E2E test results across platforms"
    )
    parser.add_argument("--web", help="Web platform results JSON")
    parser.add_argument("--mobile", help="Mobile platform results JSON")
    parser.add_argument("--desktop", help="Desktop platform results JSON")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--summary", help="Output summary markdown file")
    parser.add_argument(
        "--trend-file",
        default="backend/tests/coverage_reports/metrics/e2e_trend.json",
        help="Path to trend history JSON file (default: backend/tests/coverage_reports/metrics/e2e_trend.json)",
    )
    args = parser.parse_args()

    platform_metrics = []

    # Load and extract metrics from each platform
    if args.web:
        web_results = load_json(args.web)
        platform_metrics.append(extract_metrics(web_results, "web"))

    if args.mobile:
        mobile_results = load_json(args.mobile)
        platform_metrics.append(extract_metrics(mobile_results, "mobile"))

    if args.desktop:
        desktop_results = load_json(args.desktop)
        platform_metrics.append(extract_metrics(desktop_results, "desktop"))

    # Calculate aggregate metrics
    aggregate = calculate_aggregate_metrics(platform_metrics)

    # Append to trend history
    retention_days = int(os.getenv("E2E_TREND_DAYS", "90"))
    history = append_to_history(
        args.trend_file, aggregate, platform_metrics, retention_days
    )

    # Calculate trend metrics
    trend_metrics = calculate_trend_metrics(aggregate, platform_metrics, history)

    # Prepare output
    output = {
        "timestamp": datetime.now().isoformat(),
        "aggregate": aggregate,
        "platforms": platform_metrics,
        "trend": trend_metrics,
    }

    # Write JSON output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2))

    # Write summary markdown with trend analysis
    if args.summary:
        summary = generate_summary(aggregate, platform_metrics, trend_metrics)
        Path(args.summary).write_text(summary)

    print(f"E2E results aggregated to {args.output}")
    print(f"Aggregate: {aggregate['total_passed']}/{aggregate['total_tests']} passed ({aggregate['pass_rate']}%)")

    # Exit codes: 0 = success, 1 = test failures, 2 = trend decline
    if aggregate["total_failed"] > 0:
        sys.exit(1)

    # Warn about declining pass rates (>5% decline)
    if trend_metrics.get("pass_rate_delta", 0) < -5.0:
        print(f"WARNING: Pass rate declined by {abs(trend_metrics['pass_rate_delta']):.2f}%")
        sys.exit(2)


if __name__ == "__main__":
    main()
