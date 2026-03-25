"""
ResultAggregator service for normalizing discovery method results.

This module provides the ResultAggregator that converts discovery
method-specific results (fuzzing campaigns, chaos experiments, property
tests, browser discovery) into normalized BugReport objects.
"""

import os
import sys
from pathlib import Path
from typing import List, Dict, Any
from datetime import datetime

# Add backend to path
backend_dir = Path(__file__).parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, generate_error_signature


class ResultAggregator:
    """
    Aggregates results from all discovery methods into BugReport objects.

    Each discovery method has its own result format. ResultAggregator
    normalizes all results into BugReport objects for unified
    deduplication, severity classification, and bug filing.
    """

    def aggregate_fuzzing_results(self, fuzzing_campaign: Dict) -> List[BugReport]:
        """
        Convert fuzzing campaign results to BugReport objects.

        Args:
            fuzzing_campaign: Dict with campaign_id, crash_dir, executions, crashes

        Returns:
            List of BugReport objects
        """
        reports = []
        crash_dir = Path(fuzzing_campaign.get("crash_dir", ""))
        campaign_id = fuzzing_campaign.get("campaign_id", "unknown")

        if not crash_dir.exists():
            return reports

        # Process crash files
        crash_files = list(crash_dir.glob("*.input"))

        for crash_file in crash_files:
            crash_log_file = crash_file.with_suffix(".log")

            # Read crash log
            crash_log = ""
            stack_trace = ""
            if crash_log_file.exists():
                with open(crash_log_file, "r") as f:
                    crash_log = f.read()
                    stack_trace = crash_log

            # Generate error signature from crash log
            error_signature = generate_error_signature(crash_log or str(crash_file))

            # Extract target endpoint from campaign_id
            target_endpoint = campaign_id.split("_")[0] if "_" in campaign_id else campaign_id

            report = BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name=f"fuzzing_{target_endpoint}",
                error_message=crash_log[:200] if crash_log else f"Crash in {crash_file.name}",
                error_signature=error_signature,
                metadata={
                    "campaign_id": campaign_id,
                    "crash_file": str(crash_file),
                    "target_endpoint": target_endpoint,
                    "executions": fuzzing_campaign.get("executions", 0)
                },
                stack_trace=stack_trace[:1000] if stack_trace else None
            )

            reports.append(report)

        return reports

    def aggregate_chaos_results(self, chaos_results: Dict) -> List[BugReport]:
        """
        Convert chaos experiment results to BugReport objects.

        Args:
            chaos_results: Dict from ChaosCoordinator.run_experiment()

        Returns:
            List of BugReport objects (empty if experiment succeeded)
        """
        reports = []

        # Check if chaos experiment failed (resilience failure)
        if not chaos_results.get("success", False):
            experiment_name = chaos_results.get("experiment_name", "unknown_chaos")

            # Generate error signature from baseline + failure metrics
            baseline = chaos_results.get("baseline", {})
            failure = chaos_results.get("failure", {})
            signature_content = f"{baseline} | {failure}"
            error_signature = generate_error_signature(signature_content)

            # Check if there's an error in results
            error_message = chaos_results.get("error", "Resilience failure: system did not degrade gracefully")

            report = BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name=experiment_name,
                error_message=error_message,
                error_signature=error_signature,
                metadata={
                    "baseline_metrics": baseline,
                    "failure_metrics": failure,
                    "recovery_metrics": chaos_results.get("recovery", {}),
                    "blast_radius": "test_database_only"
                }
            )

            reports.append(report)

        return reports

    def aggregate_property_results(self, property_output: str) -> List[BugReport]:
        """
        Convert property test failures to BugReport objects.

        Args:
            property_output: Pytest stdout from property test run

        Returns:
            List of BugReport objects for failed property tests
        """
        reports = []

        # Parse pytest output for FAILED lines
        failed_tests = self._parse_property_test_failures(property_output)

        for test_name, error_message in failed_tests.items():
            # Generate error signature from test name + error message
            error_signature = generate_error_signature(f"{test_name} | {error_message}")

            report = BugReport(
                discovery_method=DiscoveryMethod.PROPERTY,
                test_name=test_name,
                error_message=error_message,
                error_signature=error_signature,
                metadata={
                    "property_test": True,
                    "invariant_violation": True
                }
            )

            reports.append(report)

        return reports

    def aggregate_browser_results(self, browser_bugs: List[Dict]) -> List[BugReport]:
        """
        Convert browser discovery bugs to BugReport objects.

        Args:
            browser_bugs: List of bug dicts from ExplorationAgent

        Returns:
            List of BugReport objects
        """
        reports = []

        for bug in browser_bugs:
            # Generate error signature from bug type + URL + error message
            bug_type = bug.get("type", "unknown")
            url = bug.get("url", "")
            error_msg = bug.get("error", "")
            error_signature = generate_error_signature(f"{bug_type} | {url} | {error_msg}")

            report = BugReport(
                discovery_method=DiscoveryMethod.BROWSER,
                test_name=f"browser_{bug_type}",
                error_message=error_msg[:200] if error_msg else f"{bug_type} detected",
                error_signature=error_signature,
                metadata={
                    "url": url,
                    "bug_type": bug_type,
                    "screenshot": bug.get("screenshot"),
                    "element": bug.get("element")
                },
                screenshot_path=bug.get("screenshot")
            )

            reports.append(report)

        return reports

    def _parse_property_test_failures(self, pytest_output: str) -> Dict[str, str]:
        """
        Parse pytest output to extract failed tests and errors.

        Args:
            pytest_output: Pytest stdout string

        Returns:
            Dict mapping test_name to error_message
        """
        failed_tests = {}

        for line in pytest_output.split("\n"):
            # Parse FAILED lines
            if "FAILED" in line and "::" in line:
                parts = line.split()
                if len(parts) >= 2:
                    test_name = parts[1]
                    # For property tests, extract test name without path
                    if "::test_" in test_name:
                        test_name = test_name.split("::")[-1]
                    error_message = "Property test failed - invariant violation detected"
                    failed_tests[test_name] = error_message

        return failed_tests
