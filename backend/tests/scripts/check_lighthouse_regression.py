#!/usr/bin/env python3
"""
Lighthouse Regression Detection Script

This script compares current Lighthouse results against a historical baseline
to detect performance regressions. It checks for:

1. Performance score regression (>20% degradation)
2. Core Web Vitals regression (>20% degradation):
   - First Contentful Paint (FCP)
   - Largest Contentful Paint (LCP)
   - Total Blocking Time (TBT)
   - Cumulative Layout Shift (CLS)

Usage:
    python check_lighthouse_regression.py \
        --current .lighthouseci/lhr-report.json \
        --baseline backend/tests/performance_regression/lighthouse_baseline.json \
        --threshold 0.2

Exit Codes:
    0: No regression detected
    1: Regression detected
    2: Error (missing files, invalid JSON, etc.)
"""

import argparse
import json
import sys
from pathlib import Path
from typing import Dict, Any, Optional, List, Tuple


# ============================================================================
# Lighthouse Metric Parsing
# ============================================================================

def parse_lighthouse_metrics(report_path: str) -> Dict[str, Any]:
    """Parse Lighthouse JSON report and extract key metrics.

    Args:
        report_path: Path to Lighthouse JSON report

    Returns:
        dict: Extracted metrics including scores and Core Web Vitals

    Raises:
        FileNotFoundError: If report file doesn't exist
        json.JSONDecodeError: If report is invalid JSON
        KeyError: If expected metrics are missing
    """
    with open(report_path, 'r') as f:
        report = json.load(f)

    categories = report.get('categories', {})
    audits = report.get('audits', {})

    # Extract performance score (0-100 scale)
    performance_score = categories.get('performance', {}).get('score', 0)
    if performance_score is not None:
        performance_score = performance_score * 100  # Convert to 0-100 scale

    # Extract Core Web Vitals
    metrics = {
        'performance_score': performance_score,
        'accessibility_score': categories.get('accessibility', {}).get('score', 0) * 100,
        'best_practices_score': categories.get('best-practices', {}).get('score', 0) * 100,
        'seo_score': categories.get('seo', {}).get('score', 0) * 100,
        'first_contentful_paint': audits.get('first-contentful-paint', {}).get('numericValue'),
        'largest_contentful_paint': audits.get('largest-contentful-paint', {}).get('numericValue'),
        'total_blocking_time': audits.get('total-blocking-time', {}).get('numericValue'),
        'cumulative_layout_shift': audits.get('cumulative-layout-shift', {}).get('numericValue'),
        'speed_index': audits.get('speed-index', {}).get('numericValue'),
    }

    return metrics


# ============================================================================
# Regression Detection
# ============================================================================

def check_regression(
    current_metrics: Dict[str, Any],
    baseline_metrics: Dict[str, Any],
    threshold: float = 0.2
) -> Tuple[bool, List[str]]:
    """Check for performance regressions by comparing current vs baseline.

    Args:
        current_metrics: Current Lighthouse metrics
        baseline_metrics: Baseline Lighthouse metrics
        threshold: Regression threshold (default 0.2 = 20%)

    Returns:
        tuple: (regression_detected, list of regression messages)
    """
    regressions = []

    # Check performance score (lower is bad)
    current_score = current_metrics.get('performance_score', 0)
    baseline_score = baseline_metrics.get('performance_score', 0)

    if baseline_score > 0 and current_score < baseline_score * (1 - threshold):
        regression_percent = ((baseline_score - current_score) / baseline_score) * 100
        regressions.append(
            f"REGRESSION: Performance score {current_score:.0f} < baseline {baseline_score:.0f} "
            f"({regression_percent:.1f}% degradation)"
        )

    # Check Core Web Vitals (higher is bad for timing metrics)
    vitals_to_check = [
        ('first_contentful_paint', 'FCP'),
        ('largest_contentful_paint', 'LCP'),
        ('total_blocking_time', 'TBT'),
        ('cumulative_layout_shift', 'CLS'),
    ]

    for metric_key, metric_name in vitals_to_check:
        current_value = current_metrics.get(metric_key)
        baseline_value = baseline_metrics.get(metric_key)

        # Skip if baseline value is missing or zero
        if baseline_value is None or baseline_value == 0:
            continue

        # Skip if current value is missing
        if current_value is None:
            continue

        # Check for regression (current > baseline * (1 + threshold))
        if current_value > baseline_value * (1 + threshold):
            regression_percent = ((current_value - baseline_value) / baseline_value) * 100
            unit = 'ms' if metric_key != 'cumulative_layout_shift' else ''

            regressions.append(
                f"REGRESSION: {metric_name} {current_value:.0f}{unit} > "
                f"baseline {baseline_value:.0f}{unit} "
                f"({regression_percent:.1f}% degradation)"
            )

    return len(regressions) > 0, regressions


# ============================================================================
# CLI Interface
# ============================================================================

