"""
Device Tool Tests

Unit tests for device capability functions including:
- Camera capture
- Screen recording
- Location services
- Notifications
- Command execution
"""

import pytest
import uuid
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from datetime import datetime
from sqlalchemy.orm import Session

from core.models import DeviceNode, DeviceSession, DeviceAudit, AgentRegistry, User, AgentStatus
from tools.device_tool import (
    device_camera_snap,
    device_screen_record_start,
    device_screen_record_stop,
    device_get_location,
    device_send_notification,
    device_execute_command,
    get_device_session_manager,
    _create_device_audit,
)
from core.agent_governance_service import AgentGovernanceService


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_db():
    """Create a mock database session."""
    db = Mock(spec=Session)
    return db


@pytest.fixture
def mock_user():
    """Create a mock user."""
    user = Mock()
    user.id = str(uuid.uuid4())
    user.email = "test@example.com"
    return user


@pytest.fixture
def mock_agent():
    """Create a mock agent."""
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.name = "Test Agent"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.7
    return agent


@pytest.fixture
def mock_device_node():
    """Create a mock device node."""
    device = Mock(spec=DeviceNode)
    device.id = str(uuid.uuid4())
    device.device_id = "test-device-123"
    device.name = "Test Device"
    device.node_type = "desktop_mac"
    device.status = "online"
    device.platform = "darwin"
    device.capabilities = ["camera", "location", "notification"]
    return device


# ============================================================================
# Session Manager Tests
# ============================================================================

class TestDeviceSessionManager:
    """Tests for DeviceSessionManager."""

    def test_create_session(self):
        """Test creating a new device session."""
        manager = get_device_session_manager()
        user_id = str(uuid.uuid4())
        device_id = "test-device-123"

        session = manager.create_session(
            user_id=user_id,
            device_node_id=device_id,
            session_type="camera",
            agent_id=None
        )

        assert session["session_id"] is not None
        assert session["user_id"] == user_id
        assert session["device_node_id"] == device_id
        assert session["session_type"] == "camera"
        assert session["status"] == "active"

    def test_get_session(self):
        """Test retrieving an existing session."""
        manager = get_device_session_manager()
        user_id = str(uuid.uuid4())
        device_id = "test-device-123"

        created = manager.create_session(
            user_id=user_id,
            device_node_id=device_id,
            session_type="screen_record"
        )

        retrieved = manager.get_session(created["session_id"])

        assert retrieved is not None
        assert retrieved["session_id"] == created["session_id"]

    def test_close_session(self):
        """Test closing a session."""
        manager = get_device_session_manager()
        user_id = str(uuid.uuid4())
        device_id = "test-device-123"

        session = manager.create_session(
            user_id=user_id,
            device_node_id=device_id,
            session_type="camera"
        )

        result = manager.close_session(session["session_id"])

        assert result is True
        assert manager.get_session(session["session_id"]) is None


# ============================================================================
# Camera Tests
# ============================================================================

class TestDeviceCameraSnap:
    """Tests for device camera capture."""

    @pytest.mark.asyncio
    async def test_camera_snap_success(self, mock_db, mock_device_node):
        """Test successful camera capture."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = await device_camera_snap(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            agent_id=None,
            camera_id="default",
            resolution="1920x1080"
        )

        assert result["success"] is True
        assert "file_path" in result
        assert result["resolution"] == "1920x1080"

    @pytest.mark.asyncio
    async def test_camera_snap_device_not_found(self, mock_db):
        """Test camera capture with non-existent device."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await device_camera_snap(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="non-existent-device",
            agent_id=None
        )

        assert result["success"] is False
        assert "not found" in result["error"].lower()


# ============================================================================
# Screen Recording Tests
# ============================================================================

class TestDeviceScreenRecord:
    """Tests for device screen recording."""

    @pytest.mark.asyncio
    async def test_screen_record_start_success(self, mock_db, mock_device_node):
        """Test starting a screen recording."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = await device_screen_record_start(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            agent_id=None,
            duration_seconds=60,
            audio_enabled=False
        )

        assert result["success"] is True
        assert "session_id" in result
        assert result["configuration"]["duration_seconds"] == 60

    @pytest.mark.asyncio
    async def test_screen_record_duration_exceeds_max(self, mock_db, mock_device_node):
        """Test screen record with duration exceeding maximum."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_screen_record_start(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            agent_id=None,
            duration_seconds=10000  # Exceeds max
        )

        assert result["success"] is False
        assert "exceeds maximum" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screen_record_stop_success(self, mock_db):
        """Test stopping a screen recording."""
        user_id = str(uuid.uuid4())

        # Create a session first
        manager = get_device_session_manager()
        session = manager.create_session(
            user_id=user_id,
            device_node_id="test-device-123",
            session_type="screen_record"
        )

        # Mock the database query
        mock_session = Mock()
        mock_session.status = "active"
        mock_db.query.return_value.filter.return_value.first.return_value = mock_session
        mock_db.commit = Mock()

        result = await device_screen_record_stop(
            db=mock_db,
            user_id=user_id,
            session_id=session["session_id"]
        )

        assert result["success"] is True
        assert "file_path" in result


