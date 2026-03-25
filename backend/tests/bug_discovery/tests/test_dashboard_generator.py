"""
Unit tests for DashboardGenerator service.

Tests weekly HTML/JSON report generation.
"""

import pytest
import tempfile
from pathlib import Path
import json

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod, Severity
from tests.bug_discovery.core.dashboard_generator import DashboardGenerator


class TestDashboardGenerator:
    """Test DashboardGenerator report generation."""

    def test_generate_weekly_report_creates_files(self):
        """Test weekly report generation creates HTML and JSON files."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = DashboardGenerator(storage_dir=tmpdir)

            reports = [
                BugReport(
                    discovery_method=DiscoveryMethod.FUZZING,
                    test_name="test1",
                    error_message="Error 1",
                    error_signature="sig1",
                    severity=Severity.CRITICAL
                ),
                BugReport(
                    discovery_method=DiscoveryMethod.CHAOS,
                    test_name="test2",
                    error_message="Error 2",
                    error_signature="sig2",
                    severity=Severity.HIGH
                )
            ]

            report_path = generator.generate_weekly_report(
                bugs_found=10,
                unique_bugs=2,
                filed_bugs=2,
                reports=reports
            )

            # Check HTML report exists
            assert Path(report_path).exists()
            assert report_path.endswith(".html")

            # Check JSON report exists
            json_path = report_path.replace(".html", ".json")
            assert Path(json_path).exists()

            # Verify JSON content
            with open(json_path) as f:
                data = json.load(f)
                assert data["bugs_found"] == 10
                assert data["unique_bugs"] == 2
                assert data["filed_bugs"] == 2

    def test_group_by_method(self):
        """Test grouping bugs by discovery method."""
        generator = DashboardGenerator()

        reports = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test1",
                error_message="Error",
                error_signature="sig1"
            ),
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test2",
                error_message="Error",
                error_signature="sig2"
            ),
            BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name="test3",
                error_message="Error",
                error_signature="sig3"
            )
        ]

        by_method = generator._group_by_method(reports)

        assert by_method["fuzzing"] == 2
        assert by_method["chaos"] == 1

    def test_group_by_severity(self):
        """Test grouping bugs by severity."""
        generator = DashboardGenerator()

        reports = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test1",
                error_message="Error",
                error_signature="sig1",
                severity=Severity.CRITICAL
            ),
            BugReport(
                discovery_method=DiscoveryMethod.CHAOS,
                test_name="test2",
                error_message="Error",
                error_signature="sig2",
                severity=Severity.HIGH
            ),
            BugReport(
                discovery_method=DiscoveryMethod.PROPERTY,
                test_name="test3",
                error_message="Error",
                error_signature="sig3",
                severity=Severity.HIGH
            )
        ]

        by_severity = generator._group_by_severity(reports)

        assert by_severity["critical"] == 1
        assert by_severity["high"] == 2

    def test_calculate_regression_rate_placeholder(self):
        """Test regression rate calculation returns 0.0 placeholder."""
        generator = DashboardGenerator()

        reports = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test",
                error_message="Error",
                error_signature="sig"
            )
        ]

        regression_rate = generator._calculate_regression_rate(reports)

        assert regression_rate == 0.0

    def test_html_template_contains_sections(self):
        """Test HTML report contains all required sections."""
        with tempfile.TemporaryDirectory() as tmpdir:
            generator = DashboardGenerator(storage_dir=tmpdir)

            report_path = generator.generate_weekly_report(
                bugs_found=5,
                unique_bugs=3,
                filed_bugs=2,
                reports=[]
            )

            with open(report_path) as f:
                html = f.read()

            # Check for key sections
            assert "Weekly Bug Discovery Report" in html
            assert "Bugs Found" in html
            assert "Unique Bugs" in html
            assert "Bugs Filed" in html
            assert "Regression Rate" in html
            assert "Bugs by Discovery Method" in html
            assert "Bugs by Severity" in html
