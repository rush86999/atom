#!/usr/bin/env python3
"""
Stress Test Scheduler and Result Aggregator

This module provides functionality to:
- Aggregate test results from multiple sources (JUnit XML, k6 JSON)
- Calculate pass/fail rates and performance metrics
- Generate summary reports with trend analysis
- Send alerts via Slack or email
- Track historical performance trends
"""

import argparse
import json
import os
import sys
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Any, Optional
import xml.etree.ElementTree as ET

try:
    import requests
except ImportError:
    requests = None


class StressTestScheduler:
    """Scheduler and aggregator for stress test results."""

    def __init__(self, results_dir: str = ".", output_dir: str = "."):
        """
        Initialize the stress test scheduler.

        Args:
            results_dir: Directory containing test results
            output_dir: Directory for output files
        """
        self.results_dir = Path(results_dir)
        self.output_dir = Path(output_dir)
        self.output_dir.mkdir(parents=True, exist_ok=True)

    def aggregate_results(self, results_file: str) -> Dict[str, Any]:
        """
        Aggregate test results from JUnit XML or k6 JSON files.

        Args:
            results_file: Path to results file (JUnit XML or JSON)

        Returns:
            Dictionary with aggregated results
        """
        results_path = self.results_dir / results_file

        if not results_path.exists():
            return self._empty_summary()

        # Determine file type and parse accordingly
        if results_file.endswith('.xml'):
            return self._parse_junit_xml(results_path)
        elif results_file.endswith('.json'):
            return self._parse_k6_json(results_path)
        else:
            return self._empty_summary()

    def _parse_junit_xml(self, xml_path: Path) -> Dict[str, Any]:
        """Parse JUnit XML test results."""
        tree = ET.parse(xml_path)
        root = tree.getroot()

        total_tests = 0
        total_failures = 0
        total_errors = 0
        total_skipped = 0

        test_cases_by_category = {}

        for testsuite in root.findall('testsuite'):
            category = testsuite.get('name', 'unknown')
            tests = int(testsuite.get('tests', 0))
            failures = int(testsuite.get('failures', 0))
            errors = int(testsuite.get('errors', 0))
            skipped = int(testsuite.get('skipped', 0))

            total_tests += tests
            total_failures += failures
            total_errors += errors
            total_skipped += skipped

            test_cases_by_category[category] = {
                "total": tests,
                "passed": tests - failures - errors - skipped,
                "failed": failures + errors,
                "skipped": skipped
            }

        passed = total_tests - total_failures - total_errors - total_skipped
        failed = total_failures + total_errors
        pass_rate = passed / total_tests if total_tests > 0 else 0.0

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "skipped": total_skipped,
                "pass_rate": round(pass_rate, 3)
            },
            "by_category": test_cases_by_category,
            "performance": {
                "p50_latency_ms": None,
                "p95_latency_ms": None,
                "p99_latency_ms": None,
                "error_rate": round(failed / total_tests, 3) if total_tests > 0 else 0.0
            },
            "trends": {
                "pass_rate_change": None,
                "latency_change": None
            }
        }

    def _parse_k6_json(self, json_path: Path) -> Dict[str, Any]:
        """Parse k6 JSON test results."""
        with open(json_path, 'r') as f:
            data = json.load(f)

        # Extract metrics from k6 JSON output
        metrics = data.get('metrics', {})

        # Get HTTP request counts
        http_reqs = metrics.get('http_reqs', {})
        total_tests = http_reqs.get('values', {}).get('count', 0)

        # Get failed requests
        failed_reqs = metrics.get('http_req_failed', {})
        failed_rate = failed_reqs.get('values', {}).get('rate', 0) / 100 if failed_reqs else 0

        # Get response times
        response_times = metrics.get('http_req_duration', {})
        timings = response_times.get('values', {})

        passed = int(total_tests * (1 - failed_rate))
        failed = int(total_tests * failed_rate)

        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_tests": total_tests,
                "passed": passed,
                "failed": failed,
                "skipped": 0,
                "pass_rate": round(1 - failed_rate, 3)
            },
            "by_category": {
                "load": {
                    "total": total_tests,
                    "passed": passed,
                    "failed": failed,
                    "skipped": 0
                }
            },
            "performance": {
                "p50_latency_ms": int(timings.get('p(50)', 0)),
                "p95_latency_ms": int(timings.get('p(95)', 0)),
                "p99_latency_ms": int(timings.get('p(99)', 0)),
                "error_rate": round(failed_rate, 3)
            },
            "trends": {
                "pass_rate_change": None,
                "latency_change": None
            }
        }

    def _empty_summary(self) -> Dict[str, Any]:
        """Return empty summary structure."""
        return {
            "timestamp": datetime.utcnow().isoformat() + "Z",
            "summary": {
                "total_tests": 0,
                "passed": 0,
                "failed": 0,
                "skipped": 0,
                "pass_rate": 0.0
            },
            "by_category": {},
            "performance": {
                "p50_latency_ms": None,
                "p95_latency_ms": None,
                "p99_latency_ms": None,
                "error_rate": 0.0
            },
            "trends": {
                "pass_rate_change": None,
                "latency_change": None
            }
        }

    def calculate_trends(self, historical_results: List[Dict[str, Any]]) -> Dict[str, Any]:
        """
        Calculate trends by comparing current results to historical data.

        Args:
            historical_results: List of previous summary dictionaries

        Returns:
            Dictionary with trend metrics
        """
        if not historical_results or len(historical_results) < 2:
            return {
                "pass_rate_change": None,
                "latency_change": None,
                "sample_size": len(historical_results)
            }

        current = historical_results[-1]
        previous = historical_results[-2]

        # Calculate pass rate change
        current_rate = current.get("summary", {}).get("pass_rate", 0.0)
        previous_rate = previous.get("summary", {}).get("pass_rate", 0.0)
        pass_rate_change = round(current_rate - previous_rate, 3)

        # Calculate latency change
        current_p95 = current.get("performance", {}).get("p95_latency_ms", 0) or 0
        previous_p95 = previous.get("performance", {}).get("p95_latency_ms", 0) or 0
        latency_change = current_p95 - previous_p95

        return {
            "pass_rate_change": f"{pass_rate_change:+.3f}",
            "latency_change": f"{latency_change:+d}ms",
            "sample_size": len(historical_results)
        }

    def report_summary(self, summary_data: Dict[str, Any], slack: bool = False, email: bool = False):
        """
        Generate and print summary report.

        Args:
            summary_data: Summary dictionary from aggregate_results
            slack: If True, format for Slack
            email: If True, format for email
        """
        timestamp = summary_data.get("timestamp", "")
        summary = summary_data.get("summary", {})
        by_category = summary_data.get("by_category", {})
        performance = summary_data.get("performance", {})
        trends = summary_data.get("trends", {})

        print("\n" + "=" * 60)
        print(f"Stress Test Summary - {timestamp}")
        print("=" * 60)

        # Overall summary
        total = summary.get("total_tests", 0)
        passed = summary.get("passed", 0)
        failed = summary.get("failed", 0)
        pass_rate = summary.get("pass_rate", 0.0)

        print(f"\nOverall Results:")
        print(f"  Total Tests: {total}")
        print(f"  Passed: {passed}")
        print(f"  Failed: {failed}")
        print(f"  Pass Rate: {pass_rate:.1%}")

        # By category
        if by_category:
            print(f"\nResults by Category:")
            for category, results in by_category.items():
                cat_passed = results.get("passed", 0)
                cat_total = results.get("total", 0)
                cat_failed = results.get("failed", 0)
                print(f"  {category}: {cat_passed}/{cat_total} passed ({cat_failed} failed)")

        # Performance metrics
        p95 = performance.get("p95_latency_ms")
        error_rate = performance.get("error_rate", 0.0)

        if p95 is not None:
            print(f"\nPerformance Metrics:")
            print(f"  p95 Latency: {p95}ms")
            print(f"  Error Rate: {error_rate:.1%}")

        # Trends
        pass_change = trends.get("pass_rate_change")
        latency_change = trends.get("latency_change")

        if pass_change or latency_change:
            print(f"\nTrends:")
            if pass_change:
                print(f"  Pass Rate Change: {pass_change}")
            if latency_change:
                print(f"  Latency Change: {latency_change}")

        print("=" * 60 + "\n")

    def send_alert(self, test_failures: int, alert_type: str = "slack", webhook_url: Optional[str] = None):
        """
        Send alert for test failures.

        Args:
            test_failures: Number of test failures
            alert_type: Type of alert ("slack" or "email")
            webhook_url: Optional webhook URL (overrides env variable)
        """
        if test_failures == 0:
            print("No failures to report.")
            return

        if alert_type == "slack":
            self._send_slack_alert(test_failures, webhook_url)
        elif alert_type == "email":
            print("Email alerts not yet implemented.")
        else:
            print(f"Unknown alert type: {alert_type}")

    def _send_slack_alert(self, failures: int, webhook_url: Optional[str] = None):
        """Send Slack alert for test failures."""
        if not requests:
            print("requests library not available. Cannot send Slack alert.")
            return

        url = webhook_url or os.environ.get("SLACK_WEBHOOK_URL")

        if not url:
            print("SLACK_WEBHOOK_URL not set. Cannot send Slack alert.")
            return

        emoji = "🔴" if failures > 0 else "✅"
        text = f"{emoji} Stress Tests {'Failed' if failures > 0 else 'Passed'} ({datetime.utcnow().strftime('%Y-%m-%d')})\n\n"
        text += f"Summary: {failures} test failures detected.\n"
        text += f"View Details: {os.environ.get('GITHUB_SERVER_URL', 'https://github.com')}/{os.environ.get('GITHUB_REPOSITORY', 'atom/atom')}/actions/runs/{os.environ.get('GITHUB_RUN_ID', '')}"

        payload = {"text": text}

        try:
            response = requests.post(url, json=payload, timeout=10)
            response.raise_for_status()
            print(f"Slack alert sent successfully.")
        except Exception as e:
            print(f"Failed to send Slack alert: {e}")

    def save_summary(self, summary_data: Dict[str, Any], output_file: str):
        """
        Save summary to JSON file.

        Args:
            summary_data: Summary dictionary
            output_file: Output filename
        """
        output_path = self.output_dir / output_file

        with open(output_path, 'w') as f:
            json.dump(summary_data, f, indent=2)

        print(f"Summary saved to: {output_path}")


