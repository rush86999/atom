"""
Unit tests for flaky test detection functionality.

These tests verify the FlakyTestTracker module works correctly
without requiring browser fixtures or database setup.
"""
import json
import tempfile
from pathlib import Path

import pytest


def test_flaky_test_tracker_initialization():
    """Verify FlakyTestTracker initializes correctly."""
    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))

        assert tracker.data_file == data_file
        assert tracker.data["total_runs"] == 0
        assert len(tracker.data["tests"]) == 0


def test_flaky_test_tracker_update():
    """Verify tracker updates from pytest report."""
    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        # Create mock pytest report
        report_file = Path(tmpdir) / "pytest_report.json"
        mock_report = {
            "summary": {"total": 2, "passed": 1, "failed": 1},
            "tests": {
                "tests/test_foo.py::test_pass": {"outcome": "passed"},
                "tests/test_bar.py::test_fail": {"outcome": "failed"}
            }
        }
        report_file.write_text(json.dumps(mock_report))

        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))
        tracker.update_from_pytest_report(str(report_file))

        assert tracker.data["total_runs"] == 1
        assert len(tracker.data["tests"]) == 2
        assert tracker.data["tests"]["tests/test_foo.py::test_pass"]["passed"] == 1
        assert tracker.data["tests"]["tests/test_bar.py::test_fail"]["failed"] == 1


def test_flaky_test_detection():
    """Verify flaky tests are correctly identified."""
    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))

        # Simulate test with mixed results (flaky)
        test_name = "tests/test_flaky.py::test_intermittent"
        tracker.data["tests"][test_name] = {
            "runs": [
                {"outcome": "passed", "run": 1},
                {"outcome": "failed", "run": 2},
                {"outcome": "passed", "run": 3},
                {"outcome": "failed", "run": 4},
                {"outcome": "passed", "run": 5}
            ],
            "total_runs": 5,
            "passed": 3,
            "failed": 2
        }

        flaky = tracker.get_flaky_tests(pass_threshold=0.8, min_runs=3)

        assert len(flaky) == 1
        assert flaky[0]["test"] == test_name
        assert flaky[0]["pass_rate"] == 0.6  # 3/5 = 60%


def test_stable_test_not_flagged():
    """Verify stable tests are not flagged as flaky."""
    # Import here to avoid playwright fixture issues
    import sys
    sys.path.insert(0, str(Path(__file__).parent.parent.parent))
    from scripts.flaky_test_tracker import FlakyTestTracker

    with tempfile.TemporaryDirectory() as tmpdir:
        data_file = Path(tmpdir) / "flaky_tests.json"
        tracker = FlakyTestTracker(data_file=str(data_file))

        # Simulate stable test
        test_name = "tests/test_stable.py::test_reliable"
        tracker.data["tests"][test_name] = {
            "runs": [
                {"outcome": "passed", "run": 1},
                {"outcome": "passed", "run": 2},
                {"outcome": "passed", "run": 3},
                {"outcome": "passed", "run": 4},
                {"outcome": "passed", "run": 5}
            ],
            "total_runs": 5,
            "passed": 5,
            "failed": 0
        }

        flaky = tracker.get_flaky_tests(pass_threshold=0.8, min_runs=3)

        # Stable test should not be in flaky list
        assert not any(t["test"] == test_name for t in flaky)
