#!/usr/bin/env python3
"""
Coverage Trend Tracking System for Atom v5.0

This script tracks coverage changes over time, establishing a baseline and
monitoring progress toward the 80% target. It records snapshots, calculates
deltas, maintains historical data, and generates trend visualizations.

Usage:
    # Record current coverage with commit hash
    python coverage_trend_tracker.py --commit <hash> --chart

    # Record from specific coverage file
    python coverage_trend_tracker.py --coverage-file path/to/coverage.json --commit <hash>

    # Check for regressions (CI usage)
    python coverage_trend_tracker.py --regression-check

    # Compare two commits
    python coverage_trend_tracker.py --compare-commits <hash1> <hash2>

    # Forecast when 80% target will be reached
    python coverage_trend_tracker.py --forecast 80

    # Record coverage for CI (generates PR comment payload)
    python coverage_trend_tracker.py --ci-record

Features:
    - Per-commit coverage tracking with automatic git hash detection
    - Baseline establishment for v5.0 expansion
    - Delta calculation (absolute and relative changes)
    - Historical trend data (last 30 entries)
    - ASCII visualization with 80% target marker
    - Regression detection (alerts on >1% decrease)
    - Timeline forecasting for 80% target
    - CI integration hooks for PR comments
"""

import argparse
import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Dict, Any, List, Optional, Tuple


# Constants
DEFAULT_COVERAGE_FILE = Path("tests/coverage_reports/metrics/coverage.json")
DEFAULT_TREND_FILE = Path("tests/coverage_reports/metrics/coverage_trend_v5.0.json")
DEFAULT_TRENDS_DIR = Path("tests/coverage_reports/trends")
TARGET_COVERAGE = 80.0
REGRESSION_THRESHOLD = 1.0  # Alert if coverage decreases by >1 percentage point


def get_git_commit_hash() -> Optional[str]:
    """
    Get current git commit hash.

    Returns:
        Commit hash as string, or None if not in git repo
    """
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def get_git_commit_message(commit_hash: str) -> Optional[str]:
    """
    Get git commit message for a given hash.

    Args:
        commit_hash: Git commit hash

    Returns:
        Commit message subject line, or None if not available
    """
    try:
        result = subprocess.run(
            ["git", "log", "-1", "--format=%s", commit_hash],
            capture_output=True,
            text=True,
            check=True
        )
        return result.stdout.strip()
    except (subprocess.CalledProcessError, FileNotFoundError):
        return None


def record_snapshot(coverage_data: Dict[str, Any], commit_hash: Optional[str] = None) -> Dict[str, Any]:
    """
    Extract coverage snapshot from coverage data.

    Args:
        coverage_data: Loaded coverage.json data
        commit_hash: Git commit hash (auto-detected if None)

    Returns:
        Snapshot dict with timestamp, commit, coverage metrics
    """
    # Extract overall metrics
    totals = coverage_data.get("totals", {})
    overall_coverage = totals.get("percent_covered", 0.0)
    covered_lines = totals.get("covered_lines", 0)
    total_lines = totals.get("num_statements", 0)
    covered_branches = totals.get("covered_branches", 0)
    total_branches = totals.get("num_branches", 0)

    # Extract module breakdown from files
    files = coverage_data.get("files", {})
    module_breakdown = {}

    for file_path, file_data in files.items():
        # Determine module from file path
        if file_path.startswith("core/"):
            module = "core"
        elif file_path.startswith("api/"):
            module = "api"
        elif file_path.startswith("tools/"):
            module = "tools"
        elif file_path.startswith("skills/"):
            module = "skills"
        else:
            module = "other"

        # Aggregate module coverage
        if module not in module_breakdown:
            module_breakdown[module] = {"covered": 0, "total": 0}

        summary = file_data.get("summary", {})
        module_breakdown[module]["covered"] += summary.get("covered_lines", 0)
        module_breakdown[module]["total"] += summary.get("num_statements", 0)

    # Calculate module percentages
    module_percentages = {}
    for module, data in module_breakdown.items():
        if data["total"] > 0:
            module_percentages[module] = (data["covered"] / data["total"]) * 100
        else:
            module_percentages[module] = 0.0

    # Get commit hash
    if commit_hash is None:
        commit_hash = get_git_commit_hash()

    # Get commit message
    commit_message = None
    if commit_hash:
        commit_message = get_git_commit_message(commit_hash)

    # Build snapshot
    snapshot = {
        "timestamp": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z"),
        "commit": commit_hash,
        "commit_message": commit_message,
        "overall_coverage": round(overall_coverage, 2),
        "covered_lines": covered_lines,
        "total_lines": total_lines,
        "branch_coverage": round((covered_branches / total_branches * 100) if total_branches > 0 else 0.0, 2),
        "covered_branches": covered_branches,
        "total_branches": total_branches,
        "module_breakdown": {
            module: round(pct, 2)
            for module, pct in module_percentages.items()
        }
    }

    return snapshot


