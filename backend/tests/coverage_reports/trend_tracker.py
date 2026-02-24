#!/usr/bin/env python3
"""
Coverage Trend Tracking Script

Tracks coverage over time, detects regressions, and establishes baselines for milestones.
Used by CI/CD to monitor coverage health and alert on regressions.

Usage:
    python trend_tracker.py <phase> <plan>
    python -c "from trend_tracker import detect_regression; print(detect_regression('path/to/trending.json'))"
    python -c "from trend_tracker import establish_baseline; print(establish_baseline('path/to/trending.json', '81', 'v3.2'))"
"""

import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, Any, List


def update_trending(
    coverage_json_path: str,
    trending_json_path: str,
    phase: str,
    plan: str
) -> Dict[str, Any]:
    """
    Append current coverage to trending.json.

    Args:
        coverage_json_path: Path to coverage.json output from pytest-cov
        trending_json_path: Path to trending.json file (created if doesn't exist)
        phase: Current phase number (e.g., "81")
        plan: Current plan number (e.g., "04")

    Returns:
        Updated trending data dictionary
    """
    # Load current coverage
    with open(coverage_json_path) as f:
        coverage_data = json.load(f)

    current_coverage = coverage_data["totals"]["percent_covered"]
    lines_covered = coverage_data["totals"]["covered_lines"]
    lines_total = coverage_data["totals"]["num_statements"]

    # Load existing trending data
    try:
        with open(trending_json_path) as f:
            existing_data = json.load(f)

        # Check if it's the old format (has "phases" array)
        if "phases" in existing_data:
            # Migrate old format to new format
            history = []
            for phase_entry in existing_data["phases"]:
                data_point = {
                    "date": phase_entry.get("date"),
                    "phase": phase_entry.get("phase", "").split("-")[0] if phase_entry.get("phase") else "",
                    "plan": phase_entry.get("plan", ""),
                    "coverage_pct": phase_entry.get("coverage", 0),
                    "lines_covered": phase_entry.get("lines_covered", 0),
                    "lines_total": phase_entry.get("lines_total", 0),
                    "trend": "stable"
                }
                history.append(data_point)

            trending = {
                "history": history,
                "baselines": {},
                "migrated_from": "phases_format"
            }
        elif "history" in existing_data:
            # Already in new format
            trending = existing_data
        else:
            # Unknown format, initialize new
            trending = {
                "history": [],
                "baselines": {}
            }
    except FileNotFoundError:
        # Initialize new trending structure
        trending = {
            "history": [],
            "baselines": {}
        }

    # Calculate trend (vs previous data point)
    trend = "stable"
    if trending.get("history"):
        previous_coverage = trending["history"][-1]["coverage_pct"]
        diff = current_coverage - previous_coverage
        if diff > 1.0:
            trend = "improving"
        elif diff < -1.0:
            trend = "regressing"

    # Append new data point
    data_point = {
        "date": datetime.now().isoformat(),
        "phase": phase,
        "plan": plan,
        "coverage_pct": round(current_coverage, 2),
        "lines_covered": lines_covered,
        "lines_total": lines_total,
        "trend": trend,
    }
    trending["history"].append(data_point)
    trending["latest"] = data_point

    # Ensure history is sorted by date
    trending["history"].sort(key=lambda x: x["date"])

    # Save updated trending.json
    with open(trending_json_path, 'w') as f:
        json.dump(trending, f, indent=2)

    return trending


def detect_regression(
    trending_json_path: str,
    threshold: float = -1.0
) -> Dict[str, Any]:
    """
    Check if coverage has regressed beyond threshold.

    Args:
        trending_json_path: Path to trending.json file
        threshold: Maximum allowed decrease (default: -1.0 for 1% decrease)

    Returns:
        Dictionary with regression status, message, and details
    """
    with open(trending_json_path) as f:
        trending = json.load(f)

    if len(trending.get("history", [])) < 2:
        return {
            "regression": False,
            "message": "Insufficient data for regression detection (need 2+ data points)"
        }

    latest = trending["history"][-1]
    previous = trending["history"][-2]

    diff = latest["coverage_pct"] - previous["coverage_pct"]

    if diff < threshold:
        return {
            "regression": True,
            "message": f"Coverage decreased by {abs(diff):.2f}%",
            "from": previous["coverage_pct"],
            "to": latest["coverage_pct"],
            "threshold": threshold
        }
    else:
        return {
            "regression": False,
            "message": f"Coverage stable or improving ({diff:+.2f}%)",
            "from": previous["coverage_pct"],
            "to": latest["coverage_pct"]
        }


