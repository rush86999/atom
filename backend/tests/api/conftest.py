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


@pytest.fixture(scope="function")
def mock_daemon_class():
    """
    Mock DaemonManager class with static method patching for agent control routes.

    This fixture patches the DaemonManager class in agent_control_routes module,
    allowing tests to control daemon behavior.

    Usage:
        def test_agent_start(mock_daemon_class):
            mock_daemon_class.is_running.return_value = False
            mock_daemon_class.start_daemon.return_value = 12345
            response = client.post("/api/agent/start")
            assert response.status_code == 200
    """
    from unittest.mock import patch

    with patch('api.agent_control_routes.DaemonManager') as mock_class:
        # Configure static methods
        mock_class.is_running.return_value = False
        mock_class.get_pid.return_value = 12345
        mock_class.start_daemon.return_value = 12345
        mock_class.stop_daemon.return_value = None
        mock_class.get_status.return_value = {
            "running": True,
            "pid": 12345,
            "uptime_seconds": 3600,
            "memory_mb": 256.5,
            "cpu_percent": 5.2,
            "status": "running"
        }
        yield mock_class


# ============================================================================
# Auth-Specific Fixtures (Phase 176-01)
# ============================================================================

@pytest.fixture(scope="function")
def mock_mobile_device() -> MagicMock:
    """
    Mock MobileDevice for authentication testing.

    Usage:
        def test_mobile_login(mock_mobile_device):
            mock_mobile_device.device_token = "test_token_123"
            # Call login endpoint
    """
    from unittest.mock import Mock
    from datetime import datetime

    mock = Mock()
    mock.id = "device-test-123"
    mock.device_token = "test_device_token_123"
    mock.platform = "ios"
    mock.user_id = "user-test-123"
    mock.status = "active"
    mock.notification_enabled = True
    mock.device_info = {"model": "iPhone 14", "os_version": "16.0"}
    mock.last_active = datetime.utcnow()
    mock.created_at = datetime.utcnow()

    return mock


@pytest.fixture(scope="function")
def test_user_with_device(db_session: Session) -> tuple:
    """
    Create test User with associated MobileDevice.

    Returns:
        tuple: (User, MobileDevice) for testing

    Usage:
        def test_mobile_auth(test_user_with_device):
            user, device = test_user_with_device
            assert user.email == "test-mobile@example.com"
    """
    import uuid
    from core.models import User, MobileDevice

    user_id = str(uuid.uuid4())
    device_id = str(uuid.uuid4())

    user = User(
        id=user_id,
        email=f"test-mobile-{user_id}@example.com",
        password_hash="hashed_password",
        first_name="Test",
        last_name="Mobile",
        role="member",
        status="active"
    )

    device = MobileDevice(
        id=device_id,
        user_id=user_id,
        device_token=f"device_token_{device_id}",
        platform="ios",
        status="active",
        notification_enabled=True,
        last_active=datetime.utcnow(),
        created_at=datetime.utcnow(),
        device_info={"model": "iPhone 14", "os_version": "16.0"}
    )

    db_session.add(user)
    db_session.add(device)
    db_session.commit()
    db_session.refresh(user)
    db_session.refresh(device)

    return (user, device)


@pytest.fixture(scope="function")
def mock_auth_service() -> MagicMock:
    """
    Mock authentication service functions for auth routes testing.

    Usage:
        def test_login_with_mock(mock_auth_service):
            mock_auth_service['authenticate_mobile_user'].return_value = {
                "user": {"id": "123"},
                "access_token": "token"
            }
            # Call login endpoint
    """
    from unittest.mock import MagicMock

    mock = MagicMock()

    # Mock authenticate_mobile_user
    mock_auth_result = {
        "access_token": "test_access_token",
        "refresh_token": "test_refresh_token",
        "expires_at": "2026-03-12T17:00:00Z",
        "token_type": "bearer",
        "user": {
            "id": "user-test-123",
            "email": "test@example.com"
        }
    }
    mock.authenticate_mobile_user = MagicMock(return_value=mock_auth_result)

    # Mock create_mobile_token
    mock.create_mobile_token = MagicMock(return_value=mock_auth_result)

    # Mock verify_biometric_signature
    mock.verify_biometric_signature = MagicMock(return_value=True)

    # Mock get_mobile_device
    mock.get_mobile_device = MagicMock(return_value=mock_mobile_device())

    return mock


@pytest.fixture(scope="function")
def biometric_test_data() -> dict:
    """
    Provide biometric authentication test data.

    Returns dict with fake keys for testing (no real crypto).

    Usage:
        def test_biometric_auth(biometric_test_data):
            data = biometric_test_data
            response = client.post("/api/auth/mobile/biometric/authenticate", json=data)
    """
    return {
        "public_key": "MIIBIjANBgkqhkiG9w0BAQEFAAOCAQ8AMIIBCgKCAQEA" + "A" * 100,
        "device_token": "biometric_device_token_123",
        "signature": "mock_signature_" + "B" * 200,
        "challenge": "test_challenge_" + "C" * 50
    }


