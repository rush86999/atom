"""
Flaky Test Tracker - Tracks test results across multiple runs to identify unstable tests.

A test is considered flaky if:
- It fails in at least 1 of the last N runs (default: 5)
- Its pass rate is below threshold (default: 80%)
- It has been run at least minimum times (default: 3)

Usage:
    from scripts.flaky_test_tracker import FlakyTestTracker

    tracker = FlakyTestTracker()
    tracker.update_from_pytest_report("pytest_report.json")
    flaky_tests = tracker.get_flaky_tests(threshold=0.8)
"""
import json
import os
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional


class FlakyTestTracker:
    """Tracks test results across runs to identify flaky tests."""

    def __init__(self, data_file: str = "backend/tests/e2e_ui/data/flaky_tests.json"):
        """Initialize tracker with data file path."""
        self.data_file = Path(data_file)
        self.data: Dict = self._load_data()

    def _load_data(self) -> Dict:
        """Load historical test data from JSON file."""
        if self.data_file.exists():
            with open(self.data_file, 'r') as f:
                return json.load(f)
        return {
            "tests": {},
            "last_updated": None,
            "total_runs": 0
        }

    def _save_data(self) -> None:
        """Save test data to JSON file."""
        self.data["last_updated"] = datetime.now().isoformat()
        self.data_file.parent.mkdir(parents=True, exist_ok=True)
        with open(self.data_file, 'w') as f:
            json.dump(self.data, f, indent=2)

    def update_from_pytest_report(self, report_file: str) -> None:
        """Update tracker data from pytest JSON report."""
        with open(report_file, 'r') as f:
            report = json.load(f)

        summary = report.get("summary", {})
        self.data["total_runs"] += 1

        # Process each test result
        for test_name, test_result in report.get("tests", {}).items():
            if test_name not in self.data["tests"]:
                self.data["tests"][test_name] = {
                    "runs": [],
                    "total_runs": 0,
                    "passed": 0,
                    "failed": 0,
                    "skipped": 0,
                    "errors": 0
                }

            test_data = self.data["tests"][test_name]
            test_data["total_runs"] += 1

            # Record outcome
            outcome = test_result.get("outcome", "unknown")
            test_data["runs"].append({
                "run": self.data["total_runs"],
                "outcome": outcome,
                "timestamp": datetime.now().isoformat()
            })

            if outcome == "passed":
                test_data["passed"] += 1
            elif outcome == "failed":
                test_data["failed"] += 1
            elif outcome == "skipped":
                test_data["skipped"] += 1
            else:
                test_data["errors"] += 1

            # Keep only last N runs (default: 10)
            test_data["runs"] = test_data["runs"][-10:]

        self._save_data()

    def get_flaky_tests(
        self,
        pass_threshold: float = 0.8,
        min_runs: int = 3,
        last_n_runs: Optional[int] = None
    ) -> List[Dict]:
        """
        Get list of flaky tests.

        Args:
            pass_threshold: Minimum pass rate (0.0-1.0)
            min_runs: Minimum runs before considering test
            last_n_runs: Only consider last N runs (None = all runs)

        Returns:
            List of flaky test info dicts
        """
        flaky = []

        for test_name, test_data in self.data["tests"].items():
            # Skip tests with insufficient runs
            if test_data["total_runs"] < min_runs:
                continue

            # Calculate pass rate
            runs_to_consider = test_data["runs"][-last_n_runs:] if last_n_runs else test_data["runs"]
            if not runs_to_consider:
                continue

            passed = sum(1 for r in runs_to_consider if r["outcome"] == "passed")
            total = len(runs_to_consider)
            pass_rate = passed / total if total > 0 else 0

            # Check if flaky (below threshold AND has at least one failure)
            has_failures = any(r["outcome"] in ["failed", "error"] for r in runs_to_consider)
            if pass_rate < pass_threshold and has_failures:
                flaky.append({
                    "test": test_name,
                    "pass_rate": pass_rate,
                    "total_runs": total,
                    "passed": passed,
                    "failed": total - passed,
                    "last_outcome": runs_to_consider[-1]["outcome"]
                })

        # Sort by pass rate (most flaky first)
        flaky.sort(key=lambda x: x["pass_rate"])
        return flaky

    def get_test_history(self, test_name: str) -> Dict:
        """Get historical data for a specific test."""
        return self.data["tests"].get(test_name, {})

    def get_summary(self) -> Dict:
        """Get summary of tracked test data."""
        total_tests = len(self.data["tests"])
        flaky = self.get_flaky_tests()

        return {
            "total_tests": total_tests,
            "total_runs": self.data["total_runs"],
            "flaky_count": len(flaky),
            "flaky_tests": [t["test"] for t in flaky[:10]],  # Top 10
            "last_updated": self.data["last_updated"]
        }


if __name__ == "__main__":
    # CLI interface for manual testing
    import sys

    tracker = FlakyTestTracker()

    if len(sys.argv) > 1:
        # Update from report file
        report_file = sys.argv[1]
        tracker.update_from_pytest_report(report_file)
        print(f"Updated tracker from {report_file}")

    # Print flaky tests
    flaky = tracker.get_flaky_tests()
    print(f"\nFound {len(flaky)} flaky tests:")
    for test in flaky:
        print(f"  - {test['test']}: {test['pass_rate']:.1%} pass rate ({test['passed']}/{test['total_runs']} runs)")
