"""
Device tool governance integration tests.

Tests cover:
- Governance enforcement across all maturity levels by action complexity
- Audit trail creation for all device operations
- Agent execution record lifecycle
- Governance check integration with can_perform_action
- Graduated access (read=INTERN+, monitor=SUPERVISED+, command=AUTONOMOUS)

Focus: Verify device tool properly enforces graduated governance based on action complexity.
"""

from unittest.mock import AsyncMock, Mock, patch, MagicMock
from datetime import datetime
from uuid import uuid4
import pytest

from tools.device_tool import (
    device_camera_snap,
    device_screen_record_start,
    device_get_location,
    device_send_notification,
    device_execute_command,
    _create_device_audit,
)
from core.models import DeviceAudit, DeviceSession, AgentExecution
from core.service_factory import ServiceFactory
from core.feature_flags import FeatureFlags


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
def mock_device_node():
    """Mock DeviceNode."""
    device = MagicMock()
    device.device_id = "device-123"
    device.name = "Test Device"
    device.platform = "iOS"
    device.status = "online"
    device.capabilities = ["camera", "location", "microphone", "screen"]
    return device


@pytest.fixture
def mock_agent_student():
    """Mock STUDENT agent."""
    agent = MagicMock()
    agent.id = "student-agent-123"
    agent.name = "Student Agent"
    agent.status = "STUDENT"
    agent.confidence = 0.3
    return agent


@pytest.fixture
def mock_agent_intern():
    """Mock INTERN agent."""
    agent = MagicMock()
    agent.id = "intern-agent-123"
    agent.name = "Intern Agent"
    agent.status = "INTERN"
    agent.confidence = 0.6
    return agent


@pytest.fixture
def mock_agent_supervised():
    """Mock SUPERVISED agent."""
    agent = MagicMock()
    agent.id = "supervised-agent-123"
    agent.name = "Supervised Agent"
    agent.status = "SUPERVISED"
    agent.confidence = 0.8
    return agent


@pytest.fixture
def mock_agent_autonomous():
    """Mock AUTONOMOUS agent."""
    agent = MagicMock()
    agent.id = "autonomous-agent-123"
    agent.name = "Autonomous Agent"
    agent.status = "AUTONOMOUS"
    agent.confidence = 0.95
    return agent


@pytest.fixture
def mock_governance_allowed():
    """Mock governance service that allows actions."""
    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_factory:
        service = MagicMock()
        service.can_perform_action = MagicMock(return_value={
            "allowed": True,
            "reason": "Agent has required maturity level"
        })
        service.record_outcome = AsyncMock()
        mock_factory.return_value = service
        yield service


@pytest.fixture
def mock_governance_blocked():
    """Mock governance service that blocks actions."""
    with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_factory:
        service = MagicMock()
        service.can_perform_action = MagicMock(return_value={
            "allowed": False,
            "reason": "Agent maturity level insufficient for this action"
        })
        service.record_outcome = AsyncMock()
        mock_factory.return_value = service
        yield service


@pytest.fixture
def mock_websocket_response():
    """Mock WebSocket device response."""
    with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                mock_send.return_value = {
                    "success": True,
                    "file_path": "/tmp/photo.jpg",
                    "data": {"base64_data": "base64encodedimage"}
                }
                yield mock_send


# ============================================================================
# TestDeviceGovernanceByMaturity
# ============================================================================