# ============================================================================
# Permission Check Fixtures (Phase 176-04)
# ============================================================================

@pytest.fixture(scope="function")
def test_users_with_roles() -> dict:
    """
    Create mock User objects for all UserRole enum values.

    Returns dict mapping UserRole to User mock objects.
    Useful for parametrized permission tests across all roles.

    Usage:
        def test_permission_matrix(test_users_with_roles):
            guest_user = test_users_with_roles[UserRole.GUEST]
            admin_user = test_users_with_roles[UserRole.SUPER_ADMIN]
            # Test permissions for each role
    """
    from unittest.mock import Mock
    from core.models import UserRole

    users = {}

    for role in UserRole:
        user = Mock()
        user.id = f"user-{role.value}"
        user.email = f"{role.value}@example.com"
        user.role = role.value  # String value for DB compatibility
        user.status = "active"
        users[role] = user

    return users


@pytest.fixture(scope="function")
def mock_rbac_check() -> MagicMock:
    """
    Mock RBACService.check_permission for permission verification tests.

    Tracks permission checks and returns configurable True/False.

    Usage:
        def test_permission_enforcement(mock_rbac_check):
            mock_rbac_check.return_value = True
            # Test endpoint that checks permission
            mock_rbac_check.assert_called_once_with(user, Permission.AGENT_RUN)
    """
    from core.rbac_service import RBACService

    mock = MagicMock()
    mock.check_permission = MagicMock(return_value=True)
    mock.get_user_permissions = MagicMock(return_value=set())

    return mock


@pytest.fixture(scope="function")
def all_permissions() -> list:
    """
    Return list of all Permission enum values.

    Useful for parametrized tests across all permissions.

    Usage:
        @pytest.mark.parametrize("permission", all_permissions())
        def test_all_permissions(permission):
            # Test each permission
    """
    from core.rbac_service import Permission

    return list(Permission)


@pytest.fixture(scope="function")
def role_permission_mapping() -> dict:
    """
    Return ROLE_PERMISSIONS mapping from RBACService.

    Maps UserRole to Set[Permission] for verifying permission inheritance.

    Usage:
        def test_permission_inheritance(role_permission_mapping):
            guest_perms = role_permission_mapping[UserRole.GUEST]
            assert Permission.AGENT_VIEW in guest_perms
            assert Permission.AGENT_RUN not in guest_perms
    """
    from core.rbac_service import ROLE_PERMISSIONS

    return ROLE_PERMISSIONS


# ============================================================================
# Analytics Engine Fixtures (Phase 177-02)
# ============================================================================

@pytest.fixture(scope="function")
def mock_message_analytics() -> AsyncMock:
    """
    Mock MessageAnalyticsEngine for analytics routes testing.

    Returns deterministic analytics data with configurable filters.

    Usage:
        def test_analytics_summary(mock_message_analytics):
            mock_message_analytics.get_summary.return_value = {
                "message_stats": {"total_messages": 100},
                "sentiment_distribution": {"positive": 40, "negative": 20, "neutral": 40}
            }
            response = client.get("/api/analytics/summary")
    """
    from unittest.mock import AsyncMock

    mock = AsyncMock()

    # Mock get_summary method
    mock.get_summary = AsyncMock(return_value={
        "message_stats": {
            "total_messages": 100,
            "total_words": 5000,
            "with_attachments": 25,
            "with_mentions": 40,
            "with_urls": 30
        },
        "sentiment_distribution": {
            "positive": 40,
            "negative": 20,
            "neutral": 40
        },
        "response_times": {
            "avg_response_seconds": 3600,
            "median_response_seconds": 2400,
            "p95_response_seconds": 7200
        },
        "activity_peaks": {
            "peak_days": ["Monday", "Tuesday", "Wednesday"],
            "messages_per_day": {"2026-03-12": 50, "2026-03-11": 45}
        },
        "cross_platform": {
            "platforms": {"slack": 60, "teams": 30, "gmail": 10},
            "most_active_platform": "slack",
            "total_messages": 100
        }
    })

    # Mock get_sentiment_analysis method
    mock.get_sentiment_analysis = AsyncMock(return_value={
        "sentiment_distribution": {"positive": 40, "negative": 20, "neutral": 40},
        "sentiment_trend": [{"timestamp": "2026-03-12T00:00:00Z", "positive": 0.4}],
        "most_positive_topics": ["product launch", "feature request"],
        "most_negative_topics": ["bug report", "performance issue"]
    })

    # Mock get_response_time_metrics method
    mock.get_response_time_metrics = AsyncMock(return_value={
        "avg_response_seconds": 3600,
        "median_response_seconds": 2400,
        "p95_response_seconds": 7200,
        "p99_response_seconds": 10800,
        "response_time_distribution": [
            {"range": "0-1h", "count": 20},
            {"range": "1-4h", "count": 30},
            {"range": "4-24h", "count": 40}
        ],
        "slowest_threads": [
            {"thread_id": "thread1", "response_seconds": 10800, "participants": ["user1", "user2"]},
            {"thread_id": "thread2", "response_seconds": 9600, "participants": ["user3"]}
        ],
        "fastest_threads": [
            {"thread_id": "thread3", "response_seconds": 60, "participants": ["user4", "user5"]}
        ]
    })

    # Mock get_activity_metrics method
    mock.get_activity_metrics = AsyncMock(return_value={
        "messages_per_hour": {"9": 10, "10": 15, "11": 12},
        "messages_per_day": {"2026-03-12": 50, "2026-03-11": 45},
        "messages_per_channel": {"#general": 30, "#random": 20},
        "peak_hours": [10, 11, 14],
        "peak_days": ["Monday", "Tuesday", "Wednesday"],
        "activity_heatmap": [
            {"hour": 9, "day": "Monday", "count": 10},
            {"hour": 10, "day": "Monday", "count": 15}
        ]
    })

    # Mock get_cross_platform_analytics method
    mock.get_cross_platform_analytics = AsyncMock(return_value={
        "platforms": {
            "slack": {"message_count": 60, "sentiment": {"positive": 25, "negative": 10, "neutral": 25}, "avg_response_time": 3000},
            "teams": {"message_count": 30, "sentiment": {"positive": 12, "negative": 7, "neutral": 11}, "avg_response_time": 3600},
            "gmail": {"message_count": 10, "sentiment": {"positive": 3, "negative": 3, "neutral": 4}, "avg_response_time": 7200}
        },
        "most_active_platform": "slack",
        "platform_comparison": [
            {"platform": "slack", "message_count": 60, "percentage": 60},
            {"platform": "teams", "message_count": 30, "percentage": 30},
            {"platform": "gmail", "message_count": 10, "percentage": 10}
        ]
    })

    return mock


