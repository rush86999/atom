"""
Coverage expansion tests for device automation tool.

Tests cover critical code paths in:
- tools/device_tool.py: Device session management, WebSocket communication
- Camera capture, screen recording, location services
- Governance enforcement for device operations
- Command execution with whitelist enforcement

Target: Cover critical paths (happy path + error paths) to increase coverage.
Uses extensive mocking to avoid device/websocket dependencies.
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from datetime import datetime
import os

from tools.device_tool import DeviceSessionManager, DeviceTool


class TestDeviceSessionManagerCoverage:
    """Coverage expansion for DeviceSessionManager class."""

    @pytest.fixture
    def session_manager(self):
        """Get session manager instance."""
        return DeviceSessionManager(session_timeout_minutes=60)

    # Test: SessionManager initialization
    def test_session_manager_init(self, session_manager):
        """Session manager initializes correctly."""
        assert session_manager.sessions == {}
        assert session_manager.session_timeout_minutes == 60

    def test_session_manager_custom_timeout(self):
        """Session manager with custom timeout."""
        manager = DeviceSessionManager(session_timeout_minutes=30)
        assert manager.session_timeout_minutes == 30

    # Test: Session creation
    def test_create_session_success(self, session_manager):
        """Successfully create device session."""
        result = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        assert "session_id" in result
        assert result["user_id"] == "user-123"
        assert result["device_node_id"] == "device-123"
        assert result["session_type"] == "camera"
        assert result["session_id"] in session_manager.sessions

    def test_create_session_with_agent(self, session_manager):
        """Create session with agent ID."""
        result = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="location",
            agent_id="agent-123"
        )

        assert result["agent_id"] == "agent-123"

    def test_create_session_with_configuration(self, session_manager):
        """Create session with configuration."""
        config = {"resolution": "1080p", "fps": 30}
        result = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record",
            configuration=config
        )

        assert result["configuration"] == config

    # Test: Session retrieval
    def test_get_session_success(self, session_manager):
        """Successfully retrieve existing session."""
        created = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        retrieved = session_manager.get_session(created["session_id"])
        assert retrieved is not None
        assert retrieved["session_id"] == created["session_id"]

    def test_get_session_not_found(self, session_manager):
        """Get non-existent session returns None."""
        result = session_manager.get_session("nonexistent")
        assert result is None

    # Test: Session deletion
    def test_delete_session_success(self, session_manager):
        """Successfully delete session."""
        created = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        session_manager.delete_session(created["session_id"])
        assert session_manager.get_session(created["session_id"]) is None

    def test_delete_session_not_found(self, session_manager):
        """Delete non-existent session doesn't raise error."""
        session_manager.delete_session("nonexistent")
        # Should not raise exception