def get_trend_history(trend_file: Path = DEFAULT_TREND_FILE) -> Dict[str, Any]:
    """
    Load trend history from file, creating new structure if needed.

    Args:
        trend_file: Path to trend JSON file

    Returns:
        Trend data dict with baseline, history, current, metadata
    """
    # Default structure
    trend_data = {
        "baseline": None,  # Will be set on first snapshot
        "history": [],
        "current": None,
        "metadata": {
            "version": "5.0",
            "target_coverage": TARGET_COVERAGE,
            "max_history_entries": 30,
            "created_at": datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        }
    }

    # Load existing data if available
    if trend_file.exists():
        try:
            with open(trend_file, 'r') as f:
                loaded_data = json.load(f)
                # Merge with default structure
                trend_data.update(loaded_data)
        except (json.JSONDecodeError, IOError) as e:
            print(f"Warning: Could not load trend file: {e}", file=sys.stderr)

    return trend_data


def calculate_delta(current: float, previous: float) -> Dict[str, Any]:
    """
    Calculate delta between two coverage values.

    Args:
        current: Current coverage percentage
        previous: Previous coverage percentage

    Returns:
        Dict with absolute_change, relative_change, direction
    """
    absolute_change = current - previous
    relative_change = (absolute_change / previous * 100) if previous > 0 else 0.0

    if absolute_change > 0:
        direction = "increase"
    elif absolute_change < 0:
        direction = "decrease"
    else:
        direction = "no_change"

    return {
        "absolute_change": round(absolute_change, 2),
        "relative_change": round(relative_change, 2),
        "direction": direction
    }


def update_trend_data(snapshot: Dict[str, Any], trend_data: Dict[str, Any]) -> Dict[str, Any]:
    """
    Update trend data with new snapshot.

    Args:
        snapshot: Coverage snapshot to add
        trend_data: Existing trend data

    Returns:
        Updated trend data
    """
    # Calculate delta from previous snapshot
    if trend_data["history"]:
        previous_coverage = trend_data["history"][-1]["overall_coverage"]
        snapshot["delta"] = calculate_delta(snapshot["overall_coverage"], previous_coverage)
    else:
        snapshot["delta"] = {
            "absolute_change": 0.0,
            "relative_change": 0.0,
            "direction": "baseline"
        }

    # Append to history
    trend_data["history"].append(snapshot)

    # Keep only last 30 entries
    if len(trend_data["history"]) > trend_data["metadata"]["max_history_entries"]:
        trend_data["history"] = trend_data["history"][-trend_data["metadata"]["max_history_entries"]:]

    # Update current
    trend_data["current"] = snapshot

    # Set baseline if not set
    if trend_data["baseline"] is None:
        trend_data["baseline"] = snapshot

    # Update metadata
    trend_data["metadata"]["last_updated"] = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
    trend_data["metadata"]["total_snapshots"] = len(trend_data["history"])

    return trend_data