@pytest.fixture(scope="function")
def mock_correlation_engine() -> AsyncMock:
    """
    Mock CrossPlatformCorrelationEngine for correlation testing.

    Returns deterministic correlation data with linked conversations.

    Usage:
        def test_correlations(mock_correlation_engine):
            mock_correlation_engine.correlate_conversations.return_value = [
                MockLinkedConversation(conversation_id="conv1", platforms={"slack", "teams"})
            ]
            response = client.post("/api/analytics/correlations", json=messages)
    """
    from unittest.mock import AsyncMock, Mock
    from core.cross_platform_correlation import LinkedConversation, CorrelationStrength

    # Create mock linked conversation
    mock_linked_conv = Mock(spec=LinkedConversation)
    mock_linked_conv.conversation_id = "linked-conv-123"
    mock_linked_conv.platforms = {"slack", "teams"}
    mock_linked_conv.participants = {"user1@example.com", "user2@example.com"}
    mock_linked_conv.message_count = 15
    mock_linked_conv.correlation_strength = CorrelationStrength.STRONG
    mock_linked_conv.unified_messages = [
        {"id": "msg1", "platform": "slack", "content": "Test message", "sender": "user1", "timestamp": "2026-03-12T10:00:00Z", "_correlation_source": "slack"},
        {"id": "msg2", "platform": "teams", "content": "Related message", "sender": "user2", "timestamp": "2026-03-12T10:05:00Z", "_correlation_source": "teams"}
    ]

    mock = AsyncMock()

    # Mock correlate_conversations method
    mock.correlate_conversations = Mock(return_value=[mock_linked_conv])

    # Mock get_unified_timeline method (returns None for non-existent conversation)
    mock.get_unified_timeline = Mock(return_value=[
        {"id": "msg1", "platform": "slack", "content": "Test message", "sender": "user1", "timestamp": "2026-03-12T10:00:00Z", "_correlation_source": "slack"},
        {"id": "msg2", "platform": "teams", "content": "Related message", "sender": "user2", "timestamp": "2026-03-12T10:05:00Z", "_correlation_source": "teams"}
    ])

    # Mock cross_platform_links attribute
    mock.cross_platform_links = [
        {"source_conv": "slack-conv-1", "target_conv": "teams-conv-2", "strength": 0.85}
    ]

    # Mock linked_conversations attribute
    mock.linked_conversations = [mock_linked_conv]

    return mock


