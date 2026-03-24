"""
Automated Bug Filing Tests

This module tests the bug filing service for all test types:
load, network, memory, mobile, desktop, visual, a11y.
"""

import os
import tempfile
from unittest.mock import patch, MagicMock

import pytest

from backend.tests.bug_discovery.bug_filing_service import BugFilingService, file_bug_from_test_failure
from backend.tests.bug_discovery.fixtures.bug_filing_fixtures import (
    test_metadata,
    test_metadata_network,
    test_metadata_memory,
    test_metadata_mobile,
    test_metadata_desktop,
    test_metadata_visual,
    test_metadata_a11y
)


class TestBugFilingLoadFailure:
    """Test bug filing for load test failures."""

    def test_bug_filing_load_failure(self, bug_filing_service, test_metadata):
        """
        Test bug filing for load test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata: Sample load test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms: Actual p(95) = 650ms",
            metadata=test_metadata
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1
        assert "github.com/test/repo/issues/1" in result["issue_url"]

    def test_bug_filing_load_labels(self, bug_filing_service, test_metadata):
        """Test that load test bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms",
            metadata=test_metadata
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]  # Get the json argument

        # Verify labels
        assert "bug" in issue_data["labels"]
        assert "automated" in issue_data["labels"]
        assert "test-type:load" in issue_data["labels"]
        assert "severity:high" in issue_data["labels"]
        assert "platform:web" in issue_data["labels"]

    def test_bug_filing_load_body_contains_metrics(self, bug_filing_service, test_metadata):
        """Test that load test bug body contains performance metrics."""
        bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms",
            metadata=test_metadata
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_body = last_issue[1]["json"]["body"]

        # Verify performance metrics in body
        assert "p95_latency_ms" in issue_body
        assert "650" in issue_body
        assert "error_rate" in issue_body
        assert "Performance Metrics" in issue_body