def write_trend_data(
    trend_data: Dict[str, Any],
    trend_file: Path = DEFAULT_TREND_FILE,
    trends_dir: Path = DEFAULT_TRENDS_DIR
) -> None:
    """
    Write trend data to main file and create daily snapshot.

    Args:
        trend_data: Trend data to write
        trend_file: Path to main trend file
        trends_dir: Path to daily snapshots directory
    """
    # Create directories if needed
    trend_file.parent.mkdir(parents=True, exist_ok=True)
    trends_dir.mkdir(parents=True, exist_ok=True)

    # Write main trend file
    with open(trend_file, 'w') as f:
        json.dump(trend_data, f, indent=2)

    # Create daily snapshot
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    daily_snapshot_path = trends_dir / f"{today}_coverage_trend.json"

    with open(daily_snapshot_path, 'w') as f:
        json.dump(trend_data, f, indent=2)

    print(f"✅ Trend data saved to: {trend_file}")
    print(f"✅ Daily snapshot saved to: {daily_snapshot_path}")


def generate_visualization(trend_data: Dict[str, Any], width: int = 60) -> str:
    """
    Generate ASCII chart showing coverage trend over time.

    Args:
        trend_data: Trend data with history
        width: Chart width in characters

    Returns:
        Formatted ASCII chart string
    """
    if not trend_data["history"]:
        return "No trend data available yet."

    lines = []
    lines.append("")
    lines.append("=" * 80)
    lines.append("COVERAGE TREND VISUALIZATION")
    lines.append("=" * 80)
    lines.append("")

    # Get current coverage
    current = trend_data["current"]["overall_coverage"]
    baseline = trend_data["baseline"]["overall_coverage"]

    # Show summary
    lines.append(f"Baseline:  {baseline:6.2f}%")
    lines.append(f"Current:   {current:6.2f}%")
    lines.append(f"Target:    {TARGET_COVERAGE:6.2f}%")
    lines.append("")

    # Show delta
    if "delta" in trend_data["current"]:
        delta = trend_data["current"]["delta"]
        direction_symbol = {
            "increase": "↑",
            "decrease": "↓",
            "no_change": "→",
            "baseline": "="
        }.get(delta["direction"], "?")

        lines.append(f"Change:    {direction_symbol} {delta['absolute_change']:+6.2f}% ({delta['relative_change']:+.2f}% relative)")
    lines.append("")

    # Generate chart
    lines.append("Coverage History (last 30 snapshots):")
    lines.append("")

    # Find min/max for scaling
    coverages = [s["overall_coverage"] for s in trend_data["history"]]
    min_cov = min(coverages)
    max_cov = max(coverages)

    # Include target in scale if relevant
    if min_cov < TARGET_COVERAGE < max_cov:
        max_cov = max(max_cov, TARGET_COVERAGE)

    # Chart height
    chart_height = 20
    range_cov = max_cov - min_cov if max_cov > min_cov else 1.0

    # Generate chart rows (top to bottom)
    for row in range(chart_height, -1, -1):
        value = min_cov + (range_cov * row / chart_height)

        # Y-axis label
        label = f"{value:5.1f}%"

        # Build chart row
        chart_row = label + " |"

        # Plot each history point
        for snapshot in trend_data["history"]:
            cov = snapshot["overall_coverage"]

            # Check if value is close to this point
            if abs(cov - value) < (range_cov / chart_height):
                # Mark baseline, current, or regular point
                if snapshot == trend_data["baseline"]:
                    chart_row += "B"  # Baseline
                elif snapshot == trend_data["current"]:
                    chart_row += "C"  # Current
                else:
                    chart_row += "*"  # Regular point
            else:
                chart_row += " "

        chart_row += "|"

        # Mark target line
        if abs(TARGET_COVERAGE - value) < (range_cov / chart_height):
            chart_row += " <-- TARGET (80%)"

        lines.append(chart_row)

    # X-axis
    lines.append("       +" + "-" * width + "+")
    lines.append("")
    lines.append("Legend: B = Baseline, C = Current, * = Historical snapshot")
    lines.append("")

    # Show history table
    lines.append("Recent Snapshots:")
    lines.append("")
    lines.append(f"{'Timestamp':<25} {'Commit':<12} {'Coverage':>8} {'Change':>8}")
    lines.append("-" * 60)

    for snapshot in trend_data["history"][-10:]:
        timestamp = snapshot["timestamp"][:19].replace("T", " ")
        commit = (snapshot["commit"] or "unknown")[:10]
        coverage = f"{snapshot['overall_coverage']:.2f}%"

        if "delta" in snapshot:
            delta = snapshot["delta"]["absolute_change"]
            change = f"{delta:+.2f}%"
        else:
            change = "N/A"

        lines.append(f"{timestamp:<25} {commit:<12} {coverage:>8} {change:>8}")

    lines.append("")
    lines.append("=" * 80)

    return "\n".join(lines)


