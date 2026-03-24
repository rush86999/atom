"""
Bug Filing Fixtures for Automated Bug Discovery Tests

This module provides pytest fixtures for testing the bug filing service,
including mock GitHub API, test metadata, and failure capture hooks.
"""

import os
import tempfile
from typing import Dict, List, Optional
from datetime import datetime
from unittest.mock import Mock, patch, MagicMock

import pytest
import requests

from backend.tests.bug_discovery.bug_filing_service import BugFilingService


@pytest.fixture
def mock_github_api():
    """
    Mock GitHub API calls for testing.

    Returns:
        Mock object that tracks GitHub API calls
    """
    # Create mock for requests.Session
    mock_session = MagicMock()
    mock_response = MagicMock()

    # Track created issues
    created_issues: List[Dict] = []

    def mock_post(url, json=None, **kwargs):
        """Mock POST requests (issue creation)."""
        mock_response.status_code = 201
        issue_number = len(created_issues) + 1
        issue_data = {
            "number": issue_number,
            "html_url": f"https://github.com/test/repo/issues/{issue_number}",
            "title": json.get("title", "Test Bug"),
            "body": json.get("body", ""),
            "labels": json.get("labels", []),
            "state": "open"
        }
        created_issues.append(issue_data)
        mock_response.json.return_value = issue_data
        return mock_response

    def mock_get(url, params=None, **kwargs):
        """Mock GET requests (issue listing)."""
        mock_response.status_code = 200
        mock_response.json.return_value = created_issues
        return mock_response

    mock_session.post.side_effect = mock_post
    mock_session.get.side_effect = mock_get
    mock_session.headers = {}

    # Patch requests.Session
    with patch("backend.tests.bug_discovery.bug_filing_service.requests.Session", return_value=mock_session):
        yield mock_session, created_issues


@pytest.fixture
def bug_filing_service(mock_github_api):
    """
    Create BugFilingService instance for testing.

    Args:
        mock_github_api: Mock GitHub API fixture

    Returns:
        BugFilingService instance
    """
    mock_session, created_issues = mock_github_api

    # Create service with test config
    service = BugFilingService(
        github_token="test_token_ghp_xxx",
        github_repository="test/repo"
    )

    # Inject mock session
    service.session = mock_session

    return service


@pytest.fixture
def test_metadata() -> Dict:
    """
    Create sample metadata dict for testing.

    Returns:
        Dict with test metadata simulating test failure
    """
    return {
        "test_file": "backend/tests/load/test_api_load_baseline.py",
        "error_type": "Load Test Failure",
        "stack_trace": "Error: p(95) > 500ms\n  at test_api_load_baseline (test_api_load_baseline.py:42)",
        "screenshot_path": "/tmp/test_screenshot.png",
        "screenshot_url": "https://example.com/screenshot.png",
        "log_path": "/tmp/test_log.log",
        "log_content": "INFO: Starting load test\nERROR: Threshold exceeded: p(95) = 650ms",
        "performance_metrics": {
            "p95_latency_ms": 650,
            "p99_latency_ms": 1200,
            "error_rate": 8.5,
            "throughput_rps": 45
        },
        "platform_info": "Linux-5.15.0-x86_64-with-glibc2.35",
        "os_info": "Linux-5.15.0-x86_64-with-glibc2.35",
        "python_version": "3.11.2",
        "test_type": "load",
        "platform": "web",
        "ci_run_url": "https://github.com/test/repo/actions/runs/12345",
        "commit_sha": "abc123def456",
        "branch_name": "main"
    }


@pytest.fixture
def test_metadata_network() -> Dict:
    """
    Create sample metadata for network test failure.

    Returns:
        Dict with network test metadata
    """
    return {
        "test_file": "backend/tests/e2e_ui/tests/test_network_simulation.py",
        "error_type": "Network Test Failure",
        "stack_trace": "Error: Offline mode not handled\n  at test_offline_mode (test_network_simulation.py:15)",
        "screenshot_path": "",
        "log_path": "/tmp/network_test.log",
        "log_content": "INFO: Starting offline mode test\nERROR: Application not handling offline mode",
        "network_condition": "offline",
        "test_type": "network",
        "platform": "web",
        "os_info": "macOS-14.2-arm64-arm-64bit",
        "python_version": "3.11.2"
    }


