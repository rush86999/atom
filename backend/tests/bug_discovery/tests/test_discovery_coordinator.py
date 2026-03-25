"""
Integration tests for DiscoveryCoordinator service.

Tests end-to-end orchestration of all discovery methods.
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import Mock, patch, MagicMock

from tests.bug_discovery.models.bug_report import BugReport, DiscoveryMethod
from tests.bug_discovery.core.discovery_coordinator import DiscoveryCoordinator


class TestDiscoveryCoordinator:
    """Test DiscoveryCoordinator orchestration."""

    @pytest.fixture
    def coordinator(self):
        """Create DiscoveryCoordinator with mock credentials."""
        with tempfile.TemporaryDirectory() as tmpdir:
            yield DiscoveryCoordinator(
                github_token="test_token",
                github_repository="test/repo",
                storage_dir=tmpdir
            )

    def test_initialization(self, coordinator):
        """Test DiscoveryCoordinator initializes with all services."""
        assert coordinator.bug_filing_service is not None
        assert coordinator.result_aggregator is not None
        assert coordinator.bug_deduplicator is not None
        assert coordinator.severity_classifier is not None
        assert coordinator.dashboard_generator is not None

    def test_run_full_discovery_with_mocks(self, coordinator):
        """Test full discovery run with mocked discovery methods."""
        # Mock all discovery methods
        coordinator._run_fuzzing_discovery = Mock(return_value=[
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="fuzzing_test",
                error_message="Fuzzing crash",
                error_signature="fuzz_sig"
            )
        ])
        coordinator._run_chaos_discovery = Mock(return_value=[])
        coordinator._run_property_discovery = Mock(return_value=[])
        coordinator._run_browser_discovery = Mock(return_value=[])

        # Mock bug filing
        coordinator.bug_filing_service.file_bug = Mock(return_value={
            "status": "created",
            "issue_number": 123
        })

        result = coordinator.run_full_discovery(
            duration_seconds=60,
            run_property_tests=False,
            run_browser_discovery=False
        )

        assert result["bugs_found"] == 1
        assert result["unique_bugs"] == 1
        assert result["filed_bugs"] == 1
        assert "report_path" in result
        assert Path(result["report_path"]).exists()

    def test_integration_flow_end_to_end(self, coordinator):
        """Test complete integration flow with minimal mocking."""
        # Create mock reports
        mock_reports = [
            BugReport(
                discovery_method=DiscoveryMethod.FUZZING,
                test_name="test",
                error_message="Test error",
                error_signature="test_sig"
            )
        ]

        # Mock discovery methods to return empty (focus on aggregation flow)
        coordinator._run_fuzzing_discovery = Mock(return_value=mock_reports)
        coordinator._run_chaos_discovery = Mock(return_value=[])
        coordinator._run_property_discovery = Mock(return_value=[])
        coordinator._run_browser_discovery = Mock(return_value=[])

        # Mock bug filing
        coordinator.bug_filing_service.file_bug = Mock(return_value={
            "status": "created",
            "issue_number": 42
        })

        result = coordinator.run_full_discovery(
            duration_seconds=1,
            run_property_tests=False,
            run_browser_discovery=False
        )

        # Verify flow completed
        assert coordinator._run_fuzzing_discovery.called
        assert coordinator.result_aggregator is not None
        assert coordinator.bug_deduplicator is not None
        assert coordinator.severity_classifier is not None
        assert coordinator.bug_filing_service.file_bug.called
        assert result["bugs_found"] == 1

    @patch('tests.bug_discovery.core.discovery_coordinator.os.getenv')
    def test_run_discovery_convenience_function(self, mock_getenv):
        """Test run_discovery convenience function."""
        mock_getenv.side_effect = lambda k, d=None: "test_value" if k in ["GITHUB_TOKEN", "GITHUB_REPOSITORY"] else d

        with patch('tests.bug_discovery.core.discovery_coordinator.DiscoveryCoordinator') as mock_coordinator:
            mock_instance = MagicMock()
            mock_instance.run_full_discovery.return_value = {
                "bugs_found": 5,
                "unique_bugs": 3
            }
            mock_coordinator.return_value = mock_instance

            from tests.bug_discovery.core.discovery_coordinator import run_discovery

            result = run_discovery(duration_seconds=60)

            assert result["bugs_found"] == 5
            assert mock_coordinator.called
