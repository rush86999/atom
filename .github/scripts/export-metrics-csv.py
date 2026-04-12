#!/usr/bin/env python3
"""
Export quality metrics to CSV format.

Usage: python3 .github/scripts/export-metrics-csv.py > metrics.csv
"""

import json
import csv
import sys
from pathlib import Path

def load_metrics():
    """Load quality metrics."""
    metrics_file = Path("backend/tests/coverage_reports/metrics/quality_metrics.json")
    with open(metrics_file) as f:
        return json.load(f)

def export_to_csv(metrics):
    """Export metrics to CSV."""
    history = metrics.get("history", [])

    if not history:
        print("No historical data available")
        return

    # Write CSV header
    writer = csv.DictWriter(sys.stdout, fieldnames=["timestamp", "backend_coverage", "frontend_coverage"])
    writer.writeheader()

    # Write data rows
    for entry in history:
        writer.writerow({
            "timestamp": entry.get("timestamp", ""),
            "backend_coverage": entry.get("backend", {}).get("coverage", 0),
            "frontend_coverage": entry.get("frontend", {}).get("coverage", 0)
        })

def main():
    """Export metrics."""
    metrics = load_metrics()
    export_to_csv(metrics)

if __name__ == "__main__":
    main()