@pytest.fixture
def test_metadata_memory() -> Dict:
    """
    Create sample metadata for memory leak test failure.

    Returns:
        Dict with memory leak test metadata
    """
    return {
        "test_file": "backend/tests/e2e_ui/tests/test_memory_leaks.py",
        "error_type": "Memory Leak Detected",
        "stack_trace": "Error: Memory leak: 10MB increase after 10 iterations\n  at test_memory_leak_agent_execution (test_memory_leaks.py:28)",
        "screenshot_path": "",
        "log_path": "/tmp/memory_test.log",
        "log_content": "INFO: Starting memory leak test\nERROR: Heap size increased by 10.5MB",
        "memory_increase_mb": 10.5,
        "iterations": 10,
        "test_type": "memory",
        "platform": "web",
        "os_info": "Windows-11-10.0.22621",
        "python_version": "3.11.2"
    }


@pytest.fixture
def test_metadata_mobile() -> Dict:
    """
    Create sample metadata for mobile API test failure.

    Returns:
        Dict with mobile test metadata
    """
    return {
        "test_file": "backend/tests/mobile_api/test_mobile_auth.py",
        "error_type": "Mobile API Failure",
        "stack_trace": "Error: API returned 500\n  at test_mobile_agent_execute (test_mobile_auth.py:45)",
        "screenshot_path": "",
        "log_path": "/tmp/mobile_test.log",
        "log_content": "INFO: Testing mobile agent execution\nERROR: POST /api/v1/agents/execute returned 500",
        "endpoint": "/api/v1/agents/execute",
        "status_code": 500,
        "test_type": "mobile",
        "platform": "mobile",
        "device": "iPhone 14",
        "os_info": "iOS-17.2",
        "python_version": "3.11.2"
    }


@pytest.fixture
def test_metadata_desktop() -> Dict:
    """
    Create sample metadata for desktop test failure.

    Returns:
        Dict with desktop test metadata
    """
    return {
        "test_file": "backend/tests/desktop/test_window_management.py",
        "error_type": "Desktop Test Failure",
        "stack_trace": "Error: Window minimize failed\n  at test_window_minimize (test_window_management.py:33)",
        "screenshot_path": "/tmp/desktop_screenshot.png",
        "log_path": "/tmp/desktop_test.log",
        "log_content": "INFO: Testing window management\nERROR: Window.minimize() call failed",
        "action": "minimize",
        "test_type": "desktop",
        "platform": "desktop",
        "os_info": "macOS-14.2-arm64-arm-64bit",
        "python_version": "3.11.2"
    }


@pytest.fixture
def test_metadata_visual() -> Dict:
    """
    Create sample metadata for visual regression test failure.

    Returns:
        Dict with visual regression test metadata
    """
    return {
        "test_file": "backend/tests/visual/test_visual_regression.py",
        "error_type": "Visual Regression Detected",
        "stack_trace": "Error: Visual diff detected\n  at test_visual_dashboard (test_visual_regression.py:22)",
        "screenshot_path": "/tmp/visual_diff.png",
        "log_path": "/tmp/visual_test.log",
        "log_content": "INFO: Running visual regression test\nERROR: Percy detected 3 pixel differences",
        "percy_diff_url": "https://percy.io/test/repo/builds/12345/comparisons/67890",
        "pixel_diff_count": 3,
        "test_type": "visual",
        "platform": "web",
        "os_info": "Linux-5.15.0-x86_64",
        "python_version": "3.11.2"
    }


@pytest.fixture
def test_metadata_a11y() -> Dict:
    """
    Create sample metadata for accessibility test failure.

    Returns:
        Dict with accessibility test metadata
    """
    return {
        "test_file": "backend/tests/a11y/test_wcag_compliance.py",
        "error_type": "WCAG Violation Detected",
        "stack_trace": "Error: WCAG violation: color-contrast\n  at test_wcag_compliance_dashboard (test_wcag_compliance.py:18)",
        "screenshot_path": "/tmp/a11y_screenshot.png",
        "log_path": "/tmp/a11y_test.log",
        "log_content": "INFO: Running WCAG compliance test\nERROR: Axe-core detected 5 violations",
        "violation_type": "color-contrast",
        "violation_count": 5,
        "wcag_level": "AA",
        "test_type": "a11y",
        "platform": "web",
        "os_info": "macOS-14.2-arm64-arm-64bit",
        "python_version": "3.11.2"
    }


@pytest.fixture
def artifacts_dir():
    """
    Create temporary artifacts directory for test screenshots and logs.

    Returns:
        Path to temporary artifacts directory
    """
    artifacts_path = tempfile.mkdtemp(prefix="test_artifacts_")

    # Create subdirectories
    os.makedirs(os.path.join(artifacts_path, "screenshots"), exist_ok=True)
    os.makedirs(os.path.join(artifacts_path, "logs"), exist_ok=True)

    yield artifacts_path

    # Cleanup
    import shutil
    shutil.rmtree(artifacts_path, ignore_errors=True)