class TestBugFilingNetworkFailure:
    """Test bug filing for network test failures."""

    def test_bug_filing_network_failure(self, bug_filing_service, test_metadata_network):
        """
        Test bug filing for network test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata_network: Sample network test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_offline_mode",
            error_message="Network error not handled: offline mode",
            metadata=test_metadata_network
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1

    def test_bug_filing_network_labels(self, bug_filing_service, test_metadata_network):
        """Test that network test bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_offline_mode",
            error_message="Network error not handled",
            metadata=test_metadata_network
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]

        # Verify labels
        assert "test-type:network" in issue_data["labels"]
        assert "severity:high" in issue_data["labels"]

    def test_bug_filing_network_body_contains_context(self, bug_filing_service, test_metadata_network):
        """Test that network test bug body includes network context."""
        bug_filing_service.file_bug(
            test_name="test_offline_mode",
            error_message="Network error not handled",
            metadata=test_metadata_network
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_body = last_issue[1]["json"]["body"]

        # Verify network context in body
        assert "offline" in issue_body.lower()
        assert "network_condition" in issue_body


class TestBugFilingMemoryLeak:
    """Test bug filing for memory leak test failures."""

    def test_bug_filing_memory_leak(self, bug_filing_service, test_metadata_memory):
        """
        Test bug filing for memory leak test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata_memory: Sample memory leak test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_memory_leak_agent_execution",
            error_message="Memory leak detected: 10MB increase",
            metadata=test_metadata_memory
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1

    def test_bug_filing_memory_labels(self, bug_filing_service, test_metadata_memory):
        """Test that memory leak bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_memory_leak_agent_execution",
            error_message="Memory leak detected",
            metadata=test_metadata_memory
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]

        # Verify labels
        assert "test-type:memory" in issue_data["labels"]
        assert "severity:high" in issue_data["labels"]

    def test_bug_filing_memory_body_contains_heap_info(self, bug_filing_service, test_metadata_memory):
        """Test that memory leak bug body includes heap snapshot comparison."""
        bug_filing_service.file_bug(
            test_name="test_memory_leak_agent_execution",
            error_message="Memory leak detected",
            metadata=test_metadata_memory
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_body = last_issue[1]["json"]["body"]

        # Verify memory info in body
        assert "10.5MB" in issue_body
        assert "memory_increase_mb" in issue_body


class TestBugFilingMobileAPI:
    """Test bug filing for mobile API test failures."""

    def test_bug_filing_mobile_api(self, bug_filing_service, test_metadata_mobile):
        """
        Test bug filing for mobile API test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata_mobile: Sample mobile test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_mobile_agent_execute",
            error_message="API returned 500",
            metadata=test_metadata_mobile
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1

    def test_bug_filing_mobile_labels(self, bug_filing_service, test_metadata_mobile):
        """Test that mobile test bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_mobile_agent_execute",
            error_message="API returned 500",
            metadata=test_metadata_mobile
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]

        # Verify labels
        assert "test-type:mobile" in issue_data["labels"]
        assert "platform:mobile" in issue_data["labels"]
        assert "severity:medium" in issue_data["labels"]

    def test_bug_filing_mobile_body_contains_endpoint(self, bug_filing_service, test_metadata_mobile):
        """Test that mobile test bug body includes endpoint info."""
        bug_filing_service.file_bug(
            test_name="test_mobile_agent_execute",
            error_message="API returned 500",
            metadata=test_metadata_mobile
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_body = last_issue[1]["json"]["body"]

        # Verify endpoint info in body
        assert "/api/v1/agents/execute" in issue_body
        assert "500" in issue_body


class TestBugFilingDesktop:
    """Test bug filing for desktop test failures."""

    def test_bug_filing_desktop(self, bug_filing_service, test_metadata_desktop):
        """
        Test bug filing for desktop test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata_desktop: Sample desktop test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_window_minimize",
            error_message="Window minimize failed",
            metadata=test_metadata_desktop
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1

    def test_bug_filing_desktop_labels(self, bug_filing_service, test_metadata_desktop):
        """Test that desktop test bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_window_minimize",
            error_message="Window minimize failed",
            metadata=test_metadata_desktop
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]

        # Verify labels
        assert "test-type:desktop" in issue_data["labels"]
        assert "platform:desktop" in issue_data["labels"]
        assert "severity:medium" in issue_data["labels"]


