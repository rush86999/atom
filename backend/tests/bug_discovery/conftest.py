"""
Bug Discovery Test Configuration

This module imports bug filing fixtures for pytest discovery.
"""

from backend.tests.bug_discovery.fixtures.bug_filing_fixtures import (
    mock_github_api,
    bug_filing_service,
    test_metadata,
    test_metadata_network,
    test_metadata_memory,
    test_metadata_mobile,
    test_metadata_desktop,
    test_metadata_visual,
    test_metadata_a11y,
    artifacts_dir,
    sample_screenshot_file,
    sample_log_file
)

__all__ = [
    "mock_github_api",
    "bug_filing_service",
    "test_metadata",
    "test_metadata_network",
    "test_metadata_memory",
    "test_metadata_mobile",
    "test_metadata_desktop",
    "test_metadata_visual",
    "test_metadata_a11y",
    "artifacts_dir",
    "sample_screenshot_file",
    "sample_log_file"
]