def establish_baseline(
    trending_json_path: str,
    phase: str = "81",
    baseline_name: str = "v3.2"
) -> Dict[str, Any]:
    """
    Mark current coverage as baseline for milestone.

    Args:
        trending_json_path: Path to trending.json file
        phase: Phase number for baseline (e.g., "81")
        baseline_name: Name of baseline (e.g., "v3.2")

    Returns:
        Baseline dictionary with coverage metrics
    """
    with open(trending_json_path) as f:
        trending = json.load(f)

    if not trending.get("latest"):
        raise ValueError("No coverage data available in trending.json. Run update_trending first.")

    baseline = {
        "name": baseline_name,
        "phase": phase,
        "date": trending["latest"]["date"],
        "coverage_pct": trending["latest"]["coverage_pct"],
        "lines_covered": trending["latest"]["lines_covered"],
        "lines_total": trending["latest"]["lines_total"],
    }

    trending.setdefault("baselines", {})[baseline_name] = baseline

    with open(trending_json_path, 'w') as f:
        json.dump(trending, f, indent=2)

    return baseline


def get_trend_summary(trending_json_path: str) -> Dict[str, Any]:
    """
    Get summary of coverage trends and baselines.

    Args:
        trending_json_path: Path to trending.json file

    Returns:
        Summary dictionary with trend statistics
    """
    with open(trending_json_path) as f:
        trending = json.load(f)

    history = trending.get("history", [])
    baselines = trending.get("baselines", {})

    if not history:
        return {
            "total_data_points": 0,
            "latest_coverage": None,
            "oldest_coverage": None,
            "overall_change": None,
            "baselines_count": len(baselines)
        }

    latest = history[-1]
    oldest = history[0]
    overall_change = latest["coverage_pct"] - oldest["coverage_pct"]

    return {
        "total_data_points": len(history),
        "latest_coverage": latest["coverage_pct"],
        "oldest_coverage": oldest["coverage_pct"],
        "overall_change": round(overall_change, 2),
        "latest_trend": latest.get("trend", "unknown"),
        "baselines_count": len(baselines),
        "baseline_names": list(baselines.keys())
    }


if __name__ == "__main__":
    # CLI entry point
    phase = sys.argv[1] if len(sys.argv) > 1 else "81"
    plan = sys.argv[2] if len(sys.argv) > 2 else "04"

    # Default paths (relative to script location)
    script_dir = Path(__file__).parent
    coverage_json = script_dir / "metrics" / "coverage.json"
    trending_json = script_dir / "metrics" / "trending.json"

    if not coverage_json.exists():
        print(f"ERROR: Coverage file not found: {coverage_json}")
        print("Run pytest with coverage first: pytest --cov=core --cov=api --cov=tools --cov-report=json")
        sys.exit(1)

    # Update trending data
    trending = update_trending(
        str(coverage_json),
        str(trending_json),
        phase,
        plan
    )

    # Check for regression
    regression = detect_regression(str(trending_json))

    # Get trend summary
    summary = get_trend_summary(str(trending_json))

    # Print results
    print(f"Coverage: {trending['latest']['coverage_pct']}% "
          f"({trending['latest']['lines_covered']:,}/{trending['latest']['lines_total']:,} lines)")
    print(f"Trend: {trending['latest']['trend']}")
    print(f"Regression: {regression['regression']}")
    print(f"Message: {regression['message']}")
    print(f"\nSummary: {summary['total_data_points']} data points, "
          f"{summary['baselines_count']} baseline(s)")

    # Exit with error code if regression detected
    if regression['regression']:
        sys.exit(1)