@pytest.fixture(scope="function")
def mock_insights_engine() -> AsyncMock:
    """
    Mock PredictiveInsightsEngine for predictive insights testing.

    Returns deterministic predictions with confidence levels.

    Usage:
        def test_predict_response_time(mock_insights_engine):
            mock_prediction = Mock()
            mock_prediction.predicted_seconds = 3600
            mock_prediction.confidence.value = "high"
            mock_insights_engine.predict_response_time.return_value = mock_prediction
            response = client.get("/api/analytics/predictions/response-time")
    """
    from unittest.mock import AsyncMock, Mock
    from core.predictive_insights import ResponseTimePrediction, ChannelRecommendation, BottleneckAlert, CommunicationPattern, RecommendationConfidence, UrgencyLevel

    # Create mock prediction
    mock_prediction = Mock(spec=ResponseTimePrediction)
    mock_prediction.user_id = "user123"
    mock_prediction.predicted_seconds = 3600
    mock_prediction.confidence = RecommendationConfidence.HIGH
    mock_prediction.factors = ["Time of day", "Historical patterns", "Platform activity"]

    # Create mock channel recommendation
    mock_recommendation = Mock(spec=ChannelRecommendation)
    mock_recommendation.user_id = "user123"
    mock_recommendation.recommended_platform = "slack"
    mock_recommendation.reason = "User is most active on Slack during this time"
    mock_recommendation.confidence = RecommendationConfidence.HIGH
    mock_recommendation.expected_response_time = 1800  # 30 minutes
    mock_recommendation.alternatives = ["teams", "gmail"]

    # Create mock bottleneck alert
    mock_bottleneck = Mock(spec=BottleneckAlert)
    mock_bottleneck.severity = UrgencyLevel.MEDIUM
    mock_bottleneck.thread_id = "thread-123"
    mock_bottleneck.platform = "slack"
    mock_bottleneck.description = "No response for 24 hours"
    mock_bottleneck.affected_users = ["user1@example.com", "user2@example.com"]
    mock_bottleneck.wait_time_seconds = 86400  # 24 hours
    mock_bottleneck.suggested_action = "Send follow-up message or escalate"

    # Create mock user pattern
    mock_pattern = Mock(spec=CommunicationPattern)
    mock_pattern.user_id = "user123"
    mock_pattern.most_active_platform = "slack"
    mock_pattern.most_active_hours = [9, 10, 11, 14, 15]
    mock_pattern.avg_response_time = 3600
    mock_pattern.response_probability_by_hour = {
        9: 0.8, 10: 0.9, 11: 0.7, 14: 0.85, 15: 0.75
    }
    mock_pattern.preferred_message_types = ["general", "question", "update"]

    mock = AsyncMock()

    # Mock predict_response_time method
    mock.predict_response_time = Mock(return_value=mock_prediction)

    # Mock recommend_channel method
    mock.recommend_channel = Mock(return_value=mock_recommendation)

    # Mock detect_bottlenecks method
    mock.detect_bottlenecks = Mock(return_value=[mock_bottleneck])

    # Mock get_user_pattern method (returns None for non-existent user)
    mock.get_user_pattern = Mock(return_value=mock_pattern)

    # Mock get_insights_summary method
    mock.get_insights_summary = Mock(return_value={
        "users_analyzed": 50,
        "bottlenecks_detected": 5,
        "avg_response_time_all_users": 3600,
        "most_active_platform": "slack",
        "peak_hours": [10, 11, 14]
    })

    return mock


@pytest.fixture(scope="function")
def analytics_routes_client(mock_message_analytics, mock_correlation_engine, mock_insights_engine) -> TestClient:
    """
    Create TestClient with analytics routes router.

    Uses per-file FastAPI app pattern to avoid SQLAlchemy metadata conflicts.
    All analytics engines are mocked for deterministic testing.

    Usage:
        def test_analytics_summary(analytics_routes_client):
            response = analytics_routes_client.get("/api/analytics/summary")
            assert response.status_code == 200
    """
    from fastapi import FastAPI
    from api.analytics_dashboard_routes import router
    from unittest.mock import patch

    app = FastAPI()
    app.include_router(router)

    # Patch engine getters to return mocks
    with patch('api.analytics_dashboard_routes.get_message_analytics_engine', return_value=mock_message_analytics), \
         patch('api.analytics_dashboard_routes.get_cross_platform_correlation_engine', return_value=mock_correlation_engine), \
         patch('api.analytics_dashboard_routes.get_predictive_insights_engine', return_value=mock_insights_engine):

        client = TestClient(app)
        yield client


# ============================================================================
# Feedback Analytics Fixtures (Phase 177-03)
# ============================================================================

