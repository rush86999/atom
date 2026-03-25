"""
Unit tests for DashboardGenerator enhancements.
"""

import pytest
import tempfile
from pathlib import Path
from datetime import datetime

# Add backend to path
import sys
backend_dir = Path(__file__).parent.parent.parent.parent.parent
if str(backend_dir) not in sys.path:
    sys.path.insert(0, str(backend_dir))

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity
from tests.bug_discovery.core.dashboard_generator import DashboardGenerator


@pytest.fixture
def temp_storage_dir(tmp_path):
    """Temporary storage directory for reports."""
    storage_dir = tmp_path / "storage"
    storage_dir.mkdir(parents=True, exist_ok=True)
    (storage_dir / "reports").mkdir(parents=True, exist_ok=True)
    return str(storage_dir)


@pytest.fixture
def sample_bug_reports():
    """Sample BugReport objects for testing."""
    return [
        BugReport(
            discovery_method=DiscoveryMethod.FUZZING,
            test_name="test_api_fuzzing",
            error_message="SQL injection",
            error_signature="abc123",
            severity=Severity.CRITICAL
        ),
        BugReport(
            discovery_method=DiscoveryMethod.CHAOS,
            test_name="test_network_chaos",
            error_message="Connection timeout",
            error_signature="def456",
            severity=Severity.HIGH
        ),
        BugReport(
            discovery_method=DiscoveryMethod.PROPERTY,
            test_name="test_idempotence",
            error_message="Invariant violated",
            error_signature="ghi789",
            severity=Severity.MEDIUM
        )
    ]


@pytest.fixture
def sample_roi_data():
    """Sample ROI data for testing."""
    return {
        "period_weeks": 4,
        "bugs_found": 42,
        "unique_bugs": 35,
        "filed_bugs": 30,
        "bugs_fixed": 15,
        "manual_qa_hours": 84.0,
        "automation_hours": 2.0,
        "hours_saved": 82.0,
        "manual_qa_cost": 6300.0,
        "automation_cost": 200.0,
        "cost_saved": 6100.0,
        "bugs_prevented": 4,
        "cost_avoidance": 40000.0,
        "total_savings": 46100.0,
        "roi_ratio": 230.5
    }


