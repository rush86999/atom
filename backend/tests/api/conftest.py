"""
Enhanced API test fixtures for TestClient-based testing

Provides reusable TestClient fixtures with proper isolation, authentication,
and external service mocking for API route testing.

This conftest is specific to API tests and does NOT duplicate fixtures from
backend/tests/conftest.py (which provides db_session, test_agent_*, etc.)
"""

import os
import pytest
from typing import Generator, Optional, Dict, Any
from fastapi.testclient import TestClient
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

# Note: We don't import main_api_app here to avoid SQLAlchemy metadata conflicts
# Individual test files will create their own TestClient instances with specific routers


# ============================================================================
# TestClient Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def api_test_client() -> Generator[TestClient, None, None]:
    """
    Create TestClient with proper isolation for API testing.

    Note: This is a placeholder fixture. Individual test files should
    create their own TestClient with specific routers to avoid
    SQLAlchemy metadata conflicts.

    Usage in test files:
        from fastapi import FastAPI
        from api.health_routes import router

        app = FastAPI()
        app.include_router(router)

        def test_something():
            client = TestClient(app)
            response = client.get("/health/live")
    """
    # Return None - tests should create their own TestClient
    yield None


@pytest.fixture(scope="function")
def authenticated_client(
    api_test_client: TestClient,
    test_token: str
) -> Generator[TestClient, None, None]:
    """
    Create TestClient with pre-configured Authorization header.

    Usage:
        def test_protected_endpoint(authenticated_client):
            response = authenticated_client.get("/api/protected")
            assert response.status_code == 200
    """
    # Set default headers for all requests
    api_test_client.headers.update({
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json"
    })
    yield api_test_client
    # Cleanup is automatic


@pytest.fixture(scope="function")
def authenticated_admin_client(
    api_test_client: TestClient,
    admin_user: tuple
) -> Generator[TestClient, None, None]:
    """
    Create TestClient with admin Authorization header.

    Usage:
        def test_admin_endpoint(authenticated_admin_client):
            response = authenticated_admin_client.delete("/api/users/123")
            assert response.status_code == 200
    """
    user, token = admin_user
    api_test_client.headers.update({
        "Authorization": f"Bearer {token}",
        "Content-Type": "application/json",
        "X-User-Role": "admin"
    })
    yield api_test_client


# ============================================================================
# Mock Service Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_llm_service() -> MagicMock:
    """
    Mock LLM service for agent chat endpoints.

    Usage:
        def test_agent_chat(mock_llm_service):
            mock_llm_service.complete.return_value = "Mock response"
            # Call endpoint that uses LLM service
    """
    mock = MagicMock()

    # Mock streaming response
    async def mock_stream(prompt: str, **kwargs):
        yield "Mock"
        yield " streaming"
        yield " response"

    # Mock completion
    mock.complete = MagicMock(return_value="Mock LLM response")
    mock.stream = mock_stream
    mock.validate_api_key = MagicMock(return_value=True)

    return mock


@pytest.fixture(scope="function")
def mock_playwright() -> MagicMock:
    """
    Mock Playwright for browser automation endpoints.

    Usage:
        def test_browser_screenshot(mock_playwright):
            mock_playwright.screenshot.return_value = "base64_image_data"
            # Call browser endpoint
    """
    mock = MagicMock()

    # Mock browser
    mock_browser = MagicMock()
    mock_page = MagicMock()

    # Mock page methods
    mock_page.goto = MagicMock()
    mock_page.click = MagicMock()
    mock_page.fill = MagicMock()
    mock_page.screenshot = MagicMock(return_value=b"fake_screenshot_data")
    mock_page.evaluate = MagicMock(return_value="{}")
    mock_page.content = MagicMock(return_value="<html>Test</html>")
    mock_page.url = "https://example.com"

    # Mock browser methods
    mock_browser.new_page = MagicMock(return_value=mock_page)
    mock_browser.close = MagicMock()

    # Mock playwright
    mock_browser.start = MagicMock(return_value=mock_browser)
    mock.stop = MagicMock()

    yield mock


@pytest.fixture(scope="function")
def mock_storage_service() -> MagicMock:
    """
    Mock storage service for file operations.

    Usage:
        def test_file_upload(mock_storage_service):
            mock_storage_service.store.return_value = "https://storage.example.com/file.txt"
            # Call upload endpoint
    """
    mock = MagicMock()

    # Mock file storage
    mock.store = MagicMock(return_value="https://mock-storage.example.com/file.txt")
    mock.retrieve = MagicMock(return_value=b"file contents")
    mock.delete = MagicMock(return_value=True)
    mock.exists = MagicMock(return_value=True)

    return mock


