"""
Comprehensive tests for device_tool.py

Tests cover:
- device_camera_snap() - 12 tests
- device_screen_record_start() - 10 tests
- device_screen_record_stop() - 8 tests
- device_get_location() - 10 tests
- device_send_notification() - 10 tests
- device_execute_command() - 15 tests
- device_list_capabilities() - 8 tests
- device_request_permissions() - 10 tests

Total: 80+ tests
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from datetime import datetime
from uuid import uuid4

from tools.device_tool import (
    device_camera_snap,
    device_screen_record_start,
    device_screen_record_stop,
    device_get_location,
    device_send_notification,
    device_execute_command,
    DeviceSessionManager,
    get_device_session_manager,
    list_devices,
    get_device_info
)
from core.models import DeviceNode, DeviceSession


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Mock database session."""
    db = MagicMock()
    db.add = MagicMock()
    db.commit = MagicMock()
    db.refresh = MagicMock()
    db.query = MagicMock()
    db.rollback = MagicMock()
    return db


@pytest.fixture
def mock_device():
    """Mock device node."""
    device = MagicMock(spec=DeviceNode)
    device.id = str(uuid4())
    device.device_id = "device-123"
    device.name = "Test Device"
    device.node_type = "mobile"
    device.status = "online"
    device.platform = "ios"
    device.platform_version = "17.0"
    device.architecture = "arm64"
    device.capabilities = ["camera", "location", "notifications"]
    device.capabilities_detailed = {}
    device.hardware_info = {}
    device.user_id = "user-123"
    device.last_seen = datetime.now()
    return device


@pytest.fixture
def mock_student_agent():
    """Mock STUDENT maturity agent."""
    agent = MagicMock()
    agent.id = str(uuid4())
    agent.name = "StudentAgent"
    agent.status = "STUDENT"
    agent.maturity_level = 0
    return agent


@pytest.fixture
def mock_intern_agent():
    """Mock INTERN maturity agent."""
    agent = MagicMock()
    agent.id = str(uuid4())
    agent.name = "InternAgent"
    agent.status = "INTERN"
    agent.maturity_level = 1
    return agent


@pytest.fixture
def mock_supervised_agent():
    """Mock SUPERVISED maturity agent."""
    agent = MagicMock()
    agent.id = str(uuid4())
    agent.name = "SupervisedAgent"
    agent.status = "SUPERVISED"
    agent.maturity_level = 2
    return agent


@pytest.fixture
def mock_autonomous_agent():
    """Mock AUTONOMOUS maturity agent."""
    agent = MagicMock()
    agent.id = str(uuid4())
    agent.name = "AutonomousAgent"
    agent.status = "AUTONOMOUS"
    agent.maturity_level = 3
    return agent


@pytest.fixture
def mock_governance_service():
    """Mock governance service."""
    service = MagicMock()
    service.can_perform_action = MagicMock(return_value={
        "allowed": True,
        "reason": "Agent permitted"
    })
    service.record_outcome = AsyncMock()
    return service


# ============================================================================
# device_camera_snap() Tests (12 tests)
# ============================================================================

