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
from types import SimpleNamespace

from tools.device_tool import DeviceSessionManager


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

        session_manager.close_session(created["session_id"])
        assert session_manager.get_session(created["session_id"]) is None

    def test_close_session_not_found(self, session_manager):
        """Close non-existent session doesn't raise error."""
        session_manager.close_session("nonexistent")
        # Should not raise exception


class TestDeviceFunctionsCoverage:
    """Coverage for the module-level device_* service functions.

    Ported from the removed DeviceTool class to the current function API:
    device_camera_snap / device_screen_record_start / device_screen_record_stop /
    device_get_location / device_send_notification / device_execute_command.
    """

    @pytest.fixture
    def mock_db_session(self):
        return MagicMock()

    @pytest.fixture
    def device_fns(self, mock_db_session):
        """Bind the module functions to a mock db session, governance open."""
        import tools.device_tool as dt
        with patch.object(dt, 'WEBSOCKET_AVAILABLE', True), \
             patch.object(dt, 'is_device_online', return_value=True), \
             patch.object(dt, '_check_device_governance',
                          new=AsyncMock(return_value={"allowed": True})):
            yield SimpleNamespace(
                camera_snap=lambda **kw: dt.device_camera_snap(
                    mock_db_session, kw["user_id"], kw["device_node_id"]),
                start_screen_recording=lambda **kw: dt.device_screen_record_start(
                    mock_db_session, kw["user_id"], kw["device_node_id"],
                    duration_seconds=kw.get("duration_seconds")),
                stop_screen_recording=lambda **kw: dt.device_screen_record_stop(
                    mock_db_session, kw["user_id"], kw.get("recording_session_id", "rec-123")),
                get_location=lambda **kw: dt.device_get_location(
                    mock_db_session, kw["user_id"], kw["device_node_id"]),
                send_notification=lambda **kw: dt.device_send_notification(
                    mock_db_session, kw["user_id"], kw["device_node_id"],
                    kw.get("title", ""), kw.get("body", "")),
                execute_command=lambda **kw: dt.device_execute_command(
                    mock_db_session, kw["user_id"], kw["device_node_id"],
                    kw.get("command", "")),
            )

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_camera_capture_snap_success(self, mock_send_cmd, device_fns):
        mock_send_cmd.return_value = {"success": True, "file_path": "/tmp/snap.jpg", "data": {"base64_data": "abc"}}
        result = await device_fns.camera_snap(device_node_id="device-123", user_id="user-123")
        assert result["success"] is True
        mock_send_cmd.assert_called_once()

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_get_location_success(self, mock_send_cmd, device_fns):
        mock_send_cmd.return_value = {
            "success": True, "latitude": 37.7749, "longitude": -122.4194, "accuracy": 10.0
        }
        result = await device_fns.get_location(device_node_id="device-123", user_id="user-123")
        assert result["success"] is True
        assert "latitude" in result

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_start_screen_recording_success(self, mock_send_cmd, device_fns):
        mock_send_cmd.return_value = {"success": True, "session_id": "recording-session-123"}
        result = await device_fns.start_screen_recording(device_node_id="device-123", user_id="user-123")
        assert result["success"] is True
        assert "session_id" in result

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_stop_screen_recording_success(self, mock_send_cmd, device_fns):
        mock_send_cmd.return_value = {"success": True, "file_path": "/tmp/rec.mp4", "data": {"base64_data": "vid"}}
        from tools.device_tool import get_device_session_manager
        sess = get_device_session_manager().create_session(
            user_id="user-123", device_node_id="device-123", session_type="screen_record")
        result = await device_fns.stop_screen_recording(
            device_node_id="device-123", user_id="user-123",
            recording_session_id=sess["session_id"])
        assert result["success"] is True

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_send_cmd, device_fns):
        mock_send_cmd.return_value = {"success": True}
        result = await device_fns.send_notification(
            device_node_id="device-123", user_id="user-123",
            title="Test Notification", body="Test body")
        assert result["success"] is True


class TestDeviceFunctionsErrorHandling:
    """Error-path coverage for the module-level device_* functions."""

    @pytest.fixture
    def mock_db_session(self):
        return MagicMock()

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_camera_capture_device_offline(self, mock_send_cmd, mock_db_session):
        """Camera capture fails when the device is not connected."""
        mock_send_cmd.return_value = {"success": False, "error": "Device not connected"}
        import tools.device_tool as dt
        with patch.object(dt, 'WEBSOCKET_AVAILABLE', True), \
             patch.object(dt, 'is_device_online', return_value=True):
            result = await dt.device_camera_snap(mock_db_session, "user-123", "offline-device")
        assert result["success"] is False

    @patch('tools.device_tool.send_device_command')
    @pytest.mark.asyncio
    async def test_camera_capture_device_not_online(self, mock_send_cmd, mock_db_session):
        """Camera capture returns failure when is_device_online is False."""
        import tools.device_tool as dt
        with patch.object(dt, 'WEBSOCKET_AVAILABLE', True), \
             patch.object(dt, 'is_device_online', return_value=False):
            result = await dt.device_camera_snap(mock_db_session, "user-123", "device-123")
        assert result["success"] is False
        assert "not currently connected" in result.get("error", "")

    @pytest.mark.asyncio
    async def test_screen_recording_exceeds_max_duration(self, mock_db_session):
        """Screen recording exceeds max duration limit."""
        import tools.device_tool as dt
        max_duration = int(os.getenv("DEVICE_SCREEN_RECORD_MAX_DURATION", "3600"))
        result = await dt.device_screen_record_start(
            mock_db_session, "user-123", "device-123", duration_seconds=max_duration + 1000)
        assert result["success"] is False
        assert "duration" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_execute_command_not_whitelisted(self, mock_db_session):
        """Reject command not in whitelist."""
        import tools.device_tool as dt
        result = await dt.device_execute_command(
            mock_db_session, "user-123", "device-123", command="rm -rf /")
        assert result["success"] is False
        assert "whitelist" in result.get("error", "").lower()

    @pytest.mark.asyncio
    async def test_execute_command_timeout(self, mock_db_session):
        """Command execution failure is returned as a failed result."""
        import tools.device_tool as dt
        with patch.object(dt, 'WEBSOCKET_AVAILABLE', True), \
             patch.object(dt, 'is_device_online', return_value=True), \
             patch.object(dt, 'send_device_command',
                          new=AsyncMock(side_effect=TimeoutError("Command timeout"))):
            result = await dt.device_execute_command(
                mock_db_session, "user-123", "device-123", command="ls")
        assert result["success"] is False