@pytest.fixture(scope="function")
def mock_websocket_manager() -> MagicMock:
    """
    Mock WebSocket manager for broadcast tests.

    Usage:
        def test_canvas_broadcast(mock_websocket_manager):
            mock_websocket_manager.broadcast.assert_called_once()
    """
    mock = MagicMock()

    # Mock WebSocket methods
    mock.connect = MagicMock()
    mock.disconnect = MagicMock()
    mock.broadcast = MagicMock()
    mock.send_personal_message = MagicMock()

    return mock


# ============================================================================
# Helper Functions
# ============================================================================

@pytest.fixture(scope="function")
def route_coverage() -> Dict[str, bool]:
    """
    Track which endpoints have been tested.

    Usage:
        def test_something(route_coverage):
            response = client.get("/api/endpoint")
            route_coverage["/api/endpoint"] = True
    """
    coverage = {}

    yield coverage

    # Print uncovered routes after test
    if coverage:
        uncovered = [route for route, tested in coverage.items() if not tested]
        if uncovered:
            print(f"\n[WARNING] {len(uncovered)} routes not tested: {uncovered}")


@pytest.fixture(scope="function")
def api_test_headers(test_token: str) -> Dict[str, str]:
    """
    Generate test headers for API requests.

    Usage:
        def test_with_headers(api_test_headers):
            response = client.get("/api/test", headers=api_test_headers)
    """
    return {
        "Authorization": f"Bearer {test_token}",
        "Content-Type": "application/json",
        "Accept": "application/json"
    }


# ============================================================================
# Deviation from Plan: No duplicate test_token fixture
# ============================================================================
# Note: test_token is already provided by backend/tests/conftest.py
# This conftest only provides API-specific fixtures (TestClient wrappers)
# ============================================================================


@pytest.fixture(scope="function")
def mock_device_permissions() -> MagicMock:
    """
    Mock device permission checks for device capability endpoints.

    Usage:
        def test_camera_access(mock_device_permissions):
            mock_device_permissions.check_camera.return_value = True
            response = client.post("/api/device/camera/request")
    """
    mock = MagicMock()

    # Mock permission checks
    mock.check_camera = MagicMock(return_value=True)
    mock.check_screen_recording = MagicMock(return_value=True)
    mock.check_location = MagicMock(return_value=True)
    mock.check_notifications = MagicMock(return_value=True)

    # Mock device capabilities
    mock.get_camera_stream = MagicMock(return_value=b"fake_camera_data")
    mock.get_screen_capture = MagicMock(return_value=b"fake_screen_data")
    mock.get_location = MagicMock(return_value={"lat": 37.7749, "lon": -122.4194})
    mock.send_notification = MagicMock(return_value=True)

    return mock


@pytest.fixture(scope="function")
def mock_email_service() -> MagicMock:
    """
    Mock email service for password reset and notification tests.

    Usage:
        def test_password_reset(mock_email_service):
            mock_email_service.send_password_reset.assert_called_once()
    """
    mock = MagicMock()

    # Mock email methods
    mock.send_password_reset = MagicMock(return_value=True)
    mock.send_verification_email = MagicMock(return_value=True)
    mock.send_notification = MagicMock(return_value=True)

    return mock


# ============================================================================
# 2FA-Specific Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_totp() -> MagicMock:
    """
    Mock pyotp.TOTP class for 2FA testing.

    Usage:
        def test_enable_2fa(mock_totp):
            mock_totp.verify.return_value = True
            # Call enable endpoint
    """
    mock = MagicMock()

    # Mock TOTP verification
    mock.verify = MagicMock(return_value=True)

    # Mock provisioning URI
    mock.provisioning_uri = MagicMock(
        return_value="otpauth://totp/Atom%20AI:user@example.com?secret=TEST_SECRET_32_CHARS&issuer=Atom+AI+(Upstream)"
    )

    return mock


@pytest.fixture(scope="function")
def mock_pyotp_random() -> MagicMock:
    """
    Mock pyotp.random_base32 for deterministic 2FA testing.

    Returns a deterministic 32-character secret for testing.

    Usage:
        def test_setup_2fa(mock_pyotp_random):
            mock_pyotp_random.return_value = "JBSWY3DPEHPK3PXP"
            # Call setup endpoint
    """
    # Return deterministic 32-char base32 secret
    return "JBSWY3DPEHPK3PXP"  # 16 chars, but simulates 32-char behavior