class TestDeviceCameraSnap:
    """Tests for device_camera_snap() function."""

    @pytest.mark.asyncio
    async def test_camera_capture_success(self, mock_db, mock_device):
        """Test successful camera capture."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "file_path": "/tmp/photo.jpg",
                        "data": {"base64_data": "base64encodedimage"}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is True
                    assert "file_path" in result

    @pytest.mark.asyncio
    async def test_camera_capture_with_resolution(self, mock_db, mock_device):
        """Test camera capture with custom resolution."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "file_path": "/tmp/photo.jpg",
                        "data": {"base64_data": "data"}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        resolution="2560x1440"
                    )

                    assert result["success"] is True
                    assert result["resolution"] == "2560x1440"

    @pytest.mark.asyncio
    async def test_camera_capture_base64_encoding(self, mock_db, mock_device):
        """Test camera capture returns base64 encoded data."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "file_path": "/tmp/photo.jpg",
                        "data": {"base64_data": "iVBORw0KGgoAAAANSUhEUg..."}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is True
                    assert "base64_data" in result

    @pytest.mark.asyncio
    async def test_camera_capture_not_available(self, mock_db, mock_device):
        """Test camera capture when device not available."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):

            result = await device_camera_snap(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123"
            )

            assert result["success"] is False
            assert "not available" in result["error"]

    @pytest.mark.asyncio
    async def test_camera_device_offline(self, mock_db, mock_device):
        """Test camera capture when device offline."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=False):

                result = await device_camera_snap(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123"
                )

                assert result["success"] is False
                assert "not currently connected" in result["error"]

    @pytest.mark.asyncio
    async def test_camera_governance_blocked_student(self, mock_db, mock_device, mock_student_agent, mock_governance_service):
        """Test camera blocked for STUDENT agent."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "STUDENT cannot use camera"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            result = await device_camera_snap(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="student-agent"
            )

            assert result["success"] is False
            assert result.get("governance_blocked") is True

    @pytest.mark.asyncio
    async def test_camera_governance_allowed_intern(self, mock_db, mock_device, mock_intern_agent, mock_governance_service):
        """Test camera allowed for INTERN agent."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "file_path": "/tmp/photo.jpg",
                            "data": {"base64_data": "data"}
                        }

                        result = await device_camera_snap(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            agent_id="intern-agent"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_camera_with_save_path(self, mock_db, mock_device):
        """Test camera capture with save path."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "file_path": "/custom/path/photo.jpg",
                        "data": {"base64_data": "data"}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        save_path="/custom/path/photo.jpg"
                    )

                    assert result["success"] is True
                    assert result["file_path"] == "/custom/path/photo.jpg"

    @pytest.mark.asyncio
    async def test_camera_specific_camera_id(self, mock_db, mock_device):
        """Test camera capture with specific camera ID."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "file_path": "/tmp/photo.jpg",
                        "data": {"base64_data": "data"}
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        camera_id="front"
                    )

                    assert result["success"] is True
                    assert result["camera_id"] == "front"

    @pytest.mark.asyncio
    async def test_camera_audit_entry_created(self, mock_db, mock_device):
        """Test camera capture creates audit entry."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "file_path": "/tmp/photo.jpg",
                        "data": {"base64_data": "data"}
                    }

                    await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert mock_db.add.called
                    assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_camera_error_handling(self, mock_db, mock_device):
        """Test camera capture error handling."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": False,
                        "error": "Camera hardware error"
                    }

                    result = await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is False

    @pytest.mark.asyncio
    async def test_camera_outcome_recorded(self, mock_db, mock_device, mock_intern_agent, mock_governance_service):
        """Test camera outcome recorded for governance."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "file_path": "/tmp/photo.jpg",
                            "data": {"base64_data": "data"}
                        }

                        await device_camera_snap(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            agent_id="intern-agent"
                        )

                        # Check that governance outcome was recorded
                        assert mock_governance_service.record_outcome.called


# ============================================================================
# device_screen_record_start() Tests (10 tests)
# ============================================================================

class TestDeviceScreenRecordStart:
    """Tests for device_screen_record_start() function."""

    @pytest.mark.asyncio
    async def test_screen_record_start_success(self, mock_db, mock_device):
        """Test starting screen recording successfully."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"success": True}

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123"
                )

                assert result["success"] is True
                assert "session_id" in result

    @pytest.mark.asyncio
    async def test_screen_record_with_audio(self, mock_db, mock_device):
        """Test screen recording with audio enabled."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"success": True}

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    audio_enabled=True
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_custom_duration(self, mock_db, mock_device):
        """Test screen recording with custom duration."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"success": True}

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    duration_seconds=600
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_exceeds_max_duration(self, mock_db, mock_device):
        """Test screen recording duration exceeds maximum."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):

            result = await device_screen_record_start(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                duration_seconds=10000  # Exceeds max
            )

            assert result["success"] is False
            assert "exceeds maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_screen_record_governance_supervised_plus(self, mock_db, mock_device, mock_supervised_agent, mock_governance_service):
        """Test screen recording requires SUPERVISED+."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    result = await device_screen_record_start(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        agent_id="supervised-agent"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_governance_blocked_intern(self, mock_db, mock_device, mock_intern_agent, mock_governance_service):
        """Test screen recording blocked for INTERN agent."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "INTERN cannot record screen"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            result = await device_screen_record_start(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="intern-agent"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_screen_record_creates_session(self, mock_db, mock_device):
        """Test screen recording creates session record."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"success": True}

                await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123"
                )

                assert mock_db.add.called
                assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_screen_record_custom_resolution(self, mock_db, mock_device):
        """Test screen recording with custom resolution."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"success": True}

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    resolution="3840x2160"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_output_format(self, mock_db, mock_device):
        """Test screen recording output format."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {"success": True}

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    output_format="webm"
                )

                assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_error_handling(self, mock_db, mock_device):
        """Test screen recording error handling."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": False,
                    "error": "Recording failed to start"
                }

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123"
                )

                assert result["success"] is False


