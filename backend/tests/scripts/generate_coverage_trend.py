#!/usr/bin/env python3
"""
Coverage trend tracking script.

Tracks test coverage over time and generates trend reports.
"""

import json
import os
from datetime import datetime
from pathlib import Path


def load_current_coverage():
    """Load current coverage from coverage.json."""
    coverage_file = Path("tests/coverage_reports/metrics/coverage.json")

    if not coverage_file.exists():
        print("Warning: Coverage file not found at", str(coverage_file))
        return None

    with open(coverage_file) as f:
        data = json.load(f)

    return data


def load_trend_history():
    """Load historical trend data."""
    trend_file = Path("tests/coverage_reports/trends.json")

    if not trend_file.exists():
        return []

    with open(trend_file) as f:
        return json.load(f)


def save_trend_history(trends):
    """Save trend history to file."""
    trend_file = Path("tests/coverage_reports/trends.json")
    trend_file.parent.mkdir(parents=True, exist_ok=True)

    with open(trend_file, "w") as f:
        json.dump(trends, f, indent=2)


def generate_trend_report():
    """Generate coverage trend report."""
    current = load_current_coverage()

    if not current:
        print("No current coverage data available")
        return

    # Extract key metrics
    totals = current.get("totals", {})
    coverage_percent = totals.get("percent_covered", 0)
    lines_total = totals.get("num", 0)
    lines_covered = totals.get("covered", 0)
    lines_missed = totals.get("missing", 0)

    # Calculate branch coverage if available
    branch_total = totals.get("branch_num", 0)
    branch_covered = totals.get("branch_covered", 0)
    branch_percent = 0
    if branch_total > 0:
        branch_percent = (branch_covered / branch_total) * 100

    # Load trend history
    trends = load_trend_history()

    # Create new trend entry
    entry = {
        "timestamp": datetime.now().isoformat(),
        "date": datetime.now().strftime("%Y-%m-%d"),
        "coverage_percent": coverage_percent,
        "lines_total": lines_total,
        "lines_covered": lines_covered,
        "lines_missed": lines_missed,
        "branch_total": branch_total,
        "branch_covered": branch_covered,
        "branch_percent": branch_percent,
    }

    # Add to history
    trends.append(entry)

    # Keep only last 30 entries
    if len(trends) > 30:
        trends = trends[-30:]

    # Save updated history
    save_trend_history(trends)

    # Generate report
    print("\n" + "="*60)
    print("COVERAGE TREND REPORT")
    print("="*60)

    print(f"\nCurrent Coverage: {coverage_percent:.1f}%")
    print(f"Lines: {lines_covered:,} / {lines_total:,} ({lines_missed:,} missed)")
    if branch_total > 0:
        print(f"Branches: {branch_covered:,} / {branch_total:,} ({branch_percent:.1f}%)")

    # Calculate trend
    if len(trends) >= 2:
        prev = trends[-2]
        change = coverage_percent - prev["coverage_percent"]

        if change > 0:
            print(f"\n✓ Coverage UP by {change:+.1f}% (from {prev['coverage_percent']:.1f}%)")
        elif change < 0:
            print(f"\n✗ Coverage DOWN by {change:+.1f}% (from {prev['coverage_percent']:.1f}%)")
        else:
            print(f"\n→ Coverage STABLE at {coverage_percent:.1f}%")

    # Show last 5 entries
    if len(trends) > 1:
        print("\nRecent History:")
        for trend in trends[-5:]:
            print(f"  {trend['date']}: {trend['coverage_percent']:.1f}%")

    # Progress toward goal
    goal = 80.0
    progress = (coverage_percent / goal) * 100

    print(f"\nGoal Progress: {coverage_percent:.1f}% / {goal:.1f}% ({progress:.1f}%)")

    if coverage_percent >= goal:
        print("✓ GOAL ACHIEVED!")
    else:
        remaining = goal - coverage_percent
        print(f"⚠ {remaining:.1f}% remaining to goal")

    print("="*60 + "\n")

    # Return entry for CI integration
    return entry


if __name__ == "__main__":
    generate_trend_report()