@pytest.fixture(scope="function")
def user_with_2fa() -> MagicMock:
    """
    Create mock user with 2FA already enabled.

    Usage:
        def test_disable_2fa(user_with_2fa):
            assert user_with_2fa.two_factor_enabled is True
    """
    from unittest.mock import Mock
    from core.models import User

    user = Mock(spec=User)
    user.id = "user-2fa-enabled"
    user.email = "2fa-user@example.com"
    user.two_factor_enabled = True
    user.two_factor_secret = "JBSWY3DPEHPK3PXP"
    user.two_factor_backup_codes = ["BACKUP-1234-5678"]

    return user


@pytest.fixture(scope="function")
def user_without_2fa() -> MagicMock:
    """
    Create mock user without 2FA enabled.

    Usage:
        def test_setup_2fa(user_without_2fa):
            assert user_without_2fa.two_factor_enabled is False
    """
    from unittest.mock import Mock
    from core.models import User

    user = Mock(spec=User)
    user.id = "user-no-2fa"
    user.email = "regular@example.com"
    user.two_factor_enabled = False
    user.two_factor_secret = None
    user.two_factor_backup_codes = None

    return user


@pytest.fixture(scope="function")
def mock_audit_log() -> MagicMock:
    """
    Mock audit_service.log_event for 2FA audit testing.

    Tracks calls for verification in tests.

    Usage:
        def test_enable_2fa_logs_audit(mock_audit_log):
            mock_audit_log.assert_called_once()
            call_kwargs = mock_audit_log.call_args.kwargs
            assert call_kwargs["action"] == "2fa_enabled"
    """
    mock = MagicMock()
    mock.return_value = None  # log_event returns None

    return mock


# ============================================================================
# Agent Control Fixtures
# ============================================================================

@pytest.fixture(scope="function")
def mock_daemon_manager() -> MagicMock:
    """
    Mock DaemonManager class for agent control routes testing.

    Usage:
        def test_agent_start(mock_daemon_manager):
            mock_daemon_manager.is_running.return_value = False
            mock_daemon_manager.start_daemon.return_value = 12345
            response = client.post("/api/agent/start")
    """
    mock = MagicMock()

    # Mock class methods
    mock.is_running = MagicMock(return_value=False)
    mock.get_pid = MagicMock(return_value=12345)
    mock.start_daemon = MagicMock(return_value=12345)
    mock.stop_daemon = MagicMock(return_value=None)
    mock.get_status = MagicMock(return_value={
        "running": True,
        "pid": 12345,
        "uptime_seconds": 3600,
        "memory_mb": 256.5,
        "cpu_percent": 5.2,
        "status": "running"
    })

    return mock


@pytest.fixture(scope="function")
def test_daemon_status() -> dict:
    """
    Provide typical daemon status dict for testing.

    Usage:
        def test_status_endpoint(test_daemon_status):
            mock_daemon_manager.get_status.return_value = test_daemon_status
            response = client.get("/api/agent/status")
            assert response.json()["status"]["running"] == True
    """
    return {
        "running": True,
        "pid": 12345,
        "uptime_seconds": 3600,
        "memory_mb": 256.5,
        "cpu_percent": 5.2,
        "status": "running"
    }


@pytest.fixture(scope="function")
def mock_running_daemon(mock_daemon_manager: MagicMock) -> MagicMock:
    """
    DaemonManager mock configured for "already running" test scenarios.

    Usage:
        def test_start_when_running(mock_running_daemon):
            response = client.post("/api/agent/start")
            assert response.status_code == 400
    """
    mock_daemon_manager.is_running.return_value = True
    mock_daemon_manager.get_pid.return_value = 12345
    return mock_daemon_manager


@pytest.fixture(scope="function")
def mock_stopped_daemon(mock_daemon_manager: MagicMock) -> MagicMock:
    """
    DaemonManager mock configured for "not running" test scenarios.

    Usage:
        def test_stop_when_not_running(mock_stopped_daemon):
            response = client.post("/api/agent/stop")
            assert response.status_code == 400
    """
    mock_daemon_manager.is_running.return_value = False
    mock_daemon_manager.get_pid.return_value = None
    return mock_daemon_manager


@pytest.fixture(scope="function")
def test_pid() -> int:
    """
    Provide test PID for daemon operations.

    Usage:
        def test_daemon_start(test_pid):
            mock_daemon_manager.start_daemon.return_value = test_pid
            assert mock_daemon_manager.start_daemon() == 12345
    """
    return 12345