@pytest.fixture(scope="function")
def mock_feedback_analytics() -> MagicMock:
    """
    Mock FeedbackAnalytics service for feedback analytics routes testing.

    Provides deterministic mock data for all analytics methods:
    - get_feedback_statistics() returns summary with counts, ratios, ratings
    - get_top_performing_agents() returns list of agent dicts
    - get_most_corrected_agents() returns list of agent dicts
    - get_feedback_breakdown_by_type() returns breakdown dict
    - get_feedback_trends() returns list of daily trends
    - get_agent_feedback_summary() returns agent-specific summary

    Usage:
        def test_feedback_dashboard(mock_feedback_analytics):
            mock_feedback_analytics.get_feedback_statistics.return_value = {
                "total_feedback": 100,
                "positive_count": 75,
                "negative_count": 25,
                "average_rating": 4.2
            }
            response = client.get("/api/feedback/analytics")
    """
    from unittest.mock import AsyncMock

    mock = MagicMock()

    # Mock get_feedback_statistics
    mock.get_feedback_statistics = MagicMock(return_value={
        "total_feedback": 100,
        "positive_count": 75,
        "negative_count": 25,
        "thumbs_up_count": 60,
        "thumbs_down_count": 15,
        "average_rating": 4.2,
        "rating_distribution": {1: 5, 2: 8, 3: 12, 4: 30, 5: 45}
    })

    # Mock get_top_performing_agents
    mock.get_top_performing_agents = MagicMock(return_value=[
        {
            "agent_id": "agent-sales-001",
            "agent_name": "Sales Assistant",
            "total_feedback": 50,
            "average_rating": 4.8,
            "positive_ratio": 0.92
        },
        {
            "agent_id": "agent-support-001",
            "agent_name": "Support Bot",
            "total_feedback": 35,
            "average_rating": 4.6,
            "positive_ratio": 0.88
        }
    ])

    # Mock get_most_corrected_agents
    mock.get_most_corrected_agents = MagicMock(return_value=[
        {
            "agent_id": "agent-data-001",
            "agent_name": "Data Analyst",
            "total_corrections": 15,
            "total_feedback": 40,
            "correction_rate": 0.375
        },
        {
            "agent_id": "agent-finance-001",
            "agent_name": "Finance Helper",
            "total_corrections": 12,
            "total_feedback": 30,
            "correction_rate": 0.40
        }
    ])

    # Mock get_feedback_breakdown_by_type
    mock.get_feedback_breakdown_by_type = MagicMock(return_value={
        "thumbs_up": 60,
        "thumbs_down": 15,
        "rating": 20,
        "correction": 5
    })

    # Mock get_feedback_trends
    mock.get_feedback_trends = MagicMock(return_value=[
        {
            "date": "2026-03-01",
            "total_feedback": 10,
            "positive_count": 8,
            "negative_count": 2,
            "average_rating": 4.3
        },
        {
            "date": "2026-03-02",
            "total_feedback": 12,
            "positive_count": 10,
            "negative_count": 2,
            "average_rating": 4.5
        }
    ])

    # Mock get_agent_feedback_summary
    mock.get_agent_feedback_summary = MagicMock(return_value={
        "agent_id": "agent-sales-001",
        "agent_name": "Sales Assistant",
        "total_feedback": 50,
        "positive_count": 46,
        "negative_count": 4,
        "thumbs_up_count": 38,
        "thumbs_down_count": 4,
        "average_rating": 4.8,
        "rating_distribution": {1: 0, 2: 1, 3: 3, 4: 8, 5: 38},
        "feedback_types": {"thumbs_up": 38, "thumbs_down": 4, "rating": 8}
    })

    return mock


@pytest.fixture(scope="function")
def mock_agent_learning() -> MagicMock:
    """
    Mock AgentLearningEnhanced service for learning signal testing.

    Provides deterministic mock data for learning signals:
    - get_learning_signals() returns learning signals dict with:
      - improvement_suggestions: list of strings
      - common_corrections: list of strings
      - performance_trends: dict

    Handles agent_id and days parameters.

    Usage:
        def test_agent_dashboard_learning(mock_agent_learning):
            mock_agent_learning.get_learning_signals.return_value = {
                "improvement_suggestions": ["Improve accuracy"],
                "common_corrections": ["Fix calculation"],
                "performance_trends": {"accuracy": 0.85}
            }
            response = client.get("/api/feedback/agent/agent-001/analytics")
    """
    from unittest.mock import AsyncMock

    mock = MagicMock()

    # Mock get_learning_signals
    mock.get_learning_signals = MagicMock(return_value={
        "improvement_suggestions": [
            "Improve response accuracy for technical queries",
            "Add more context to product recommendations",
            "Reduce response time for customer inquiries"
        ],
        "common_corrections": [
            "Pricing calculation errors",
            "Product availability mismatches",
            "Shipping estimate inaccuracies"
        ],
        "performance_trends": {
            "accuracy": 0.85,
            "response_time_ms": 450,
            "satisfaction_score": 4.2,
            "trend": "improving"
        }
    })

    return mock


@pytest.fixture(scope="function")
def feedback_analytics_client(mock_feedback_analytics: AsyncMock, mock_agent_learning: AsyncMock) -> TestClient:
    """
    Create TestClient with feedback analytics router.

    Uses per-file FastAPI app pattern to avoid SQLAlchemy conflicts.
    Includes feedback_analytics.py router with mocked services.

    Usage:
        def test_feedback_dashboard(feedback_analytics_client):
            response = feedback_analytics_client.get("/api/feedback/analytics")
            assert response.status_code == 200
    """
    from fastapi import FastAPI
    from unittest.mock import patch

    app = FastAPI()

    # Mock the database dependency
    async def mock_get_db():
        from unittest.mock import MagicMock
        mock_db = MagicMock()
        return mock_db

    # Patch FeedbackAnalytics and AgentLearningEnhanced
    # Note: AgentLearningEnhanced is imported inside the function, so patch at core module level
    with patch('api.feedback_analytics.FeedbackAnalytics', return_value=mock_feedback_analytics):
        with patch('core.agent_learning_enhanced.AgentLearningEnhanced', return_value=mock_agent_learning):
            from api.feedback_analytics import router
            app.include_router(router, prefix="/api/feedback/analytics")

            # Override get_db dependency
            app.dependency_overrides[lambda: None] = mock_get_db

            client = TestClient(app)
            yield client

            # Clean up dependency override
            app.dependency_overrides.clear()