class TestDashboardGeneratorEnhancements:
    """Test DashboardGenerator enhancement methods."""

    def test_generate_weekly_report_with_roi_creates_html(self, temp_storage_dir, sample_bug_reports, sample_roi_data):
        """Test that generate_weekly_report_with_roi creates HTML report."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        report_path = generator.generate_weekly_report_with_roi(
            bugs_found=42,
            unique_bugs=35,
            filed_bugs=30,
            reports=sample_bug_reports,
            roi_data=sample_roi_data
        )

        assert Path(report_path).exists()
        assert report_path.endswith(".html")

        # Verify HTML content
        with open(report_path) as f:
            html_content = f.read()
            assert "ROI Metrics" in html_content
            assert "Hours Saved" in html_content
            assert "Cost Saved" in html_content
            assert "ROI Ratio" in html_content

    def test_generate_weekly_report_with_roi_includes_verification_status(self, temp_storage_dir, sample_bug_reports, sample_roi_data):
        """Test that verification status is included in report."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        verification_status = {
            "fixed": 10,
            "verified": 8,
            "pending": 2,
            "regression_rate": 5.0
        }

        report_path = generator.generate_weekly_report_with_roi(
            bugs_found=42,
            unique_bugs=35,
            filed_bugs=30,
            reports=sample_bug_reports,
            roi_data=sample_roi_data,
            verification_status=verification_status
        )

        with open(report_path) as f:
            html_content = f.read()
            assert "Bug Fix Verification" in html_content
            assert "10</td>" in html_content  # Fixed count
            assert "8</td>" in html_content  # Verified count

    def test_calculate_effectiveness_metrics(self, temp_storage_dir):
        """Test _calculate_effectiveness_metrics calculation."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        effectiveness = generator._calculate_effectiveness_metrics(
            bugs_found=100,
            duration_seconds=3600,  # 1 hour
            unique_bugs=75
        )

        assert effectiveness["bugs_per_hour"] == 100.0
        assert effectiveness["unique_rate"] == 75.0
        assert effectiveness["dedup_effectiveness"] == 25.0
        assert effectiveness["total_time_hours"] == 1.0

    def test_calculate_effectiveness_metrics_handles_zero_duration(self, temp_storage_dir):
        """Test _calculate_effectiveness_metrics handles zero duration."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        effectiveness = generator._calculate_effectiveness_metrics(
            bugs_found=10,
            duration_seconds=0,
            unique_bugs=10
        )

        # Should not divide by zero
        assert effectiveness["bugs_per_hour"] >= 0
        assert effectiveness["total_time_hours"] == 0.0

    def test_calculate_regression_rate_with_db_no_db(self, temp_storage_dir, sample_bug_reports):
        """Test _calculate_regression_rate_with_db when database doesn't exist."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        regression_rate = generator._calculate_regression_rate_with_db(sample_bug_reports)

        assert regression_rate == 0.0

    def test_render_method_rows_includes_percentages(self, temp_storage_dir):
        """Test _render_method_rows includes percentage calculations."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        by_method = {"fuzzing": 20, "chaos": 10, "property": 5}
        total = 35

        rows = generator._render_method_rows(by_method, total)

        assert "20</td>" in rows
        assert "57.1%" in rows  # 20/35 ≈ 57.1%
        assert "10</td>" in rows
        assert "28.6%" in rows  # 10/35 ≈ 28.6%

    def test_render_severity_rows_includes_percentages(self, temp_storage_dir):
        """Test _render_severity_rows includes percentage calculations."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        by_severity = {"critical": 2, "high": 10, "medium": 15, "low": 15}
        total = 42

        rows = generator._render_severity_rows(by_severity, total)

        assert "2</td>" in rows
        assert "4.8%" in rows  # 2/42 ≈ 4.8%
        assert "10</td>" in rows
        assert "23.8%" in rows  # 10/42 ≈ 23.8%

    def test_render_fix_verification_section(self, temp_storage_dir):
        """Test _render_fix_verification_section rendering."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        verification_status = {
            "fixed": 15,
            "verified": 12,
            "pending": 3,
            "regression_rate": 8.5
        }

        section = generator._render_fix_verification_section(verification_status)

        assert "Bug Fix Verification" in section
        assert "15</td>" in section
        assert "12</td>" in section
        assert "3</td>" in section
        assert "8.5%" in section

    def test_render_fix_verification_section_empty_when_no_status(self, temp_storage_dir):
        """Test _render_fix_verification_section returns empty string when no status."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        section = generator._render_fix_verification_section(None)

        assert section == ""

    def test_generate_weekly_report_with_roi_creates_json_report(self, temp_storage_dir, sample_bug_reports, sample_roi_data):
        """Test that JSON report is created with ROI data."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        report_path = generator.generate_weekly_report_with_roi(
            bugs_found=42,
            unique_bugs=35,
            filed_bugs=30,
            reports=sample_bug_reports,
            roi_data=sample_roi_data
        )

        # JSON report should be in same directory with .json extension
        json_path = report_path.replace(".html", ".json")
        assert Path(json_path).exists()

        # Verify JSON content
        import json
        with open(json_path) as f:
            json_data = json.load(f)

        assert "roi" in json_data
        assert json_data["roi"]["roi_ratio"] == 230.5
        assert "effectiveness" in json_data


class TestIntegrationWithROITracker:
    """Test integration with ROITracker."""

    def test_roi_data_structure_compatibility(self, temp_storage_dir, sample_roi_data):
        """Test that ROITracker output is compatible with dashboard."""
        generator = DashboardGenerator(storage_dir=temp_storage_dir)

        # All required fields should be present
        required_fields = [
            "hours_saved", "cost_saved", "bugs_prevented", "roi_ratio",
            "automation_cost", "manual_qa_cost", "automation_hours", "manual_qa_hours"
        ]

        for field in required_fields:
            assert field in sample_roi_data

        # Should not raise error
        report_path = generator.generate_weekly_report_with_roi(
            bugs_found=10,
            unique_bugs=10,
            filed_bugs=10,
            reports=[],
            roi_data=sample_roi_data
        )

        assert Path(report_path).exists()
