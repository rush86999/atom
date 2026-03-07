#!/usr/bin/env python3
"""
CI Status Aggregator

Combines test results from all platform jobs (backend, frontend, mobile, desktop)
into a unified status report with per-platform breakdown, pass rates, and markdown summary.

Usage:
    python ci_status_aggregator.py \
        --backend results/backend/pytest_report.json \
        --frontend results/frontend/test-results.json \
        --mobile results/mobile/test-results.json \
        --desktop results/desktop/cargo_test_results.json \
        --output results/ci_status.json \
        --summary results/ci_summary.md
"""
import argparse
import json
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file with error handling.

    Args:
        file_path: Path to JSON file

    Returns:
        Parsed JSON dict, or error dict if file not found or invalid JSON
    """
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}

    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def parse_pytest_results(results: Dict) -> Dict[str, Any]:
    """Parse pytest JSON report format.

    Args:
        results: pytest JSON report dict with 'summary' key

    Returns:
        Platform metrics dict with total/passed/failed/skipped/duration/pass_rate
    """
    # Check for errors first
    if "error" in results:
        return {
            "platform": "backend",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "error": results["error"],
        }

    # Extract summary from pytest JSON report
    summary = results.get("summary", {})
    total = summary.get("total", 0)
    passed = summary.get("passed", 0)
    failed = summary.get("failed", 0)
    skipped = summary.get("skipped", 0)
    duration = summary.get("duration", 0)

    # Calculate pass rate
    pass_rate = (passed / total * 100) if total > 0 else 0

    return {
        "platform": "backend",
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration": duration,
        "pass_rate": round(pass_rate, 2),
    }


def parse_jest_results(results: Dict) -> Dict[str, Any]:
    """Parse Jest test-results.json format.

    Args:
        results: Jest JSON results dict with numTotalTests/numFailedTests/numPendingTests

    Returns:
        Platform metrics dict with total/passed/failed/skipped/duration/pass_rate
    """
    # Check for errors first
    if "error" in results:
        return {
            "platform": "frontend",  # Will be overridden by caller
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "error": results["error"],
        }

    # Extract metrics from Jest test results
    total = results.get("numTotalTests", 0)
    failed = results.get("numFailedTests", 0)
    skipped = results.get("numPendingTests", 0)
    passed = total - failed - skipped

    # Jest doesn't always report duration in JSON output
    duration = results.get("duration", 0)

    # Calculate pass rate
    pass_rate = (passed / total * 100) if total > 0 else 0

    return {
        "platform": "frontend",  # Will be overridden by caller
        "total": total,
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "duration": duration,
        "pass_rate": round(pass_rate, 2),
    }


def parse_cargo_results(results: Dict) -> Dict[str, Any]:
    """Parse cargo test JSON format (pre-processed with stats key).

    Args:
        results: Cargo test results dict with 'stats' key (pre-processed by CI)

    Returns:
        Platform metrics dict with total/passed/failed/skipped/duration/pass_rate
    """
    # Check for errors first
    if "error" in results:
        return {
            "platform": "desktop",
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "error": results["error"],
        }

    # Use pre-processed stats if available (from CI script)
    if "stats" in results:
        stats = results["stats"]
        total = stats.get("total", 0)
        passed = stats.get("passed", 0)
        failed = stats.get("failed", 0)
        skipped = stats.get("skipped", 0)
        duration = stats.get("duration", 0)

        # Calculate pass rate
        pass_rate = (passed / total * 100) if total > 0 else 0

        return {
            "platform": "desktop",
            "total": total,
            "passed": passed,
            "failed": failed,
            "skipped": skipped,
            "duration": duration,
            "pass_rate": round(pass_rate, 2),
        }

    # Unknown cargo format (no stats key)
    return {
        "platform": "desktop",
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "error": "Unknown cargo format: missing stats key",
    }


def aggregate_platform_status(platforms: List[Dict[str, Any]]) -> Dict[str, Any]:
    """Calculate aggregate metrics across all platforms.

    Args:
        platforms: List of platform metrics dicts

    Returns:
        Aggregate metrics dict with total_tests/total_passed/total_failed/pass_rate/total_duration_seconds/platform_count
    """
    total_tests = sum(p.get("total", 0) for p in platforms)
    total_passed = sum(p.get("passed", 0) for p in platforms)
    total_failed = sum(p.get("failed", 0) for p in platforms)
    total_duration = sum(p.get("duration", 0) for p in platforms)

    # Calculate overall pass rate
    pass_rate = (total_passed / total_tests * 100) if total_tests > 0 else 0

    return {
        "total_tests": total_tests,
        "total_passed": total_passed,
        "total_failed": total_failed,
        "pass_rate": round(pass_rate, 2),
        "total_duration_seconds": total_duration,
        "platform_count": len(platforms),
    }


def generate_markdown_summary(
    aggregate: Dict[str, Any],
    platforms: List[Dict[str, Any]],
) -> str:
    """Generate markdown summary for PR comments and CI dashboards.

    Args:
        aggregate: Aggregate metrics across all platforms
        platforms: List of per-platform metrics dicts

    Returns:
        Formatted markdown string with header, overall results, platform breakdown table, and status
    """
    lines = [
        "# CI Test Results Summary",
        f"Generated: {datetime.now().isoformat()}",
        "",
        "## Overall Results",
        f"- **Total Tests**: {aggregate['total_tests']}",
        f"- **Passed**: {aggregate['total_passed']}",
        f"- **Failed**: {aggregate['total_failed']}",
        f"- **Pass Rate**: {aggregate['pass_rate']}%",
        f"- **Duration**: {aggregate['total_duration_seconds']}s",
        "",
        "## Platform Breakdown",
        "| Platform | Tests | Passed | Failed | Pass Rate | Duration |",
        "|----------|-------|--------|--------|-----------|----------|",
    ]

    # Add platform breakdown table rows
    for p in platforms:
        platform = p["platform"].upper()
        lines.append(
            f"| {platform} | {p['total']} | {p['passed']} | {p['failed']} | {p['pass_rate']:.1f}% | {p['duration']}s |"
        )

    lines.append("")
    lines.append("## Status")

    # Add status message
    if aggregate["total_failed"] == 0:
        lines.append("✅ All tests passed across all platforms")
    else:
        lines.append(f"❌ {aggregate['total_failed']} test(s) failed across platforms")

    return "\n".join(lines)


def main():
    """Main entry point for CI status aggregation."""
    parser = argparse.ArgumentParser(
        description="Aggregate CI status from all platform test results"
    )
    parser.add_argument("--backend", help="Backend pytest JSON report path")
    parser.add_argument("--frontend", help="Frontend Jest JSON report path")
    parser.add_argument("--mobile", help="Mobile Jest JSON report path")
    parser.add_argument("--desktop", help="Desktop cargo JSON report path")
    parser.add_argument("--output", required=True, help="Output JSON file path")
    parser.add_argument("--summary", help="Output markdown summary file path")
    args = parser.parse_args()

    platforms = []

    # Load and parse each platform result if provided
    if args.backend:
        backend_results = load_json(args.backend)
        platforms.append(parse_pytest_results(backend_results))

    if args.frontend:
        frontend_results = load_json(args.frontend)
        frontend_metrics = parse_jest_results(frontend_results)
        frontend_metrics["platform"] = "frontend"
        platforms.append(frontend_metrics)

    if args.mobile:
        mobile_results = load_json(args.mobile)
        mobile_metrics = parse_jest_results(mobile_results)
        mobile_metrics["platform"] = "mobile"
        platforms.append(mobile_metrics)

    if args.desktop:
        desktop_results = load_json(args.desktop)
        platforms.append(parse_cargo_results(desktop_results))

    # Calculate aggregate metrics
    aggregate = aggregate_platform_status(platforms)

    # Prepare output dict
    output = {
        "timestamp": datetime.now().isoformat(),
        "aggregate": aggregate,
        "platforms": platforms,
    }

    # Write JSON output (create parent dirs if needed)
    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(output, indent=2))

    # Write markdown summary if --summary provided
    if args.summary:
        summary = generate_markdown_summary(aggregate, platforms)
        summary_path = Path(args.summary)
        summary_path.parent.mkdir(parents=True, exist_ok=True)
        summary_path.write_text(summary)

    # Print summary to console
    print(f"CI Status: {aggregate['total_passed']}/{aggregate['total_tests']} passed ({aggregate['pass_rate']}%)")

    # Exit code 1 if any tests failed, 0 if all passed
    if aggregate["total_failed"] > 0:
        sys.exit(1)


if __name__ == "__main__":
    main()