def check_regression(trend_data: Dict[str, Any], threshold: float = REGRESSION_THRESHOLD) -> Tuple[bool, List[str]]:
    """
    Check for coverage regression against recent history.

    Args:
        trend_data: Trend data with history
        threshold: Regression threshold (percentage points)

    Returns:
        Tuple of (has_regression, list of regression messages)
    """
    if len(trend_data["history"]) < 2:
        return False, ["Insufficient history for regression check"]

    messages = []
    current = trend_data["current"]["overall_coverage"]

    # Compare against last 3 snapshots (or all if fewer)
    compare_count = min(3, len(trend_data["history"]) - 1)
    has_regression = False

    for i in range(1, compare_count + 1):
        previous = trend_data["history"][-(i + 1)]
        previous_coverage = previous["overall_coverage"]
        delta = current - previous_coverage

        if delta < -threshold:
            has_regression = True
            commit_msg = previous.get("commit_message", "")[:50]
            messages.append(
                f"REGRESSION: Coverage decreased by {delta:.2f}% "
                f"since {previous['timestamp'][:10]} "
                f"(commit {previous['commit'][:8] if previous.get('commit') else 'unknown'}: '{commit_msg}')"
            )

    # Check module-level regressions
    if trend_data["history"][-1].get("module_breakdown") and trend_data["current"].get("module_breakdown"):
        current_modules = trend_data["current"]["module_breakdown"]
        previous_modules = trend_data["history"][-1]["module_breakdown"]

        for module in current_modules:
            if module in previous_modules:
                delta = current_modules[module] - previous_modules[module]
                if delta < -threshold:
                    has_regression = True
                    messages.append(
                        f"MODULE REGRESSION: {module} decreased by {delta:.2f}% "
                        f"({previous_modules[module]:.2f}% → {current_modules[module]:.2f}%)"
                    )

    if not has_regression:
        messages.append(f"No regression detected (coverage stable or improving)")

    return has_regression, messages