@pytest.fixture(scope="function")
def mock_db_session_feedback() -> MagicMock:
    """
    Mock Session for database dependency injection in feedback analytics.

    Used for get_db dependency in feedback analytics routes.
    Returns mock database session for testing.

    Usage:
        def test_with_mock_db(mock_db_session_feedback):
            mock_db_session_feedback.query.return_value.first.return_value = mock_agent
            # Test endpoint that uses get_db dependency
    """
    from unittest.mock import MagicMock
    from sqlalchemy.orm import Session

    mock = MagicMock(spec=Session)

    # Mock query chain
    mock_query = MagicMock()
    mock.query = MagicMock(return_value=mock_query)
    mock_query.filter = MagicMock(return_value=mock_query)
    mock_query.all = MagicMock(return_value=[])
    mock_query.first = MagicMock(return_value=None)

    return mock


# ============================================================================
# A/B Testing Fixtures (Phase 177-04)
# ============================================================================

@pytest.fixture(scope="function")
def mock_ab_testing_service() -> AsyncMock:
    """
    Mock ABTestingService for A/B testing routes testing.

    Provides deterministic test data for all service methods.
    Simulates success and error paths for comprehensive testing.

    Usage:
        def test_create_ab_test(mock_ab_testing_service):
            mock_ab_testing_service.create_test.return_value = {
                "test_id": "test-123",
                "status": "draft"
            }
            response = client.post("/api/ab-tests/create", json={})
    """
    from unittest.mock import AsyncMock
    from datetime import datetime

    mock = AsyncMock()

    # create_test() - Success case
    def create_test_success(**kwargs):
        return {
            "test_id": "test-123",
            "name": kwargs.get("name", "Test A"),
            "status": "draft",
            "test_type": kwargs.get("test_type", "prompt"),
            "agent_id": kwargs.get("agent_id", "test-agent"),
            "variant_a": {
                "name": kwargs.get("variant_a_name", "Control"),
                "config": kwargs.get("variant_a_config", {"temperature": 0.7})
            },
            "variant_b": {
                "name": kwargs.get("variant_b_name", "Treatment"),
                "config": kwargs.get("variant_b_config", {"temperature": 0.9})
            },
            "primary_metric": kwargs.get("primary_metric", "satisfaction_rate"),
            "min_sample_size": kwargs.get("min_sample_size", 100),
            "traffic_percentage": kwargs.get("traffic_percentage", 0.5)
        }

    mock.create_test = MagicMock(side_effect=create_test_success)

    # start_test() - Success case
    def start_test_success(test_id: str):
        return {
            "test_id": test_id,
            "name": "Test A",
            "status": "running",
            "started_at": datetime.utcnow().isoformat()
        }

    mock.start_test = MagicMock(side_effect=start_test_success)

    # complete_test() - Success case
    def complete_test_success(test_id: str):
        return {
            "test_id": test_id,
            "name": "Test A",
            "status": "completed",
            "completed_at": datetime.utcnow().isoformat(),
            "variant_a_metrics": {
                "count": 150,
                "success_count": 120,
                "success_rate": 0.80,
                "average_metric_value": 4.2
            },
            "variant_b_metrics": {
                "count": 150,
                "success_count": 135,
                "success_rate": 0.90,
                "average_metric_value": 4.7
            },
            "p_value": 0.02,
            "winner": "B",
            "min_sample_size_reached": True
        }

    mock.complete_test = MagicMock(side_effect=complete_test_success)

    # assign_variant() - Success case
    def assign_variant_success(test_id: str, user_id: str, session_id: str = None):
        # Deterministic assignment based on user_id hash
        import hashlib
        hash_value = int(hashlib.sha256(f"{test_id}:{user_id}".encode()).hexdigest(), 16)
        hash_fraction = (hash_value % 10000) / 10000.0
        variant = "B" if hash_fraction < 0.5 else "A"

        return {
            "test_id": test_id,
            "user_id": user_id,
            "variant": variant,
            "variant_name": "Control" if variant == "A" else "Treatment",
            "config": {"temperature": 0.7} if variant == "A" else {"temperature": 0.9},
            "existing_assignment": False
        }

    mock.assign_variant = MagicMock(side_effect=assign_variant_success)

    # record_metric() - Success case
    def record_metric_success(test_id: str, user_id: str, **kwargs):
        return {
            "test_id": test_id,
            "user_id": user_id,
            "variant": "A",
            "success": kwargs.get("success"),
            "metric_value": kwargs.get("metric_value"),
            "recorded_at": datetime.utcnow().isoformat()
        }

    mock.record_metric = MagicMock(side_effect=record_metric_success)

    # get_test_results() - Success case
    def get_test_results_success(test_id: str):
        return {
            "test_id": test_id,
            "name": "Test A",
            "status": "completed",
            "test_type": "prompt",
            "primary_metric": "satisfaction_rate",
            "variant_a": {
                "name": "Control",
                "participant_count": 150,
                "metrics": {
                    "count": 150,
                    "success_count": 120,
                    "success_rate": 0.80,
                    "average_metric_value": 4.2
                }
            },
            "variant_b": {
                "name": "Treatment",
                "participant_count": 150,
                "metrics": {
                    "count": 150,
                    "success_count": 135,
                    "success_rate": 0.90,
                    "average_metric_value": 4.7
                }
            },
            "winner": "B",
            "statistical_significance": 0.02,
            "started_at": datetime.utcnow().isoformat(),
            "completed_at": datetime.utcnow().isoformat()
        }

    mock.get_test_results = MagicMock(side_effect=get_test_results_success)

    # list_tests() - Success case
    def list_tests_success(agent_id: str = None, status: str = None, limit: int = 50):
        tests = [
            {
                "test_id": "test-123",
                "name": "Test A",
                "status": "running",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "primary_metric": "satisfaction_rate",
                "winner": None,
                "created_at": datetime.utcnow().isoformat()
            },
            {
                "test_id": "test-456",
                "name": "Test B",
                "status": "completed",
                "test_type": "agent_config",
                "agent_id": "agent-2",
                "primary_metric": "success_rate",
                "winner": "B",
                "created_at": datetime.utcnow().isoformat()
            }
        ]

        # Filter by agent_id if provided
        if agent_id:
            tests = [t for t in tests if t["agent_id"] == agent_id]

        # Filter by status if provided
        if status:
            tests = [t for t in tests if t["status"] == status]

        # Apply limit
        tests = tests[:limit]

        return {
            "total": len(tests),
            "tests": tests
        }

    mock.list_tests = MagicMock(side_effect=list_tests_success)

    return mock


