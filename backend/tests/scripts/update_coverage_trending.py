#!/usr/bin/env python3
"""Update coverage trending data from coverage.json.

This script reads the latest coverage metrics from coverage.json and appends
them to the trending.json history for tracking coverage over time.
"""

import json
from datetime import datetime
from pathlib import Path


def update_trending():
    """Update trending data with current coverage snapshot."""
    coverage_file = Path("tests/coverage_reports/metrics/coverage.json")
    trending_file = Path("tests/coverage_reports/trending.json")

    if not coverage_file.exists():
        print("No coverage.json found")
        return False

    with open(coverage_file) as f:
        coverage_data = json.load(f)

    # Default trending structure
    trending = {
        "history": [],
        "baseline": {
            "date": "2026-02-13",
            "overall_coverage": 4.4,
            "target_overall": 80.0
        },
        "target": {
            "overall_coverage": 80.0,
            "date": "2026-02-28"
        }
    }

    # Load existing trending data if available
    if trending_file.exists():
        with open(trending_file) as f:
            trending = json.load(f)

    # Extract coverage metrics
    overall_coverage = coverage_data.get("totals", {}).get("percent_covered", 0)
    lines_covered = coverage_data.get("totals", {}).get("covered_lines", 0)
    lines_total = coverage_data.get("totals", {}).get("num_statements", 0)

    # Add current snapshot to history
    trending["history"].append({
        "date": datetime.now().isoformat(),
        "overall_coverage": round(overall_coverage, 2),
        "lines_covered": lines_covered,
        "lines_total": lines_total
    })

    # Keep only last 30 entries to prevent file from growing too large
    trending["history"] = trending["history"][-30:]

    # Write updated trending data
    with open(trending_file, "w") as f:
        json.dump(trending, f, indent=2)

    print("Coverage trending updated: {:.2f}%".format(overall_coverage))
    print("  Lines covered: {}/{}".format(lines_covered, lines_total))
    print("  History entries: {}".format(len(trending['history'])))

    return True


if __name__ == "__main__":
    success = update_trending()
    exit(0 if success else 1)
