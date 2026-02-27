#!/usr/bin/env python3
"""
E2E Test Results Aggregator

Combines E2E test results from web (Playwright), mobile (Detox),
and desktop (WebDriverIO) platforms into a unified report.

Usage:
    python e2e_aggregator.py --web results/web.json \
                             --mobile results/mobile.json \
                             --desktop results/desktop.json \
                             --output results/e2e_unified.json
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def extract_metrics(results: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """Extract key metrics from platform-specific results."""
    # Handle different result formats (Playwright pytest, Detox, WebDriverIO)
    if "stats" in results:
        # Playwright pytest format
        return {
            "platform": platform,
            "total": results["stats"].get("total", 0),
            "passed": results["stats"].get("passed", 0),
            "failed": results["stats"].get("failed", 0),
            "skipped": results["stats"].get("skipped", 0),
            "duration": results["stats"].get("duration", 0),
        }
    elif "testResults" in results:
        # Detox format
        total = len(results.get("testResults", []))
        passed = sum(1 for r in results.get("testResults", []) if r.get("status") == "passed")
        return {
            "platform": platform,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "skipped": 0,
            "duration": results.get("duration", 0),
        }
    else:
        # WebDriverIO or unknown format
        return {
            "platform": platform,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "error": "Unknown format",
        }


def calculate_aggregate_metrics(platform_metrics: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics across all platforms."""
    total_tests = sum(m.get("total", 0) for m in platform_metrics)
    total_passed = sum(m.get("passed", 0) for m in platform_metrics)
    total_failed = sum(m.get("failed", 0) for m in platform_metrics)
    total_duration = sum(m.get("duration", 0) for m in platform_metrics)

    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(pass_rate, 2),
        "total_duration_seconds": total_duration,
        "platforms": len(platform_metrics),
    }


def generate_summary(
    aggregate: Dict[str, Any],
    platform_metrics: List[Dict[str, Any]],
) -> str:
    """Generate human-readable summary."""
    lines = [
        "# E2E Test Results Summary",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Aggregate Results",
        f"- Total Tests: {aggregate['total_tests']}",
        f"- Passed: {aggregate['total_passed']}",
        f"- Failed: {aggregate['total_failed']}",
        f"- Pass Rate: {aggregate['pass_rate']}%",
        f"- Duration: {aggregate['total_duration_seconds']}s",
        "",
        "## Platform Breakdown",
    ]

    for metrics in platform_metrics:
        platform = metrics["platform"].upper()
        lines.append(f"### {platform}")
        lines.append(f"- Tests: {metrics['total']}")
        lines.append(f"- Passed: {metrics['passed']}")
        lines.append(f"- Failed: {metrics['failed']}")
        lines.append(f"- Duration: {metrics['duration']}s")
        lines.append("")

    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Aggregate E2E test results")
    parser.add_argument("--web", help="Web platform results JSON")
    parser.add_argument("--mobile", help="Mobile platform results JSON")
    parser.add_argument("--desktop", help="Desktop platform results JSON")
    parser.add_argument("--output", required=True, help="Output JSON file")
    parser.add_argument("--summary", help="Output summary markdown file")
    args = parser.parse_args()

    platform_metrics = []

    # Load and extract metrics from each platform
    if args.web:
        web_results = load_json(args.web)
        platform_metrics.append(extract_metrics(web_results, "web"))

    if args.mobile:
        mobile_results = load_json(args.mobile)
        platform_metrics.append(extract_metrics(mobile_results, "mobile"))

    if args.desktop:
        desktop_results = load_json(args.desktop)
        platform_metrics.append(extract_metrics(desktop_results, "desktop"))

    # Calculate aggregate metrics
    aggregate = calculate_aggregate_metrics(platform_metrics)

    # Prepare output
    output = {
        "timestamp": datetime.now().isoformat(),
        "aggregate": aggregate,
        "platforms": platform_metrics,
    }

    # Write JSON output
    Path(args.output).parent.mkdir(parents=True, exist_ok=True)
    Path(args.output).write_text(json.dumps(output, indent=2))

    # Write summary markdown
    if args.summary:
        summary = generate_summary(aggregate, platform_metrics)
        Path(args.summary).write_text(summary)

    print(f"E2E results aggregated to {args.output}")
    print(f"Aggregate: {aggregate['total_passed']}/{aggregate['total_tests']} passed ({aggregate['pass_rate']}%)")

    # Exit with error code if any tests failed
    if aggregate["total_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