# ============================================================================
# Location Tests
# ============================================================================

class TestDeviceGetLocation:
    """Tests for device location services."""

    @pytest.mark.asyncio
    async def test_get_location_success(self, mock_db, mock_device_node):
        """Test getting device location."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = await device_get_location(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            agent_id=None,
            accuracy="high"
        )

        assert result["success"] is True
        assert "latitude" in result
        assert "longitude" in result
        assert result["accuracy"] == "high"

    @pytest.mark.asyncio
    async def test_get_location_device_not_found(self, mock_db):
        """Test getting location from non-existent device."""
        mock_db.query.return_value.filter.return_value.first.return_value = None

        result = await device_get_location(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="non-existent-device",
            agent_id=None
        )

        assert result["success"] is False


# ============================================================================
# Notification Tests
# ============================================================================

class TestDeviceSendNotification:
    """Tests for device notifications."""

    @pytest.mark.asyncio
    async def test_send_notification_success(self, mock_db, mock_device_node):
        """Test sending a notification."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = await device_send_notification(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            title="Test Notification",
            body="This is a test notification",
            agent_id=None
        )

        assert result["success"] is True
        assert result["title"] == "Test Notification"
        assert result["body"] == "This is a test notification"


# ============================================================================
# Command Execution Tests
# ============================================================================

class TestDeviceExecuteCommand:
    """Tests for device command execution."""

    @pytest.mark.asyncio
    async def test_execute_command_success(self, mock_db, mock_device_node):
        """Test executing a whitelisted command."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        result = await device_execute_command(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            command="ls",
            agent_id=None
        )

        assert result["success"] is True
        assert result["exit_code"] == 0
        assert "stdout" in result

    @pytest.mark.asyncio
    async def test_execute_command_not_whitelisted(self, mock_db, mock_device_node):
        """Test executing a non-whitelisted command."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_execute_command(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            command="rm -rf /",  # Dangerous command
            agent_id=None
        )

        assert result["success"] is False
        assert "not in whitelist" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_execute_command_timeout_exceeds_max(self, mock_db, mock_device_node):
        """Test command with timeout exceeding maximum."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_execute_command(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            command="ls",
            timeout_seconds=400,  # Exceeds 300s max
            agent_id=None
        )

        assert result["success"] is False
        assert "exceeds maximum" in result["error"].lower()


# ============================================================================
# Audit Tests
# ============================================================================

class TestDeviceAudit:
    """Tests for device audit trail."""

    def test_create_audit_entry(self, mock_db):
        """Test creating an audit entry."""
        mock_db.add = Mock()
        mock_db.commit = Mock()

        audit = _create_device_audit(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            action_type="camera_snap",
            action_params={"resolution": "1920x1080"},
            success=True,
            result_summary="Camera capture successful"
        )

        assert audit.id is not None
        assert audit.action_type == "camera_snap"
        assert audit.success is True
        mock_db.add.assert_called_once()
        mock_db.commit.assert_called_once()

    def test_create_audit_entry_with_error(self, mock_db):
        """Test creating an audit entry for failed action."""
        mock_db.add = Mock()
        mock_db.commit = Mock()

        audit = _create_device_audit(
            db=mock_db,
            user_id=str(uuid.uuid4()),
            device_node_id="test-device-123",
            action_type="execute_command",
            action_params={"command": "invalid"},
            success=False,
            error_message="Command not found"
        )

        assert audit.success is False
        assert audit.error_message == "Command not found"


# ============================================================================
# Helper Function Tests
# ============================================================================

class TestDeviceHelpers:
    """Tests for device helper functions."""

    @pytest.mark.asyncio
    async def test_get_device_info(self, mock_db, mock_device_node):
        """Test getting device information."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        from tools.device_tool import get_device_info

        result = await get_device_info(mock_db, "test-device-123")

        assert result is not None
        assert result["device_id"] == "test-device-123"
        assert result["name"] == "Test Device"

    @pytest.mark.asyncio
    async def test_list_devices(self, mock_db, mock_device_node):
        """Test listing devices."""
        mock_db.query.return_value.filter.return_value.all.return_value = [mock_device_node]

        from tools.device_tool import list_devices

        result = await list_devices(mock_db, str(uuid.uuid4()))

        assert len(result) == 1
        assert result[0]["device_id"] == "test-device-123"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