class TestBugFilingVisualRegression:
    """Test bug filing for visual regression test failures."""

    def test_bug_filing_visual_regression(self, bug_filing_service, test_metadata_visual):
        """
        Test bug filing for visual regression test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata_visual: Sample visual regression test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_visual_dashboard",
            error_message="Visual diff detected",
            metadata=test_metadata_visual
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1

    def test_bug_filing_visual_labels(self, bug_filing_service, test_metadata_visual):
        """Test that visual regression bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_visual_dashboard",
            error_message="Visual diff detected",
            metadata=test_metadata_visual
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]

        # Verify labels
        assert "test-type:visual" in issue_data["labels"]
        assert "severity:medium" in issue_data["labels"]

    def test_bug_filing_visual_body_contains_percy_url(self, bug_filing_service, test_metadata_visual):
        """Test that visual regression bug body includes Percy diff URL."""
        bug_filing_service.file_bug(
            test_name="test_visual_dashboard",
            error_message="Visual diff detected",
            metadata=test_metadata_visual
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_body = last_issue[1]["json"]["body"]

        # Verify Percy URL in body
        assert "percy.io" in issue_body
        assert "pixel_diff_count" in issue_body


class TestBugFilingAccessibility:
    """Test bug filing for accessibility test failures."""

    def test_bug_filing_accessibility(self, bug_filing_service, test_metadata_a11y):
        """
        Test bug filing for accessibility test failure.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata_a11y: Sample accessibility test metadata
        """
        result = bug_filing_service.file_bug(
            test_name="test_wcag_compliance_dashboard",
            error_message="WCAG violation: color-contrast",
            metadata=test_metadata_a11y
        )

        # Verify issue created
        assert result["status"] == "created"
        assert result["issue_number"] == 1

    def test_bug_filing_a11y_labels(self, bug_filing_service, test_metadata_a11y):
        """Test that accessibility test bugs have correct labels."""
        bug_filing_service.file_bug(
            test_name="test_wcag_compliance_dashboard",
            error_message="WCAG violation: color-contrast",
            metadata=test_metadata_a11y
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_data = last_issue[1]["json"]

        # Verify labels
        assert "test-type:a11y" in issue_data["labels"]
        assert "severity:high" in issue_data["labels"]

    def test_bug_filing_a11y_body_contains_violations(self, bug_filing_service, test_metadata_a11y):
        """Test that accessibility bug body includes axe-core violation details."""
        bug_filing_service.file_bug(
            test_name="test_wcag_compliance_dashboard",
            error_message="WCAG violation: color-contrast",
            metadata=test_metadata_a11y
        )

        # Get the last created issue from the mock
        last_issue = bug_filing_service.session.post.call_args
        issue_body = last_issue[1]["json"]["body"]

        # Verify violation details in body
        assert "color-contrast" in issue_body
        assert "violation_count" in issue_body
        assert "WCAG" in issue_body


class TestBugFilingIdempotency:
    """Test bug filing idempotency (no duplicate issues)."""

    def test_bug_filing_idempotency(self, bug_filing_service, test_metadata):
        """
        Test that filing the same bug twice creates only one issue.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata: Sample test metadata
        """
        # File bug first time
        result1 = bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms",
            metadata=test_metadata
        )

        # File bug second time (same test name, error type, and metadata)
        result2 = bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms",
            metadata=test_metadata
        )

        # Verify first bug created
        assert result1["status"] == "created"
        assert result1["issue_number"] == 1

        # Verify second bug detected as duplicate
        assert result2["status"] == "duplicate"
        assert result2["issue_number"] == 1  # Same issue as first
        assert "already filed" in result2["message"].lower()

    def test_bug_filing_different_errors_create_different_issues(self, bug_filing_service, test_metadata):
        """
        Test that different errors create different issues.

        Args:
            bug_filing_service: BugFilingService instance
            test_metadata: Sample test metadata
        """
        # File first bug
        result1 = bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms",
            metadata=test_metadata
        )

        # File second bug with different error type
        import copy
        test_metadata2 = copy.deepcopy(test_metadata)
        test_metadata2["error_type"] = "Connection Timeout"

        result2 = bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="Connection timeout",
            metadata=test_metadata2
        )

        # Verify both bugs created
        assert result1["status"] == "created"
        assert result1["issue_number"] == 1

        assert result2["status"] == "created"
        assert result2["issue_number"] == 2

    def test_bug_filing_check_duplicate_bug_prevents_duplicates(self, bug_filing_service, test_metadata):
        """Test that _check_duplicate_bug prevents duplicate filing."""
        # Create first issue
        bug_filing_service.file_bug(
            test_name="test_api_load_baseline",
            error_message="p(95) > 500ms",
            metadata=test_metadata
        )

        # Check for duplicate manually
        title = "[Bug] Load Test Failure: Test Api Load Baseline"
        existing_issue = bug_filing_service._check_duplicate_bug(title)

        # Verify duplicate found
        assert existing_issue is not None
        assert existing_issue["number"] == 1
        assert existing_issue["state"] == "open"