@pytest.fixture(scope="function")
def sample_test_request() -> dict:
    """
    Factory for CreateTestRequest with valid default values.

    Provides valid test configuration data for creating A/B tests.
    All fields have sensible defaults that can be overridden.

    Usage:
        def test_create_test(sample_test_request):
            data = sample_test_request.copy()
            data["name"] = "Custom Test"
            response = client.post("/api/ab-tests/create", json=data)
    """
    return {
        "name": "Test A",
        "test_type": "prompt",
        "agent_id": "test-agent",
        "variant_a_config": {"temperature": 0.7},
        "variant_b_config": {"temperature": 0.9},
        "primary_metric": "satisfaction_rate",
        "traffic_percentage": 0.5,
        "min_sample_size": 100,
        "confidence_level": 0.95
    }


@pytest.fixture(scope="function")
def ab_testing_client() -> TestClient:
    """
    TestClient with A/B testing router.

    Creates per-file FastAPI app with ab_testing router.
    Avoids SQLAlchemy metadata conflicts by not importing main app.

    Usage:
        def test_ab_endpoint(ab_testing_client):
            response = ab_testing_client.get("/api/ab-tests")
            assert response.status_code == 200
    """
    from fastapi import FastAPI
    from api.ab_testing import router

    app = FastAPI()
    app.include_router(router, prefix="/api/ab-tests")

    return TestClient(app)


@pytest.fixture(scope="function")
def mock_db_session() -> Session:
    """
    Mock Session for database dependency injection.

    Used to override get_db dependency in API routes.
    Provides deterministic mock database for testing.

    Usage:
        def test_with_mock_db(mock_db_session, ab_testing_client):
            # Override get_db dependency
            def override_get_db():
                yield mock_db_session

            app.dependency_overrides[get_db] = override_get_db
            # Make requests...
    """
    from unittest.mock import MagicMock
    from sqlalchemy.orm import Session

    mock = MagicMock(spec=Session)

    # Mock common session methods
    mock.add = MagicMock()
    mock.commit = MagicMock()
    mock.rollback = MagicMock()
    mock.refresh = MagicMock()
    mock.query = MagicMock()
    mock.flush = MagicMock()
    mock.close = MagicMock()

    return mock


# ============================================================================
# Workflow Analytics Dashboard Fixtures (Phase 177-01)
# ============================================================================

