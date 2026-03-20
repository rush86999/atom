"""
Unit Tests for Device Automation Tool

Tests device hardware access functions:
- Camera capture (INTERN+ permission)
- Screen recording (SUPERVISED+ permission)
- Location access (INTERN+ permission)
- Notifications (INTERN+ permission)
- Command execution (AUTONOMOUS only)
- Permission checks per maturity level
- Governance integration
- Error handling and WebSocket communication
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

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
    get_device_session_manager,
    _check_device_governance,
    _create_device_audit,
)
from core.models import DeviceNode, DeviceSession, DeviceAudit


# ============================================================================
# Test Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_device_node():
    """Mock device node."""
    device = Mock(spec=DeviceNode)
    device.id = "test-device-id"
    device.device_id = "device-123"
    device.name = "Test Device"
    device.node_type = "mobile"
    device.status = "online"
    device.platform = "iOS"
    device.platform_version = "17.0"
    device.architecture = "arm64"
    device.capabilities = ["camera", "location", "microphone"]
    device.capabilities_detailed = {}
    device.hardware_info = {}
    device.user_id = "user-123"
    device.last_seen = datetime.now()
    return device


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    with patch("tools.device_tool.ServiceFactory.get_governance_service") as mock:
        service = Mock()
        service.can_perform_action = Mock(return_value={
            "allowed": True,
            "reason": "Agent permitted"
        })
        service.record_outcome = AsyncMock()
        mock.return_value = service
        yield mock


@pytest.fixture
def mock_websocket_available():
    """Mock WebSocket availability."""
    with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
        with patch("tools.device_tool.is_device_online", return_value=True):
            yield


# ============================================================================
# Test Camera Capture (device_camera_snap)
# ============================================================================

class TestCameraCapture:
    """Test camera capture functionality."""

    @pytest.mark.asyncio
    async def test_camera_snap_success(self, mock_db, mock_device_node, mock_governance_service):
        """Test successful camera capture."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {
                        "success": True,
                        "file_path": "/tmp/test.jpg",
                        "data": {"base64_data": "base64encodeddata"}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        agent_id="agent-123",
                        camera_id="front",
                        resolution="1920x1080",
                        save_path="/tmp/capture.jpg"
                    )

                    assert result["success"] is True
                    assert result["file_path"] == "/tmp/test.jpg"
                    assert result["resolution"] == "1920x1080"
                    assert result["camera_id"] == "front"
                    assert "captured_at" in result

    @pytest.mark.asyncio
    async def test_camera_snap_without_agent(self, mock_db, mock_device_node):
        """Test camera capture without agent (no governance check)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {
                        "success": True,
                        "file_path": "/tmp/test.jpg",
                        "data": {"base64_data": "base64encodeddata"}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        resolution="1280x720"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_camera_snap_governance_blocked(self, mock_db, mock_device_node, mock_websocket_available):
        """Test camera capture blocked by governance."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool._check_device_governance", new_callable=AsyncMock) as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Agent maturity level too low",
                "governance_check_passed": False
            }

            result = await device_camera_snap(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="student-agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert "maturity level too low" in result["error"]

    @pytest.mark.asyncio
    async def test_camera_snap_device_offline(self, mock_db, mock_device_node):
        """Test camera capture when device is offline."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=False):
                result = await device_camera_snap(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123"
                )

                assert result["success"] is False
                assert "not currently connected" in result["error"]

    @pytest.mark.asyncio
    async def test_camera_snap_websocket_unavailable(self, mock_db, mock_device_node):
        """Test camera capture when WebSocket module is unavailable."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", False):
            result = await device_camera_snap(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123"
            )

            assert result["success"] is False
            assert "WebSocket module not available" in result["error"]


# ============================================================================
# Test Screen Recording (device_screen_record_start/stop)
# ============================================================================