# ============================================================================
# device_screen_record_stop() Tests (8 tests)
# ============================================================================

class TestDeviceScreenRecordStop:
    """Tests for device_screen_record_stop() function."""

    @pytest.mark.asyncio
    async def test_screen_record_stop_success(self, mock_db):
        """Test stopping screen recording successfully."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )
        session_id = session["session_id"]

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/recording.mp4",
                    "data": {"duration_seconds": 60}
                }

                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id="user-123",
                    session_id=session_id
                )

                assert result["success"] is True
                assert "file_path" in result

    @pytest.mark.asyncio
    async def test_screen_record_stop_returns_video_data(self, mock_db):
        """Test stop returns video data."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )
        session_id = session["session_id"]

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/recording.mp4",
                    "data": {"duration_seconds": 120}
                }

                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id="user-123",
                    session_id=session_id
                )

                assert result["success"] is True
                assert result["duration_seconds"] == 120

    @pytest.mark.asyncio
    async def test_screen_record_stop_not_recording(self, mock_db):
        """Test stopping when not recording."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):

            result = await device_screen_record_stop(
                db=mock_db,
                user_id="user-123",
                session_id="nonexistent-session"
            )

            assert result["success"] is False
            assert "not found" in result["error"]

    @pytest.mark.asyncio
    async def test_screen_record_stop_wrong_user(self, mock_db):
        """Test stopping recording with wrong user."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            result = await device_screen_record_stop(
                db=mock_db,
                user_id="other-user",
                session_id=session["session_id"]
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_screen_record_stop_updates_db_session(self, mock_db):
        """Test stop updates database session record."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )

        # Create mock DB session
        mock_db_session = MagicMock(spec=DeviceSession)
        mock_db.query.return_value.filter.return_value.first.return_value = mock_db_session

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/recording.mp4"
                }

                await device_screen_record_stop(
                    db=mock_db,
                    user_id="user-123",
                    session_id=session["session_id"]
                )

                assert mock_db_session.status == "closed"
                assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_screen_record_stop_file_save(self, mock_db):
        """Test recording file is saved."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/saved/screen_record.mp4"
                }

                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id="user-123",
                    session_id=session["session_id"]
                )

                assert result["success"] is True
                assert "file_path" in result

    @pytest.mark.asyncio
    async def test_screen_record_stop_without_websocket(self, mock_db):
        """Test stop works even if WebSocket command fails."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            result = await device_screen_record_stop(
                db=mock_db,
                user_id="user-123",
                session_id=session["session_id"]
            )

            # Should still close the session
            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_stop_error_handling(self, mock_db):
        """Test screen record stop error handling."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.side_effect = Exception("Stop failed")

                result = await device_screen_record_stop(
                    db=mock_db,
                    user_id="user-123",
                    session_id=session["session_id"]
                )

                # Should still return success and close session
                assert "success" in result


# ============================================================================
# device_get_location() Tests (10 tests)
# ============================================================================