@pytest.fixture(scope="function")
def mock_workflow_analytics() -> MagicMock:
    """
    AsyncMock for WorkflowAnalyticsEngine with deterministic return values.

    Provides complete mock for all workflow analytics operations including:
    - Performance metrics (executions, success rate, duration)
    - Workflow metadata (names, IDs, execution times)
    - Execution timeline data
    - Error breakdown
    - Alerts management
    - Real-time events

    Usage:
        def test_get_dashboard_kpis(mock_workflow_analytics):
            mock_workflow_analytics.get_performance_metrics.return_value = test_metrics
            response = client.get("/api/analytics/dashboard/kpis")
            assert response.status_code == 200
    """
    from datetime import datetime, timedelta
    from unittest.mock import AsyncMock

    mock = MagicMock()

    # Mock get_performance_metrics
    from collections import namedtuple
    PerformanceMetrics = namedtuple('PerformanceMetrics', [
        'total_executions', 'successful_executions', 'failed_executions',
        'success_rate', 'average_duration_ms', 'median_duration_ms',
        'p95_duration_ms', 'p99_duration_ms', 'error_rate', 'unique_users',
        'executions_by_user', 'most_common_errors', 'average_step_duration'
    ])

    mock_metrics = PerformanceMetrics(
        total_executions=100,
        successful_executions=95,
        failed_executions=5,
        success_rate=95.0,
        average_duration_ms=1500.0,
        median_duration_ms=1200.0,
        p95_duration_ms=3000.0,
        p99_duration_ms=5000.0,
        error_rate=5.0,
        unique_users=10,
        executions_by_user={},
        most_common_errors=[],
        average_step_duration={}
    )
    mock.get_performance_metrics.return_value = mock_metrics

    # Mock get_all_workflow_ids
    mock.get_all_workflow_ids.return_value = [
        "workflow-001",
        "workflow-002",
        "workflow-003"
    ]

    # Mock get_workflow_name
    def get_workflow_name(workflow_id: str) -> str:
        names = {
            "workflow-001": "Data Import Pipeline",
            "workflow-002": "Email Campaign",
            "workflow-003": "Report Generation"
        }
        return names.get(workflow_id, workflow_id)

    mock.get_workflow_name.side_effect = get_workflow_name

    # Mock get_last_execution_time
    mock.get_last_execution_time.return_value = datetime.now()

    # Mock get_execution_timeline
    from collections import namedtuple
    ExecutionTimelineData = namedtuple('ExecutionTimelineData', [
        'timestamp', 'count', 'success_count', 'failure_count', 'average_duration_ms'
    ])

    mock_timeline_data = [
        ExecutionTimelineData(
            timestamp=datetime.now() - timedelta(hours=1),
            count=10,
            success_count=9,
            failure_count=1,
            average_duration_ms=1500.0
        )
    ]
    mock.get_execution_timeline.return_value = mock_timeline_data

    # Mock get_error_breakdown
    mock.get_error_breakdown.return_value = {
        "ValidationError": 15,
        "TimeoutError": 8,
        "ConnectionError": 5
    }

    # Mock get_all_alerts
    from core.workflow_analytics_engine import AlertSeverity
    # Mock severity enum
    MockSeverity = namedtuple('MockSeverity', ['value'])(['high'])

    from collections import namedtuple
    Alert = namedtuple(('Alert', [
        'alert_id', 'name', 'description', 'severity', 'metric_name',
        'condition', 'threshold_value', 'workflow_id', 'enabled',
        'created_at', 'notification_channels'
    ])

    mock_alerts = [
        Alert(
            alert_id="alert-001",
            name="High Error Rate",
            description="Error rate exceeds 5%",
            severity=MockSeverity('high'),
            metric_name="error_rate",
            condition="error_rate > 5",
            threshold_value=5.0,
            workflow_id="workflow-001",
            enabled=True,
            created_at=datetime.now(),
            notification_channels=[]
        )
    ]
    mock.get_all_alerts.return_value = mock_alerts

    # Mock get_recent_events
    from collections import namedtuple
    RealtimeExecutionEvent = namedtuple('RealtimeExecutionEvent', [
        'event_id', 'workflow_id', 'workflow_name', 'execution_id',
        'event_type', 'timestamp', 'status', 'duration_ms', 'user_id'
    ])

    mock_events = [
        RealtimeExecutionEvent(
            event_id="event-001",
            workflow_id="workflow-001",
            workflow_name="Data Import Pipeline",
            execution_id="exec-001",
            event_type="workflow.completed",
            timestamp=datetime.now(),
            status="completed",
            duration_ms=1500,
            user_id="user-001"
        )
    ]
    mock.get_recent_events.return_value = mock_events

    # Mock create_alert
    mock.create_alert.return_value = "alert-002"

    # Mock update_alert
    mock.update_alert.return_value = True

    # Mock delete_alert
    mock.delete_alert.return_value = True

    # Mock get_unique_workflow_count
    mock.get_unique_workflow_count.return_value = 3

    return mock


@pytest.fixture(scope="function")
def analytics_dashboard_test_client() -> TestClient:
    """
    TestClient with analytics dashboard router included.

    Uses per-file FastAPI app pattern to avoid SQLAlchemy metadata conflicts.
    Includes both analytics_dashboard_routes.py and analytics_dashboard_endpoints.py.

    Usage:
        def test_analytics_endpoint(analytics_dashboard_test_client):
            response = analytics_dashboard_test_client.get("/api/analytics/dashboard/kpis")
            assert response.status_code == 200
    """
    from fastapi import FastAPI
    from api.analytics_dashboard_routes import router as message_analytics_router
    from api.analytics_dashboard_endpoints import router as dashboard_router

    app = FastAPI()
    app.include_router(message_analytics_router)
    app.include_router(dashboard_router)

    return TestClient(app)