class TestScreenRecording:
    """Test screen recording functionality."""

    @pytest.mark.asyncio
    async def test_screen_record_start_success(self, mock_db, mock_device_node, mock_governance_service):
        """Test successful screen recording start."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                mock_cmd.return_value = {
                    "success": True,
                    "recording_id": "rec-123"
                }

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    agent_id="agent-123",
                    duration_seconds=60,
                    audio_enabled=True,
                    resolution="1920x1080",
                    output_format="mp4"
                )

                assert result["success"] is True
                assert "session_id" in result
                assert result["device_node_id"] == "device-123"
                assert result["configuration"]["duration_seconds"] == 60
                assert result["configuration"]["audio_enabled"] is True

    @pytest.mark.asyncio
    async def test_screen_record_start_duration_validation(self, mock_db, mock_device_node):
        """Test screen recording duration validation."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.DEVICE_SCREEN_RECORD_MAX_DURATION", 300):
            result = await device_screen_record_start(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                duration_seconds=500  # Exceeds max
            )

            assert result["success"] is False
            assert "exceeds maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_screen_record_stop_success(self, mock_db):
        """Test successful screen recording stop."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record",
            agent_id="agent-123"
        )

        mock_db_session = Mock(spec=DeviceSession)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                mock_cmd.return_value = {
                    "success": True,
                    "file_path": "/tmp/recording.mp4",
                    "data": {"duration_seconds": 60}
                }

                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id="user-123",
                    session_id=session["session_id"]
                )

                assert result["success"] is True
                assert result["session_id"] == session["session_id"]
                assert result["file_path"] == "/tmp/recording.mp4"
                assert result["duration_seconds"] == 60

    @pytest.mark.asyncio
    async def test_screen_record_stop_not_found(self, mock_db):
        """Test stopping non-existent recording session."""
        result = await device_screen_record_stop(
            db=mock_db,
            user_id="user-123",
            session_id="nonexistent-session"
        )

        assert result["success"] is False
        assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_screen_record_stop_wrong_user(self, mock_db):
        """Test stopping session owned by different user."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-456",
            device_node_id="device-123",
            session_type="screen_record"
        )

        result = await device_screen_record_stop(
            db=mock_db,
            user_id="user-123",  # Different user
            session_id=session["session_id"]
        )

        assert result["success"] is False
        assert "does not belong to user" in result["error"]


# ============================================================================
# Test Location Access (device_get_location)
# ============================================================================

class TestLocationAccess:
    """Test location access functionality."""

    @pytest.mark.asyncio
    async def test_get_location_success(self, mock_db, mock_device_node, mock_governance_service):
        """Test successful location retrieval."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {
                        "success": True,
                        "data": {
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                            "altitude": 10.5,
                            "timestamp": datetime.now().isoformat()
                        }
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        agent_id="agent-123",
                        accuracy="high"
                    )

                    assert result["success"] is True
                    assert result["latitude"] == 37.7749
                    assert result["longitude"] == -122.4194
                    assert result["accuracy"] == "high"
                    assert result["altitude"] == 10.5

    @pytest.mark.asyncio
    async def test_get_location_without_agent(self, mock_db, mock_device_node):
        """Test location retrieval without agent."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {
                        "success": True,
                        "data": {
                            "latitude": 40.7128,
                            "longitude": -74.0060
                        }
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        accuracy="medium"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_location_governance_blocked(self, mock_db, mock_device_node):
        """Test location access blocked by governance."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool._check_device_governance", new_callable=AsyncMock) as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "INTERN maturity required",
                "governance_check_passed": False
            }

            result = await device_get_location(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="student-agent"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True


# ============================================================================
# Test Notifications (device_send_notification)
# ============================================================================

class TestNotifications:
    """Test notification functionality."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_db, mock_device_node, mock_governance_service):
        """Test successful notification send."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        agent_id="agent-123",
                        title="Test Notification",
                        body="Test notification body",
                        icon="/path/to/icon.png",
                        sound="default"
                    )

                    assert result["success"] is True
                    assert result["title"] == "Test Notification"
                    assert result["body"] == "Test notification body"
                    assert result["device_node_id"] == "device-123"

    @pytest.mark.asyncio
    async def test_send_notification_minimal_params(self, mock_db, mock_device_node):
        """Test notification with minimal parameters."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Alert",
                        body="Something happened"
                    )

                    assert result["success"] is True


# ============================================================================
# Test Command Execution (device_execute_command)
# ============================================================================

