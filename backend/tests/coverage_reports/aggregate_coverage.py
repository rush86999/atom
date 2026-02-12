#!/usr/bin/env python3
"""
Coverage Aggregation Script

Aggregates test coverage metrics from backend, mobile, and desktop platforms.
Calculates overall coverage as the average of all three platforms.

Usage:
    python aggregate_coverage.py

Output:
    Updates coverage_trend.json with aggregated metrics
"""

import json
import os
from datetime import datetime
from pathlib import Path

# Configuration
COVERAGE_DIR = Path(__file__).parent
BACKEND_COVERAGE_FILE = COVERAGE_DIR / "metrics" / "coverage.json"
MOBILE_COVERAGE_FILE = COVERAGE_DIR.parent.parent.parent / "mobile" / "coverage" / "coverage-summary.json"
DESKTOP_COVERAGE_FILE = COVERAGE_DIR / "desktop_coverage.json"
TREND_FILE = COVERAGE_DIR / "coverage_trend.json"

# Coverage targets
TARGET_PERCENT = 80.0


def load_json_file(file_path):
    """Load JSON file, return None if not found."""
    if file_path.exists():
        try:
            with open(file_path, 'r') as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError) as e:
            print(f"⚠️  Warning: Could not load {file_path}: {e}")
            return None
    return None


def get_backend_coverage(data):
    """Extract backend coverage percentage from pytest coverage.json."""
    if data is None:
        return None

    # Try to find overall coverage in various formats
    if 'totals' in data and 'percent_covered' in data['totals']:
        return data['totals']['percent_covered']

    if 'percent_covered' in data:
        return data['percent_covered']

    return None


def get_mobile_coverage(data):
    """Extract mobile coverage percentage from Jest coverage-summary.json."""
    if data is None:
        return None

    if 'total' in data and 'lines' in data['total']:
        # Jest coverage: { total: { lines: { pct: 85.5 } } }
        if 'pct' in data['total']['lines']:
            return data['total']['lines']['pct']

    return None


def get_desktop_coverage(data):
    """Extract desktop coverage percentage from desktop_coverage.json."""
    if data is None:
        return None

    if 'desktop_percent' in data:
        return data['desktop_percent']

    return None


def calculate_overall_coverage(backend, mobile, desktop):
    """Calculate overall coverage as average of three platforms."""
    coverages = [c for c in [backend, mobile, desktop] if c is not None]

    if not coverages:
        return None

    return round(sum(coverages) / len(coverages), 1)


def main():
    """Main aggregation function."""
    print("📊 Aggregating coverage metrics...\n")

    # Load coverage data
    backend_data = load_json_file(BACKEND_COVERAGE_FILE)
    mobile_data = load_json_file(MOBILE_COVERAGE_FILE)
    desktop_data = load_json_file(DESKTOP_COVERAGE_FILE)

    # Extract percentages
    backend_cov = get_backend_coverage(backend_data)
    mobile_cov = get_mobile_coverage(mobile_data)
    desktop_cov = get_desktop_coverage(desktop_data)

    # Display current coverage
    print(f"Platform Coverage:")
    print(f"  Backend:  {backend_cov:5.1f}% {'✓' if backend_cov and backend_cov >= TARGET_PERCENT else '✗'}" if backend_cov else "  Backend:  N/A  (file not found)")
    print(f"  Mobile:   {mobile_cov:5.1f}% {'✓' if mobile_cov and mobile_cov >= TARGET_PERCENT else '✗'}" if mobile_cov else "  Mobile:   N/A  (file not found)")
    print(f"  Desktop:  {desktop_cov:5.1f}% {'✓' if desktop_cov and desktop_cov >= TARGET_PERCENT else '✗'}" if desktop_cov else "  Desktop:  N/A  (file not found)")

    # Calculate overall
    overall_cov = calculate_overall_coverage(backend_cov, mobile_cov, desktop_cov)

    if overall_cov:
        status = "✓" if overall_cov >= TARGET_PERCENT else "✗"
        print(f"\n{'─' * 40}")
        print(f"  Overall:  {overall_cov:5.1f}% {status}")
        print(f"  Target:   {TARGET_PERCENT:5.1f}%")
        print(f"{'─' * 40}\n")
    else:
        print("\n⚠️  Warning: Could not calculate overall coverage (no data available)")
        overall_cov = 0.0

    # Load or create trend data
    trend_data = load_json_file(TREND_FILE)
    if trend_data is None:
        trend_data = {
            "history": []
        }

    # Create new entry
    entry = {
        "date": datetime.now().strftime("%Y-%m-%d"),
        "timestamp": datetime.now().isoformat(),
        "backend_percent": backend_cov,
        "mobile_percent": mobile_cov,
        "desktop_percent": desktop_cov,
        "overall_percent": overall_cov,
        "meets_target": overall_cov >= TARGET_PERCENT if overall_cov else False
    }

    # Add to history
    if "history" not in trend_data:
        trend_data["history"] = []

    trend_data["history"].append(entry)

    # Keep latest entry as current
    trend_data["backend_percent"] = backend_cov
    trend_data["mobile_percent"] = mobile_cov
    trend_data["desktop_percent"] = desktop_cov
    trend_data["overall_percent"] = overall_cov
    trend_data["last_updated"] = datetime.now().isoformat()

    # Save trend file
    with open(TREND_FILE, 'w') as f:
        json.dump(trend_data, f, indent=2)

    print(f"✓ Updated coverage_trend.json")
    print(f"  File: {TREND_FILE}")

    # Print trend summary
    if len(trend_data["history"]) > 1:
        print(f"\n📈 Trend (last 5 entries):")
        for h in trend_data["history"][-5:]:
            date = h["date"]
            overall = h.get("overall_percent", "N/A")
            status = "✓" if h.get("meets_target", False) else "✗"
            print(f"  {date}: {overall:5.1f}% {status}" if isinstance(overall, (int, float)) else f"  {date}: N/A")

    return 0 if overall_cov >= TARGET_PERCENT else 1


if __name__ == "__main__":
    exit(main())