@pytest.fixture(autouse=True)
def capture_screenshot_on_failure(request, artifacts_dir):
    """
    Pytest hook to capture screenshot on test failure.

    This fixture runs automatically and captures screenshots
    when tests fail (for visual/E2E tests).

    Args:
        request: Pytest request object
        artifacts_dir: Temporary artifacts directory
    """
    yield

    # Check if test failed
    if request.node.rep_call.failed:
        # Only capture screenshots for E2E or visual tests
        test_type = request.node.get_closest_marker("test_type")
        if test_type and test_type.args[0] in ["e2e", "visual"]:
            try:
                # Try to get page from test if available
                if hasattr(request.node, "obj") and hasattr(request.node.obj, "page"):
                    page = request.node.obj.page
                    screenshot_path = os.path.join(
                        artifacts_path,
                        "screenshots",
                        f"{request.node.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
                    )
                    page.screenshot(path=screenshot_path)
                    print(f"Screenshot saved to: {screenshot_path}")
            except Exception as e:
                print(f"Warning: Failed to capture screenshot: {e}")


@pytest.fixture(autouse=True)
def capture_log_on_failure(request, artifacts_dir):
    """
    Pytest hook to capture logs on test failure.

    This fixture runs automatically and captures test logs
    when tests fail.

    Args:
        request: Pytest request object
        artifacts_dir: Temporary artifacts directory
    """
    yield

    # Check if test failed
    if request.node.rep_call.failed:
        try:
            # Capture log output
            log_path = os.path.join(
                artifacts_dir,
                "logs",
                f"{request.node.name}_{datetime.now().strftime('%Y%m%d_%H%M%S')}.log"
            )

            # Write captured logs (if any)
            with open(log_path, "w") as f:
                f.write(f"Test: {request.node.name}\n")
                f.write(f"File: {request.node.fspath}\n")
                f.write(f"Failed at: {datetime.now().isoformat()}\n")
                f.write(f"Status: {request.node.rep_call.outcome}\n")

                # Add exception info if available
                if hasattr(request.node, "rep_call") and request.node.rep_call.failed:
                    if hasattr(request.node.rep_call, "longrepr"):
                        f.write(f"\nException:\n{request.node.rep_call.longrepr}\n")

            print(f"Log saved to: {log_path}")
        except Exception as e:
            print(f"Warning: Failed to capture logs: {e}")


@pytest.fixture
def sample_screenshot_file(artifacts_dir):
    """
    Create a sample screenshot file for testing.

    Args:
        artifacts_dir: Temporary artifacts directory

    Returns:
        Path to sample screenshot file
    """
    screenshot_path = os.path.join(artifacts_dir, "screenshots", "test_screenshot.png")

    # Create a minimal PNG file (1x1 pixel)
    import struct
    with open(screenshot_path, "wb") as f:
        # PNG header
        f.write(b'\x89PNG\r\n\x1a\n')
        # IHDR chunk (1x1 pixel)
        f.write(struct.pack('>I', 13))  # Length
        f.write(b'IHDR')
        f.write(struct.pack('>I', 1))  # Width
        f.write(struct.pack('>I', 1))  # Height
        f.write(b'\x08\x02\x00\x00\x00')  # Bit depth, color type, etc.
        f.write(struct.pack('>I', 0x419bdfc9))  # CRC

    return screenshot_path


@pytest.fixture
def sample_log_file(artifacts_dir):
    """
    Create a sample log file for testing.

    Args:
        artifacts_dir: Temporary artifacts directory

    Returns:
        Path to sample log file
    """
    log_path = os.path.join(artifacts_dir, "logs", "test_log.log")

    with open(log_path, "w") as f:
        f.write("INFO: Starting test\n")
        f.write("DEBUG: Initializing test data\n")
        f.write("ERROR: Test assertion failed\n")
        f.write("TRACEBACK: at test_example (test_example.py:10)\n")

    return log_path


# Pytest hook configuration
@pytest.hookimpl(tryfirst=True, hookwrapper=True)
def pytest_runtest_makereport(item, call):
    """
    Pytest hook to capture test result for screenshot/log capture.

    This hook stores the test result in item.rep_call so other
    fixtures can access it.
    """
    outcome = yield
    rep = outcome.get_result()

    # Store report for other fixtures
    setattr(item, "rep_" + rep.when, rep)