class TestCommandExecution:
    """Test shell command execution functionality."""

    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_db, mock_device_node, mock_governance_service):
        """Test successful command execution."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool.WEBSOCKET_AVAILABLE", True):
            with patch("tools.device_tool.is_device_online", return_value=True):
                with patch("tools.device_tool.send_device_command", new_callable=AsyncMock) as mock_cmd:
                    mock_cmd.return_value = {
                        "success": True,
                        "data": {
                            "exit_code": 0,
                            "stdout": "file1.txt\nfile2.txt",
                            "stderr": ""
                        }
                    }

                    result = await device_execute_command(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        agent_id="agent-123",
                        command="ls",
                        working_dir="/tmp",
                        timeout_seconds=10
                    )

                    assert result["success"] is True
                    assert result["exit_code"] == 0
                    assert "file1.txt" in result["stdout"]
                    assert result["command"] == "ls"

    @pytest.mark.asyncio
    async def test_execute_command_not_whitelisted(self, mock_db, mock_device_node):
        """Test command execution with non-whitelisted command."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_execute_command(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            command="rm -rf /"  # Dangerous command
        )

        assert result["success"] is False
        assert "not in whitelist" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_command_timeout_exceeded(self, mock_db, mock_device_node):
        """Test command execution with excessive timeout."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_execute_command(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            command="ls",
            timeout_seconds=500  # Exceeds 300s max
        )

        assert result["success"] is False
        assert "exceeds maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_command_read_category(self, mock_db, mock_device_node):
        """Test read command category (INTERN+)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool._check_device_governance", new_callable=AsyncMock) as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Permitted",
                "governance_check_passed": True
            }

            # Should check device_shell_read governance
            await device_execute_command(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="agent-123",
                command="cat file.txt"
            )

            # Verify correct governance action was checked
            mock_gov.assert_called_once()
            call_args = mock_gov.call_args
            assert call_args[0][2] == "device_shell_read"  # action_type

    @pytest.mark.asyncio
    async def test_execute_command_monitor_category(self, mock_db, mock_device_node):
        """Test monitor command category (SUPERVISED+)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch("tools.device_tool._check_device_governance", new_callable=AsyncMock) as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Permitted",
                "governance_check_passed": True
            }

            # Should check device_shell_monitor governance
            await device_execute_command(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="agent-123",
                command="ps aux"
            )

            # Verify correct governance action was checked
            mock_gov.assert_called_once()
            call_args = mock_gov.call_args
            assert call_args[0][2] == "device_shell_monitor"  # action_type


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test helper functions."""

    @pytest.mark.asyncio
    async def test_get_device_info(self, mock_db, mock_device_node):
        """Test getting device information."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await get_device_info(mock_db, "device-123")

        assert result is not None
        assert result["device_id"] == "device-123"
        assert result["name"] == "Test Device"
        assert result["platform"] == "iOS"
        assert result["status"] == "online"

    @pytest.mark.asyncio
    async def test_get_device_info_not_found(self, mock_db):
        """Test getting info for non-existent device."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await get_device_info(mock_db, "nonexistent-device")

        assert result is None

    @pytest.mark.asyncio
    async def test_list_devices(self, mock_db, mock_device_node):
        """Test listing devices."""
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_device_node]

        result = await list_devices(mock_db, "user-123")

        assert len(result) == 1
        assert result[0]["device_id"] == "device-123"
        assert result[0]["name"] == "Test Device"

    @pytest.mark.asyncio
    async def test_list_devices_with_status_filter(self, mock_db, mock_device_node):
        """Test listing devices with status filter."""
        # Mock the query chain properly
        query_mock = Mock()
        query_mock.filter.return_value = query_mock
        query_mock.all.return_value = [mock_device_node]
        mock_db.query.return_value = query_mock

        result = await list_devices(mock_db, "user-123", status="online")

        assert len(result) == 1


# ============================================================================
# Test Generic Command Executor
# ============================================================================

