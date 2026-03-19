#!/usr/bin/env python3
"""
Performance Regression Detector

This script compares current load test results against a baseline to detect
performance regressions. It checks P95 response times and RPS throughput,
failing if regressions exceed the specified threshold.

Usage:
    python compare_performance.py baseline.json current.json
    python compare_performance.py baseline.json current.json --threshold 20

Reference: Phase 209 Plan 05 Task 4
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, List, Any


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


def extract_metrics(data: dict) -> Dict[str, Dict[str, float]]:
    """
    Extract key metrics from Locust results.

    Args:
        data: Parsed Locust JSON output

    Returns:
        Dictionary mapping endpoint names to their metrics
        {
            "endpoint_name": {
                "p95_response_time": float,
                "requests_per_second": float,
                "avg_response_time": float
            }
        }
    """
    stats = data.get('stats', [])
    metrics = {}

    # Calculate total duration in seconds
    state = data.get('state', {})
    run_time_ms = state.get('run_time', 0)
    duration_seconds = run_time_ms / 1000 if run_time_ms > 0 else 1

    for stat in stats:
        name = stat.get('name', 'unknown')
        num_requests = stat.get('num_requests', 0)

        # Extract P95 response time
        response_times = stat.get('response_times', {})
        p95 = response_times.get('0.95', 0)

        # Calculate RPS for this endpoint
        rps = num_requests / duration_seconds if duration_seconds > 0 else 0

        # Extract average response time
        avg_response = stat.get('avg_response_time', 0)

        metrics[name] = {
            'p95_response_time': p95,
            'requests_per_second': rps,
            'avg_response_time': avg_response
        }

    return metrics


def compare_metrics(
    baseline: dict,
    current: dict,
    threshold: float
) -> List[Dict[str, Any]]:
    """
    Compare current metrics against baseline and detect regressions.

    A regression is detected when:
    - P95 response time increases by more than threshold %
    - RPS (throughput) decreases by more than threshold %

    Args:
        baseline: Baseline metrics dictionary
        current: Current metrics dictionary
        threshold: Percentage threshold for regression detection

    Returns:
        List of regression dictionaries with details
    """
    regressions = []

    for endpoint_name, current_metrics in current.items():
        if endpoint_name not in baseline:
            # New endpoint, skip comparison
            continue

        baseline_metrics = baseline[endpoint_name]

        # Check P95 response time regression (increase is bad)
        baseline_p95 = baseline_metrics.get('p95_response_time', 0)
        current_p95 = current_metrics.get('p95_response_time', 0)

        if baseline_p95 > 0:
            p95_change = ((current_p95 - baseline_p95) / baseline_p95) * 100
            if p95_change > threshold:
                regressions.append({
                    'endpoint': endpoint_name,
                    'metric': 'p95_response_time',
                    'baseline': baseline_p95,
                    'current': current_p95,
                    'change_percent': p95_change,
                    'direction': 'increase'
                })

        # Check RPS regression (decrease is bad)
        baseline_rps = baseline_metrics.get('requests_per_second', 0)
        current_rps = current_metrics.get('requests_per_second', 0)

        if baseline_rps > 0:
            rps_change = ((current_rps - baseline_rps) / baseline_rps) * 100
            if rps_change < -threshold:  # Negative change is regression
                regressions.append({
                    'endpoint': endpoint_name,
                    'metric': 'requests_per_second',
                    'baseline': baseline_rps,
                    'current': current_rps,
                    'change_percent': abs(rps_change),
                    'direction': 'decrease'
                })

    return regressions


def format_regression(regression: Dict[str, Any]) -> str:
    """
    Format a regression for display.

    Args:
        regression: Regression dictionary

    Returns:
        Formatted string
    """
    endpoint = regression['endpoint']
    metric = regression['metric'].replace('_', ' ').title()
    change = regression['change_percent']
    direction = regression['direction']

    if metric == 'P95 Response Time':
        baseline_str = f"{regression['baseline']:.0f}ms"
        current_str = f"{regression['current']:.0f}ms"
    else:  # Requests Per Second
        baseline_str = f"{regression['baseline']:.1f}"
        current_str = f"{regression['current']:.1f}"

    return f"🔴 {endpoint} - {metric}: {baseline_str} → {current_str} ({direction[:3]} {change:.1f}%)"


def main():
    """Main entry point for performance comparison."""
    parser = argparse.ArgumentParser(
        description='Compare load test results against baseline to detect regressions'
    )
    parser.add_argument(
        'baseline',
        help='Path to baseline JSON file'
    )
    parser.add_argument(
        'current',
        help='Path to current JSON file'
    )
    parser.add_argument(
        '--threshold', '-t',
        type=float,
        default=15.0,
        help='Regression threshold in percentage (default: 15%%)'
    )

    args = parser.parse_args()

    try:
        # Load results
        print(f"Loading baseline from {args.baseline}...")
        baseline_data = load_results(args.baseline)
        baseline_metrics = extract_metrics(baseline_data)

        print(f"Loading current results from {args.current}...")
        current_data = load_results(args.current)
        current_metrics = extract_metrics(current_data)

        # Compare metrics
        print(f"\nComparing metrics (threshold: {args.threshold}%)...")
        regressions = compare_metrics(baseline_metrics, current_metrics, args.threshold)

        # Display results
        if not regressions:
            print(f"✅ No performance regressions detected (threshold: {args.threshold}%)")
            return 0
        else:
            print(f"\n❌ PERFORMANCE REGRESSION DETECTED ({len(regressions)} regression{'s' if len(regressions) > 1 else ''})")
            print("\nRegressions:")
            for regression in regressions:
                print(f"  {format_regression(regression)}")

            print(f"\n💡 Tip: Update baseline only after verifying improvements are legitimate")
            return 1

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