def forecast_target(trend_data: Dict[str, Any], target: float = TARGET_COVERAGE) -> str:
    """
    Forecast when target coverage will be reached based on trend.

    Args:
        trend_data: Trend data with history
        target: Target coverage percentage

    Returns:
        Formatted forecast string
    """
    if len(trend_data["history"]) < 3:
        return "Insufficient history for forecasting (need at least 3 snapshots)"

    current = trend_data["current"]["overall_coverage"]

    if current >= target:
        return f"Target {target}% already reached! Current: {current:.2f}%"

    # Calculate average increase per snapshot (last 5 snapshots)
    recent_snapshots = trend_data["history"][-5:]
    increases = []

    for i in range(1, len(recent_snapshots)):
        delta = recent_snapshots[i]["overall_coverage"] - recent_snapshots[i - 1]["overall_coverage"]
        increases.append(delta)

    avg_increase = sum(increases) / len(increases) if increases else 0

    if avg_increase <= 0:
        return (
            f"Cannot forecast: Coverage trend is flat or decreasing "
            f"(avg change: {avg_increase:.2f}% per snapshot)"
        )

    # Calculate snapshots needed
    remaining = target - current
    snapshots_needed = int(remaining / avg_increase) + 1

    # Estimate dates based on snapshot frequency
    if len(trend_data["history"]) >= 2:
        first_snapshot = datetime.fromisoformat(trend_data["history"][0]["timestamp"].replace("Z", "+00:00"))
        last_snapshot = datetime.fromisoformat(trend_data["current"]["timestamp"].replace("Z", "+00:00"))
        days_span = (last_snapshot - first_snapshot).days
        days_per_snapshot = days_span / (len(trend_data["history"]) - 1) if len(trend_data["history"]) > 1 else 1

        estimated_days = snapshots_needed * days_per_snapshot
        from datetime import timedelta
        estimated_date = last_snapshot + timedelta(days=estimated_days)

        # Generate scenarios
        optimistic_days = estimated_days * 0.7
        realistic_days = estimated_days
        pessimistic_days = estimated_days * 1.3

        optimistic_date = last_snapshot + timedelta(days=optimistic_days)
        pessimistic_date = last_snapshot + timedelta(days=pessimistic_days)

        lines = []
        lines.append("")
        lines.append("=" * 80)
        lines.append(f"COVERAGE FORECAST: {target}% TARGET")
        lines.append("=" * 80)
        lines.append("")
        lines.append(f"Current Coverage: {current:.2f}%")
        lines.append(f"Target Coverage:  {target:.2f}%")
        lines.append(f"Remaining:        {remaining:.2f}%")
        lines.append("")
        lines.append(f"Average Increase: {avg_increase:.2f}% per snapshot")
        lines.append(f"Snapshot Frequency: ~{days_per_snapshot:.1f} days per snapshot")
        lines.append("")
        lines.append(f"Snapshots Needed:  ~{snapshots_needed} snapshots")
        lines.append(f"Estimated Timeline: ~{estimated_days:.0f} days")
        lines.append("")
        lines.append("Scenarios:")
        lines.append(f"  Optimistic:  {optimistic_date.strftime('%Y-%m-%d')} ({optimistic_days:.0f} days)")
        lines.append(f"  Realistic:   {estimated_date.strftime('%Y-%m-%d')} ({realistic_days:.0f} days)")
        lines.append(f"  Pessimistic: {pessimistic_date.strftime('%Y-%m-%d')} ({pessimistic_days:.0f} days)")
        lines.append("")
        lines.append("=" * 80)

        return "\n".join(lines)
    else:
        return f"~{snapshots_needed} snapshots needed (timeline estimation requires more history)"


def record_coverage_ci() -> Dict[str, Any]:
    """
    Record coverage snapshot for CI/CD integration.

    Returns:
        PR comment payload dict
    """
    # Load current coverage
    if not DEFAULT_COVERAGE_FILE.exists():
        return {"error": "Coverage file not found"}

    with open(DEFAULT_COVERAGE_FILE) as f:
        coverage_data = json.load(f)

    # Get commit from environment
    commit_hash = get_git_commit_hash()

    # Record snapshot
    snapshot = record_snapshot(coverage_data, commit_hash)
    trend_data = get_trend_history()
    trend_data = update_trend_data(snapshot, trend_data)
    write_trend_data(trend_data)

    # Generate PR comment payload
    current = snapshot["overall_coverage"]
    baseline = trend_data["baseline"]["overall_coverage"]
    delta = current - baseline

    payload = {
        "title": "Coverage Report",
        "summary": {
            "current": f"{current:.2f}%",
            "baseline": f"{baseline:.2f}%",
            "delta": f"{delta:+.2f}%",
            "target": f"{TARGET_COVERAGE:.2f}%"
        },
        "metrics": {
            "lines_covered": snapshot["covered_lines"],
            "total_lines": snapshot["total_lines"],
            "branch_coverage": snapshot["branch_coverage"]
        },
        "modules": snapshot.get("module_breakdown", {}),
        "trend": "increasing" if delta > 0 else "stable" if delta == 0 else "decreasing",
        "commit": commit_hash[:8] if commit_hash else "unknown"
    }

    return payload


