#!/usr/bin/env python
"""
Unit tests for flaky test detector integration.

Tests cover:
- Multi-run detection with known flaky test patterns
- JSON export format validation
- Database integration (record/retrieve)
- Classification logic (stable/flaky/broken)
- Reliability scoring
"""

import json
import sqlite3
import tempfile
from pathlib import Path
from unittest import mock

import pytest

from tests.scripts.flaky_test_detector import (
    classify_flakiness,
    export_flaky_tests_json,
    record_to_quarantine_db,
)
from tests.scripts.flaky_test_tracker import FlakyTestTracker


class TestClassifyFlakiness:
    """Test flakiness classification logic."""

    def test_classify_stable_zero_failures(self):
        """Classification should be 'stable' when there are zero failures."""
        classification, flaky_rate = classify_flakiness(0, 10)
        assert classification == "stable"
        assert flaky_rate == 0.0

    def test_classify_flaky_intermittent_failures(self):
        """Classification should be 'flaky' when failures are intermittent."""
        # 3 failures out of 10 runs = 30% flaky rate
        classification, flaky_rate = classify_flakiness(3, 10)
        assert classification == "flaky"
        assert flaky_rate == 0.3

    def test_classify_broken_all_failures(self):
        """Classification should be 'broken' when all runs fail."""
        classification, flaky_rate = classify_flakiness(10, 10)
        assert classification == "broken"
        assert flaky_rate == 1.0

    def test_classify_boundary_one_failure(self):
        """Classification should be 'flaky' with 1 failure out of many."""
        classification, flaky_rate = classify_flakiness(1, 10)
        assert classification == "flaky"
        assert flaky_rate == 0.1

    def test_classify_boundary_one_pass(self):
        """Classification should be 'flaky' with 1 pass out of many failures."""
        classification, flaky_rate = classify_flakiness(9, 10)
        assert classification == "flaky"
        assert flaky_rate == 0.9

    def test_classify_zero_total_runs(self):
        """Classification should handle zero total runs gracefully."""
        classification, flaky_rate = classify_flakiness(0, 0)
        assert classification == "stable"
        assert flaky_rate == 0.0


class TestExportFlakyTestsJson:
    """Test JSON export functionality."""

    def test_export_format_valid_json(self, tmp_path):
        """Export should produce valid JSON with correct schema."""
        flaky_tests_data = [
            {
                "test_path": "tests/test_foo.py::test_bar",
                "platform": "backend",
                "total_runs": 10,
                "failure_count": 3,
                "flaky_rate": 0.3,
                "classification": "flaky",
                "failure_details": [
                    {"run": i, "failed": i < 3}
                    for i in range(10)
                ]
            }
        ]

        output_path = tmp_path / "flaky_export.json"
        export_flaky_tests_json(flaky_tests_data, total_tests_scanned=100, output_path=output_path)

        # Verify file exists and is valid JSON
        assert output_path.exists()
        with open(output_path) as f:
            data = json.load(f)

        # Verify schema
        assert "scan_date" in data
        assert "detection_runs" in data
        assert "flaky_tests" in data
        assert "summary" in data

    def test_export_summary_counts(self, tmp_path):
        """Export should correctly count flaky, broken, and stable tests."""
        flaky_tests_data = [
            {
                "test_path": "tests/test_a.py::test_x",
                "platform": "backend",
                "total_runs": 10,
                "failure_count": 3,
                "flaky_rate": 0.3,
                "classification": "flaky",
                "failure_details": []
            },
            {
                "test_path": "tests/test_b.py::test_y",
                "platform": "backend",
                "total_runs": 10,
                "failure_count": 10,
                "flaky_rate": 1.0,
                "classification": "broken",
                "failure_details": []
            }
        ]

        output_path = tmp_path / "flaky_export.json"
        export_flaky_tests_json(flaky_tests_data, total_tests_scanned=50, output_path=output_path)

        with open(output_path) as f:
            data = json.load(f)

        # Verify summary
        assert data["summary"]["flaky_count"] == 1
        assert data["summary"]["broken_count"] == 1
        assert data["summary"]["stable_count"] == 48  # 50 - 1 - 1
        assert data["summary"]["total_tests_scanned"] == 50

    def test_export_empty_flaky_tests(self, tmp_path):
        """Export should handle empty flaky tests list."""
        output_path = tmp_path / "flaky_export.json"
        export_flaky_tests_json([], total_tests_scanned=0, output_path=output_path)

        with open(output_path) as f:
            data = json.load(f)

        assert data["flaky_tests"] == []
        assert data["summary"]["total_tests_scanned"] == 0
        assert data["summary"]["flaky_count"] == 0
        assert data["summary"]["broken_count"] == 0
        assert data["summary"]["stable_count"] == 0


