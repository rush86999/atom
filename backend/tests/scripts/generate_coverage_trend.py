#!/usr/bin/env python3
"""
Coverage Trend Generation and Analysis Script

Tracks coverage trends over time, detects regressions, and predicts completion dates.
Generates HTML reports with visual charts and trend analysis.

Usage:
    python tests/scripts/generate_coverage_trend.py --help
    python tests/scripts/generate_coverage_trend.py --html-output /tmp/report.html
    python tests/scripts/generate_coverage_trend.py --coverage-json custom/coverage.json
"""

import argparse
import json
import os
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path
from typing import Dict, Any, List, Tuple, Optional


# Default paths (relative to backend directory)
DEFAULT_COVERAGE_JSON = "tests/coverage_reports/metrics/coverage.json"
DEFAULT_TRENDING_JSON = "tests/coverage_reports/metrics/trending.json"
DEFAULT_HTML_OUTPUT = "tests/coverage_reports/metrics/coverage_trend_report.html"


def load_current_coverage(coverage_json_path: str) -> Optional[Dict[str, Any]]:
    """Load current coverage from coverage.json."""
    coverage_path = Path(coverage_json_path)

    if not coverage_path.exists():
        print(f"ERROR: Coverage file not found: {coverage_path}")
        print("Run pytest with coverage first:")
        print("  pytest --cov=core --cov=api --cov=tools --cov-report=json")
        return None

    with open(coverage_path) as f:
        data = json.load(f)

    return data


def load_trending_data(trending_json_path: str) -> Dict[str, Any]:
    """Load trending.json or create new structure if doesn't exist."""
    trending_path = Path(trending_json_path)

    if not trending_path.exists():
        # Initialize new trending structure
        return {
            "coverage_history": [],
            "trend_analysis": {},
            "regression_alerts": [],
            "baselines": {},
            "metadata": {
                "created": datetime.now().isoformat(),
                "version": "2.0"
            }
        }

    with open(trending_path) as f:
        data = json.load(f)

    # If old format, migrate to new format
    if "history" in data and "coverage_history" not in data:
        # Migrate old "history" to new "coverage_history"
        data["coverage_history"] = []
        for entry in data["history"]:
            data["coverage_history"].append({
                "date": entry["date"],
                "phase": entry.get("phase", ""),
                "plan": entry.get("plan", ""),
                "coverage_percent": entry.get("coverage_pct", 0),
                "files_covered": entry.get("lines_covered", 0),
                "files_total": entry.get("lines_total", 0),
                "branches_covered": entry.get("branches_covered", 0),
                "branches_total": entry.get("branches_total", 0),
                "new_files_added": 0,
                "modified_files": 0,
                "trend": entry.get("trend", "stable")
            })
        data["trend_analysis"] = {}
        data["regression_alerts"] = []

    # Ensure all required keys exist
    if "coverage_history" not in data:
        data["coverage_history"] = []
    if "trend_analysis" not in data:
        data["trend_analysis"] = {}
    if "regression_alerts" not in data:
        data["regression_alerts"] = []
    if "baselines" not in data:
        data["baselines"] = {}
    if "metadata" not in data:
        data["metadata"] = {"version": "2.0"}

    return data


def get_git_metrics() -> Dict[str, int]:
    """Get file metrics from git diff (new files, modified files)."""
    try:
        # Get list of modified/added Python files
        result = subprocess.run(
            ["git", "diff", "--name-only", "HEAD~1", "HEAD"],
            capture_output=True,
            text=True,
            timeout=5
        )

        files = result.stdout.strip().split('\n') if result.stdout.strip() else []
        python_files = [f for f in files if f.endswith('.py') and 'core/' in f or 'api/' in f or 'tools/' in f]

        return {
            "new_files_added": len([f for f in python_files if 'new file' in result.stdout]),
            "modified_files": len(python_files)
        }
    except (subprocess.TimeoutExpired, subprocess.CalledProcessError, FileNotFoundError):
        # Git not available or error
        return {
            "new_files_added": 0,
            "modified_files": 0
        }


