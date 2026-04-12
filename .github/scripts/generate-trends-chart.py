#!/usr/bin/env python3
"""
Generate ASCII charts for quality metrics trends.

Usage: python3 .github/scripts/generate-trends-chart.py
"""

import json
from pathlib import Path

def load_metrics():
    """Load quality metrics."""
    metrics_file = Path("backend/tests/coverage_reports/metrics/quality_metrics.json")
    with open(metrics_file) as f:
        return json.load(f)

def generate_ascii_chart(data_points, width=40, height=10):
    """Generate ASCII chart from data points."""
    if not data_points or len(data_points) < 2:
        return "Insufficient data for chart"

    min_val = min(data_points)
    max_val = max(data_points)
    range_val = max_val - min_val

    if range_val == 0:
        return "No variation in data"

    chart = []
    chart.append(f"{'':^4} {'-' * width}")
    chart.append(f"{'Max':<4} {max_val:>6.2f}% |")

    # Generate chart rows
    for i in range(height - 2):
        y_val = max_val - (range_val * (i / (height - 2)))
        chart.append(f"{'':<4}{'|':>{width + 1}}")

    chart.append(f"{'Min':<4} {min_val:>6.2f}% |")
    chart.append(f"{'':^4} {'-' * width}")

    return "\n".join(chart)

def generate_trends_section(metrics):
    """Generate trends section with charts."""
    history = metrics.get("history", [])

    if not history:
        return "No historical data available"

    backend_data = [h.get("backend", {}).get("coverage", 0) for h in history]
    frontend_data = [h.get("frontend", {}).get("coverage", 0) for h in history]

    section = "## Coverage Trends (Last 30 Days)\n\n"
    section += "### Backend Coverage\n\n"
    section += "```\n"
    section += generate_ascii_chart(backend_data[-30:])
    section += "\n```\n\n"
    section += "### Frontend Coverage\n\n"
    section += "```\n"
    section += generate_ascii_chart(frontend_data[-30:])
    section += "\n```\n"

    return section

def main():
    """Generate trends charts."""
    metrics = load_metrics()
    trends = generate_trends_section(metrics)

    output_file = Path("backend/docs/QUALITY_TRENDS.md")
    with open(output_file, "w") as f:
        f.write(trends)

    print(f"✅ Trends chart generated: {output_file}")

if __name__ == "__main__":
    main()