def main():
    """Main CLI entry point."""
    parser = argparse.ArgumentParser(description="Stress Test Scheduler and Result Aggregator")
    subparsers = parser.add_subparsers(dest="command", help="Command to execute")

    # Aggregate command
    aggregate_parser = subparsers.add_parser("aggregate", help="Aggregate test results")
    aggregate_parser.add_argument("--results-file", required=True, help="Path to results file")
    aggregate_parser.add_argument("--output", default="stress-test-summary.json", help="Output file")
    aggregate_parser.add_argument("--load-results", nargs="*", help="k6 load test results")
    aggregate_parser.add_argument("--network-results", help="Network test results")
    aggregate_parser.add_argument("--memory-results", help="Memory test results")

    # Report command
    report_parser = subparsers.add_parser("report", help="Generate summary report")
    report_parser.add_argument("--summary-file", required=True, help="Summary JSON file")
    report_parser.add_argument("--slack", action="store_true", help="Format for Slack")
    report_parser.add_argument("--email", action="store_true", help="Format for email")

    # Send alert command
    alert_parser = subparsers.add_parser("send_alert", help="Send alert for failures")
    alert_parser.add_argument("--results-file", required=True, help="Results file")
    alert_parser.add_argument("--alert-type", choices=["slack", "email"], default="slack", help="Alert type")
    alert_parser.add_argument("--webhook-url", help="Override webhook URL")

    args = parser.parse_args()

    if not args.command:
        parser.print_help()
        sys.exit(1)

    scheduler = StressTestScheduler()

    if args.command == "aggregate":
        summary = scheduler.aggregate_results(args.results_file)
        scheduler.save_summary(summary, args.output)
        scheduler.report_summary(summary)

    elif args.command == "report":
        with open(args.summary_file, 'r') as f:
            summary = json.load(f)
        scheduler.report_summary(summary, slack=args.slack, email=args.email)

    elif args.command == "send_alert":
        # Read results file to count failures
        if args.results_file.endswith('.xml'):
            tree = ET.parse(args.results_file)
            root = tree.getroot()
            failures = sum(int(ts.get('failures', 0)) + int(ts.get('errors', 0)) for ts in root.findall('testsuite'))
        elif args.results_file.endswith('.json'):
            with open(args.results_file, 'r') as f:
                data = json.load(f)
            failures = data.get("summary", {}).get("failed", 0)
        else:
            failures = 0

        scheduler.send_alert(failures, args.alert_type, args.webhook_url)


if __name__ == "__main__":
    main()