def parse_args() -> argparse.Namespace:
    """Parse command-line arguments."""
    parser = argparse.ArgumentParser(
        description='Check Lighthouse results for performance regressions',
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
Examples:
    # Check for regressions with default 20% threshold
    %(prog)s --current .lighthouseci/lhr-report.json \\
             --baseline backend/tests/performance_regression/lighthouse_baseline.json

    # Use custom threshold (15%)
    %(prog)s --current .lighthouseci/lhr-report.json \\
             --baseline backend/tests/performance_regression/lighthouse_baseline.json \\
             --threshold 0.15

Exit Codes:
    0: No regression detected
    1: Regression detected
    2: Error (missing files, invalid JSON)
        """
    )

    parser.add_argument(
        '--current',
        required=True,
        help='Path to current Lighthouse JSON report'
    )

    parser.add_argument(
        '--baseline',
        required=True,
        help='Path to baseline Lighthouse JSON file'
    )

    parser.add_argument(
        '--threshold',
        type=float,
        default=0.2,
        help='Regression threshold (default: 0.2 = 20%%)'
    )

    return parser.parse_args()


def main() -> int:
    """Main entry point for CLI."""
    args = parse_args()

    # Validate threshold
    if args.threshold <= 0 or args.threshold >= 1:
        print(f"ERROR: Threshold must be between 0 and 1, got {args.threshold}", file=sys.stderr)
        return 2

    # Check if current report exists
    current_path = Path(args.current)
    if not current_path.exists():
        print(f"ERROR: Current report not found: {args.current}", file=sys.stderr)
        return 2

    # Check if baseline exists
    baseline_path = Path(args.baseline)
    if not baseline_path.exists():
        print(f"ERROR: Baseline file not found: {args.baseline}", file=sys.stderr)
        return 2

    # Parse current metrics
    try:
        current_metrics = parse_lighthouse_metrics(args.current)
    except FileNotFoundError:
        print(f"ERROR: Current report not found: {args.current}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in current report: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: Failed to parse current report: {e}", file=sys.stderr)
        return 2

    # Parse baseline metrics
    try:
        # Baseline file might be in different format (simplified JSON)
        with open(args.baseline, 'r') as f:
            baseline_data = json.load(f)

        # Handle both full Lighthouse report and simplified baseline format
        if 'metrics' in baseline_data:
            # Simplified baseline format
            baseline_metrics = baseline_data['metrics']
        elif 'categories' in baseline_data:
            # Full Lighthouse report format
            baseline_metrics = parse_lighthouse_metrics(args.baseline)
        else:
            # Assume it's already a metrics dict
            baseline_metrics = baseline_data

    except FileNotFoundError:
        print(f"ERROR: Baseline file not found: {args.baseline}", file=sys.stderr)
        return 2
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in baseline: {e}", file=sys.stderr)
        return 2
    except Exception as e:
        print(f"ERROR: Failed to parse baseline: {e}", file=sys.stderr)
        return 2

    # Print comparison header
    print("=" * 80)
    print("Lighthouse Regression Detection")
    print("=" * 80)
    print(f"Current:  {args.current}")
    print(f"Baseline: {args.baseline}")
    print(f"Threshold: {args.threshold * 100:.0f}%")
    print("=" * 80)

    # Print current metrics
    print("\n[Current Metrics]")
    print(f"  Performance Score:  {current_metrics.get('performance_score', 0):.0f}/100")
    print(f"  Accessibility Score: {current_metrics.get('accessibility_score', 0):.0f}/100")
    print(f"  Best Practices:      {current_metrics.get('best_practices_score', 0):.0f}/100")
    print(f"  SEO Score:           {current_metrics.get('seo_score', 0):.0f}/100")
    print(f"  FCP:                 {current_metrics.get('first_contentful_paint', 0) or 0:.0f}ms")
    print(f"  LCP:                 {current_metrics.get('largest_contentful_paint', 0) or 0:.0f}ms")
    print(f"  TBT:                 {current_metrics.get('total_blocking_time', 0) or 0:.0f}ms")
    print(f"  CLS:                 {current_metrics.get('cumulative_layout_shift', 0) or 0:.3f}")
    print(f"  Speed Index:         {current_metrics.get('speed_index', 0) or 0:.0f}ms")

    # Print baseline metrics
    print("\n[Baseline Metrics]")
    print(f"  Performance Score:  {baseline_metrics.get('performance_score', 0):.0f}/100")
    print(f"  Accessibility Score: {baseline_metrics.get('accessibility_score', 0):.0f}/100")
    print(f"  Best Practices:      {baseline_metrics.get('best_practices_score', 0):.0f}/100")
    print(f"  SEO Score:           {baseline_metrics.get('seo_score', 0):.0f}/100")
    print(f"  FCP:                 {baseline_metrics.get('first_contentful_paint', 0) or 0:.0f}ms")
    print(f"  LCP:                 {baseline_metrics.get('largest_contentful_paint', 0) or 0:.0f}ms")
    print(f"  TBT:                 {baseline_metrics.get('total_blocking_time', 0) or 0:.0f}ms")
    print(f"  CLS:                 {baseline_metrics.get('cumulative_layout_shift', 0) or 0:.3f}")
    print(f"  Speed Index:         {baseline_metrics.get('speed_index', 0) or 0:.0f}ms")

    # Check for regressions
    has_regression, regression_messages = check_regression(
        current_metrics,
        baseline_metrics,
        args.threshold
    )

    # Print regression results
    print("\n" + "=" * 80)
    if has_regression:
        print("REGRESSION DETECTED!")
        print("=" * 80)
        for msg in regression_messages:
            print(f"  {msg}")
        print("=" * 80)
        print("\nAction Required: Investigate performance degradation")
        return 1
    else:
        print("NO REGRESSION DETECTED")
        print("=" * 80)
        print("\nAll metrics within acceptable threshold")
        return 0


if __name__ == '__main__':
    sys.exit(main())
