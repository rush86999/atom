"""
Memory and Performance Bug Filing Fixtures

This module provides pytest fixtures and helper functions for automatically
filing memory and performance bugs during test execution. These fixtures
integrate with the MemoryPerformanceFilingService to provide convenient
bug filing with graceful degradation.

Key Fixtures:
- file_memory_bug: Helper function to file memory leak bugs
- file_performance_bug: Helper function to file performance regression bugs
- memory_bug_metadata: Standard metadata dict for memory bugs
- performance_bug_metadata: Standard metadata dict for performance bugs

Usage:
    def test_memory_leak_detected(memray_session, file_memory_bug):
        # Run test that detects memory leak
        memory_growth_mb = calculate_memory_growth()

        if memory_growth_mb > 10:
            # File bug automatically
            file_memory_bug(
                test_name="test_memory_leak_detected",
                memory_increase_mb=memory_growth_mb,
                iterations=100
            )

        assert memory_growth_mb < 10

Phase: 243-04 (Memory & Performance Bug Discovery)
See: .planning/phases/243-memory-and-performance-bug-discovery/243-04-PLAN.md
"""

import os
from typing import Dict, Optional
from datetime import datetime

import pytest

# Import MemoryPerformanceFilingService
from backend.tests.bug_discovery.core.memory_performance_filing import (
    MemoryPerformanceFilingService,
    file_memory_bug_from_test,
    file_performance_bug_from_test
)


# =============================================================================
# Memory Bug Filing Helper Fixture
# =============================================================================