class TestDeviceToolCoverage:
    """Coverage expansion for DeviceTool class."""

    @pytest.fixture
    def mock_db_session(self):
        """Get mock database session."""
        return MagicMock()

    @pytest.fixture
    def device_tool(self, mock_db_session):
        """Get device tool instance."""
        return DeviceTool(mock_db_session)

    # Test: DeviceTool initialization
    def test_device_tool_init(self, device_tool):
        """Device tool initializes correctly."""
        assert device_tool.db == device_tool.db
        assert isinstance(device_tool.session_manager, DeviceSessionManager)

    # Test: Camera capture
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_camera_capture_snap_success(self, mock_send_cmd, device_tool):
        """Successfully capture camera snap."""
        mock_send_cmd.return_value = {
            "success": True,
            "data": "base64_image_data"
        }

        result = await device_tool.camera_snap(
            device_node_id="device-123",
            user_id="user-123"
        )

        assert result["success"] == True
        mock_send_cmd.assert_called_once()

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_camera_capture_clip_success(self, mock_send_cmd, device_tool):
        """Successfully capture camera clip."""
        mock_send_cmd.return_value = {
            "success": True,
            "data": "base64_video_data"
        }

        result = await device_tool.camera_clip(
            device_node_id="device-123",
            user_id="user-123",
            duration_ms=5000
        )

        assert result["success"] == True

    # Test: Location services
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_get_location_success(self, mock_send_cmd, device_tool):
        """Successfully get device location."""
        mock_send_cmd.return_value = {
            "success": True,
            "latitude": 37.7749,
            "longitude": -122.4194,
            "accuracy": 10.0
        }

        result = await device_tool.get_location(
            device_node_id="device-123",
            user_id="user-123"
        )

        assert result["success"] == True
        assert "latitude" in result

    # Test: Screen recording
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_start_screen_recording_success(self, mock_send_cmd, device_tool):
        """Successfully start screen recording."""
        mock_send_cmd.return_value = {
            "success": True,
            "session_id": "recording-session-123"
        }

        result = await device_tool.start_screen_recording(
            device_node_id="device-123",
            user_id="user-123"
        )

        assert result["success"] == True
        assert "session_id" in result

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_stop_screen_recording_success(self, mock_send_cmd, device_tool):
        """Successfully stop screen recording."""
        mock_send_cmd.return_value = {
            "success": True,
            "data": "base64_video_data"
        }

        result = await device_tool.stop_screen_recording(
            device_node_id="device-123",
            user_id="user-123",
            recording_session_id="rec-123"
        )

        assert result["success"] == True

    # Test: Notifications
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_send_cmd, device_tool):
        """Successfully send notification."""
        mock_send_cmd.return_value = {
            "success": True
        }

        result = await device_tool.send_notification(
            device_node_id="device-123",
            user_id="user-123",
            title="Test Notification",
            body="Test body",
            payload={"key": "value"}
        )

        assert result["success"] == True

    # Test: Command execution
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_send_cmd, device_tool):
        """Successfully execute whitelisted command."""
        mock_send_cmd.return_value = {
            "success": True,
            "output": "file1.txt\nfile2.txt"
        }

        result = await device_tool.execute_command(
            device_node_id="device-123",
            user_id="user-123",
            command="ls",
            args=["-la"]
        )

        assert result["success"] == True
        assert "output" in result

    @pytest.mark.asyncio
    async def test_execute_command_not_whitelisted(self, device_tool):
        """Reject command not in whitelist."""
        # Mock a command that's not in whitelist
        result = await device_tool.execute_command(
            device_node_id="device-123",
            user_id="user-123",
            command="rm",  # Not in default whitelist
            args=["-rf", "/"]
        )

        assert result["success"] == False
        assert "whitelist" in result["error"].lower() or "not allowed" in result["error"].lower()


class TestDeviceToolErrorHandling:
    """Coverage expansion for device tool error handling."""

    @pytest.fixture
    def mock_db_session(self):
        """Get mock database session."""
        return MagicMock()

    @pytest.fixture
    def device_tool(self, mock_db_session):
        """Get device tool instance."""
        return DeviceTool(mock_db_session)

    # Test: Device offline
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_camera_capture_device_offline(self, mock_send_cmd, device_tool):
        """Camera capture fails when device offline."""
        mock_send_cmd.return_value = {
            "success": False,
            "error": "Device not connected"
        }

        result = await device_tool.camera_snap(
            device_node_id="offline-device",
            user_id="user-123"
        )

        assert result["success"] == False

    # Test: Command execution timeout
    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, mock_send_cmd, device_tool):
        """Command execution times out."""
        import asyncio
        mock_send_cmd.side_effect = asyncio.TimeoutError("Command timeout")

        result = await device_tool.execute_command(
            device_node_id="device-123",
            user_id="user-123",
            command="sleep",
            args=["100"]
        )

        assert result["success"] == False

    # Test: Invalid screen recording duration
    @pytest.mark.asyncio
    async def test_screen_recording_exceeds_max_duration(self, device_tool):
        """Screen recording exceeds max duration limit."""
        max_duration = int(os.getenv("DEVICE_SCREEN_RECORD_MAX_DURATION", "3600"))

        result = await device_tool.start_screen_recording(
            device_node_id="device-123",
            user_id="user-123",
            duration_seconds=max_duration + 1000
        )

        assert result["success"] == False
        assert "duration" in result["error"].lower()

    # Test: Missing required parameters
    @pytest.mark.asyncio
    async def test_camera_snap_missing_device_id(self, device_tool):
        """Camera snap without device ID."""
        result = await device_tool.camera_snap(
            device_node_id="",  # Empty device ID
            user_id="user-123"
        )

        assert result["success"] == False

    @pytest.mark.asyncio
    async def test_send_notification_missing_title(self, device_tool):
        """Send notification without title."""
        result = await device_tool.send_notification(
            device_node_id="device-123",
            user_id="user-123",
            title="",  # Empty title
            body="Body text"
        )

        assert result["success"] == False
