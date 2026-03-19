"""Test coverage for device_tool.py - Target 50%+ coverage.

This test file focuses on covering missing lines from device_tool.py:
- Import error handling (WebSocket unavailable)
- Governance check failure paths
- Device not found scenarios
- WebSocket command failures
- execute_device_command wrapper function
- Error handling in screen record stop
"""

import pytest
from unittest.mock import Mock, patch, MagicMock, AsyncMock
from sqlalchemy.orm import Session

from tools.device_tool import (
    device_camera_snap,
    device_screen_record_start,
    device_screen_record_stop,
    device_get_location,
    device_send_notification,
    device_execute_command,
    DeviceSessionManager,
    get_device_session_manager,
    _check_device_governance,
    get_device_info,
    list_devices,
    execute_device_command
)
from core.models import AgentRegistry, AgentStatus, DeviceSession, DeviceNode, DeviceAudit


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def db_session():
    """Mock database session for testing."""
    return Mock(spec=Session)


@pytest.fixture
def intern_agent(db_session):
    """Create an INTERN level agent (minimum for location)."""
    agent = AgentRegistry(
        id="test-intern-agent",
        tenant_id="test-tenant",
        name="Test Intern Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.INTERN.value,
        confidence_score=0.6
    )
    return agent


@pytest.fixture
def supervised_agent(db_session):
    """Create a SUPERVISED level agent (required for camera/notifications)."""
    agent = AgentRegistry(
        id="test-supervised-agent",
        tenant_id="test-tenant",
        name="Test Supervised Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.SUPERVISED.value,
        confidence_score=0.8
    )
    return agent


@pytest.fixture
def autonomous_agent(db_session):
    """Create an AUTONOMOUS level agent for testing."""
    agent = AgentRegistry(
        id="test-autonomous-agent",
        tenant_id="test-tenant",
        name="Test Autonomous Agent",
        category="Test",
        module_path="test.module",
        class_name="TestClass",
        status=AgentStatus.AUTONOMOUS.value,
        confidence_score=0.95
    )
    return agent


@pytest.fixture
def mock_device_node():
    """Mock device node object."""
    device = Mock(spec=DeviceNode)
    device.id = "test-device-id"
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
    device.last_seen = Mock()
    return device


@pytest.fixture
def mock_device_session():
    """Mock device session object."""
    session = Mock(spec=DeviceSession)
    session.session_id = "test-device-session-123"
    session.device_node_id = "device-123"
    session.user_id = "user-123"
    session.agent_id = "agent-123"
    session.session_type = "screen_record"
    session.status = "active"
    session.configuration = {}
    return session


# ============================================================================
# Test WebSocket Import Error Handling
# ============================================================================