@pytest.fixture(scope="function")
def file_memory_bug():
    """
    Helper function to file memory leak bugs from test failures.

    This fixture provides a convenience wrapper around MemoryPerformanceFilingService
    for filing memory leak bugs with standard metadata. It handles graceful
    degradation if GitHub credentials are not configured.

    Returns:
        Callable[[str, float, int, **kwargs], Optional[Dict]]: Bug filing function

    Args:
        test_name: Name of the failed test
        memory_increase_mb: Memory growth in MB
        iterations: Number of iterations performed
        flame_graph_path: Optional path to flame graph artifact
        **kwargs: Additional metadata (test_file, platform, etc.)

    Returns:
        Dict with issue URL and number if created, or None if credentials missing

    Examples:
        def test_canvas_presentation_no_leak(memray_session, file_memory_bug):
            # ... run test, detect memory leak ...
            memory_growth_mb = 15.5

            if memory_growth_mb >= 10:
                file_memory_bug(
                    test_name="test_canvas_presentation_no_leak",
                    memory_increase_mb=memory_growth_mb,
                    iterations=50,
                    test_file=__file__,
                    platform="backend-python"
                )

            assert memory_growth_mb < 10

    Graceful Degradation:
        - Returns None if GITHUB_TOKEN not set (no error raised)
        - Returns None if GITHUB_REPOSITORY not set (no error raised)
        - Prints warning message instead of raising exception
        - Tests continue to run and report failures normally

    Phase: 243-04
    """
    def _file_memory_bug(
        test_name: str,
        memory_increase_mb: float,
        iterations: int,
        flame_graph_path: Optional[str] = None,
        **kwargs
    ) -> Optional[Dict]:
        """
        File memory leak bug with standard metadata.

        Args:
            test_name: Name of the failed test
            memory_increase_mb: Memory growth in MB
            iterations: Number of iterations performed
            flame_graph_path: Optional path to flame graph artifact
            **kwargs: Additional metadata

        Returns:
            Dict with issue URL and number if created, or None if credentials missing
        """
        # Add standard metadata
        metadata = {
            "test_file": kwargs.get("test_file", "unknown"),
            "platform": kwargs.get("platform", "backend-python"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # Merge additional metadata
        metadata.update(kwargs)

        # File bug using convenience function
        return file_memory_bug_from_test(
            test_name=test_name,
            memory_increase_mb=memory_increase_mb,
            iterations=iterations,
            flame_graph_path=flame_graph_path,
            **metadata
        )

    return _file_memory_bug


# =============================================================================
# Performance Bug Filing Helper Fixture
# =============================================================================

@pytest.fixture(scope="function")
def file_performance_bug():
    """
    Helper function to file performance regression bugs from test failures.

    This fixture provides a convenience wrapper around MemoryPerformanceFilingService
    for filing performance regression bugs with standard metadata. It handles
    graceful degradation if GitHub credentials are not configured.

    Returns:
        Callable[[str, float, float, float, **kwargs], Optional[Dict]]: Bug filing function

    Args:
        test_name: Name of the failed test
        baseline_ms: Baseline latency in milliseconds
        actual_ms: Actual latency in milliseconds
        degradation_percent: Performance degradation as percentage
        throughput_baseline: Optional baseline throughput (ops/sec)
        throughput_actual: Optional actual throughput (ops/sec)
        **kwargs: Additional metadata (test_file, platform, etc.)

    Returns:
        Dict with issue URL and number if created, or None if credentials missing

    Examples:
        def test_api_latency_no_regression(file_performance_bug):
            # ... run test, measure latency ...
            baseline_ms = 100
            actual_ms = 150
            degradation_percent = 50.0

            if degradation_percent >= 20:
                file_performance_bug(
                    test_name="test_api_latency_no_regression",
                    baseline_ms=baseline_ms,
                    actual_ms=actual_ms,
                    degradation_percent=degradation_percent,
                    test_file=__file__,
                    platform="backend-python"
                )

            assert degradation_percent < 20

    Graceful Degradation:
        - Returns None if GITHUB_TOKEN not set (no error raised)
        - Returns None if GITHUB_REPOSITORY not set (no error raised)
        - Prints warning message instead of raising exception
        - Tests continue to run and report failures normally

    Phase: 243-04
    """
    def _file_performance_bug(
        test_name: str,
        baseline_ms: float,
        actual_ms: float,
        degradation_percent: float,
        throughput_baseline: Optional[float] = None,
        throughput_actual: Optional[float] = None,
        **kwargs
    ) -> Optional[Dict]:
        """
        File performance regression bug with standard metadata.

        Args:
            test_name: Name of the failed test
            baseline_ms: Baseline latency in milliseconds
            actual_ms: Actual latency in milliseconds
            degradation_percent: Performance degradation as percentage
            throughput_baseline: Optional baseline throughput (ops/sec)
            throughput_actual: Optional actual throughput (ops/sec)
            **kwargs: Additional metadata

        Returns:
            Dict with issue URL and number if created, or None if credentials missing
        """
        # Add standard metadata
        metadata = {
            "test_file": kwargs.get("test_file", "unknown"),
            "platform": kwargs.get("platform", "backend-python"),
            "timestamp": datetime.utcnow().isoformat() + "Z"
        }

        # Merge additional metadata
        metadata.update(kwargs)

        # File bug using convenience function
        return file_performance_bug_from_test(
            test_name=test_name,
            baseline_ms=baseline_ms,
            actual_ms=actual_ms,
            degradation_percent=degradation_percent,
            throughput_baseline=throughput_baseline,
            throughput_actual=throughput_actual,
            **metadata
        )

    return _file_performance_bug


# =============================================================================
# Memory Bug Metadata Fixture
# =============================================================================

@pytest.fixture(scope="function")
def memory_bug_metadata():
    """
    Standard metadata dictionary for memory bug filing.

    This fixture provides a pre-populated metadata dict with common fields
    for memory leak bugs. Tests can customize it by adding additional fields.

    Returns:
        Dict: Standard metadata dict for memory bugs

    Examples:
        def test_memory_leak_with_metadata(memray_session, memory_bug_metadata, file_memory_bug):
            # Customize metadata
            memory_bug_metadata["canvas_type"] = "chart"
            memory_bug_metadata["ui_framework"] = "react"

            # File bug with custom metadata
            file_memory_bug(
                test_name="test_memory_leak_with_metadata",
                memory_increase_mb=15.5,
                iterations=50,
                **memory_bug_metadata
            )

    Standard Fields:
        - test_type: "memory"
        - platform: "backend-python"
        - timestamp: ISO format timestamp
        - python_version: Python version
        - os_info: Operating system info

    Phase: 243-04
    """
    import platform

    return {
        "test_type": "memory",
        "platform": "backend-python",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "python_version": platform.python_version(),
        "os_info": platform.platform()
    }


# =============================================================================
# Performance Bug Metadata Fixture
# =============================================================================

@pytest.fixture(scope="function")
def performance_bug_metadata():
    """
    Standard metadata dictionary for performance bug filing.

    This fixture provides a pre-populated metadata dict with common fields
    for performance regression bugs. Tests can customize it by adding
    additional fields.

    Returns:
        Dict: Standard metadata dict for performance bugs

    Examples:
        def test_performance_regression_with_metadata(performance_bug_metadata, file_performance_bug):
            # Customize metadata
            performance_bug_metadata["endpoint"] = "/api/v1/agents"
            performance_bug_metadata["http_method"] = "POST"

            # File bug with custom metadata
            file_performance_bug(
                test_name="test_performance_regression_with_metadata",
                baseline_ms=100,
                actual_ms=150,
                degradation_percent=50.0,
                **performance_bug_metadata
            )

    Standard Fields:
        - test_type: "performance"
        - platform: "backend-python"
        - timestamp: ISO format timestamp
        - python_version: Python version
        - os_info: Operating system info

    Phase: 243-04
    """
    import platform

    return {
        "test_type": "performance",
        "platform": "backend-python",
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "python_version": platform.python_version(),
        "os_info": platform.platform()
    }


# =============================================================================
# GitHub Credentials Validation Fixture
# =============================================================================

@pytest.fixture(scope="session")
def github_credentials_available():
    """
    Check if GitHub credentials are available for bug filing.

    This fixture checks if GITHUB_TOKEN and GITHUB_REPOSITORY environment
    variables are set. Tests can use this fixture to skip bug filing
    verification steps when credentials are not available.

    Returns:
        bool: True if credentials are available, False otherwise

    Examples:
        def test_bug_filing_integration(github_credentials_available):
            if not github_credentials_available:
                pytest.skip("GitHub credentials not available")

            # Verify bug filing works
            result = file_memory_bug(...)
            assert result is not None
            assert "issue_url" in result

    Phase: 243-04
    """
    github_token = os.getenv("GITHUB_TOKEN")
    github_repository = os.getenv("GITHUB_REPOSITORY")

    return bool(github_token and github_repository)


# =============================================================================
# Pytest Configuration
# =============================================================================

def pytest_configure(config):
    """
    Configure pytest markers for memory/performance bug filing.

    This function is called by pytest at configuration time to register
    custom markers used in memory and performance bug filing tests.

    Markers Registered:
        - files_memory_bugs: Tests that file memory leak bugs
        - files_performance_bugs: Tests that file performance regression bugs

    Usage:
        @pytest.mark.files_memory_bugs
        def test_memory_leak_files_bug(file_memory_bug):
            ...

    Phase: 243-04
    """
    config.addinivalue_line(
        "markers",
        "files_memory_bugs: Tests that file memory leak bugs (requires GITHUB_TOKEN)"
    )
    config.addinivalue_line(
        "markers",
        "files_performance_bugs: Tests that file performance regression bugs (requires GITHUB_TOKEN)"
    )