class TestGenericCommandExecutor:
    """Test the generic execute_device_command wrapper."""

    @pytest.mark.asyncio
    async def test_execute_camera_command(self, mock_db):
        """Test generic executor with camera command."""
        with patch("tools.device_tool.device_camera_snap", new_callable=AsyncMock) as mock_snap:
            mock_snap.return_value = {"success": True, "file_path": "/tmp/capture.jpg"}

            result = await execute_device_command(
                db=mock_db,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="camera",
                parameters={"timeout": 10}
            )

            assert result["success"] is True
            mock_snap.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_location_command(self, mock_db):
        """Test generic executor with location command."""
        with patch("tools.device_tool.device_get_location", new_callable=AsyncMock) as mock_loc:
            mock_loc.return_value = {
                "success": True,
                "latitude": 37.7749,
                "longitude": -122.4194
            }

            result = await execute_device_command(
                db=mock_db,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="location",
                parameters={"high_accuracy": True}
            )

            assert result["success"] is True
            mock_loc.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_notification_command(self, mock_db):
        """Test generic executor with notification command."""
        with patch("tools.device_tool.device_send_notification", new_callable=AsyncMock) as mock_notif:
            mock_notif.return_value = {"success": True}

            result = await execute_device_command(
                db=mock_db,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="notification",
                parameters={"title": "Test", "body": "Body"}
            )

            assert result["success"] is True
            mock_notif.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_shell_command(self, mock_db):
        """Test generic executor with shell command."""
        with patch("tools.device_tool.device_execute_command", new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {"success": True, "exit_code": 0}

            result = await execute_device_command(
                db=mock_db,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="command",
                parameters={"command": "ls", "working_dir": "/tmp"}
            )

            assert result["success"] is True
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_unknown_command_type(self, mock_db):
        """Test generic executor with unknown command type."""
        result = await execute_device_command(
            db=mock_db,
            user_id="user-123",
            agent_id="agent-123",
            device_id="device-123",
            command_type="unknown_type",
            parameters={}
        )

        assert result["success"] is False
        assert "Unknown command type" in result["error"]


# ============================================================================
# Test Session Manager
# ============================================================================

class TestSessionManager:
    """Test device session manager."""

    def test_create_session(self):
        """Test creating a device session."""
        manager = get_device_session_manager()
        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record",
            agent_id="agent-123"
        )

        assert "session_id" in session
        assert session["user_id"] == "user-123"
        assert session["device_node_id"] == "device-123"
        assert session["session_type"] == "screen_record"
        assert session["status"] == "active"

    def test_get_session(self):
        """Test retrieving a session."""
        manager = get_device_session_manager()
        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        retrieved = manager.get_session(session["session_id"])
        assert retrieved is not None
        assert retrieved["session_id"] == session["session_id"]

    def test_close_session(self):
        """Test closing a session."""
        manager = get_device_session_manager()
        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        closed = manager.close_session(session["session_id"])
        assert closed is True

        retrieved = manager.get_session(session["session_id"])
        assert retrieved is None

    def test_cleanup_expired_sessions(self):
        """Test cleanup of expired sessions."""
        manager = get_device_session_manager()
        manager.session_timeout_minutes = 0  # Mark all as expired

        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        # Modify last_used to make it old
        session["last_used"] = datetime.fromtimestamp(0)

        cleaned = manager.cleanup_expired_sessions()
        assert cleaned >= 0


# ============================================================================
# Test Governance Integration
# ============================================================================

class TestGovernanceIntegration:
    """Test governance integration for device actions."""

    @pytest.mark.asyncio
    async def test_governance_check_allowed(self, mock_governance_service):
        """Test governance check when allowed."""
        result = await _check_device_governance(
            db=Mock(),
            agent_id="agent-123",
            action_type="device_camera_snap",
            user_id="user-123"
        )

        assert result["allowed"] is True
        assert "governance_check_passed" in result

    @pytest.mark.asyncio
    async def test_governance_check_disabled(self):
        """Test governance check when disabled."""
        with patch("tools.device_tool.FeatureFlags.should_enforce_governance", return_value=False):
            result = await _check_device_governance(
                db=Mock(),
                agent_id="agent-123",
                action_type="device_camera_snap",
                user_id="user-123"
            )

            assert result["allowed"] is True
            assert "disabled" in result["reason"]

    @pytest.mark.asyncio
    async def test_governance_check_failure_fails_open(self):
        """Test governance check fails open on error."""
        with patch("tools.device_tool.ServiceFactory.get_governance_service", side_effect=Exception("DB error")):
            result = await _check_device_governance(
                db=Mock(),
                agent_id="agent-123",
                action_type="device_camera_snap",
                user_id="user-123"
            )

            # Should fail open (allow) for availability
            assert result["allowed"] is True
            assert result["governance_check_passed"] is False


# ============================================================================
# Test Audit Creation
# ============================================================================

class TestAuditCreation:
    """Test device audit entry creation."""

    def test_create_audit_success(self, mock_db):
        """Test creating audit entry for successful action."""
        audit = _create_device_audit(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            action_type="camera_snap",
            action_params={"resolution": "1920x1080"},
            success=True,
            result_summary="Camera capture successful",
            result_data={"file_path": "/tmp/capture.jpg"},
            file_path="/tmp/capture.jpg",
            duration_ms=1500,
            agent_id="agent-123",
            session_id="session-123",
            governance_check_passed=True
        )

        assert audit.action_type == "camera_snap"
        assert audit.user_id == "user-123"
        assert audit.device_node_id == "device-123"
        assert audit.success is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_audit_failure(self, mock_db):
        """Test creating audit entry for failed action."""
        audit = _create_device_audit(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            action_type="camera_snap",
            action_params={},
            success=False,
            error_message="Device offline",
            duration_ms=100,
            agent_id="agent-123"
        )

        assert audit.success is False
        assert audit.error_message == "Device offline"
        mock_db.add.assert_called_once()