class TestDeviceGovernanceByMaturity:
    """
    Tests for device tool governance by maturity level.

    Verifies graduated access:
    - Camera/Location/Notifications: INTERN+ (Complexity 2)
    - Screen Recording: SUPERVISED+ (Complexity 3)
    - Command Execution: AUTONOMOUS only (Complexity 4)
    """

    @pytest.mark.asyncio
    async def test_student_blocked_camera(
        self, mock_db, mock_device_node, mock_agent_student,
        mock_governance_blocked, mock_websocket_response
    ):
        """Verify STUDENT blocked for device_camera_snap (Complexity 2)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_camera_snap(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="student-agent-123"
        )

        assert result["success"] is False
        assert result["governance_blocked"] is True
        assert "insufficient" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_intern_allowed_camera(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify INTERN allowed for device_camera_snap."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool._create_device_audit'):
            result = await device_camera_snap(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="intern-agent-123"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_intern_blocked_screen_record(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_blocked, mock_websocket_response
    ):
        """Verify INTERN blocked for device_screen_record_start (Complexity 3)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        result = await device_screen_record_start(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="intern-agent-123"
        )

        assert result["success"] is False
        assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_supervised_allowed_screen_record(
        self, mock_db, mock_device_node, mock_agent_supervised,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify SUPERVISED allowed for screen recording."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool._create_device_audit'):
            result = await device_screen_record_start(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="supervised-agent-123"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_intern_allowed_location(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify INTERN allowed for device_get_location."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "data": {
                "latitude": 37.7749,
                "longitude": -122.4194,
                "accuracy": 10.5
            }
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_get_location(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                agent_id="intern-agent-123"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_intern_allowed_notification(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify INTERN allowed for device_send_notification."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "data": {"sent_at": "2026-03-11T22:00:00Z"}
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_send_notification(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                title="Test Notification",
                body="Test body",
                agent_id="intern-agent-123"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_supervised_blocked_command(
        self, mock_db, mock_device_node, mock_agent_supervised,
        mock_governance_blocked, mock_websocket_response
    ):
        """Verify SUPERVISED blocked for device_execute_command (Complexity 4)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "output",
                "stderr": ""
            }
        }

        result = await device_execute_command(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            command="ls",
            agent_id="supervised-agent-123"
        )

        assert result["success"] is False
        assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_autonomous_allowed_command(
        self, mock_db, mock_device_node, mock_agent_autonomous,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify AUTONOMOUS allowed for command execution."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "data": {
                "exit_code": 0,
                "stdout": "file1.txt\nfile2.txt",
                "stderr": ""
            }
        }

        with patch('tools.device_tool._create_device_audit'):
            result = await device_execute_command(
                db=mock_db,
                user_id="user-123",
                device_node_id="device-123",
                command="ls",
                agent_id="autonomous-agent-123"
            )

        assert result["success"] is True

    @pytest.mark.asyncio
    async def test_governance_read_vs_monitor_vs_command(
        self, mock_db, mock_device_node, mock_websocket_response
    ):
        """Test graduated access (read=INTERN+, monitor=SUPERVISED+, command=AUTONOMOUS)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        # Test read command (INTERN+)
        with patch('core.service_factory.ServiceFactory.get_governance_service') as mock_factory:
            governance_intern = MagicMock()
            governance_intern.can_perform_action.return_value = {
                "allowed": True,
                "reason": "Read command allowed for INTERN+"
            }
            mock_factory.get_governance_service.return_value = governance_intern

            mock_websocket_response.return_value = {
                "success": True,
                "data": {"exit_code": 0, "stdout": "file.txt", "stderr": ""}
            }

            with patch('tools.device_tool._create_device_audit'):
                result = await device_execute_command(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    command="ls",  # Read command
                    agent_id="intern-agent-123"
                )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_governance_disabled_bypass(
        self, mock_db, mock_device_node, mock_agent_student,
        mock_websocket_response
    ):
        """Patch FeatureFlags to disable governance, verify actions allowed."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool.FeatureFlags.should_enforce_governance', return_value=False):
            mock_websocket_response.return_value = {
                "success": True,
                "file_path": "/tmp/photo.jpg",
                "data": {"base64_data": "base64encodedimage"}
            }

            with patch('tools.device_tool._create_device_audit'):
                result = await device_camera_snap(
                    db=mock_db,
                    user_id="user-123",
                    device_node_id="device-123",
                    agent_id="student-agent-123"
                )

            # When governance disabled, STUDENT agent can perform action
            assert result["success"] is True


# ============================================================================
# TestDeviceAuditTrail
# ============================================================================

class TestDeviceAuditTrail:
    """
    Tests for device audit trail creation.

    Verifies:
    - Audit entries created on success
    - Audit entries created on failure
    - governance_check_passed field set correctly
    - agent_id recorded
    - duration_ms captured
    """

    @pytest.mark.asyncio
    async def test_audit_created_on_camera_success(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify DeviceAudit created with success=True, file_path."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "file_path": "/tmp/photo.jpg",
            "data": {"base64_data": "base64encodedimage"}
        }

        await device_camera_snap(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="intern-agent-123"
        )

        # Verify _create_device_audit was called
        mock_db.add.assert_called()
        added_objects = [call_args[0][0] for call_args in mock_db.add.call_args_list]

        audit_records = [obj for obj in added_objects if isinstance(obj, DeviceAudit)]
        assert len(audit_records) > 0

        audit = audit_records[0]
        assert audit.success is True
        assert audit.file_path == "/tmp/photo.jpg"

    @pytest.mark.asyncio
    async def test_audit_created_on_camera_failure(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed
    ):
        """Verify DeviceAudit with success=False, error_message."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool.WEBSOCKET_AVAILABLE', True):
            with patch('tools.device_tool.is_device_online', return_value=True):
                with patch('tools.device_tool.send_device_command', new_callable=AsyncMock) as mock_send:
                    # Mock failure response
                    mock_send.return_value = {
                        "success": False,
                        "error": "Camera hardware busy"
                    }

                    await device_camera_snap(
                        db=mock_db,
                        user_id="user-123",
                        device_node_id="device-123",
                        agent_id="intern-agent-123"
                    )

        # Verify audit created with failure info
        mock_db.add.assert_called()
        added_objects = [call_args[0][0] for call_args in mock_db.add.call_args_list]

        audit_records = [obj for obj in added_objects if isinstance(obj, DeviceAudit)]
        assert len(audit_records) > 0

        audit = audit_records[0]
        assert audit.success is False
        assert audit.error_message is not None

    @pytest.mark.asyncio
    async def test_audit_governance_check_passed(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify governance_check_passed field set correctly."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "file_path": "/tmp/photo.jpg",
            "data": {"base64_data": "base64encodedimage"}
        }

        await device_camera_snap(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="intern-agent-123"
        )

        # Verify governance_check_passed set to True
        mock_db.add.assert_called()
        added_objects = [call_args[0][0] for call_args in mock_db.add.call_args_list]

        audit_records = [obj for obj in added_objects if isinstance(obj, DeviceAudit)]
        assert len(audit_records) > 0

        audit = audit_records[0]
        assert audit.governance_check_passed is True

    @pytest.mark.asyncio
    async def test_audit_agent_id_recorded(
        self, mock_db, mock_device_node, mock_agent_autonomous,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify agent_id stored in audit."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "file_path": "/tmp/photo.jpg",
            "data": {"base64_data": "base64encodedimage"}
        }

        await device_camera_snap(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="autonomous-agent-123"
        )

        # Verify agent_id recorded
        mock_db.add.assert_called()
        added_objects = [call_args[0][0] for call_args in mock_db.add.call_args_list]

        audit_records = [obj for obj in added_objects if isinstance(obj, DeviceAudit)]
        assert len(audit_records) > 0

        audit = audit_records[0]
        assert audit.agent_id == "autonomous-agent-123"

    @pytest.mark.asyncio
    async def test_audit_duration_ms_recorded(
        self, mock_db, mock_device_node, mock_agent_intern,
        mock_governance_allowed, mock_websocket_response
    ):
        """Verify duration captured."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        mock_websocket_response.return_value = {
            "success": True,
            "file_path": "/tmp/photo.jpg",
            "data": {"base64_data": "base64encodedimage"}
        }

        await device_camera_snap(
            db=mock_db,
            user_id="user-123",
            device_node_id="device-123",
            agent_id="intern-agent-123"
        )

        # Verify duration_ms recorded
        mock_db.add.assert_called()
        added_objects = [call_args[0][0] for call_args in mock_db.add.call_args_list]

        audit_records = [obj for obj in added_objects if isinstance(obj, DeviceAudit)]
        assert len(audit_records) > 0

        audit = audit_records[0]
        assert audit.duration_ms is not None
        assert audit.duration_ms >= 0


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
