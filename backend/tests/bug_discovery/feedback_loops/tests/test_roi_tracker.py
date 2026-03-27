"""
Unit tests for ROITracker.
"""

import pytest
import tempfile
import sqlite3
from pathlib import Path
from datetime import datetime, timedelta

# Add backend to path
import sys
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.feedback_loops.roi_tracker import ROITracker


@pytest.fixture
def temp_db_path(tmp_path):
    """Temporary database path for testing."""
    return str(tmp_path / "test_metrics.db")


@pytest.fixture
def roi_tracker(temp_db_path):
    """ROITracker instance with temporary database."""
    return ROITracker(db_path=temp_db_path)


class TestROITracker:
    """Test ROITracker class."""

    def test_init_creates_database(self, temp_db_path):
        """Test that __init__ creates database and tables."""
        tracker = ROITracker(db_path=temp_db_path)

        assert Path(temp_db_path).exists()

        # Verify tables exist
        conn = sqlite3.connect(temp_db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
        tables = [row[0] for row in cursor.fetchall()]
        conn.close()

        assert "discovery_runs" in tables
        assert "bug_fixes" in tables
        assert "roi_summary" in tables

    def test_init_uses_default_cost_assumptions(self, temp_db_path):
        """Test that default cost assumptions are set."""
        tracker = ROITracker(db_path=temp_db_path)

        assert tracker.manual_qa_hourly_rate == 75.0
        assert tracker.developer_hourly_rate == 100.0
        assert tracker.bug_production_cost == 10000.0
        assert tracker.manual_qa_hours_per_bug == 2.0

    def test_init_accepts_custom_cost_assumptions(self, temp_db_path):
        """Test that custom cost assumptions can be set."""
        tracker = ROITracker(
            db_path=temp_db_path,
            manual_qa_hourly_rate=50.0,
            developer_hourly_rate=80.0,
            bug_production_cost=5000.0,
            manual_qa_hours_per_bug=1.5
        )

        assert tracker.manual_qa_hourly_rate == 50.0
        assert tracker.developer_hourly_rate == 80.0
        assert tracker.bug_production_cost == 5000.0
        assert tracker.manual_qa_hours_per_bug == 1.5

    def test_record_discovery_run(self, roi_tracker):
        """Test recording a discovery run."""
        roi_tracker.record_discovery_run(
            bugs_found=42,
            unique_bugs=35,
            filed_bugs=30,
            duration_seconds=3600,
            by_method={"fuzzing": 20, "chaos": 10, "property": 8, "browser": 4},
            by_severity={"critical": 2, "high": 10, "medium": 15, "low": 15}
        )

        # Verify record was created
        conn = sqlite3.connect(roi_tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM discovery_runs")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[2] == 42  # bugs_found
        assert row[3] == 35  # unique_bugs
        assert row[4] == 30  # filed_bugs

    def test_record_discovery_run_calculates_automation_cost(self, roi_tracker):
        """Test that automation cost is calculated correctly."""
        # 1 hour at $100/hour = $100
        roi_tracker.record_discovery_run(
            bugs_found=10,
            unique_bugs=10,
            filed_bugs=10,
            duration_seconds=3600,  # 1 hour
            by_method={"fuzzing": 10},
            by_severity={"high": 10}
        )

        conn = sqlite3.connect(roi_tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT automation_cost FROM discovery_runs")
        automation_cost = cursor.fetchone()[0]
        conn.close()

        assert automation_cost == 100.0

    def test_record_fixes(self, roi_tracker):
        """Test recording bug fixes."""
        roi_tracker.record_fixes(
            bug_ids=["abc123", "def456"],
            issue_numbers=[123, 124],
            filed_dates=["2026-03-20T10:00:00Z", "2026-03-21T14:00:00Z"],
            fix_duration_hours=8.0,
            severity="high",
            discovery_method="fuzzing"
        )

        # Verify records were created
        conn = sqlite3.connect(roi_tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM bug_fixes")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 2

    def test_generate_roi_report(self, roi_tracker):
        """Test generating ROI report."""
        # Record some discovery runs
        roi_tracker.record_discovery_run(
            bugs_found=50,
            unique_bugs=40,
            filed_bugs=35,
            duration_seconds=7200,  # 2 hours
            by_method={"fuzzing": 25, "chaos": 15, "property": 10},
            by_severity={"critical": 2, "high": 15, "medium": 20, "low": 13}
        )

        # Record some fixes
        roi_tracker.record_fixes(
            bug_ids=["bug1"],
            issue_numbers=[100],
            filed_dates=["2026-03-20T10:00:00Z"],
            fix_duration_hours=6.0
        )

        # Generate report
        report = roi_tracker.generate_roi_report(weeks=4)

        # Verify report structure
        assert "bugs_found" in report
        assert "unique_bugs" in report
        assert "filed_bugs" in report
        assert "bugs_fixed" in report
        assert "hours_saved" in report
        assert "cost_saved" in report
        assert "roi_ratio" in report
        assert "bugs_prevented" in report
        assert "cost_avoidance" in report
        assert "total_savings" in report

        # Verify values
        assert report["bugs_found"] == 50
        assert report["unique_bugs"] == 40
        assert report["bugs_fixed"] == 1

    def test_roi_calculation(self, roi_tracker):
        """Test ROI calculation logic."""
        # Manual QA: 10 bugs * 2 hours * $75 = $1500
        # Automation: 1 hour * $100 = $100
        # Cost saved: $1500 - $100 = $1400
        # Bugs prevented: 10 * 10% = 1 * $10000 = $10000
        # Total savings: $1400 + $10000 = $11400
        # ROI: $11400 / $100 = 114x

        roi_tracker.record_discovery_run(
            bugs_found=10,
            unique_bugs=10,
            filed_bugs=10,
            duration_seconds=3600,  # 1 hour
            by_method={"fuzzing": 10},
            by_severity={"high": 10}
        )

        report = roi_tracker.generate_roi_report(weeks=4)

        assert report["manual_qa_hours"] == 20.0  # 10 bugs * 2 hours
        assert report["automation_hours"] == 1.0
        assert report["hours_saved"] == 19.0
        assert report["manual_qa_cost"] == 1500.0  # 20 hours * $75
        assert report["automation_cost"] == 100.0  # 1 hour * $100
        assert report["cost_saved"] == 1400.0
        assert report["bugs_prevented"] == 1  # 10 * 10%
        assert report["cost_avoidance"] == 10000.0
        assert report["total_savings"] == 11400.0
        assert report["roi_ratio"] == 114.0

    def test_get_weekly_trends(self, roi_tracker):
        """Test getting weekly trend data."""
        # Record data for different weeks
        for i in range(4):
            roi_tracker.record_discovery_run(
                bugs_found=10 * (i + 1),
                unique_bugs=10 * (i + 1),
                filed_bugs=10 * (i + 1),
                duration_seconds=3600,
                by_method={"fuzzing": 10 * (i + 1)},
                by_severity={"medium": 10 * (i + 1)}
            )

        trends = roi_tracker.get_weekly_trends(weeks=4)

        assert len(trends) == 4
        assert all("week_start" in t for t in trends)
        assert all("bugs_found" in t for t in trends)

    def test_save_weekly_summary(self, roi_tracker):
        """Test saving weekly summary."""
        roi_tracker.record_discovery_run(
            bugs_found=42,
            unique_bugs=35,
            filed_bugs=30,
            duration_seconds=3600,
            by_method={"fuzzing": 20, "chaos": 10, "property": 8, "browser": 4},
            by_severity={"critical": 2, "high": 10, "medium": 15, "low": 15}
        )

        report = roi_tracker.generate_roi_report(weeks=4)
        roi_tracker.save_weekly_summary(report)

        # Verify summary was saved
        conn = sqlite3.connect(roi_tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM roi_summary")
        row = cursor.fetchone()
        conn.close()

        assert row is not None
        assert row[2] == 42  # bugs_found

    def test_save_weekly_summary_updates_existing(self, roi_tracker):
        """Test that save_weekly_summary updates existing week."""
        roi_tracker.record_discovery_run(
            bugs_found=10,
            unique_bugs=10,
            filed_bugs=10,
            duration_seconds=3600,
            by_method={"fuzzing": 10},
            by_severity={"medium": 10}
        )

        report1 = roi_tracker.generate_roi_report(weeks=4)
        roi_tracker.save_weekly_summary(report1)

        # Add more bugs
        roi_tracker.record_discovery_run(
            bugs_found=20,
            unique_bugs=20,
            filed_bugs=20,
            duration_seconds=3600,
            by_method={"fuzzing": 20},
            by_severity={"medium": 20}
        )

        report2 = roi_tracker.generate_roi_report(weeks=4)
        roi_tracker.save_weekly_summary(report2)

        # Should have updated, not inserted new row
        conn = sqlite3.connect(roi_tracker.db_path)
        cursor = conn.cursor()
        cursor.execute("SELECT COUNT(*) FROM roi_summary")
        count = cursor.fetchone()[0]
        conn.close()

        assert count == 1  # Only one row (updated, not new insert)

    def test_generate_roi_report_includes_breakdown(self, roi_tracker):
        """Test that report includes breakdown when requested."""
        roi_tracker.record_discovery_run(
            bugs_found=30,
            unique_bugs=25,
            filed_bugs=20,
            duration_seconds=3600,
            by_method={"fuzzing": 15, "chaos": 10, "property": 5},
            by_severity={"critical": 1, "high": 10, "medium": 15, "low": 4}
        )

        report = roi_tracker.generate_roi_report(weeks=4, include_breakdown=True)

        assert "breakdown" in report
        assert "by_method" in report["breakdown"]
        assert "by_severity" in report["breakdown"]
        assert report["breakdown"]["by_method"]["fuzzing"] == 15
        assert report["breakdown"]["by_severity"]["critical"] == 1


class TestIntegrationWithDiscoveryCoordinator:
    """Test integration with DiscoveryCoordinator."""

    def test_cost_assumptions_documented(self, roi_tracker):
        """Test that cost assumptions are accessible for documentation."""
        assumptions = {
            "manual_qa_hourly_rate": roi_tracker.manual_qa_hourly_rate,
            "developer_hourly_rate": roi_tracker.developer_hourly_rate,
            "bug_production_cost": roi_tracker.bug_production_cost,
            "manual_qa_hours_per_bug": roi_tracker.manual_qa_hours_per_bug
        }

        assert all(k in assumptions for k in [
            "manual_qa_hourly_rate",
            "developer_hourly_rate",
            "bug_production_cost",
            "manual_qa_hours_per_bug"
        ])