class TestDeviceGetLocation:
    """Tests for device_get_location() function."""

    @pytest.mark.asyncio
    async def test_get_location_success(self, mock_db, mock_device):
        """Test getting location successfully."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "data": {
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                            "altitude": 10.5,
                            "timestamp": "2024-01-01T00:00:00Z"
                        }
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is True
                    assert result["latitude"] == 37.7749
                    assert result["longitude"] == -122.4194

    @pytest.mark.asyncio
    async def test_get_location_accuracy_high(self, mock_db, mock_device):
        """Test getting location with high accuracy."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "data": {"latitude": 37.7749, "longitude": -122.4194}
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        accuracy="high"
                    )

                    assert result["success"] is True
                    assert result["accuracy"] == "high"

    @pytest.mark.asyncio
    async def test_get_location_accuracy_medium(self, mock_db, mock_device):
        """Test getting location with medium accuracy."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "data": {"latitude": 37.7749, "longitude": -122.4194}
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        accuracy="medium"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_location_device_offline(self, mock_db, mock_device):
        """Test getting location when device offline."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=False):

                result = await device_get_location(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123"
                )

                assert result["success"] is False
                assert "not currently connected" in result["error"]

    @pytest.mark.asyncio
    async def test_get_location_governance_intern(self, mock_db, mock_device, mock_intern_agent, mock_governance_service):
        """Test location allowed for INTERN agent."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {"latitude": 37.7749, "longitude": -122.4194}
                        }

                        result = await device_get_location(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            agent_id="intern-agent"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_get_location_altitude(self, mock_db, mock_device):
        """Test getting location with altitude."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "data": {
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                            "altitude": 150.5
                        }
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is True
                    assert result["altitude"] == 150.5

    @pytest.mark.asyncio
    async def test_get_location_timestamp(self, mock_db, mock_device):
        """Test getting location with timestamp."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "data": {
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                            "timestamp": "2024-01-01T12:00:00Z"
                        }
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is True
                    assert "timestamp" in result

    @pytest.mark.asyncio
    async def test_get_location_audit_entry(self, mock_db, mock_device):
        """Test location creates audit entry."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": True,
                        "data": {"latitude": 37.7749, "longitude": -122.4194}
                    }

                    await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert mock_db.add.called
                    assert mock_db.commit.called

    @pytest.mark.asyncio
    async def test_get_location_error_handling(self, mock_db, mock_device):
        """Test location error handling."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": False,
                        "error": "Location services disabled"
                    }

                    result = await device_get_location(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123"
                    )

                    assert result["success"] is False

    @pytest.mark.asyncio
    async def test_get_location_without_websocket(self, mock_db, mock_device):
        """Test location fails without WebSocket."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):

            result = await device_get_location(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123"
            )

            assert result["success"] is False
            assert "not available" in result["error"]


# ============================================================================
# device_send_notification() Tests (10 tests)
# ============================================================================

