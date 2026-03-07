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