class TestBugFilingConvenienceFunction:
    """Test the convenience function file_bug_from_test_failure."""

    def test_file_bug_from_test_failure_with_env_vars(self, monkeypatch):
        """Test convenience function with environment variables set."""
        # Set environment variables
        monkeypatch.setenv("GITHUB_TOKEN", "test_token_ghp_xxx")
        monkeypatch.setenv("GITHUB_REPOSITORY", "test/repo")

        # Mock BugFilingService
        with patch("backend.tests.bug_discovery.bug_filing_service.BugFilingService") as mock_service_class:
            mock_service = MagicMock()
            mock_service.file_bug.return_value = {
                "status": "created",
                "issue_number": 1,
                "issue_url": "https://github.com/test/repo/issues/1"
            }
            mock_service_class.return_value = mock_service

            # Call convenience function
            result = file_bug_from_test_failure(
                test_name="test_example",
                error_message="Test failed",
                stack_trace="Error at line 42",
                test_type="load"
            )

            # Verify service created and called
            mock_service_class.assert_called_once_with("test_token_ghp_xxx", "test/repo")
            mock_service.file_bug.assert_called_once()
            assert result["status"] == "created"

    def test_file_bug_from_test_failure_missing_token(self, monkeypatch):
        """Test convenience function raises error without GITHUB_TOKEN."""
        # Remove GITHUB_TOKEN
        monkeypatch.delenv("GITHUB_TOKEN", raising=False)

        # Should raise ValueError
        with pytest.raises(ValueError, match="GITHUB_TOKEN environment variable not set"):
            file_bug_from_test_failure(
                test_name="test_example",
                error_message="Test failed",
                stack_trace="Error at line 42",
                test_type="load"
            )

    def test_file_bug_from_test_failure_missing_repository(self, monkeypatch):
        """Test convenience function raises error without GITHUB_REPOSITORY."""
        # Set token but not repository
        monkeypatch.setenv("GITHUB_TOKEN", "test_token_ghp_xxx")
        monkeypatch.delenv("GITHUB_REPOSITORY", raising=False)

        # Should raise ValueError
        with pytest.raises(ValueError, match="GITHUB_REPOSITORY environment variable not set"):
            file_bug_from_test_failure(
                test_name="test_example",
                error_message="Test failed",
                stack_trace="Error at line 42",
                test_type="load"
            )


class TestBugFilingAttachments:
    """Test screenshot and log attachment functionality."""

    def test_attach_screenshot_with_existing_file(self, bug_filing_service, test_metadata, sample_screenshot_file):
        """Test attaching screenshot when file exists."""
        # Update metadata with real screenshot path
        test_metadata["screenshot_path"] = sample_screenshot_file

        # File bug (should attach screenshot)
        result = bug_filing_service.file_bug(
            test_name="test_with_screenshot",
            error_message="Test failed",
            metadata=test_metadata
        )

        # Verify issue created
        assert result["status"] == "created"

    def test_attach_screenshot_with_missing_file(self, bug_filing_service, test_metadata, capsys):
        """Test attaching screenshot when file doesn't exist (should warn)."""
        # Use non-existent screenshot path
        test_metadata["screenshot_path"] = "/nonexistent/screenshot.png"

        # File bug (should warn but not fail)
        result = bug_filing_service.file_bug(
            test_name="test_with_missing_screenshot",
            error_message="Test failed",
            metadata=test_metadata
        )

        # Verify issue still created
        assert result["status"] == "created"

        # Verify warning printed
        captured = capsys.readouterr()
        assert "Warning: Screenshot file not found" in captured.out

    def test_attach_logs_with_existing_file(self, bug_filing_service, test_metadata, sample_log_file):
        """Test attaching logs when file exists."""
        # Update metadata with real log path
        test_metadata["log_path"] = sample_log_file

        # File bug (should attach logs)
        result = bug_filing_service.file_bug(
            test_name="test_with_logs",
            error_message="Test failed",
            metadata=test_metadata
        )

        # Verify issue created
        assert result["status"] == "created"

    def test_attach_logs_with_missing_file(self, bug_filing_service, test_metadata, capsys):
        """Test attaching logs when file doesn't exist (should warn)."""
        # Use non-existent log path
        test_metadata["log_path"] = "/nonexistent/test.log"

        # File bug (should warn but not fail)
        result = bug_filing_service.file_bug(
            test_name="test_with_missing_logs",
            error_message="Test failed",
            metadata=test_metadata
        )

        # Verify issue still created
        assert result["status"] == "created"

        # Verify warning printed
        captured = capsys.readouterr()
        assert "Warning: Log file not found" in captured.out
