#!/usr/bin/env python3
"""
Load Test Report Generator

This script generates HTML reports from Locust JSON output files.
It provides a comprehensive summary of load test results with metrics
and endpoint breakdowns.

Usage:
    python generate_load_report.py --input results.json --output report.html

Reference: Phase 209 Plan 05 Task 3
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path


def load_results(filepath: str) -> dict:
    """
    Load Locust JSON results from file.

    Args:
        filepath: Path to Locust JSON output file

    Returns:
        Parsed JSON data as dictionary

    Raises:
        FileNotFoundError: If file doesn't exist
        json.JSONDecodeError: If file is not valid JSON
    """
    path = Path(filepath)
    if not path.exists():
        raise FileNotFoundError(f"Results file not found: {filepath}")

    with open(path, 'r') as f:
        try:
            data = json.load(f)
        except json.JSONDecodeError as e:
            raise json.JSONDecodeError(f"Invalid JSON in {filepath}: {e}", e.doc, e.pos)

    return data


def format_response_time(ms: float) -> str:
    """Format response time in milliseconds."""
    return f"{ms:.0f}ms"


def format_percentage(value: float) -> str:
    """Format percentage with 2 decimal places."""
    return f"{value:.2f}%"


def generate_color_class(failure_rate: float) -> str:
    """Generate CSS class based on failure rate."""
    if failure_rate == 0:
        return "success"
    elif failure_rate < 1:
        return "warning"
    else:
        return "error"


def generate_html_report(data: dict) -> str:
    """
    Generate HTML report from Locust JSON data.

    Args:
        data: Parsed Locust JSON output

    Returns:
        HTML string
    """
    # Extract test metadata
    start_time = datetime.fromtimestamp(data.get('start_time', 0)).strftime('%Y-%m-%d %H:%M:%S')
    duration_seconds = data.get('state', {}).get('run_time', 0)
    duration = f"{duration_seconds // 60}m {duration_seconds % 60}s"

    # Calculate summary metrics
    stats = data.get('stats', [])
    total_requests = sum(s.get('num_requests', 0) for s in stats)
    total_failures = sum(s.get('num_failures', 0) for s in stats)
    failure_rate = (total_failures / total_requests * 100) if total_requests > 0 else 0

    # Calculate response times
    avg_response_time = sum(
        s.get('avg_response_time', 0) * s.get('num_requests', 0) for s in stats
    ) / total_requests if total_requests > 0 else 0

    # Calculate RPS (requests per second)
    rps = total_requests / (duration_seconds / 1000) if duration_seconds > 0 else 0

    # Generate CSS
    css = """
    <style>
        body {
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            margin: 0;
            padding: 20px;
            background: #f5f5f5;
        }
        .container {
            max-width: 1200px;
            margin: 0 auto;
            background: white;
            padding: 30px;
            border-radius: 8px;
            box-shadow: 0 2px 8px rgba(0,0,0,0.1);
        }
        .header {
            border-bottom: 2px solid #007bff;
            padding-bottom: 20px;
            margin-bottom: 30px;
        }
        .header h1 {
            color: #333;
            margin: 0 0 10px 0;
        }
        .metadata {
            color: #666;
            font-size: 14px;
        }
        .summary {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(200px, 1fr));
            gap: 20px;
            margin-bottom: 30px;
        }
        .metric-card {
            background: #f8f9fa;
            padding: 20px;
            border-radius: 6px;
            border-left: 4px solid #007bff;
        }
        .metric-card h3 {
            margin: 0 0 10px 0;
            color: #666;
            font-size: 14px;
            text-transform: uppercase;
        }
        .metric-card .value {
            font-size: 28px;
            font-weight: bold;
            color: #333;
        }
        .metric-card.error {
            border-left-color: #dc3545;
        }
        .metric-card.warning {
            border-left-color: #ffc107;
        }
        .metric-card.success {
            border-left-color: #28a745;
        }
        table {
            width: 100%;
            border-collapse: collapse;
            margin-top: 20px;
        }
        th {
            background: #007bff;
            color: white;
            padding: 12px;
            text-align: left;
            font-weight: 600;
        }
        td {
            padding: 12px;
            border-bottom: 1px solid #dee2e6;
        }
        tr:hover {
            background: #f8f9fa;
        }
        .endpoint {
            font-family: 'Courier New', monospace;
            font-weight: 600;
        }
        .success { color: #28a745; }
        .warning { color: #ffc107; }
        .error { color: #dc3545; }
    </style>
    """

    # Generate HTML
    html = f"""<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Load Test Report</title>
    {css}
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>Load Test Report</h1>
            <div class="metadata">
                <strong>Start Time:</strong> {start_time} |
                <strong>Duration:</strong> {duration}
            </div>
        </div>

        <div class="summary">
            <div class="metric-card">
                <h3>Total Requests</h3>
                <div class="value">{total_requests:,}</div>
            </div>
            <div class="metric-card">
                <h3>Requests/Second</h3>
                <div class="value">{rps:.1f}</div>
            </div>
            <div class="metric-card">
                <h3>Failure Rate</h3>
                <div class="value">{format_percentage(failure_rate)}</div>
            </div>
            <div class="metric-card">
                <h3>Avg Response Time</h3>
                <div class="value">{format_response_time(avg_response_time)}</div>
            </div>
        </div>

        <h2>Endpoint Breakdown</h2>
        <table>
            <thead>
                <tr>
                    <th>Endpoint</th>
                    <th>Requests</th>
                    <th>Failures</th>
                    <th>Avg</th>
                    <th>P50</th>
                    <th>P95</th>
                    <th>P99</th>
                </tr>
            </thead>
            <tbody>
"""

    # Add table rows for each endpoint
    for stat in sorted(stats, key=lambda s: s.get('num_requests', 0), reverse=True):
        name = stat.get('name', 'N/A')
        num_requests = stat.get('num_requests', 0)
        num_failures = stat.get('num_failures', 0)
        failure_rate = (num_failures / num_requests * 100) if num_requests > 0 else 0
        avg_response = stat.get('avg_response_time', 0)
        response_times = stat.get('response_times', {})
        p50 = response_times.get('0.5', 0)
        p95 = response_times.get('0.95', 0)
        p99 = response_times.get('0.99', 0)

        color_class = generate_color_class(failure_rate)

        html += f"""                <tr>
                    <td class="endpoint">{name}</td>
                    <td>{num_requests:,}</td>
                    <td class="{color_class}">{num_failures} ({format_percentage(failure_rate)})</td>
                    <td>{format_response_time(avg_response)}</td>
                    <td>{format_response_time(p50)}</td>
                    <td>{format_response_time(p95)}</td>
                    <td>{format_response_time(p99)}</td>
                </tr>
"""

    html += """            </tbody>
        </table>
    </div>
</body>
</html>"""

    return html


def main():
    """Main entry point for report generation."""
    parser = argparse.ArgumentParser(
        description='Generate HTML report from Locust JSON output'
    )
    parser.add_argument(
        '--input', '-i',
        required=True,
        help='Path to Locust JSON output file'
    )
    parser.add_argument(
        '--output', '-o',
        required=True,
        help='Path to output HTML report file'
    )

    args = parser.parse_args()

    try:
        # Load results
        print(f"Loading results from {args.input}...")
        data = load_results(args.input)

        # Generate HTML
        print("Generating HTML report...")
        html = generate_html_report(data)

        # Save report
        output_path = Path(args.output)
        output_path.parent.mkdir(parents=True, exist_ok=True)
        with open(output_path, 'w') as f:
            f.write(html)

        print(f"✅ Report generated: {output_path}")
        return 0

    except FileNotFoundError as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1
    except json.JSONDecodeError as e:
        print(f"❌ Error: Invalid JSON - {e}", file=sys.stderr)
        return 1
    except Exception as e:
        print(f"❌ Error: {e}", file=sys.stderr)
        return 1


if __name__ == '__main__':
    sys.exit(main())