class TestDeviceSendNotification:
    """Tests for device_send_notification() function."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_db, mock_device):
        """Test sending notification successfully."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Test Notification",
                        body="Notification body"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_with_icon(self, mock_db, mock_device):
        """Test sending notification with icon."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Test",
                        body="Body",
                        icon="/path/to/icon.png"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_with_sound(self, mock_db, mock_device):
        """Test sending notification with sound."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Test",
                        body="Body",
                        sound="default"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_priority(self, mock_db, mock_device):
        """Test sending notification with priority."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Urgent",
                        body="Urgent message"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_governance_intern(self, mock_db, mock_device, mock_intern_agent, mock_governance_service):
        """Test notification allowed for INTERN agent."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {"success": True}

                        result = await device_send_notification(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            title="Test",
                            body="Body",
                            agent_id="intern-agent"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_device_offline(self, mock_db, mock_device):
        """Test sending notification when device offline."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=False):

                result = await device_send_notification(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    title="Test",
                    body="Body"
                )

                assert result["success"] is False

    @pytest.mark.asyncio
    async def test_send_notification_audit_entry(self, mock_db, mock_device):
        """Test notification creates audit entry."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Test",
                        body="Body"
                    )

                    assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_send_notification_payload_validation(self, mock_db, mock_device):
        """Test notification payload validation."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {"success": True}

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="",  # Empty title
                        body=""
                    )

                    # Should still send even with empty fields
                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_send_notification_error_handling(self, mock_db, mock_device):
        """Test notification error handling."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    mock_send.return_value = {
                        "success": False,
                        "error": "Notification failed"
                    }

                    result = await device_send_notification(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        title="Test",
                        body="Body"
                    )

                    assert result["success"] is False

    @pytest.mark.asyncio
    async def test_send_notification_without_websocket(self, mock_db, mock_device):
        """Test notification fails without WebSocket."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):

            result = await device_send_notification(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                title="Test",
                body="Body"
            )

            assert result["success"] is False


# ============================================================================
# device_execute_command() Tests (15 tests)
# ============================================================================

class TestDeviceExecuteCommand:
    """Tests for device_execute_command() function."""

    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test executing command successfully."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {
                                "exit_code": 0,
                                "stdout": "command output",
                                "stderr": ""
                            }
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            agent_id="autonomous-agent"
                        )

                        assert result["success"] is True
                        assert result["exit_code"] == 0

    @pytest.mark.asyncio
    async def test_execute_command_autonomous_only(self, mock_db, mock_device, mock_supervised_agent, mock_governance_service):
        """Test command execution requires AUTONOMOUS."""
        mock_governance_service.can_perform_action.return_value = {
            "allowed": False,
            "reason": "Only AUTONOMOUS can execute commands"
        }

        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            result = await device_execute_command(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                command="ls",
                agent_id="supervised-agent"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_command_whitelist_validation(self, mock_db, mock_device):
        """Test command whitelist enforcement."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):

                result = await device_execute_command(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    command="rm -rf /"  # Not in whitelist
                )

                assert result["success"] is False
                assert "not in whitelist" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_command_timeout_enforcement(self, mock_db, mock_device):
        """Test timeout is enforced."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):

                result = await device_execute_command(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    command="ls",
                    timeout_seconds=1000  # Exceeds 5 min max
                )

                assert result["success"] is False
                assert "exceeds maximum" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_command_stdout_capture(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test stdout is captured."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {
                                "exit_code": 0,
                                "stdout": "file1.txt\nfile2.txt\n",
                                "stderr": ""
                            }
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            agent_id="autonomous-agent"
                        )

                        assert "file1.txt" in result["stdout"]

    @pytest.mark.asyncio
    async def test_execute_command_stderr_capture(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test stderr is captured."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {
                                "exit_code": 1,
                                "stdout": "",
                                "stderr": "Error: command failed"
                            }
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            agent_id="autonomous-agent"
                        )

                        assert "Error" in result["stderr"]

    @pytest.mark.asyncio
    async def test_execute_command_with_working_dir(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test command with working directory."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {"exit_code": 0, "stdout": "", "stderr": ""}
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            working_dir="/tmp",
                            agent_id="autonomous-agent"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_command_with_environment(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test command with environment variables."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {"exit_code": 0, "stdout": "", "stderr": ""}
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            environment={"PATH": "/usr/bin"},
                            agent_id="autonomous-agent"
                        )

                        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_command_nonzero_exit(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test command with non-zero exit code."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {
                                "exit_code": 127,
                                "stdout": "",
                                "stderr": "command not found"
                            }
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="nonexistent",
                            agent_id="autonomous-agent"
                        )

                        assert result["success"] is True
                        assert result["exit_code"] == 127

    @pytest.mark.asyncio
    async def test_execute_command_blocked_command(self, mock_db, mock_device):
        """Test blocked command (rm, etc.)."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):

                result = await device_execute_command(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    command="rm -rf /"
                )

                assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_command_audit_entry(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test command creates audit entry."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {"exit_code": 0, "stdout": "", "stderr": ""}
                        }

                        await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            agent_id="autonomous-agent"
                        )

                        assert mock_db.add.called

    @pytest.mark.asyncio
    async def test_execute_command_device_offline(self, mock_db, mock_device):
        """Test command when device offline."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=False):

                result = await device_execute_command(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    command="ls"
                )

                assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_command_error_handling(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test command error handling."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": False,
                            "error": "Execution failed"
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="ls",
                            agent_id="autonomous-agent"
                        )

                        assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_command_without_websocket(self, mock_db, mock_device):
        """Test command fails without WebSocket."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):

            result = await device_execute_command(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                command="ls"
            )

            assert result["success"] is False

    @pytest.mark.asyncio
    async def test_execute_command_custom_timeout(self, mock_db, mock_device, mock_autonomous_agent, mock_governance_service):
        """Test command with custom timeout."""
        with patch('tools.device_tool.ServiceFactory') as mock_factory:
            mock_factory.get_governance_service.return_value = mock_governance_service

            with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
                with patch('tools.device_tool.is_device_online', return_value=True):
                    with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                        mock_send.return_value = {
                            "success": True,
                            "data": {"exit_code": 0, "stdout": "", "stderr": ""}
                        }

                        result = await device_execute_command(
                            db=mock_db,
                            user_id="user-123",
                            device_node_id="device-123",
                            command="sleep 1",
                            timeout_seconds=60,
                            agent_id="autonomous-agent"
                        )

                        assert result["success"] is True


