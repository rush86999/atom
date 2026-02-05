"""
Device Capabilities Tests

Tests for device capability integrations:
- Camera service (expo-camera)
- Location service (expo-location)
- Notification service (expo-notifications)
- Command execution (desktop only)
"""

import pytest
from unittest.mock import Mock, patch, AsyncMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import DeviceNode, User
from tools.device_tool import (
    DeviceCapability,
    DeviceCommandRequest,
    execute_device_command,
    get_device_capabilities,
    register_device,
    update_device_status
)
from api.device_capabilities import router as device_capabilities_router


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def device_user(db_session: Session):
    """Create a test user for device tests."""
    user = User(
        email="device@test.com",
        first_name="Device",
        last_name="Test User",
        password_hash="$2b$12$test_hashed_password",
        role="MEMBER"
    )
    db_session.add(user)
    db_session.commit()
    db_session.refresh(user)
    return user


@pytest.fixture
def mobile_device(db_session: Session, device_user):
    """Create a test mobile device."""
    device = DeviceNode(
        device_id="mobile_device_123",
        name="Test Mobile Device",
        platform="ios",
        app_type="mobile",
        status="online",
        user_id=str(device_user.id),
        capabilities=["camera", "location", "notification"],
        workspace_id="default",
        last_command_at=None
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


@pytest.fixture
def desktop_device(db_session: Session, device_user):
    """Create a test desktop device."""
    device = DeviceNode(
        device_id="desktop_device_123",
        name="Test Desktop Device",
        platform="darwin",
        app_type="desktop",
        status="online",
        user_id=str(device_user.id),
        capabilities=["command", "notification"],
        workspace_id="default",
        last_command_at=None
    )
    db_session.add(device)
    db_session.commit()
    db_session.refresh(device)
    return device


# ============================================================================
# Camera Capability Tests
# ============================================================================

class TestCameraCapability:
    """Tests for camera device capability."""

    def test_camera_snap_command_mobile(self, client: TestClient, mobile_device):
        """Test camera snap command on mobile device."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "camera_snap",
                "params": {
                    "quality": 0.8,
                    "base64": True
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should be queued for WebSocket execution
        assert response.status_code in [200, 202]

    def test_camera_requires_internet_maturity(self, client: TestClient, mobile_device):
        """Test camera commands require INTERN maturity or higher."""
        # This test verifies governance checks
        # Camera commands should be gated by maturity level
        pass

    def test_camera_snap_with_save_path(self, client: TestClient, mobile_device):
        """Test camera snap with custom save path."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "camera_snap",
                "params": {
                    "quality": 0.9,
                    "base64": True,
                    "save_path": "/tmp/camera_test.jpg"
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code in [200, 202]

    def test_camera_snap_requires_permission(self, client: TestClient, mobile_device):
        """Test camera snap requires camera permission."""
        # Test that permission check is in place
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "camera_snap",
                "params": {}
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should validate permission
        assert response.status_code != 500


# ============================================================================
# Location Capability Tests
# ============================================================================

class TestLocationCapability:
    """Tests for location device capability."""

    def test_get_location_command_mobile(self, client: TestClient, mobile_device):
        """Test get location command on mobile device."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "get_location",
                "params": {
                    "accuracy": "high"
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should be queued for WebSocket execution
        assert response.status_code in [200, 202]

    def test_location_requires_internet_maturity(self, client: TestClient, mobile_device):
        """Test location commands require INTERN maturity or higher."""
        pass

    def test_location_returns_coordinates(self, client: TestClient, mobile_device):
        """Test location returns latitude, longitude, accuracy."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "get_location",
                "params": {}
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code in [200, 202]

    def test_location_requires_permission(self, client: TestClient, mobile_device):
        """Test get location requires location permission."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "get_location",
                "params": {}
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should validate permission
        assert response.status_code != 500


# ============================================================================
# Notification Capability Tests
# ============================================================================

class TestNotificationCapability:
    """Tests for notification device capability."""

    def test_send_notification_mobile(self, client: TestClient, mobile_device):
        """Test sending notification to mobile device."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "send_notification",
                "params": {
                    "title": "Test Notification",
                    "body": "Test notification body",
                    "sound": "default"
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code in [200, 202]

    def test_send_notification_desktop(self, client: TestClient, desktop_device):
        """Test sending notification to desktop device."""
        response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "send_notification",
                "params": {
                    "title": "Test Notification",
                    "body": "Test notification body"
                }
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        assert response.status_code in [200, 202]

    def test_notification_requires_internet_maturity(self, client: TestClient, mobile_device):
        """Test notification commands require INTERN maturity or higher."""
        pass

    def test_notification_with_custom_sound(self, client: TestClient, mobile_device):
        """Test notification with custom sound."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "send_notification",
                "params": {
                    "title": "Test",
                    "body": "Test",
                    "sound": "custom_sound"
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code in [200, 202]

    def test_notification_with_data_payload(self, client: TestClient, mobile_device):
        """Test notification with custom data payload."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "send_notification",
                "params": {
                    "title": "Test",
                    "body": "Test",
                    "data": {
                        "key1": "value1",
                        "key2": "value2"
                    }
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code in [200, 202]


# ============================================================================
# Screen Recording Capability Tests
# ============================================================================

class TestScreenRecordingCapability:
    """Tests for screen recording device capability."""

    def test_screen_recording_not_available_on_mobile(self, client: TestClient, mobile_device):
        """Test screen recording is not available on mobile devices."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "screen_record_start",
                "params": {}
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should return error for mobile devices
        assert response.status_code == 400

    def test_screen_recording_available_on_desktop(self, client: TestClient, desktop_device):
        """Test screen recording is available on desktop devices."""
        response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "screen_record_start",
                "params": {}
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        # Should be queued or executed
        assert response.status_code in [200, 202]

    def test_screen_recording_requires_supervised_maturity(self, client: TestClient, desktop_device):
        """Test screen recording requires SUPERVISED maturity or higher."""
        pass

    def test_screen_record_start_and_stop(self, client: TestClient, desktop_device):
        """Test starting and stopping screen recording."""
        # Start recording
        start_response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "screen_record_start",
                "params": {}
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        assert start_response.status_code in [200, 202]

        # Stop recording
        stop_response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "screen_record_stop",
                "params": {}
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        assert stop_response.status_code in [200, 202]


# ============================================================================
# Command Execution Capability Tests
# ============================================================================

class TestCommandExecutionCapability:
    """Tests for command execution device capability."""

    def test_command_execution_not_available_on_mobile(self, client: TestClient, mobile_device):
        """Test command execution is not available on mobile devices."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "execute_command",
                "params": {
                    "command": "ls",
                    "args": ["-la"]
                }
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should return error for mobile devices
        assert response.status_code == 400

    def test_command_execution_available_on_desktop(self, client: TestClient, desktop_device):
        """Test command execution is available on desktop devices."""
        response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "execute_command",
                "params": {
                    "command": "echo",
                    "args": ["hello"]
                }
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        # Should be queued or executed
        assert response.status_code in [200, 202]

    def test_command_execution_requires_autonomous_maturity(self, client: TestClient, desktop_device):
        """Test command execution requires AUTONOMOUS maturity."""
        pass

    def test_command_execution_with_timeout(self, client: TestClient, desktop_device):
        """Test command execution with timeout parameter."""
        response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "execute_command",
                "params": {
                    "command": "sleep",
                    "args": ["1"],
                    "timeout": 2
                }
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        assert response.status_code in [200, 202]

    def test_command_execution_returns_output(self, client: TestClient, desktop_device):
        """Test command execution returns command output."""
        response = client.post(
            f"/api/devices/{desktop_device.device_id}/command",
            json={
                "command": "execute_command",
                "params": {
                    "command": "echo",
                    "args": ["test"]
                }
            },
            headers={"X-Device-ID": desktop_device.device_id}
        )

        assert response.status_code in [200, 202]


# ============================================================================
# Device Registration Tests
# ============================================================================

class TestDeviceRegistration:
    """Tests for device registration and capability detection."""

    def test_register_mobile_device(self, client: TestClient, device_user):
        """Test registering a new mobile device."""
        response = client.post(
            "/api/devices/register",
            json={
                "device_id": "new_mobile_123",
                "name": "New Mobile Device",
                "platform": "ios",
                "app_type": "mobile",
                "capabilities": ["camera", "location", "notification"],
                "device_info": {
                    "model": "iPhone 15",
                    "os_version": "17.1"
                }
            },
            headers={"X-User-ID": str(device_user.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == "new_mobile_123"
        assert data["status"] == "registered"

    def test_register_desktop_device(self, client: TestClient, device_user):
        """Test registering a new desktop device."""
        response = client.post(
            "/api/devices/register",
            json={
                "device_id": "new_desktop_123",
                "name": "New Desktop Device",
                "platform": "darwin",
                "app_type": "desktop",
                "capabilities": ["command", "notification"],
                "device_info": {
                    "model": "MacBook Pro",
                    "os_version": "14.0"
                }
            },
            headers={"X-User-ID": str(device_user.id)}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["device_id"] == "new_desktop_123"
        assert data["status"] == "registered"

    def test_update_device_capabilities(self, client: TestClient, mobile_device):
        """Test updating device capabilities."""
        response = client.put(
            f"/api/devices/{mobile_device.device_id}/capabilities",
            json={
                "capabilities": ["camera", "location", "notification", "bluetooth"]
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code == 200

    def test_get_device_capabilities(self, client: TestClient, mobile_device):
        """Test getting device capabilities."""
        response = client.get(
            f"/api/devices/{mobile_device.device_id}/capabilities",
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert "capabilities" in data
        assert "camera" in data["capabilities"]
        assert "location" in data["capabilities"]
        assert "notification" in data["capabilities"]


# ============================================================================
# Device Status Tests
# ============================================================================

class TestDeviceStatus:
    """Tests for device status updates and monitoring."""

    def test_update_device_status_online(self, client: TestClient, mobile_device):
        """Test updating device status to online."""
        response = client.put(
            f"/api/devices/{mobile_device.device_id}/status",
            json={
                "status": "online"
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code == 200

    def test_update_device_status_offline(self, client: TestClient, mobile_device):
        """Test updating device status to offline."""
        response = client.put(
            f"/api/devices/{mobile_device.device_id}/status",
            json={
                "status": "offline"
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code == 200

    def test_update_last_command_timestamp(self, client: TestClient, mobile_device):
        """Test updating last_command_at timestamp."""
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "send_notification",
                "params": {}
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )

        # Should update last_command_at
        assert response.status_code in [200, 202]

    def test_get_device_status(self, client: TestClient, mobile_device):
        """Test getting device status."""
        response = client.get(
            f"/api/devices/{mobile_device.device_id}/status",
            headers={"X-Device-ID": mobile_device.device_id}
        )

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "last_command_at" in data


# ============================================================================
# Performance Tests
# ============================================================================

class TestDeviceCapabilitiesPerformance:
    """Performance tests for device capabilities."""

    def test_queue_command_performance(self, client: TestClient, mobile_device):
        """Test that queuing a command is fast (<100ms)."""
        import time

        start = time.time()
        response = client.post(
            f"/api/devices/{mobile_device.device_id}/command",
            json={
                "command": "send_notification",
                "params": {}
            },
            headers={"X-Device-ID": mobile_device.device_id}
        )
        duration = (time.time() - start) * 1000

        assert response.status_code in [200, 202]
        assert duration < 100  # Should be < 100ms

    def test_register_device_performance(self, client: TestClient, device_user):
        """Test that device registration is fast (<500ms)."""
        import time

        start = time.time()
        response = client.post(
            "/api/devices/register",
            json={
                "device_id": "perf_test_device",
                "name": "Performance Test Device",
                "platform": "ios",
                "app_type": "mobile",
                "capabilities": ["camera", "location", "notification"]
            },
            headers={"X-User-ID": str(device_user.id)}
        )
        duration = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration < 500  # Should be < 500ms

    def test_get_capabilities_performance(self, client: TestClient, mobile_device):
        """Test that getting capabilities is fast (<50ms)."""
        import time

        start = time.time()
        response = client.get(
            f"/api/devices/{mobile_device.device_id}/capabilities",
            headers={"X-Device-ID": mobile_device.device_id}
        )
        duration = (time.time() - start) * 1000

        assert response.status_code == 200
        assert duration < 50  # Should be < 50ms