def calculate_trend_metrics(history: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate trend metrics from coverage history."""
    if len(history) < 2:
        return {
            "seven_day_avg": history[0]["coverage_percent"] if history else 0,
            "thirty_day_avg": history[0]["coverage_percent"] if history else 0,
            "week_over_week_change": 0,
            "trend_direction": "stable"
        }

    # Get recent history
    recent_entries = history[-30:]  # Last 30 entries

    # Calculate averages
    seven_day_entries = recent_entries[-7:] if len(recent_entries) >= 7 else recent_entries
    thirty_day_entries = recent_entries

    seven_day_avg = sum(e["coverage_percent"] for e in seven_day_entries) / len(seven_day_entries)
    thirty_day_avg = sum(e["coverage_percent"] for e in thirty_day_entries) / len(thirty_day_entries)

    # Calculate week-over-week change
    if len(history) >= 7:
        wow_change = history[-1]["coverage_percent"] - history[-7]["coverage_percent"]
    elif len(history) >= 2:
        wow_change = history[-1]["coverage_percent"] - history[-2]["coverage_percent"]
    else:
        wow_change = 0

    # Determine trend direction
    if wow_change > 0.5:
        trend_direction = "increasing"
    elif wow_change < -0.5:
        trend_direction = "decreasing"
    else:
        trend_direction = "stable"

    return {
        "seven_day_avg": round(seven_day_avg, 2),
        "thirty_day_avg": round(thirty_day_avg, 2),
        "week_over_week_change": round(wow_change, 2),
        "trend_direction": trend_direction
    }


def detect_regression(current: float, baseline: float, threshold: float = 5.0) -> Dict[str, Any]:
    """Detect if coverage has regressed beyond threshold."""
    diff = current - baseline

    if diff < -threshold:
        return {
            "regression_detected": True,
            "severity": "high" if diff < -10 else "medium",
            "change": round(diff, 2),
            "message": f"Coverage dropped by {abs(diff):.2f}% (threshold: {threshold}%)"
        }

    return {
        "regression_detected": False,
        "severity": "none",
        "change": round(diff, 2),
        "message": "No regression detected"
    }


def predict_target_date(history: List[Dict[str, Any]], target: float = 80) -> Dict[str, Any]:
    """
    Predict when coverage will reach target using linear regression.

    Returns estimated date and confidence level.
    """
    if len(history) < 3:
        return {
            "target_percent": target,
            "estimated_date": None,
            "confidence": "low",
            "message": "Insufficient data for prediction (need 3+ data points)"
        }

    # Get last 30 data points
    recent = history[-30:]

    # Extract dates and coverage values
    dates = []
    for e in recent:
        date_str = e["date"]
        # Handle both 'Z' suffix and timezone-aware formats
        if date_str.endswith('Z'):
            date_str = date_str.replace('Z', '+00:00')
        try:
            dates.append(datetime.fromisoformat(date_str))
        except ValueError:
            # Fallback for various datetime formats
            dates.append(datetime.fromisoformat(date_str.replace('+00:00', '')))

    coverages = [e["coverage_percent"] for e in recent]

    # Strip timezone info for calculations
    first_date = dates[0].replace(tzinfo=None)
    x_values = [(d.replace(tzinfo=None) - first_date).days for d in dates]

    # Calculate linear regression: y = mx + b
    n = len(x_values)
    sum_x = sum(x_values)
    sum_y = sum(coverages)
    sum_xy = sum(x * y for x, y in zip(x_values, coverages))
    sum_x2 = sum(x ** 2 for x in x_values)

    # Calculate slope (m) and intercept (b)
    denominator = n * sum_x2 - sum_x ** 2
    if denominator == 0:
        return {
            "target_percent": target,
            "estimated_date": None,
            "confidence": "low",
            "message": "Cannot calculate trend (insufficient variation)"
        }

    slope = (n * sum_xy - sum_x * sum_y) / denominator
    intercept = (sum_y - slope * sum_x) / n

    # Calculate R-squared for confidence
    y_mean = sum_y / n
    ss_tot = sum((y - y_mean) ** 2 for y in coverages)
    ss_res = sum((y - (slope * x + intercept)) ** 2 for x, y in zip(x_values, coverages))
    r_squared = 1 - (ss_res / ss_tot) if ss_tot > 0 else 0

    # Determine confidence based on R-squared and data points
    if r_squared > 0.7 and len(history) >= 10:
        confidence = "high"
    elif r_squared > 0.5 and len(history) >= 5:
        confidence = "medium"
    else:
        confidence = "low"

    # Predict days to reach target
    if slope <= 0.001:
        return {
            "target_percent": target,
            "estimated_date": None,
            "confidence": confidence,
            "message": "Coverage not trending upward (slope: {:.4f})".format(slope)
        }

    current_coverage = coverages[-1]
    if current_coverage >= target:
        return {
            "target_percent": target,
            "estimated_date": dates[-1].strftime("%Y-%m-%d"),
            "confidence": confidence,
            "message": "Target already achieved!"
        }

    days_to_target = (target - intercept) / slope
    estimated_date = first_date + timedelta(days=days_to_target)

    return {
        "target_percent": target,
        "estimated_date": estimated_date.strftime("%Y-%m-%d"),
        "confidence": confidence,
        "slope": round(slope, 4),
        "r_squared": round(r_squared, 2),
        "days_to_target": int(days_to_target),
        "message": f"Estimated {int(days_to_target)} days to reach {target}% target"
    }

    return {
        "target_percent": target,
        "estimated_date": estimated_date.strftime("%Y-%m-%d"),
        "confidence": confidence,
        "slope": round(slope, 4),
        "r_squared": round(r_squared, 2),
        "days_to_target": int(days_to_target),
        "message": f"Estimated {int(days_to_target)} days to reach {target}% target"
    }


def generate_html_report(trending: Dict[str, Any], output_path: str) -> None:
    """Generate HTML trend report with charts and visualizations."""
    history = trending.get("coverage_history", [])
    analysis = trending.get("trend_analysis", {})
    alerts = trending.get("regression_alerts", [])

    # Prepare chart data
    dates = [e["date"][:10] for e in history[-30:]]  # Last 30 entries
    coverage_values = [e["coverage_percent"] for e in history[-30:]]

    # Generate SVG chart
    chart_svg = generate_svg_chart(dates, coverage_values, analysis.get("target_prediction", {}).get("target_percent", 80))

    # Create trend indicators
    trend_emoji = "📈" if analysis.get("trend_direction") == "increasing" else "📉" if analysis.get("trend_direction") == "decreasing" else "➡️"
    trend_color = "green" if analysis.get("trend_direction") == "increasing" else "red" if analysis.get("trend_direction") == "decreasing" else "gray"

    html_content = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Coverage Trend Report - Atom</title>
    <style>
        * {{
            margin: 0;
            padding: 0;
            box-sizing: border-box;
        }}

        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            padding: 20px;
            line-height: 1.6;
        }}

        .container {{
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            border-radius: 12px;
            box-shadow: 0 20px 60px rgba(0,0,0,0.3);
            overflow: hidden;
        }}

        .header {{
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
            padding: 30px;
            text-align: center;
        }}

        .header h1 {{
            font-size: 2.5em;
            margin-bottom: 10px;
        }}

        .header .timestamp {{
            opacity: 0.9;
            font-size: 0.9em;
        }}

        .summary-cards {{
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(250px, 1fr));
            gap: 20px;
            padding: 30px;
            background: #f8f9fa;
        }}

        .card {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
            transition: transform 0.2s;
        }}

        .card:hover {{
            transform: translateY(-2px);
            box-shadow: 0 4px 12px rgba(0,0,0,0.15);
        }}

        .card-label {{
            font-size: 0.85em;
            color: #666;
            text-transform: uppercase;
            letter-spacing: 0.5px;
            margin-bottom: 8px;
        }}

        .card-value {{
            font-size: 2em;
            font-weight: bold;
            color: #333;
        }}

        .card-sub {{
            font-size: 0.9em;
            color: #888;
            margin-top: 4px;
        }}

        .trend-up {{ color: #28a745; }}
        .trend-down {{ color: #dc3545; }}
        .trend-stable {{ color: #6c757d; }}

        .chart-section {{
            padding: 30px;
        }}

        .chart-container {{
            background: white;
            border-radius: 8px;
            padding: 20px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }}

        .chart-title {{
            font-size: 1.5em;
            margin-bottom: 20px;
            color: #333;
        }}

        .chart {{
            width: 100%;
            height: 400px;
        }}

        .alerts-section {{
            padding: 0 30px 30px;
        }}

        .alert {{
            background: #fff3cd;
            border-left: 4px solid #ffc107;
            padding: 15px 20px;
            margin-bottom: 10px;
            border-radius: 4px;
        }}

        .alert-high {{
            background: #f8d7da;
            border-left-color: #dc3545;
        }}

        .alert-medium {{
            background: #fff3cd;
            border-left-color: #ffc107;
        }}

        .footer {{
            background: #f8f9fa;
            padding: 20px 30px;
            text-align: center;
            color: #666;
            font-size: 0.9em;
        }}

        .footer a {{
            color: #667eea;
            text-decoration: none;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>📊 Coverage Trend Report</h1>
            <div class="timestamp">Last updated: {datetime.now().strftime("%Y-%m-%d %H:%M:%S")}</div>
        </div>

        <div class="summary-cards">
            <div class="card">
                <div class="card-label">Current Coverage</div>
                <div class="card-value">{analysis.get("current_coverage", 0):.1f}%</div>
                <div class="card-sub">
                    {trend_emoji} {analysis.get("trend_direction", "unknown").title()}
                </div>
            </div>

            <div class="card">
                <div class="card-label">30-Day Average</div>
                <div class="card-value">{analysis.get("thirty_day_avg", 0):.1f}%</div>
                <div class="card-sub">Moving average</div>
            </div>

            <div class="card">
                <div class="card-label">Week-over-Week</div>
                <div class="card-value trend-{analysis.get("trend_direction", "stable")}">
                    {analysis.get("week_over_week_change", 0):+.1f}%
                </div>
                <div class="card-sub">Change from last week</div>
            </div>

            <div class="card">
                <div class="card-label">Target Prediction</div>
                <div class="card-value">
                    {analysis.get("target_prediction", {}).get("estimated_date", "N/A")}
                </div>
                <div class="card-sub">
                    Confidence: {analysis.get("target_prediction", {}).get("confidence", "N/A").title()}
                </div>
            </div>
        </div>

        <div class="chart-section">
            <div class="chart-container">
                <div class="chart-title">Coverage History (Last 30 Data Points)</div>
                <div class="chart">
                    {chart_svg}
                </div>
            </div>
        </div>

        {f'''        <div class="alerts-section">
            <div class="chart-title">Regression Alerts</div>
            {''.join(f'<div class="alert alert-{a.get("severity", "medium")}">{a.get("message", "")}</div>' for a in alerts)}
            {'<div class="alert">No regression alerts detected</div>' if not alerts else ''}
        </div>
        ''' if alerts else ''}

        <div class="footer">
            Generated by Coverage Trend System |
            <a href="../html/index.html">Full Coverage Report</a> |
            <a href="coverage.json">Raw Data</a>
        </div>
    </div>
</body>
</html>"""

    # Write HTML file
    output_file = Path(output_path)
    output_file.parent.mkdir(parents=True, exist_ok=True)

    with open(output_file, 'w') as f:
        f.write(html_content)

    print(f"HTML report generated: {output_path}")


def generate_svg_chart(dates: List[str], values: List[float], target: float) -> str:
    """Generate SVG line chart for coverage trends."""
    if not values:
        return '<div style="text-align:center; padding:50px; color:#888;">No data available</div>'

    width = 800
    height = 400
    padding = 40

    # Calculate scales
    min_val = min(values)
    max_val = max(max(values), target)
    val_range = max_val - min_val or 1

    x_step = (width - 2 * padding) / max(len(values) - 1, 1)

    # Generate points
    points = []
    for i, (date, value) in enumerate(zip(dates, values)):
        x = padding + i * x_step
        y = height - padding - ((value - min_val) / val_range) * (height - 2 * padding)
        points.append((x, y))

    # Generate SVG
    svg_lines = []

    # Grid lines
    for i in range(5):
        y = padding + i * (height - 2 * padding) / 4
        val = max_val - i * val_range / 4
        svg_lines.append(f'<line x1="{padding}" y1="{y}" x2="{width-padding}" y2="{y}" stroke="#e0e0e0" stroke-dasharray="5,5"/>')
        svg_lines.append(f'<text x="{padding-5}" y="{y+4}" text-anchor="end" font-size="10" fill="#888">{val:.1f}%</text>')

    # Target line
    target_y = height - padding - ((target - min_val) / val_range) * (height - 2 * padding)
    svg_lines.append(f'<line x1="{padding}" y1="{target_y}" x2="{width-padding}" y2="{target_y}" stroke="#28a745" stroke-width="2" stroke-dasharray="10,5"/>')
    svg_lines.append(f'<text x="{width-padding+5}" y="{target_y+4}" font-size="10" fill="#28a745" font-weight="bold">Target ({target}%)</text>')

    # Data line
    if len(points) > 1:
        path_data = "M" + " L".join(f"{x:.1f},{y:.1f}" for x, y in points)
        svg_lines.append(f'<path d="{path_data}" fill="none" stroke="#667eea" stroke-width="3"/>')

        # Area fill
        area_path = path_data + f" L{points[-1][0]:.1f},{height-padding} L{points[0][0]:.1f},{height-padding} Z"
        svg_lines.append(f'<path d="{area_path}" fill="url(#gradient)" opacity="0.3"/>')

    # Data points
    for i, (x, y) in enumerate(points):
        color = "#28a745" if values[i] >= target else "#dc3545" if values[i] < 70 else "#ffc107"
        svg_lines.append(f'<circle cx="{x:.1f}" cy="{y:.1f}" r="5" fill="{color}" stroke="white" stroke-width="2"/>')

        # Show date for some points
        if i % max(len(points) // 5, 1) == 0:
            svg_lines.append(f'<text x="{x:.1f}" y="{height-10}" text-anchor="middle" font-size="9" fill="#666">{dates[i]}</text>')

    svg = f'''<svg viewBox="0 0 {width} {height}" xmlns="http://www.w3.org/2000/svg">
    <defs>
        <linearGradient id="gradient" x1="0%" y1="0%" x2="0%" y2="100%">
            <stop offset="0%" style="stop-color:#667eea;stop-opacity:1" />
            <stop offset="100%" style="stop-color:#667eea;stop-opacity:0" />
        </linearGradient>
    </defs>
    {''.join(svg_lines)}
</svg>'''

    return svg


def main():
    """Main entry point for trend generation."""
    parser = argparse.ArgumentParser(
        description="Generate coverage trend reports with analysis and predictions"
    )
    parser.add_argument(
        "--coverage-json",
        default=DEFAULT_COVERAGE_JSON,
        help="Path to coverage.json file"
    )
    parser.add_argument(
        "--trending-json",
        default=DEFAULT_TRENDING_JSON,
        help="Path to trending.json file"
    )
    parser.add_argument(
        "--html-output",
        default=DEFAULT_HTML_OUTPUT,
        help="Path for HTML report output"
    )
    parser.add_argument(
        "--target",
        type=float,
        default=80.0,
        help="Coverage target percentage (default: 80)"
    )
    parser.add_argument(
        "--phase",
        default=os.getenv("GSD_PHASE", "090"),
        help="Current phase number"
    )
    parser.add_argument(
        "--plan",
        default=os.getenv("GSD_PLAN", "03"),
        help="Current plan number"
    )

    args = parser.parse_args()

    # Load current coverage
    print(f"Loading coverage from: {args.coverage_json}")
    coverage_data = load_current_coverage(args.coverage_json)

    if not coverage_data:
        sys.exit(1)

    # Extract coverage metrics
    totals = coverage_data["totals"]
    current_coverage = totals["percent_covered"]
    files_covered = totals.get("num_statements", 0)  # Using statements as proxy for files
    files_total = totals.get("covered_lines", 0) + totals.get("missing_lines", 0)
    branches_covered = totals.get("covered_branches", 0)
    branches_total = totals.get("num_branches", 0)

    print(f"Current coverage: {current_coverage:.2f}%")

    # Load trending data
    print(f"Loading trending data from: {args.trending_json}")
    trending = load_trending_data(args.trending_json)

    # Get git metrics
    git_metrics = get_git_metrics()

    # Create new history entry
    new_entry = {
        "date": datetime.now().isoformat() + "Z",
        "phase": args.phase,
        "plan": args.plan,
        "coverage_percent": round(current_coverage, 2),
        "files_covered": files_covered,
        "files_total": files_total,
        "branches_covered": branches_covered,
        "branches_total": branches_total,
        "new_files_added": git_metrics["new_files_added"],
        "modified_files": git_metrics["modified_files"],
        "trend": "stable"
    }

    # Append to history
    trending["coverage_history"].append(new_entry)

    # Calculate trend metrics
    print("Calculating trend metrics...")
    trend_metrics = calculate_trend_metrics(trending["coverage_history"])

    # Detect regression
    if len(trending["coverage_history"]) >= 2:
        baseline = trending["coverage_history"][-2]["coverage_percent"]
        regression = detect_regression(current_coverage, baseline)
    else:
        regression = {"regression_detected": False, "severity": "none", "message": "Insufficient data"}

    # Add alert if regression detected
    if regression["regression_detected"]:
        trending["regression_alerts"].append({
            "date": datetime.now().isoformat() + "Z",
            "severity": regression["severity"],
            "message": regression["message"],
            "from": baseline,
            "to": current_coverage
        })

    # Update trending.json structure to maintain compatibility with existing data
    # Keep old structure but add new fields
    if "history" not in trending:
        trending["history"] = []
    for entry in trending.get("coverage_history", []):
        trending["history"].append({
            "date": entry["date"],
            "phase": entry.get("phase", ""),
            "plan": entry.get("plan", ""),
            "coverage_pct": entry["coverage_percent"],
            "lines_covered": entry.get("files_covered", 0),
            "lines_total": entry.get("files_total", 0),
            "trend": entry.get("trend", "stable")
        })
    trending["latest"] = trending["history"][-1] if trending["history"] else {}

    # Predict target date
    print(f"Predicting target date ({args.target}%)...")
    prediction = predict_target_date(trending["coverage_history"], args.target)

    # Update trend_analysis section
    trending["trend_analysis"] = {
        "current_coverage": round(current_coverage, 2),
        "seven_day_avg": trend_metrics["seven_day_avg"],
        "thirty_day_avg": trend_metrics["thirty_day_avg"],
        "week_over_week_change": trend_metrics["week_over_week_change"],
        "trend_direction": trend_metrics["trend_direction"],
        "regression_detected": regression["regression_detected"],
        "target_prediction": prediction,
        "last_updated": datetime.now().isoformat() + "Z"
    }

    # Save updated trending.json
    trending_path = Path(args.trending_json)
    trending_path.parent.mkdir(parents=True, exist_ok=True)

    with open(trending_path, 'w') as f:
        json.dump(trending, f, indent=2)

    print(f"Trending data saved to: {args.trending_json}")

    # Generate HTML report
    print("Generating HTML report...")
    generate_html_report(trending, args.html_output)

    # Add alert if regression detected
    if regression["regression_detected"]:
        trending["regression_alerts"].append({
            "date": datetime.now().isoformat() + "Z",
            "severity": regression["severity"],
            "message": regression["message"],
            "from": baseline,
            "to": current_coverage
        })

    # Predict target date
    print(f"Predicting target date ({args.target}%)...")
    prediction = predict_target_date(trending["coverage_history"], args.target)

    # Update trend_analysis section
    trending["trend_analysis"] = {
        "current_coverage": round(current_coverage, 2),
        "seven_day_avg": trend_metrics["seven_day_avg"],
        "thirty_day_avg": trend_metrics["thirty_day_avg"],
        "week_over_week_change": trend_metrics["week_over_week_change"],
        "trend_direction": trend_metrics["trend_direction"],
        "regression_detected": regression["regression_detected"],
        "target_prediction": prediction,
        "last_updated": datetime.now().isoformat() + "Z"
    }

    # Save updated trending.json
    trending_path = Path(args.trending_json)
    trending_path.parent.mkdir(parents=True, exist_ok=True)

    with open(trending_path, 'w') as f:
        json.dump(trending, f, indent=2)

    print(f"Trending data saved to: {args.trending_json}")

    # Generate HTML report
    print("Generating HTML report...")
    generate_html_report(trending, args.html_output)

    # Print summary
    print("\n" + "="*60)
    print("COVERAGE TREND SUMMARY")
    print("="*60)
    print(f"Current Coverage: {current_coverage:.2f}%")
    print(f"30-Day Average: {trend_metrics['thirty_day_avg']:.2f}%")
    print(f"Week-over-Week: {trend_metrics['week_over_week_change']:+.2f}%")
    print(f"Trend Direction: {trend_metrics['trend_direction'].title()}")
    print(f"Regression Detected: {regression['regression_detected']}")
    print(f"Target Prediction: {prediction.get('estimated_date', 'N/A')} ({prediction.get('confidence', 'N/A')} confidence)")
    print("="*60)

    return 0


if __name__ == "__main__":
    sys.exit(main())