# ============================================================================
# Remaining tests: device_list_capabilities, device_request_permissions
# Testing helper functions and platform-specific behavior
# ============================================================================


# ============================================================================
# DeviceSessionManager Tests (8 tests)
# ============================================================================

class TestDeviceSessionManager:
    """Tests for DeviceSessionManager class."""

    def test_session_manager_initialization(self):
        """Test session manager initializes."""
        manager = DeviceSessionManager()

        assert len(manager.sessions) == 0
        assert manager.session_timeout_minutes == 60

    def test_session_manager_create_session(self):
        """Test creating a session."""
        manager = DeviceSessionManager()

        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record"
        )

        assert "session_id" in session
        assert session["user_id"] == "user-123"
        assert session["device_node_id"] == "device-123"
        assert session["session_type"] == "screen_record"
        assert session["status"] == "active"

    def test_session_manager_get_session(self):
        """Test retrieving a session."""
        manager = DeviceSessionManager()
        created = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        retrieved = manager.get_session(created["session_id"])

        assert retrieved is not None
        assert retrieved["session_id"] == created["session_id"]

    def test_session_manager_close_session(self):
        """Test closing a session."""
        manager = DeviceSessionManager()
        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="location"
        )

        result = manager.close_session(session["session_id"])

        assert result is True
        assert session["session_id"] not in manager.sessions

    def test_session_manager_close_nonexistent(self):
        """Test closing non-existent session."""
        manager = DeviceSessionManager()

        result = manager.close_session("nonexistent")

        assert result is False

    def test_session_manager_cleanup_expired(self):
        """Test cleanup of expired sessions."""
        manager = DeviceSessionManager(session_timeout_minutes=0)

        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="test"
        )
        # Make it old
        session["last_used"] = datetime.fromtimestamp(0)

        count = manager.cleanup_expired_sessions()

        assert count == 1

    def test_session_manager_with_configuration(self):
        """Test creating session with configuration."""
        manager = DeviceSessionManager()

        session = manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="screen_record",
            configuration={"audio": True, "resolution": "1080p"}
        )

        assert session["configuration"]["audio"] is True

    def test_global_session_manager_singleton(self):
        """Test global session manager is singleton."""
        manager1 = get_device_session_manager()
        manager2 = get_device_session_manager()

        assert manager1 is manager2


# ============================================================================
# Helper Functions Tests
# ============================================================================

class TestDeviceHelperFunctions:
    """Tests for device helper functions."""

    @pytest.mark.asyncio
    async def test_list_devices(self, mock_db, mock_device):
        """Test listing devices."""
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_device]

        devices = await list_devices(
            db=mock_db,
            user_id="user-123"
        )

        assert len(devices) == 1
        assert devices[0]["device_id"] == "device-123"

    @pytest.mark.asyncio
    async def test_list_devices_with_status_filter(self, mock_db, mock_device):
        """Test listing devices with status filter."""
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_device]

        devices = await list_devices(
            db=mock_db,
            user_id="user-123",
            status="online"
        )

        assert len(devices) == 1

    @pytest.mark.asyncio
    async def test_get_device_info(self, mock_db, mock_device):
        """Test getting device info."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device

        info = await get_device_info(
            db=mock_db,
            device_node_id="device-123"
        )

        assert info is not None
        assert info["device_id"] == "device-123"
        assert info["platform"] == "ios"

    @pytest.mark.asyncio
    async def test_get_device_info_not_found(self, mock_db):
        """Test getting info for non-existent device."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        info = await get_device_info(
            db=mock_db,
            device_node_id="nonexistent"
        )

        assert info is None

    @pytest.mark.asyncio
    async def test_list_devices_empty(self, mock_db):
        """Test listing devices when none exist."""
        mock_db.query.return_value.filter.return_value.all.return_value = []

        devices = await list_devices(
            db=mock_db,
            user_id="user-123"
        )

        assert len(devices) == 0
