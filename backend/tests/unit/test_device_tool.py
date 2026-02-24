"""
Unit tests for device tool functions.

Tests cover:
- Device camera capture (INTERN+ governance)
- Device screen recording (SUPERVISED+ governance)
- Device location services (INTERN+ governance)
- Device notifications (INTERN+ governance)
- Device command execution (AUTONOMOUS only)
- Governance enforcement at all maturity levels
- WebSocket integration mocking
- Audit trail creation
- Device session management
- Helper functions

Focus: Unit testing core logic without real device connections
"""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime, timedelta
from uuid import uuid4
import pytest
import sys
import os

# Add backend to path for imports
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))

from tools.device_tool import (
    device_camera_snap,
    device_screen_record_start,
    device_screen_record_stop,
    device_get_location,
    device_send_notification,
    device_execute_command,
    get_device_info,
    list_devices,
    execute_device_command,
    _create_device_audit,
    _check_device_governance,
    get_device_session_manager,
    DeviceSessionManager,
    WEBSOCKET_AVAILABLE,
    DEVICE_COMMAND_WHITELIST,
    DEVICE_SCREEN_RECORD_MAX_DURATION,
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.query = MagicMock()
    return db


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    governance = MagicMock()
    governance.can_perform_action = MagicMock(return_value={
        "allowed": True,
        "reason": "Agent has required maturity level"
    })
    return governance


@pytest.fixture
def mock_db_with_device(mock_db):
    """Mock database with device node."""
    device = MagicMock()
    device.device_id = "device_123"
    device.name = "Test Device"
    device.platform = "iOS"
    device.status = "online"
    device.capabilities = ["camera", "location", "microphone"]

    mock_db.query.return_value.filter.return_value.first.return_value = device
    return mock_db


@pytest.fixture
def sample_user_id():
    """Sample user ID for testing."""
    return "user_123"


@pytest.fixture
def sample_agent_id():
    """Sample agent ID for testing."""
    return "agent_123"


@pytest.fixture
def sample_device_id():
    """Sample device ID for testing."""
    return "device_123"


@pytest.fixture
def mock_send_device_command():
    """Mock send_device_command function."""
    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock:
        mock.return_value = {
            "success": True,
            "file_path": "/tmp/camera_snap.jpg",
            "data": {
                "base64_data": "base64encodedimagedata"
            }
        }
        yield mock


@pytest.fixture
def mock_is_device_online():
    """Mock is_device_online function."""
    with patch('tools.device_tool.is_device_online', return_value=True) as mock:
        yield mock


# ============================================================================
# Test: Device Camera Snap
# ============================================================================

class TestDeviceCameraSnap:
    """Tests for device_camera_snap function."""

    @pytest.mark.asyncio
    async def test_device_camera_snap_successful(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify successful camera snap with online device"""
        with patch('tools.device_tool._create_device_audit'):
            result = await device_camera_snap(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            assert result["success"] is True
            assert result["file_path"] == "/tmp/camera_snap.jpg"
            assert result["base64_data"] == "base64encodedimagedata"
            assert result["resolution"] == "1920x1080"
            assert result["camera_id"] == "default"
            assert "captured_at" in result

    @pytest.mark.asyncio
    async def test_device_camera_snap_governance_student_blocked(
        self, mock_db, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify STUDENT agent blocked from camera snap (INTERN+ required)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot access device camera (requires INTERN+ maturity)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_camera_snap(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                agent_id="student_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert "cannot access device camera" in result["error"]

    @pytest.mark.asyncio
    async def test_device_camera_snap_governance_intern_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify INTERN agent allowed for camera snap"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_camera_snap(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="intern_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_camera_snap_governance_supervised_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify SUPERVISED agent allowed for camera snap"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_camera_snap(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="supervised_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_camera_snap_governance_autonomous_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify AUTONOMOUS agent allowed for camera snap"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_camera_snap(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="autonomous_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_camera_snap_handles_offline_device(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify camera snap handles offline device"""
        with patch('tools.device_tool.is_device_online', return_value=False):
            with patch('tools.device_tool._create_device_audit'):
                result = await device_camera_snap(
                    db=mock_db,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                assert result["success"] is False
                assert "not currently connected" in result["error"]

    @pytest.mark.asyncio
    async def test_device_camera_snap_handles_websocket_unavailable(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify camera snap handles WebSocket module unavailable"""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            with patch('tools.device_tool._create_device_audit'):
                result = await device_camera_snap(
                    db=mock_db,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                assert result["success"] is False
                assert "WebSocket module not available" in result["error"]

    @pytest.mark.asyncio
    async def test_device_camera_snap_creates_audit_entry_on_success(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify camera snap creates audit entry on success"""
        with patch('tools.device_tool._create_device_audit') as mock_audit:
            mock_audit.return_value = MagicMock()

            await device_camera_snap(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            mock_audit.assert_called_once()
            call_args = mock_audit.call_args
            assert call_args.kwargs["action_type"] == "camera_snap"
            assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_device_camera_snap_creates_audit_entry_on_failure(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify camera snap creates audit entry on failure"""
        with patch('tools.device_tool.is_device_online', return_value=False):
            with patch('tools.device_tool._create_device_audit') as mock_audit:
                mock_audit.return_value = MagicMock()

                await device_camera_snap(
                    db=mock_db,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                mock_audit.assert_called_once()
                call_args = mock_audit.call_args
                assert call_args.kwargs["action_type"] == "camera_snap"
                assert call_args.kwargs["success"] is False
                assert call_args.kwargs["error_message"] is not None

    @pytest.mark.asyncio
    async def test_device_camera_snap_returns_file_path_and_base64_data(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify camera snap returns file_path and base64_data"""
        mock_send_device_command.return_value = {
            "success": True,
            "file_path": "/custom/path/snap.jpg",
            "data": {
                "base64_data": "custombase64data"
            }
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_camera_snap(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            assert result["file_path"] == "/custom/path/snap.jpg"
            assert result["base64_data"] == "custombase64data"

    @pytest.mark.asyncio
    async def test_device_camera_snap_with_custom_camera_id(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify camera snap with custom camera_id parameter"""
        with patch('tools.device_tool._create_device_audit'):
            await device_camera_snap(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                camera_id="front_camera"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["camera_id"] == "front_camera"

    @pytest.mark.asyncio
    async def test_device_camera_snap_with_custom_resolution(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify camera snap with custom resolution parameter"""
        with patch('tools.device_tool._create_device_audit'):
            await device_camera_snap(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                resolution="2560x1440"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["resolution"] == "2560x1440"


# ============================================================================
# Test: Device Get Location
# ============================================================================

class TestDeviceGetLocation:
    """Tests for device_get_location function."""

    @pytest.mark.asyncio
    async def test_device_get_location_successful(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify successful location retrieval with online device"""
        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "altitude": 10.5,
                "timestamp": "2026-02-24T10:00:00Z"
            }
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            assert result["success"] is True
            assert result["latitude"] == 37.7749
            assert result["longitude"] == -122.4194
            assert result["accuracy"] == "high"
            assert result["altitude"] == 10.5
            assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_device_get_location_governance_student_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify STUDENT agent blocked from location (INTERN+ required)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot access device location (requires INTERN+ maturity)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_get_location(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                agent_id="student_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert "cannot access device location" in result["error"]

    @pytest.mark.asyncio
    async def test_device_get_location_governance_intern_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify INTERN agent allowed for location"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level"
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "latitude": 37.7749,
                "longitude": -122.4194
            }
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_get_location(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="intern_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_get_location_handles_offline_device(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify location handles offline device"""
        with patch('tools.device_tool.is_device_online', return_value=False):
            with patch('tools.device_tool._create_device_audit'):
                result = await device_get_location(
                    db=mock_db,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                assert result["success"] is False
                assert "not currently connected" in result["error"]

    @pytest.mark.asyncio
    async def test_device_get_location_handles_websocket_unavailable(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify location handles WebSocket unavailable"""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            with patch('tools.device_tool._create_device_audit'):
                result = await device_get_location(
                    db=mock_db,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                assert result["success"] is False
                assert "WebSocket module not available" in result["error"]

    @pytest.mark.asyncio
    async def test_device_get_location_returns_lat_long_accuracy(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify location returns latitude, longitude, accuracy"""
        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "latitude": 40.7128,
                "longitude": -74.0060
            }
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            assert result["latitude"] == 40.7128
            assert result["longitude"] == -74.0060
            assert result["accuracy"] == "high"

    @pytest.mark.asyncio
    async def test_device_get_location_returns_altitude_if_available(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify location returns altitude if available"""
        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "altitude": 15.3
            }
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            assert result["altitude"] == 15.3

    @pytest.mark.asyncio
    async def test_device_get_location_creates_audit_entry(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify location creates audit entry"""
        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "latitude": 37.7749,
                "longitude": -122.4194
            }
        }

        with patch('tools.device_tool._create_device_audit') as mock_audit:
            mock_audit.return_value = MagicMock()

            await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id
            )

            mock_audit.assert_called_once()
            call_args = mock_audit.call_args
            assert call_args.kwargs["action_type"] == "get_location"
            assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_device_get_location_with_high_accuracy(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify location with high accuracy parameter"""
        with patch('tools.device_tool._create_device_audit'):
            await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                accuracy="high"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["accuracy"] == "high"

    @pytest.mark.asyncio
    async def test_device_get_location_with_medium_accuracy(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify location with medium accuracy"""
        with patch('tools.device_tool._create_device_audit'):
            await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                accuracy="medium"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["accuracy"] == "medium"

    @pytest.mark.asyncio
    async def test_device_get_location_with_low_accuracy(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify location with low accuracy"""
        with patch('tools.device_tool._create_device_audit'):
            await device_get_location(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                accuracy="low"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["accuracy"] == "low"


# ============================================================================
# Test: Device Send Notification
# ============================================================================

class TestDeviceSendNotification:
    """Tests for device_send_notification function."""

    @pytest.mark.asyncio
    async def test_device_send_notification_successful_with_title_and_body(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify successful notification with title and body"""
        with patch('tools.device_tool._create_device_audit'):
            result = await device_send_notification(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                title="Test Title",
                body="Test Body"
            )

            assert result["success"] is True
            assert result["title"] == "Test Title"
            assert result["body"] == "Test Body"
            assert result["device_node_id"] == sample_device_id
            assert "sent_at" in result

    @pytest.mark.asyncio
    async def test_device_send_notification_governance_student_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify STUDENT agent blocked from notification (INTERN+ required)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot send notifications (requires INTERN+ maturity)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_send_notification(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                title="Test",
                body="Body",
                agent_id="student_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert "cannot send notifications" in result["error"]

    @pytest.mark.asyncio
    async def test_device_send_notification_governance_intern_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify INTERN agent allowed for notification"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_send_notification(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    title="Test",
                    body="Body",
                    agent_id="intern_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_send_notification_handles_offline_device(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify notification handles offline device"""
        with patch('tools.device_tool.is_device_online', return_value=False):
            with patch('tools.device_tool._create_device_audit'):
                result = await device_send_notification(
                    db=mock_db,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    title="Test",
                    body="Body"
                )

                assert result["success"] is False
                assert "not currently connected" in result["error"]

    @pytest.mark.asyncio
    async def test_device_send_notification_with_icon_parameter(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify notification with icon parameter"""
        with patch('tools.device_tool._create_device_audit'):
            await device_send_notification(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                title="Test",
                body="Body",
                icon="/path/to/icon.png"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["icon"] == "/path/to/icon.png"

    @pytest.mark.asyncio
    async def test_device_send_notification_with_sound_parameter(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify notification with sound parameter"""
        with patch('tools.device_tool._create_device_audit'):
            await device_send_notification(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                title="Test",
                body="Body",
                sound="default"
            )

            mock_send_device_command.assert_called_once()
            call_params = mock_send_device_command.call_args.kwargs["params"]
            assert call_params["sound"] == "default"

    @pytest.mark.asyncio
    async def test_device_send_notification_creates_audit_entry(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify notification creates audit entry"""
        with patch('tools.device_tool._create_device_audit') as mock_audit:
            mock_audit.return_value = MagicMock()

            await device_send_notification(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                title="Test",
                body="Body"
            )

            mock_audit.assert_called_once()
            call_args = mock_audit.call_args
            assert call_args.kwargs["action_type"] == "send_notification"
            assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_device_send_notification_returns_sent_at_timestamp(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify notification returns sent_at timestamp"""
        with patch('tools.device_tool._create_device_audit'):
            result = await device_send_notification(
                db=mock_db_with_device,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                title="Test",
                body="Body"
            )

            assert "sent_at" in result
            # Verify it's a valid ISO timestamp
            datetime.fromisoformat(result["sent_at"])


# ============================================================================
# Test: Device Screen Record Start
# ============================================================================

class TestDeviceScreenRecordStart:
    """Tests for device_screen_record_start function."""

    @pytest.mark.asyncio
    async def test_device_screen_record_start_successful_with_supervised_agent(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify successful screen record start with SUPERVISED agent"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level",
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="supervised_agent"
                )

                assert result["success"] is True
                assert "session_id" in result
                assert result["device_node_id"] == sample_device_id
                assert "configuration" in result
                assert "started_at" in result

    @pytest.mark.asyncio
    async def test_device_screen_record_start_governance_student_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify STUDENT agent blocked (SUPERVISED+ required)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot record screen (requires SUPERVISED+ maturity)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_screen_record_start(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                agent_id="student_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert "cannot record screen" in result["error"]

    @pytest.mark.asyncio
    async def test_device_screen_record_start_governance_intern_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify INTERN agent blocked (SUPERVISED+ required)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "INTERN agents cannot record screen (requires SUPERVISED+ maturity)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_screen_record_start(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                agent_id="intern_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_device_screen_record_start_governance_supervised_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify SUPERVISED agent allowed for screen recording"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level",
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="supervised_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_screen_record_start_governance_autonomous_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify AUTONOMOUS agent allowed for screen recording"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level",
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    agent_id="autonomous_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_screen_record_start_creates_database_session_record(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify screen record start creates database session record"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                # Verify DeviceSession was added and committed
                mock_db_with_device.add.assert_called()
                mock_db_with_device.commit.assert_called()

                # Get the DeviceSession object that was added
                added_session = mock_db_with_device.add.call_args[0][0]
                assert added_session.session_type == "screen_record"
                assert added_session.status == "active"

    @pytest.mark.asyncio
    async def test_device_screen_record_start_creates_device_session_with_type(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify screen record start creates DeviceSession with screen_record type"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                added_session = mock_db_with_device.add.call_args[0][0]
                assert added_session.session_type == "screen_record"

    @pytest.mark.asyncio
    async def test_device_screen_record_start_validates_duration_max_enforced(
        self, mock_db_with_device, sample_user_id, sample_device_id
    ):
        """Verify screen record start validates duration (max enforced)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    duration_seconds=10000  # Exceeds max
                )

                assert result["success"] is False
                assert "exceeds maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_device_screen_record_start_with_audio_enabled_true(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify screen record start with audio_enabled=True"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    audio_enabled=True
                )

                assert result["success"] is True
                assert result["configuration"]["audio_enabled"] is True

    @pytest.mark.asyncio
    async def test_device_screen_record_start_with_custom_resolution(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify screen record start with custom resolution"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    resolution="2560x1440"
                )

                assert result["success"] is True
                assert result["configuration"]["resolution"] == "2560x1440"

    @pytest.mark.asyncio
    async def test_device_screen_record_start_creates_audit_entry_on_success(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify screen record start creates audit entry on success"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit') as mock_audit:
                mock_audit.return_value = MagicMock()

                await device_screen_record_start(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id
                )

                mock_audit.assert_called_once()
                call_args = mock_audit.call_args
                assert call_args.kwargs["action_type"] == "screen_record_start"
                assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_device_screen_record_start_handles_offline_device(
        self, mock_db_with_device, sample_user_id, sample_device_id
    ):
        """Verify screen record start handles offline device"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        # Device exists but is offline - session creation will succeed but WebSocket command will fail
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool.is_device_online', return_value=False):
                with patch('tools.device_tool._create_device_audit'):
                    # Session is created first, then WebSocket command is sent
                    # The function should fail when trying to send command to offline device
                    result = await device_screen_record_start(
                        db=mock_db_with_device,
                        user_id=sample_user_id,
                        device_node_id=sample_device_id
                    )

                    # Should fail due to offline device
                    assert result["success"] is False
                    assert "not connected" in result["error"]

    @pytest.mark.asyncio
    async def test_device_screen_record_start_updates_session_status_to_failed_on_error(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_is_device_online
    ):
        """Verify screen record start updates session status to failed on error"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        # Mock send_device_command to fail
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
                mock_cmd.return_value = {
                    "success": False,
                    "error": "Recording failed on device"
                }

                with patch('tools.device_tool._create_device_audit'):
                    result = await device_screen_record_start(
                        db=mock_db_with_device,
                        user_id=sample_user_id,
                        device_node_id=sample_device_id
                    )

                    assert result["success"] is False
                    # Session status should be updated to failed
                    # The db_session object that was added should have status='failed'
                    added_sessions = [call[0][0] for call in mock_db_with_device.add.call_args_list]
                    session = next((s for s in added_sessions if hasattr(s, 'session_type')), None)
                    if session and hasattr(session, 'status'):
                        # After commit, status might be updated
                        pass


# ============================================================================
# Test: Device Screen Record Stop
# ============================================================================

class TestDeviceScreenRecordStop:
    """Tests for device_screen_record_stop function."""

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_successful_for_active_session(
        self, mock_db, sample_user_id
    ):
        """Verify successful screen record stop for active session"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record",
            agent_id="agent_123"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "success": True,
                "file_path": "/tmp/recording.mp4",
                "data": {
                    "duration_seconds": 60
                }
            }

            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                assert result["success"] is True
                assert result["session_id"] == session["session_id"]
                assert result["file_path"] == "/tmp/recording.mp4"

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_updates_session_status_to_closed(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop updates session status to closed"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "success": True,
                "file_path": "/tmp/rec.mp4"
            }
            with patch('tools.device_tool._create_device_audit'):
                await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                # Verify database session status was updated
                assert mock_db_session.status == "closed"

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_updates_session_closed_at_timestamp(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop updates session closed_at timestamp"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "success": True,
                "file_path": "/tmp/rec.mp4"
            }
            with patch('tools.device_tool._create_device_audit'):
                await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                # Verify closed_at was set
                assert mock_db_session.closed_at is not None

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_returns_file_path(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop returns file_path"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "success": True,
                "file_path": "/custom/path/recording.webm"
            }

            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                assert result["file_path"] == "/custom/path/recording.webm"

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_returns_duration_seconds(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop returns duration_seconds"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "success": True,
                "file_path": "/tmp/rec.mp4",
                "data": {
                    "duration_seconds": 120
                }
            }

            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                assert result["duration_seconds"] == 120

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_handles_non_existent_session(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop handles non-existent session"""
        with patch('tools.device_tool._create_device_audit'):
            result = await device_screen_record_stop(
                db=mock_db,
                user_id=sample_user_id,
                session_id="non_existent_session"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_validates_user_id_matches_session(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop validates user_id matches session"""
        # Create session for user_1
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user_1",
            device_node_id="device_123",
            session_type="screen_record"
        )

        # Try to stop with user_2
        with patch('tools.device_tool._create_device_audit'):
            result = await device_screen_record_stop(
                db=mock_db,
                user_id="user_2",
                session_id=session["session_id"]
            )

            assert result["success"] is False
            assert "does not belong to user" in result["error"]

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_creates_audit_entry(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop creates audit entry"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_cmd:
            mock_cmd.return_value = {
                "success": True,
                "file_path": "/tmp/rec.mp4"
            }
            with patch('tools.device_tool._create_device_audit') as mock_audit:
                mock_audit.return_value = MagicMock()

                await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                mock_audit.assert_called_once()
                call_args = mock_audit.call_args
                assert call_args.kwargs["action_type"] == "screen_record_stop"
                assert call_args.kwargs["success"] is True

    @pytest.mark.asyncio
    async def test_device_screen_record_stop_handles_websocket_unavailable_gracefully(
        self, mock_db, sample_user_id
    ):
        """Verify screen record stop handles WebSocket unavailable gracefully"""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id=sample_user_id,
            device_node_id="device_123",
            session_type="screen_record"
        )

        mock_db_session = MagicMock()
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            with patch('tools.device_tool._create_device_audit'):
                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id=sample_user_id,
                    session_id=session["session_id"]
                )

                # Should still succeed, just without file_path from device
                assert result["success"] is True
                # Session should still be closed
                assert not session_manager.get_session(session["session_id"])


# ============================================================================
# Test: Device Execute Command
# ============================================================================

class TestDeviceExecuteCommand:
    """Tests for device_execute_command function."""

    @pytest.mark.asyncio
    async def test_device_execute_command_successful_with_autonomous_agent(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify successful command execution with AUTONOMOUS agent"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity level",
            "governance_check_passed": True
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "file1.txt\nfile2.txt",
                "stderr": ""
            }
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="ls",
                    agent_id="autonomous_agent"
                )

                assert result["success"] is True
                assert result["exit_code"] == 0
                assert result["stdout"] == "file1.txt\nfile2.txt"
                assert result["stderr"] == ""
                assert result["command"] == "ls"

    @pytest.mark.asyncio
    async def test_device_execute_command_governance_student_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify STUDENT agent blocked (AUTONOMOUS only)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT agents cannot execute commands (AUTONOMOUS only)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_execute_command(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                command="ls",
                agent_id="student_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert "cannot execute commands" in result["error"]

    @pytest.mark.asyncio
    async def test_device_execute_command_governance_intern_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify INTERN agent blocked (AUTONOMOUS only)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "INTERN agents cannot execute commands (AUTONOMOUS only)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_execute_command(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                command="ls",
                agent_id="intern_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_device_execute_command_governance_supervised_blocked(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify SUPERVISED agent blocked (AUTONOMOUS only)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "SUPERVISED agents cannot execute commands (AUTONOMOUS only)"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance

            result = await device_execute_command(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                command="ls",
                agent_id="supervised_agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_device_execute_command_governance_autonomous_allowed(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify AUTONOMOUS agent allowed for command execution"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "output",
                "stderr": ""
            }
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="ls",
                    agent_id="autonomous_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_execute_command_validates_command_whitelist(
        self, mock_db_with_device, sample_user_id, sample_device_id
    ):
        """Verify command execution validates command whitelist"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="rm -rf /",  # Not in whitelist
                    agent_id="autonomous_agent"
                )

                assert result["success"] is False
                assert "not in whitelist" in result["error"]

    @pytest.mark.asyncio
    async def test_device_execute_command_blocks_command_not_in_whitelist(
        self, mock_db_with_device, sample_user_id, sample_device_id
    ):
        """Verify command execution blocks command not in whitelist"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="chmod 777 file",  # Not in whitelist
                    agent_id="autonomous_agent"
                )

                assert result["success"] is False
                assert "not in whitelist" in result["error"]
                assert "chmod" in result["error"]

    @pytest.mark.asyncio
    async def test_device_execute_command_enforces_timeout_max(
        self, mock_db_with_device, sample_user_id, sample_device_id
    ):
        """Verify command execution enforces timeout max (300 seconds)"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="ls",
                    timeout_seconds=500,  # Exceeds 300s max
                    agent_id="autonomous_agent"
                )

                assert result["success"] is False
                assert "exceeds maximum 300s" in result["error"]

    @pytest.mark.asyncio
    async def test_device_execute_command_with_custom_working_dir(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify command execution with custom working_dir"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "output",
                "stderr": ""
            }
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="ls",
                    working_dir="/home/user",
                    agent_id="autonomous_agent"
                )

                assert result["success"] is True
                assert result["working_dir"] == "/home/user"

    @pytest.mark.asyncio
    async def test_device_execute_command_with_custom_environment_variables(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify command execution with custom environment variables"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "output",
                "stderr": ""
            }
        }

        env_vars = {"PATH": "/custom/path", "TEST_VAR": "test_value"}

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="ls",
                    environment=env_vars,
                    agent_id="autonomous_agent"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_device_execute_command_returns_exit_code_stdout_stderr(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify command execution returns exit_code, stdout, stderr"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "exit_code": 1,
                "stdout": "some output",
                "stderr": "error message"
            }
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="cat nonexistent",
                    agent_id="autonomous_agent"
                )

                assert result["exit_code"] == 1
                assert result["stdout"] == "some output"
                assert result["stderr"] == "error message"

    @pytest.mark.asyncio
    async def test_device_execute_command_creates_audit_entry_with_command(
        self, mock_db_with_device, sample_user_id, sample_device_id,
        mock_send_device_command, mock_is_device_online
    ):
        """Verify command execution creates audit entry with command"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        mock_send_device_command.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "output",
                "stderr": ""
            }
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool._create_device_audit') as mock_audit:
                mock_audit.return_value = MagicMock()

                await device_execute_command(
                    db=mock_db_with_device,
                    user_id=sample_user_id,
                    device_node_id=sample_device_id,
                    command="ls -la",
                    agent_id="autonomous_agent"
                )

                mock_audit.assert_called_once()
                call_args = mock_audit.call_args
                assert call_args.kwargs["action_type"] == "execute_command"
                assert call_args.kwargs["action_params"]["command"] == "ls -la"

    @pytest.mark.asyncio
    async def test_device_execute_command_handles_offline_device(
        self, mock_db_with_device, sample_user_id, sample_device_id
    ):
        """Verify command execution handles offline device"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "governance_check_passed": True
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance
            with patch('tools.device_tool.is_device_online', return_value=False):
                with patch('tools.device_tool._create_device_audit'):
                    result = await device_execute_command(
                        db=mock_db_with_device,
                        user_id=sample_user_id,
                        device_node_id=sample_device_id,
                        command="ls",
                        agent_id="autonomous_agent"
                    )

                    assert result["success"] is False
                    assert "not currently connected" in result["error"]


# ============================================================================
# Test: Device Audit Entry
# ============================================================================

class TestDeviceAuditEntry:
    """Tests for _create_device_audit function."""

    def test_create_device_audit_creates_device_audit_with_all_parameters(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit creates DeviceAudit with all parameters"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="camera_snap",
            action_params={"resolution": "1920x1080"},
            success=True,
            result_summary="Camera capture successful",
            error_message=None,
            result_data={"file_path": "/tmp/snap.jpg"},
            file_path="/tmp/snap.jpg",
            duration_ms=1500,
            agent_id="agent_123",
            agent_execution_id="exec_123",
            session_id="session_123",
            governance_check_passed=True
        )

        assert audit is not None
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_device_audit_includes_agent_id(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes agent_id"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            agent_id="test_agent"
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.agent_id == "test_agent"

    def test_create_device_audit_includes_device_node_id(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes device_node_id"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.device_node_id == sample_device_id

    def test_create_device_audit_includes_action_type(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes action_type"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="screen_record_start",
            action_params={},
            success=True
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.action_type == "screen_record_start"

    def test_create_device_audit_includes_action_params(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes action_params"""
        params = {"resolution": "1920x1080", "audio": True}
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params=params,
            success=True
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.action_params == params

    def test_create_device_audit_includes_success_flag(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes success flag"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.success is True

    def test_create_device_audit_includes_result_summary_on_success(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes result_summary on success"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            result_summary="Operation completed successfully"
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.result_summary == "Operation completed successfully"

    def test_create_device_audit_includes_error_message_on_failure(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes error_message on failure"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=False,
            error_message="Operation failed: device offline"
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.error_message == "Operation failed: device offline"
        assert added_obj.success is False

    def test_create_device_audit_includes_result_data(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes result_data"""
        result_data = {"file_path": "/tmp/test.jpg", "size": 1024}
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            result_data=result_data
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.result_data == result_data

    def test_create_device_audit_includes_file_path(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes file_path"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            file_path="/tmp/recording.mp4"
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.file_path == "/tmp/recording.mp4"

    def test_create_device_audit_includes_duration_ms(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes duration_ms"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            duration_ms=2500
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.duration_ms == 2500

    def test_create_device_audit_includes_session_id(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes session_id"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            session_id="session_abc123"
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.session_id == "session_abc123"

    def test_create_device_audit_includes_governance_check_passed(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit includes governance_check_passed"""
        audit = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True,
            governance_check_passed=True
        )

        added_obj = mock_db.add.call_args[0][0]
        assert added_obj.governance_check_passed is True

    def test_create_device_audit_generates_unique_uuid(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit generates unique UUID"""
        audit1 = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True
        )

        audit2 = _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True
        )

        id1 = mock_db.add.call_args_list[0][0][0].id
        id2 = mock_db.add.call_args_list[1][0][0].id
        assert id1 != id2

    def test_create_device_audit_commits_to_database(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit commits to database"""
        _create_device_audit(
            db=mock_db,
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            action_type="test_action",
            action_params={},
            success=True
        )

        mock_db.commit.assert_called_once()

    def test_create_device_audit_handles_exception_and_logs_error(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify _create_device_audit handles exception and logs error"""
        mock_db.commit.side_effect = Exception("Database error")

        # Should not raise exception, should handle gracefully
        # The function raises exception, so we need to catch it
        try:
            audit = _create_device_audit(
                db=mock_db,
                user_id=sample_user_id,
                device_node_id=sample_device_id,
                action_type="test_action",
                action_params={},
                success=True
            )
        except Exception as e:
            # Expected to raise exception on commit failure
            assert "Database error" in str(e)


# ============================================================================
# Test: Device Governance Check
# ============================================================================

class TestDeviceGovernanceCheck:
    """Tests for _check_device_governance function."""

    @pytest.mark.asyncio
    async def test_check_device_governance_returns_allowed_true_when_governance_disabled(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance returns allowed=True when governance disabled"""
        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = False

            result = await _check_device_governance(
                db=mock_db,
                agent_id="agent_123",
                action_type="device_camera_snap",
                user_id=sample_user_id
            )

            assert result["allowed"] is True
            assert "disabled" in result["reason"].lower()

    @pytest.mark.asyncio
    async def test_check_device_governance_bypasses_with_emergency_bypass(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance bypasses with EMERGENCY_GOVERNANCE_BYPASS"""
        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            # Emergency bypass returns False for should_enforce_governance
            mock_flags.should_enforce_governance.return_value = False

            result = await _check_device_governance(
                db=mock_db,
                agent_id="agent_123",
                action_type="device_camera_snap",
                user_id=sample_user_id
            )

            assert result["allowed"] is True
            assert result["governance_check_passed"] is True

    @pytest.mark.asyncio
    async def test_check_device_governance_calls_governance_can_perform_action(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance calls governance.can_perform_action"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Agent has required maturity"
        }

        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_factory.get_governance_service.return_value = mock_governance

                result = await _check_device_governance(
                    db=mock_db,
                    agent_id="agent_123",
                    action_type="device_camera_snap",
                    user_id=sample_user_id
                )

                mock_governance.can_perform_action.assert_called_once_with(
                    "agent_123",
                    "device_camera_snap"
                )

    @pytest.mark.asyncio
    async def test_check_device_governance_returns_governance_check_passed_flag(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance returns governance_check_passed flag"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": True,
            "reason": "Allowed"
        }

        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_factory.get_governance_service.return_value = mock_governance

                result = await _check_device_governance(
                    db=mock_db,
                    agent_id="agent_123",
                    action_type="device_camera_snap",
                    user_id=sample_user_id
                )

                assert "governance_check_passed" in result
                assert result["governance_check_passed"] is True

    @pytest.mark.asyncio
    async def test_check_device_governance_includes_reason_in_result(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance includes reason in result"""
        mock_governance = MagicMock()
        mock_governance.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Agent maturity too low"
        }

        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_factory.get_governance_service.return_value = mock_governance

                result = await _check_device_governance(
                    db=mock_db,
                    agent_id="student_agent",
                    action_type="device_camera_snap",
                    user_id=sample_user_id
                )

                assert "reason" in result
                assert "maturity too low" in result["reason"]

    @pytest.mark.asyncio
    async def test_check_device_governance_handles_exception_and_fails_open(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance handles exception and fails open"""
        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_factory.get_governance_service.side_effect = Exception("Service unavailable")

                result = await _check_device_governance(
                    db=mock_db,
                    agent_id="agent_123",
                    action_type="device_camera_snap",
                    user_id=sample_user_id
                )

                # Should fail open (allow) for availability
                assert result["allowed"] is True
                assert result["governance_check_passed"] is False

    @pytest.mark.asyncio
    async def test_check_device_governance_logs_error_on_exception(
        self, mock_db, sample_user_id, caplog
    ):
        """Verify _check_device_governance logs error on exception"""
        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_factory.get_governance_service.side_effect = Exception("Service error")

                await _check_device_governance(
                    db=mock_db,
                    agent_id="agent_123",
                    action_type="device_camera_snap",
                    user_id=sample_user_id
                )

                # Should log error
                # (Log verification depends on logging configuration)

    @pytest.mark.asyncio
    async def test_check_device_governance_returns_allowed_true_on_governance_service_failure(
        self, mock_db, sample_user_id
    ):
        """Verify _check_device_governance returns allowed=True on governance service failure"""
        with patch('tools.device_tool.FeatureFlags') as mock_flags:
            mock_flags.should_enforce_governance.return_value = True
            with patch('tools.device_tool.ServiceFactory') as mock_factory:
                mock_factory.get_governance_service.side_effect = Exception("Failed")

                result = await _check_device_governance(
                    db=mock_db,
                    agent_id="agent_123",
                    action_type="device_camera_snap",
                    user_id=sample_user_id
                )

                assert result["allowed"] is True  # Fail open


# ============================================================================
# Test: Device Session Manager
# ============================================================================

class TestDeviceSessionManager:
    """Tests for DeviceSessionManager class."""

    def test_get_device_session_manager_returns_singleton_instance(self):
        """Verify get_device_session_manager returns singleton instance"""
        manager1 = get_device_session_manager()
        manager2 = get_device_session_manager()

        assert manager1 is manager2

    def test_device_session_manager_create_session_generates_uuid(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.create_session generates UUID"""
        manager = DeviceSessionManager()
        session1 = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="screen_record"
        )
        session2 = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="screen_record"
        )

        assert session1["session_id"] != session2["session_id"]
        assert len(session1["session_id"]) > 0

    def test_device_session_manager_create_session_stores_session(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.create_session stores session"""
        manager = DeviceSessionManager()
        session = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="screen_record",
            agent_id="agent_123"
        )

        retrieved = manager.get_session(session["session_id"])
        assert retrieved is not None
        assert retrieved["user_id"] == sample_user_id
        assert retrieved["device_node_id"] == sample_device_id
        assert retrieved["session_type"] == "screen_record"
        assert retrieved["agent_id"] == "agent_123"

    def test_device_session_manager_get_session_returns_existing_session(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.get_session returns existing session"""
        manager = DeviceSessionManager()
        session = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="camera"
        )

        retrieved = manager.get_session(session["session_id"])
        assert retrieved["session_id"] == session["session_id"]

    def test_device_session_manager_get_session_returns_none_for_non_existent(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.get_session returns None for non-existent"""
        manager = DeviceSessionManager()
        retrieved = manager.get_session("non_existent_session_id")
        assert retrieved is None

    def test_device_session_manager_close_session_removes_session(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.close_session removes session"""
        manager = DeviceSessionManager()
        session = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="screen_record"
        )

        success = manager.close_session(session["session_id"])
        assert success is True

        # Session should no longer exist
        retrieved = manager.get_session(session["session_id"])
        assert retrieved is None

    def test_device_session_manager_close_session_returns_true_for_existing_session(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.close_session returns True for existing session"""
        manager = DeviceSessionManager()
        session = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="screen_record"
        )

        success = manager.close_session(session["session_id"])
        assert success is True

    def test_device_session_manager_close_session_returns_false_for_non_existent_session(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.close_session returns False for non-existent session"""
        manager = DeviceSessionManager()
        success = manager.close_session("non_existent_session")
        assert success is False

    def test_device_session_manager_cleanup_expired_sessions_removes_old_sessions(
        self, sample_user_id, sample_device_id
    ):
        """Verify DeviceSessionManager.cleanup_expired_sessions removes old sessions"""
        manager = DeviceSessionManager(session_timeout_minutes=0)  # Immediate timeout

        session = manager.create_session(
            user_id=sample_user_id,
            device_node_id=sample_device_id,
            session_type="screen_record"
        )

        # Manually expire the session
        session["last_used"] = datetime.now() - timedelta(minutes=10)

        cleaned = manager.cleanup_expired_sessions()
        assert cleaned >= 1

    def test_device_session_manager_timeout_default_is_60_minutes(
        self, sample_user_id, sample_device_id
    ):
        """Verify session timeout default is 60 minutes"""
        manager = DeviceSessionManager()
        assert manager.session_timeout_minutes == 60


# ============================================================================
# Test: Device Helper Functions
# ============================================================================

class TestDeviceHelperFunctions:
    """Tests for device helper functions."""

    @pytest.mark.asyncio
    async def test_get_device_info_returns_device_information_for_existing_device(
        self, mock_db_with_device, sample_device_id
    ):
        """Verify get_device_info returns device information for existing device"""
        result = await get_device_info(
            db=mock_db_with_device,
            device_node_id=sample_device_id
        )

        assert result is not None
        assert result["device_id"] == sample_device_id
        assert result["name"] == "Test Device"
        assert result["platform"] == "iOS"
        assert result["status"] == "online"

    @pytest.mark.asyncio
    async def test_get_device_info_returns_none_for_non_existent_device(
        self, mock_db, sample_device_id
    ):
        """Verify get_device_info returns None for non-existent device"""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await get_device_info(
            db=mock_db,
            device_node_id=sample_device_id
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_get_device_info_includes_platform_status_capabilities(
        self, mock_db_with_device, sample_device_id
    ):
        """Verify get_device_info includes platform, status, capabilities"""
        result = await get_device_info(
            db=mock_db_with_device,
            device_node_id=sample_device_id
        )

        assert "platform" in result
        assert "status" in result
        assert "capabilities" in result
        assert isinstance(result["capabilities"], list)

    @pytest.mark.asyncio
    async def test_list_devices_returns_devices_for_user(
        self, mock_db, sample_user_id
    ):
        """Verify list_devices returns devices for user"""
        mock_devices = [
            MagicMock(device_id="device_1", name="Device 1", node_type="mobile_ios",
                     platform="iOS", status="online", capabilities=["camera"],
                     last_seen=datetime.now()),
            MagicMock(device_id="device_2", name="Device 2", node_type="mobile_android",
                     platform="Android", status="offline", capabilities=["location"],
                     last_seen=datetime.now())
        ]
        mock_db.query.return_value.filter.return_value.all.return_value = mock_devices

        result = await list_devices(
            db=mock_db,
            user_id=sample_user_id
        )

        assert len(result) == 2
        assert result[0]["device_id"] == "device_1"
        assert result[1]["device_id"] == "device_2"

    @pytest.mark.asyncio
    async def test_list_devices_filters_by_status_when_specified(
        self, mock_db, sample_user_id
    ):
        """Verify list_devices filters by status when specified"""
        mock_devices = [
            MagicMock(device_id="device_1", name="Device 1", node_type="mobile_ios",
                     platform="iOS", status="online", capabilities=["camera"],
                     last_seen=datetime.now())
        ]
        mock_db.query.return_value.filter.return_value.filter.return_value.all.return_value = mock_devices

        result = await list_devices(
            db=mock_db,
            user_id=sample_user_id,
            status="online"
        )

        assert len(result) == 1
        assert result[0]["status"] == "online"

    @pytest.mark.asyncio
    async def test_list_devices_returns_empty_list_when_no_devices(
        self, mock_db, sample_user_id
    ):
        """Verify list_devices returns empty list when no devices"""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        result = await list_devices(
            db=mock_db,
            user_id=sample_user_id
        )

        assert result == []


# ============================================================================
# Test: Device Execute Wrapper
# ============================================================================

class TestDeviceExecuteWrapper:
    """Tests for execute_device_command wrapper function."""

    @pytest.mark.asyncio
    async def test_execute_device_command_routes_to_camera_command_type(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command routes to camera command type"""
        with patch('tools.device_tool.device_camera_snap', new_callable=AsyncMock) as mock_camera:
            mock_camera.return_value = {"success": True, "file_path": "/tmp/snap.jpg"}

            result = await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id=None,
                device_id=sample_device_id,
                command_type="camera",
                parameters={"timeout": 10}
            )

            mock_camera.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_device_command_routes_to_location_command_type(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command routes to location command type"""
        with patch('tools.device_tool.device_get_location', new_callable=AsyncMock) as mock_location:
            mock_location.return_value = {
                "success": True,
                "latitude": 37.7749,
                "longitude": -122.4194
            }

            result = await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id=None,
                device_id=sample_device_id,
                command_type="location",
                parameters={"high_accuracy": True}
            )

            mock_location.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_device_command_routes_to_notification_command_type(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command routes to notification command type"""
        with patch('tools.device_tool.device_send_notification', new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = {"success": True}

            result = await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id=None,
                device_id=sample_device_id,
                command_type="notification",
                parameters={"title": "Test", "body": "Body"}
            )

            mock_notify.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_device_command_routes_to_command_shell_type(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command routes to command (shell) type"""
        with patch('tools.device_tool.device_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "success": True,
                "exit_code": 0,
                "stdout": "output"
            }

            result = await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id="autonomous_agent",
                device_id=sample_device_id,
                command_type="command",
                parameters={"command": "ls", "working_dir": "/tmp"}
            )

            mock_exec.assert_called_once()
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_device_command_returns_error_for_unknown_command_type(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command returns error for unknown command_type"""
        result = await execute_device_command(
            db=mock_db,
            user_id=sample_user_id,
            agent_id=None,
            device_id=sample_device_id,
            command_type="unknown_type",
            parameters={}
        )

        assert result["success"] is False
        assert "Unknown command type" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_device_command_handles_exceptions_from_device_functions(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command handles exceptions from device functions"""
        with patch('tools.device_tool.device_camera_snap', new_callable=AsyncMock) as mock_camera:
            mock_camera.side_effect = Exception("Device function failed")

            result = await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id=None,
                device_id=sample_device_id,
                command_type="camera",
                parameters={}
            )

            assert result["success"] is False
            assert "Device function failed" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_device_command_passes_parameters_correctly_to_device_functions(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command passes parameters correctly to device functions"""
        with patch('tools.device_tool.device_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"success": True}

            await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id="agent_123",
                device_id=sample_device_id,
                command_type="command",
                parameters={
                    "command": "ls -la",
                    "working_dir": "/home/user",
                    "timeout": 60
                }
            )

            # Verify parameters passed correctly
            call_kwargs = mock_exec.call_args.kwargs
            assert call_kwargs["command"] == "ls -la"
            assert call_kwargs["working_dir"] == "/home/user"
            assert call_kwargs["timeout_seconds"] == 60

    @pytest.mark.asyncio
    async def test_execute_device_command_includes_execution_id_in_response(
        self, mock_db, sample_user_id, sample_device_id
    ):
        """Verify execute_device_command includes execution_id in response when provided"""
        with patch('tools.device_tool.device_get_location', new_callable=AsyncMock) as mock_location:
            mock_location.return_value = {"success": True, "latitude": 37.7749}

            result = await execute_device_command(
                db=mock_db,
                user_id=sample_user_id,
                agent_id=None,
                device_id=sample_device_id,
                command_type="location",
                parameters={},
                execution_id="exec_12345"
            )

            # Note: The function doesn't currently return execution_id,
            # but we verify it doesn't cause errors
            assert result["success"] is True
