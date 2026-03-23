#!/usr/bin/env python3
"""
Allure Result Aggregator

Converts pytest JSON results to Allure format and aggregates results
from all platforms (backend, web, mobile) into unified Allure report.

Usage:
    python allure_aggregator.py convert-pytest --input report.json --output allure-results/backend --platform backend
    python allure_aggregator.py aggregate-allure --backend allure-results/backend --web allure-results/web --output allure-results/
"""
import argparse
import json
import os
import shutil
from pathlib import Path
from typing import Dict, List, Any, Optional


def load_json(file_path: str) -> Dict[str, Any]:
    """Load JSON file with error handling."""
    path = Path(file_path)
    if not path.exists():
        return {"error": f"File not found: {file_path}"}
    try:
        return json.loads(path.read_text())
    except json.JSONDecodeError as e:
        return {"error": f"Invalid JSON: {e}"}


def parse_cargo_json_line(line: str) -> Optional[Dict[str, Any]]:
    """Parse a single line of cargo test JSON output.

    Args:
        line: Single line from cargo test --format json output

    Returns:
        Parsed test dict if line is a test result, None otherwise
    """
    try:
        data = json.loads(line.strip())
        if data.get("type") == "test":
            return {
                "name": data.get("name", "unknown"),
                "passed": data.get("passed", False),
            }
    except (json.JSONDecodeError, KeyError):
        pass
    return None