class TestWebSocketImportErrors:
    """Test WebSocket module import error handling."""

    @pytest.mark.asyncio
    async def test_camera_snap_without_websocket_module(self, db_session):
        """Test camera snap fails gracefully when WebSocket module is not available."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            result = await device_camera_snap(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123"
            )

            assert result["success"] is False
            assert "WebSocket module not available" in result["error"]

    @pytest.mark.asyncio
    async def test_get_location_without_websocket_module(self, db_session):
        """Test get location fails gracefully when WebSocket module is not available."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            result = await device_get_location(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123"
            )

            assert result["success"] is False
            assert "WebSocket module not available" in result["error"]

    @pytest.mark.asyncio
    async def test_send_notification_without_websocket_module(self, db_session):
        """Test send notification fails gracefully when WebSocket module is not available."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            result = await device_send_notification(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                title="Test",
                body="Test body"
            )

            assert result["success"] is False
            assert "WebSocket module not available" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_command_without_websocket_module(self, db_session):
        """Test execute command fails gracefully when WebSocket module is not available."""
        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', False):
            result = await device_execute_command(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                command="ls"
            )

            assert result["success"] is False
            assert "WebSocket module not available" in result["error"]


# ============================================================================
# Test Governance Check Failure Paths
# ============================================================================

class TestGovernanceFailures:
    """Test governance check failure paths."""

    @pytest.mark.asyncio
    async def test_governance_check_exception_handling(self, db_session, intern_agent):
        """Test governance check exception is handled gracefully."""
        with patch('tools.device_tool.ServiceFactory.get_governance_service') as mock_factory:
            mock_service = Mock()
            mock_service.can_perform_action.side_effect = Exception("Governance service error")
            mock_factory.return_value = mock_service

            result = await _check_device_governance(
                db=db_session,
                agent_id="agent-123",
                action_type="device_camera_snap",
                user_id="user-123"
            )

            # Should fail open for availability
            assert result["allowed"] is True
            assert "Governance check failed" in result["reason"]
            assert result["governance_check_passed"] is False

    @pytest.mark.asyncio
    async def test_camera_snap_governance_blocked(self, db_session, intern_agent):
        """Test camera snap blocked by governance."""
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "LOW_MATURITY",
                "governance_check_passed": False
            }

            result = await device_camera_snap(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="agent-123"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True
            assert result["error"] == "LOW_MATURITY"

    @pytest.mark.asyncio
    async def test_get_location_governance_blocked(self, db_session, intern_agent):
        """Test get location blocked by governance."""
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "LOW_MATURITY",
                "governance_check_passed": False
            }

            result = await device_get_location(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="agent-123"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_send_notification_governance_blocked(self, db_session, intern_agent):
        """Test send notification blocked by governance."""
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "LOW_MATURITY",
                "governance_check_passed": False
            }

            result = await device_send_notification(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                title="Test",
                body="Test body",
                agent_id="agent-123"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_execute_command_governance_blocked(self, db_session, autonomous_agent):
        """Test execute command blocked by governance."""
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "LOW_MATURITY",
                "governance_check_passed": False
            }

            result = await device_execute_command(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                command="ls",
                agent_id="agent-123"
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True


# ============================================================================
# Test Device Not Found Scenarios
# ============================================================================

class TestDeviceNotFound:
    """Test device not found scenarios."""

    @pytest.mark.asyncio
    async def test_screen_record_start_device_not_found(self, db_session, supervised_agent):
        """Test screen record start fails when device not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query = Mock(return_value=mock_query)

        result = await device_screen_record_start(
            db=db_session,
            user_id="user-123",
            device_node_id="nonexistent-device",
            agent_id="agent-123"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_command_device_not_found(self, db_session, autonomous_agent):
        """Test execute command fails when device not found."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query = Mock(return_value=mock_query)

        result = await device_execute_command(
            db=db_session,
            user_id="user-123",
            device_node_id="nonexistent-device",
            command="ls",
            agent_id="agent-123"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()


# ============================================================================
# Test Screen Record Error Handling
# ============================================================================

class TestScreenRecordErrors:
    """Test screen recording error handling."""

    @pytest.mark.asyncio
    async def test_screen_record_start_duration_exceeds_max(self, db_session, supervised_agent, mock_device_node):
        """Test screen record start fails with excessive duration."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_device_node
        db_session.query = Mock(return_value=mock_query)

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "governance_check_passed": True
            }

            result = await device_screen_record_start(
                db=db_session,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="agent-123",
                duration_seconds=10000  # Exceeds max of 3600
            )

            assert result["success"] is False
            assert "exceeds maximum" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screen_record_stop_session_not_found(self, db_session):
        """Test screen record stop fails when session not found."""
        result = await device_screen_record_stop(
            db=db_session,
            user_id="user-123",
            session_id="nonexistent-session"
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screen_record_stop_wrong_user(self, db_session):
        """Test screen record stop fails when session belongs to different user."""
        session_manager = get_device_session_manager()
        session = session_manager.create_session(
            user_id="other-user",
            device_node_id="device-123",
            session_type="screen_record"
        )

        result = await device_screen_record_stop(
            db=db_session,
            user_id="user-123",
            session_id=session["session_id"]
        )

        assert result["success"] is False
        assert "does not belong to user" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screen_record_start_websocket_failure(self, db_session, supervised_agent, mock_device_node):
        """Test screen record start handles WebSocket command failure."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_device_node
        db_session.query = Mock(return_value=mock_query)

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "governance_check_passed": True
            }

            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": False,
                    "error": "Device rejected command"
                }

                result = await device_screen_record_start(
                    db=db_session,
                    user_id="user-123",
                    device_node_id="device-123",
                    agent_id="agent-123"
                )

                assert result["success"] is False
                assert "rejected" in result["error"].lower() or "failed" in result["error"].lower()


# ============================================================================
# Test execute_device_command Wrapper Function
# ============================================================================

class TestExecuteDeviceCommandWrapper:
    """Test the execute_device_command wrapper function."""

    @pytest.mark.asyncio
    async def test_execute_device_command_camera(self, db_session, intern_agent):
        """Test execute_device_command with camera command type."""
        with patch('tools.device_tool.device_camera_snap', new_callable=AsyncMock) as mock_camera:
            mock_camera.return_value = {
                "success": True,
                "file_path": "/tmp/photo.jpg"
            }

            result = await execute_device_command(
                db=db_session,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="camera",
                parameters={"timeout": 10}
            )

            assert result["success"] is True
            mock_camera.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_device_command_location(self, db_session, intern_agent):
        """Test execute_device_command with location command type."""
        with patch('tools.device_tool.device_get_location', new_callable=AsyncMock) as mock_location:
            mock_location.return_value = {
                "success": True,
                "latitude": 37.7749,
                "longitude": -122.4194
            }

            result = await execute_device_command(
                db=db_session,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="location",
                parameters={"high_accuracy": True}
            )

            assert result["success"] is True
            mock_location.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_device_command_notification(self, db_session, intern_agent):
        """Test execute_device_command with notification command type."""
        with patch('tools.device_tool.device_send_notification', new_callable=AsyncMock) as mock_notify:
            mock_notify.return_value = {
                "success": True,
                "device_node_id": "device-123"
            }

            result = await execute_device_command(
                db=db_session,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="notification",
                parameters={"title": "Test", "body": "Body"}
            )

            assert result["success"] is True
            mock_notify.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_device_command_shell(self, db_session, autonomous_agent):
        """Test execute_device_command with shell command type."""
        with patch('tools.device_tool.device_execute_command', new_callable=AsyncMock) as mock_exec:
            mock_exec.return_value = {
                "success": True,
                "exit_code": 0,
                "stdout": "output"
            }

            result = await execute_device_command(
                db=db_session,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="command",
                parameters={"command": "ls", "working_dir": "/tmp"}
            )

            assert result["success"] is True
            mock_exec.assert_called_once()

    @pytest.mark.asyncio
    async def test_execute_device_command_unknown_type(self, db_session):
        """Test execute_device_command with unknown command type."""
        result = await execute_device_command(
            db=db_session,
            user_id="user-123",
            agent_id=None,
            device_id="device-123",
            command_type="unknown",
            parameters={}
        )

        assert result["success"] is False
        assert "Unknown command type" in result["error"]

    @pytest.mark.asyncio
    async def test_execute_device_command_exception_handling(self, db_session):
        """Test execute_device_command handles exceptions gracefully."""
        with patch('tools.device_tool.device_camera_snap', new_callable=AsyncMock) as mock_camera:
            mock_camera.side_effect = Exception("Unexpected error")

            result = await execute_device_command(
                db=db_session,
                user_id="user-123",
                agent_id="agent-123",
                device_id="device-123",
                command_type="camera",
                parameters={}
            )

            assert result["success"] is False
            assert "Unexpected error" in result["error"]


# ============================================================================
# Test Helper Functions
# ============================================================================

class TestHelperFunctions:
    """Test device helper functions."""

    @pytest.mark.asyncio
    async def test_get_device_info_success(self, db_session, mock_device_node):
        """Test get_device_info returns correct information."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = mock_device_node
        db_session.query = Mock(return_value=mock_query)

        result = await get_device_info(
            db=db_session,
            device_node_id="device-123"
        )

        assert result is not None
        assert result["device_id"] == "device-123"
        assert result["name"] == "Test Device"
        assert result["platform"] == "ios"

    @pytest.mark.asyncio
    async def test_get_device_info_not_found(self, db_session):
        """Test get_device_info returns None for nonexistent device."""
        mock_query = Mock()
        mock_query.filter.return_value.first.return_value = None
        db_session.query = Mock(return_value=mock_query)

        result = await get_device_info(
            db=db_session,
            device_node_id="nonexistent"
        )

        assert result is None

    @pytest.mark.asyncio
    async def test_list_devices_all(self, db_session, mock_device_node):
        """Test list_devices returns all user devices."""
        mock_query = Mock()
        mock_query.filter.return_value.all.return_value = [mock_device_node]
        db_session.query = Mock(return_value=mock_query)

        result = await list_devices(
            db=db_session,
            user_id="user-123"
        )

        assert len(result) == 1
        assert result[0]["device_id"] == "device-123"

    @pytest.mark.asyncio
    async def test_list_devices_with_status_filter(self, db_session, mock_device_node):
        """Test list_devices filters by status."""
        mock_query = Mock()
        mock_filter = Mock()
        mock_filter.filter.return_value = mock_filter
        mock_filter.all.return_value = [mock_device_node]
        mock_query.filter.return_value = mock_filter
        db_session.query = Mock(return_value=mock_query)

        result = await list_devices(
            db=db_session,
            user_id="user-123",
            status="online"
        )

        assert len(result) == 1
        assert result[0]["status"] == "online"


# ============================================================================
# Test Session Management
# ============================================================================

class TestDeviceSessionManagement:
    """Test device session lifecycle."""

    def test_create_device_session(self):
        """Test creating a new device session."""
        session_manager = DeviceSessionManager()

        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera",
            agent_id="agent-123",
            configuration={"timeout": 30}
        )

        assert "session_id" in session
        assert session["user_id"] == "user-123"
        assert session["device_node_id"] == "device-123"
        assert session["session_type"] == "camera"
        assert session["status"] == "active"

    def test_close_device_session(self):
        """Test closing a device session."""
        session_manager = DeviceSessionManager()

        session = session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        result = session_manager.close_session(session["session_id"])

        assert result is True
        assert session["session_id"] not in session_manager.sessions

    def test_close_nonexistent_session(self):
        """Test closing a session that doesn't exist."""
        session_manager = DeviceSessionManager()

        result = session_manager.close_session("nonexistent-session")

        assert result is False

    def test_cleanup_expired_sessions(self):
        """Test automatic cleanup of expired sessions."""
        session_manager = DeviceSessionManager(session_timeout_minutes=0)  # Immediate timeout

        session_manager.create_session(
            user_id="user-123",
            device_node_id="device-123",
            session_type="camera"
        )

        expired_count = session_manager.cleanup_expired_sessions()

        assert expired_count == 1
        assert len(session_manager.sessions) == 0