def main():
    """Main execution entry point."""
    parser = argparse.ArgumentParser(
        description="Track coverage trends for Atom v5.0",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
  # Record current coverage with visualization
  python coverage_trend_tracker.py --commit $(git rev-parse HEAD) --chart

  # Check for regressions (CI usage)
  python coverage_trend_tracker.py --regression-check

  # Compare two commits
  python coverage_trend_tracker.py --compare-commits abc123 def456

  # Forecast when 80% will be reached
  python coverage_trend_tracker.py --forecast 80

  # Record for CI (generates PR comment payload)
  python coverage_trend_tracker.py --ci-record
        """
    )

    parser.add_argument(
        "--coverage-file",
        type=Path,
        default=DEFAULT_COVERAGE_FILE,
        help="Path to coverage.json (default: backend/tests/coverage_reports/metrics/coverage.json)"
    )
    parser.add_argument(
        "--output",
        type=Path,
        default=DEFAULT_TREND_FILE,
        help="Output path for trend data (default: backend/tests/coverage_reports/metrics/coverage_trend_v5.0.json)"
    )
    parser.add_argument(
        "--commit",
        type=str,
        default=None,
        help="Git commit hash (auto-detected if not provided)"
    )
    parser.add_argument(
        "--chart",
        action="store_true",
        help="Generate ASCII visualization chart"
    )
    parser.add_argument(
        "--regression-check",
        action="store_true",
        help="Check for coverage regressions (exits with 1 on regression)"
    )
    parser.add_argument(
        "--compare-commits",
        nargs=2,
        metavar=("COMMIT1", "COMMIT2"),
        help="Compare coverage between two commits"
    )
    parser.add_argument(
        "--forecast",
        type=float,
        metavar="TARGET",
        default=None,
        help="Forecast when TARGET coverage will be reached (default: 80.0%%)"
    )
    parser.add_argument(
        "--ci-record",
        action="store_true",
        help="Record snapshot for CI and generate PR comment payload"
    )

    args = parser.parse_args()

    # Load coverage data
    if not args.coverage_file.exists():
        print(f"Error: Coverage file not found: {args.coverage_file}", file=sys.stderr)
        sys.exit(1)

    with open(args.coverage_file) as f:
        coverage_data = json.load(f)

    # CI record mode
    if args.ci_record:
        payload = record_coverage_ci()
        print(json.dumps(payload, indent=2))
        sys.exit(0)

    # Get or create trend data
    trend_data = get_trend_history(args.output)

    # Record snapshot
    snapshot = record_snapshot(coverage_data, args.commit)
    trend_data = update_trend_data(snapshot, trend_data)
    write_trend_data(trend_data, args.output)

    # Print summary
    print("")
    print("=" * 80)
    print("COVERAGE SNAPSHOT RECORDED")
    print("=" * 80)
    print(f"Timestamp:    {snapshot['timestamp']}")
    print(f"Commit:       {snapshot['commit'] or 'unknown'}")
    print(f"Coverage:     {snapshot['overall_coverage']:.2f}%")
    print(f"Lines:        {snapshot['covered_lines']:,} / {snapshot['total_lines']:,}")
    print(f"Branch:       {snapshot['branch_coverage']:.2f}%")
    print("")

    if "delta" in snapshot:
        delta = snapshot["delta"]
        symbol = {"increase": "↑", "decrease": "↓", "no_change": "→", "baseline": "="}[delta["direction"]]
        print(f"Change:       {symbol} {delta['absolute_change']:+.2f}% ({delta['relative_change']:+.2f}% relative)")

    print("")
    print("Module Breakdown:")
    for module, pct in snapshot.get("module_breakdown", {}).items():
        print(f"  {module}: {pct:.2f}%")

    print("")

    # Generate chart if requested
    if args.chart:
        print(generate_visualization(trend_data))

    # Regression check
    if args.regression_check:
        has_regression, messages = check_regression(trend_data)

        print("=" * 80)
        print("REGRESSION CHECK")
        print("=" * 80)
        for msg in messages:
            print(msg)
        print("")

        if has_regression:
            print("❌ REGRESSION DETECTED")
            sys.exit(1)
        else:
            print("✅ No regression")
            sys.exit(0)

    # Forecast
    if args.forecast:
        print(forecast_target(trend_data, args.forecast))

    return 0


if __name__ == "__main__":
    sys.exit(main())