class TestFlakyTestTracker:
    """Test FlakyTestTracker database operations."""

    def test_schema_creation(self, tmp_path):
        """Database schema should be created with correct tables and indexes."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        # Verify table exists
        conn = sqlite3.connect(db_path)
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='flaky_tests'"
        )
        assert cursor.fetchone() is not None

        # Verify indexes exist
        cursor = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='index' AND name LIKE 'idx_%'"
        )
        indexes = [row[0] for row in cursor.fetchall()]
        assert "idx_test_path_platform" in indexes
        assert "idx_flaky_rate" in indexes
        assert "idx_classification" in indexes

        conn.close()
        tracker.close()

    def test_record_flaky_test_insert(self, tmp_path):
        """Recording a new flaky test should insert a row."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        failure_history = [
            {"run": 0, "failed": True},
            {"run": 1, "failed": False},
            {"run": 2, "failed": True}
        ]

        test_id = tracker.record_flaky_test(
            "tests/test_foo.py::test_bar",
            "backend",
            10,
            3,
            "flaky",
            failure_history
        )

        assert test_id == 1  # First insert should have ID 1

        tracker.close()

    def test_record_flaky_test_update(self, tmp_path):
        """Recording existing test should update the row."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        # First record
        failure_history_1 = [
            {"run": 0, "failed": True},
            {"run": 1, "failed": False}
        ]

        test_id_1 = tracker.record_flaky_test(
            "tests/test_foo.py::test_bar",
            "backend",
            2,
            1,
            "flaky",
            failure_history_1
        )

        # Second record (should update)
        failure_history_2 = [
            {"run": 0, "failed": True},
            {"run": 1, "failed": True}
        ]

        test_id_2 = tracker.record_flaky_test(
            "tests/test_foo.py::test_bar",
            "backend",
            2,
            2,
            "flaky",
            failure_history_2
        )

        assert test_id_1 == test_id_2  # Same ID means update, not insert

        tracker.close()

    def test_get_quarantined_tests(self, tmp_path):
        """Getting quarantined tests should filter by classification and platform."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        # Record flaky test
        tracker.record_flaky_test(
            "tests/test_flaky.py::test_x",
            "backend",
            10,
            3,
            "flaky",
            []
        )

        # Record broken test (should not appear in quarantined)
        tracker.record_flaky_test(
            "tests/test_broken.py::test_y",
            "backend",
            10,
            10,
            "broken",
            []
        )

        # Get quarantined tests
        quarantined = tracker.get_quarantined_tests("backend")

        assert len(quarantined) == 1
        assert quarantined[0]["test_path"] == "tests/test_flaky.py::test_x"

        tracker.close()

    def test_get_reliability_score(self, tmp_path):
        """Reliability score should be 1.0 - flaky_rate."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        # Test with 30% flaky rate
        tracker.record_flaky_test(
            "tests/test_foo.py::test_bar",
            "backend",
            10,
            3,
            "flaky",
            []
        )

        # Reliability should be 1.0 - 0.3 = 0.7
        score = tracker.get_test_reliability_score("tests/test_foo.py::test_bar", "backend")
        assert score == 0.7

        tracker.close()

    def test_get_reliability_score_not_found(self, tmp_path):
        """Reliability score should be 1.0 for tests not in database."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        score = tracker.get_test_reliability_score("tests/unknown.py::test_x", "backend")
        assert score == 1.0  # No failures = perfect reliability

        tracker.close()

    def test_failure_history_merge(self, tmp_path):
        """Updating a test should merge failure history."""
        db_path = tmp_path / "test.db"
        tracker = FlakyTestTracker(db_path)

        # First record
        failure_history_1 = [{"run": 0, "failed": True}]
        tracker.record_flaky_test(
            "tests/test_foo.py::test_bar",
            "backend",
            1,
            1,
            "flaky",
            failure_history_1
        )

        # Second record
        failure_history_2 = [{"run": 0, "failed": False}]
        tracker.record_flaky_test(
            "tests/test_foo.py::test_bar",
            "backend",
            1,
            0,
            "stable",
            failure_history_2
        )

        # Get test history
        history = tracker.get_test_history("tests/test_foo.py::test_bar", "backend")
        assert len(history["failure_history"]) == 2  # Merged history

        tracker.close()


class TestRecordToQuarantineDb:
    """Test database recording from flaky test detector."""

    def test_record_flaky_tests_to_db(self, tmp_path):
        """Flaky tests should be recorded to database correctly."""
        db_path = tmp_path / "test.db"

        # Mock flaky tests
        flaky_tests = {
            "tests/test_a.py::test_x": 0.3,  # 30% flaky rate
            "tests/test_b.py::test_y": 0.5   # 50% flaky rate
        }

        with mock.patch('tests.scripts.flaky_test_detector.FlakyTestTracker') as MockTracker:
            mock_instance = mock.Mock()
            MockTracker.return_value.__enter__ = mock.Mock(return_value=mock_instance)
            MockTracker.return_value.__exit__ = mock.Mock(return_value=False)
            MockTracker.return_value.close = mock.Mock()

            record_to_quarantine_db(flaky_tests, total_runs=10, db_path=db_path, platform="backend")

            # Verify FlakyTestTracker was instantiated
            MockTracker.assert_called_once_with(db_path)

            # Verify record_flaky_test was called twice (once per test)
            assert mock_instance.record_flaky_test.call_count == 2

    def test_record_empty_flaky_tests(self, tmp_path):
        """Empty flaky tests dict should not call record_flaky_test."""
        db_path = tmp_path / "test.db"

        with mock.patch('tests.scripts.flaky_test_detector.FlakyTestTracker') as MockTracker:
            mock_instance = mock.Mock()
            MockTracker.return_value.__enter__ = mock.Mock(return_value=mock_instance)
            MockTracker.return_value.__exit__ = mock.Mock(return_value=False)
            MockTracker.return_value.close = mock.Mock()

            record_to_quarantine_db({}, total_runs=10, db_path=db_path, platform="backend")

            # Verify no records were made
            mock_instance.record_flaky_test.assert_not_called()