def extract_tauri_metrics(results: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """Extract metrics from Tauri cargo test JSON format.

    Args:
        results: Test results dict (may have stats from pre-processing or raw cargo data)
        platform: Platform name (desktop)

    Returns:
        Metrics dict matching Playwright pytest format
    """
    # If results already have stats key (pre-processed by CI), use that
    if "stats" in results:
        return {
            "platform": platform,
            "total": results["stats"].get("total", 0),
            "passed": results["stats"].get("passed", 0),
            "failed": results["stats"].get("failed", 0),
            "skipped": results["stats"].get("skipped", 0),
            "duration": results["stats"].get("duration", 0),
        }

    # Parse raw cargo test results
    if "testResults" in results:
        test_results = results.get("testResults", [])
        total = len(test_results)
        passed = sum(1 for r in test_results if r.get("passed", False))
        return {
            "platform": platform,
            "total": total,
            "passed": passed,
            "failed": total - passed,
            "skipped": 0,
            "duration": results.get("duration", 0),
        }

    # Unknown Tauri format
    return {
        "platform": platform,
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "error": "Unknown Tauri format",
    }


def extract_metrics(results: Dict[str, Any], platform: str) -> Dict[str, Any]:
    """Extract key metrics from platform-specific results.

    Args:
        results: Platform-specific test results dict
        platform: Platform name (web, mobile, desktop)

    Returns:
        Metrics dict with total/passed/failed/skipped/duration fields
    """
    # Check for errors first
    if "error" in results:
        return {
            "platform": platform,
            "total": 0,
            "passed": 0,
            "failed": 0,
            "skipped": 0,
            "duration": 0,
            "error": results["error"],
        }

    # Playwright pytest format (used by both web E2E and mobile API tests)
    if "stats" in results:
        return {
            "platform": platform,
            "total": results["stats"].get("total", 0),
            "passed": results["stats"].get("passed", 0),
            "failed": results["stats"].get("failed", 0),
            "skipped": results["stats"].get("skipped", 0),
            "duration": results["stats"].get("duration", 0),
        }

    # Tauri cargo test format (desktop)
    # Note: Mobile API tests use pytest (same as Playwright), no separate Detox parser needed
    if "testResults" in results or "test_suites" in results:
        return extract_tauri_metrics(results, platform)

    # Unknown format
    return {
        "platform": platform,
        "total": 0,
        "passed": 0,
        "failed": 0,
        "skipped": 0,
        "duration": 0,
        "error": f"Unknown format for {platform}: missing stats or testResults keys",
    }


def convert_pytest_to_allure(
    pytest_json_path: str,
    output_dir: str,
    platform: str
) -> int:
    """
    Convert pytest JSON results to Allure format.

    Args:
        pytest_json_path: Path to pytest JSON report
        output_dir: Allure results output directory
        platform: Platform name (backend, web, mobile)

    Returns:
        Number of test results converted
    """
    results = load_json(pytest_json_path)
    if "error" in results:
        print(f"Error loading pytest JSON: {results['error']}")
        return 0

    os.makedirs(output_dir, exist_ok=True)
    count = 0

    # Parse pytest JSON format (from pytest-json-report)
    tests = results.get("tests", [])
    for test in tests:
        test_name = test.get("name", "unknown")
        outcome = test.get("outcome", "passed")  # passed, failed, skipped

        # Convert to Allure format
        allure_result = {
            "name": f"[{platform}] {test_name}",
            "status": "passed" if outcome == "passed" else ("failed" if outcome == "failed" else "skipped"),
            "statusDetails": {
                "message": test.get("call", {}).get("longrepr", ""),
                "trace": test.get("call", {}).get("traceback", "")
            } if outcome == "failed" else {},
            "steps": [],
            "attachments": [],
            "parameters": [
                {"name": "platform", "value": platform},
                {"name": "file", "value": test.get("file", "")}
            ],
            "start": int(test.get("setup", {}).get("duration", 0) * 1000),
            "stop": int(test.get("duration", 0) * 1000)
        }

        # Write to Allure results directory
        test_id = f"{platform}_{test_name.replace('::', '_').replace('/', '_')}"
        result_file = os.path.join(output_dir, f"{test_id}-result.json")
        with open(result_file, 'w') as f:
            json.dump(allure_result, f)
        count += 1

    print(f"Converted {count} {platform} tests to Allure format")
    return count


def aggregate_allure_results(
    backend_results: str,
    web_results: str,
    mobile_results: str,
    output_dir: str
) -> int:
    """
    Aggregate Allure results from all platforms.

    Args:
        backend_results: Path to backend Allure results
        web_results: Path to web Allure results
        mobile_results: Path to mobile Allure results
        output_dir: Unified Allure results directory

    Returns:
        Total number of results aggregated
    """
    os.makedirs(output_dir, exist_ok=True)
    total = 0

    for platform, results_dir in [
        ("backend", backend_results),
        ("web", web_results),
        ("mobile", mobile_results)
    ]:
        if os.path.exists(results_dir):
            for file in os.listdir(results_dir):
                if file.endswith("-result.json"):
                    src = os.path.join(results_dir, file)
                    dst = os.path.join(output_dir, f"{platform}_{file}")
                    shutil.copy2(src, dst)
                    total += 1

    print(f"Aggregated {total} Allure results from all platforms")
    return total


def main():
    parser = argparse.ArgumentParser(
        description="Convert pytest to Allure and aggregate results"
    )
    subparsers = parser.add_subparsers(dest="command", help="Command to run")

    # convert-pytest command
    convert_parser = subparsers.add_parser("convert-pytest", help="Convert pytest JSON to Allure")
    convert_parser.add_argument("--input", required=True, help="Pytest JSON report path")
    convert_parser.add_argument("--output", required=True, help="Allure results output directory")
    convert_parser.add_argument("--platform", required=True, choices=["backend", "web", "mobile"], help="Platform name")

    # aggregate-allure command
    aggregate_parser = subparsers.add_parser("aggregate-allure", help="Aggregate Allure results from all platforms")
    aggregate_parser.add_argument("--backend", required=True, help="Backend Allure results directory")
    aggregate_parser.add_argument("--web", required=True, help="Web Allure results directory")
    aggregate_parser.add_argument("--mobile", required=True, help="Mobile Allure results directory")
    aggregate_parser.add_argument("--output", required=True, help="Unified Allure results directory")

    args = parser.parse_args()

    if args.command == "convert-pytest":
        count = convert_pytest_to_allure(args.input, args.output, args.platform)
        print(f"✅ Converted {count} test results to Allure format")
    elif args.command == "aggregate-allure":
        total = aggregate_allure_results(args.backend, args.web, args.mobile, args.output)
        print(f"✅ Aggregated {total} Allure results")
    else:
        parser.print_help()
        sys.exit(1)


if __name__ == "__main__":
    import sys
    main()
