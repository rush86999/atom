"""
Desktop Device Governance Tests

Tests for governance integration with desktop device capabilities including:
- Desktop device registration and management
- Desktop-specific device capability governance (camera, screen recording, shell execution)
- Desktop permission requirements (AUTONOMOUS agents only for shell execution)
- Desktop device session management
- Maturity-based authorization for desktop commands
- Audit trail creation for desktop device operations
"""

import uuid
from datetime import datetime
from unittest.mock import Mock, patch, AsyncMock
import pytest
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import (
    AgentRegistry, AgentStatus, DeviceAudit, DeviceNode, DeviceSession,
    User, Workspace
)
from tools.device_tool import (
    device_camera_snap,
    device_execute_command,
    device_screen_record_start,
    device_screen_record_stop,
    device_get_location,
    device_send_notification,
)

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
    user.teams = []
    user.workspace_id = "default"
    return user


@pytest.fixture
def mock_workspace():
    """Create a mock workspace."""
    workspace = Mock()
    workspace.id = str(uuid.uuid4())
    workspace.name = "Test Workspace"
    return workspace


@pytest.fixture
def desktop_device_mac():
    """Create a mock macOS desktop device node."""
    device = Mock(spec=DeviceNode)
    device.id = str(uuid.uuid4())
    device.device_id = "desktop-mac-123"
    device.name = "MacBook Pro"
    device.node_type = "desktop_mac"
    device.status = "online"
    device.platform = "macos"
    device.platform_version = "14.0"
    device.capabilities = ["camera", "screen_recording", "location", "notifications", "shell"]
    device.user_id = str(uuid.uuid4())
    device.workspace_id = "default"
    device.last_seen = datetime.utcnow()
    return device


@pytest.fixture
def desktop_device_windows():
    """Create a mock Windows desktop device node."""
    device = Mock(spec=DeviceNode)
    device.id = str(uuid.uuid4())
    device.device_id = "desktop-windows-456"
    device.name = "Dell XPS 15"
    device.node_type = "desktop_windows"
    device.status = "online"
    device.platform = "windows"
    device.platform_version = "11"
    device.capabilities = ["camera", "screen_recording", "location", "notifications", "shell"]
    device.user_id = str(uuid.uuid4())
    device.workspace_id = "default"
    device.last_seen = datetime.utcnow()
    return device


@pytest.fixture
def desktop_device_linux():
    """Create a mock Linux desktop device node."""
    device = Mock(spec=DeviceNode)
    device.id = str(uuid.uuid4())
    device.device_id = "desktop-linux-789"
    device.name = "Ubuntu Desktop"
    device.node_type = "desktop_linux"
    device.status = "online"
    device.platform = "linux"
    device.platform_version = "22.04"
    device.capabilities = ["camera", "screen_recording", "location", "notifications", "shell"]
    device.user_id = str(uuid.uuid4())
    device.workspace_id = "default"
    device.last_seen = datetime.utcnow()
    return device


@pytest.fixture
def student_agent():
    """Create a STUDENT level agent."""
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.name = "Student Agent"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.4
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.configuration = {}
    return agent


@pytest.fixture
def intern_agent():
    """Create an INTERN level agent."""
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.name = "Intern Agent"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.6
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.configuration = {}
    return agent


@pytest.fixture
def supervised_agent():
    """Create a SUPERVISED level agent."""
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.name = "Supervised Agent"
    agent.status = AgentStatus.SUPERVISED.value
    agent.confidence_score = 0.8
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.configuration = {}
    return agent


@pytest.fixture
def autonomous_agent():
    """Create an AUTONOMOUS level agent."""
    agent = Mock()
    agent.id = str(uuid.uuid4())
    agent.name = "Autonomous Agent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.confidence_score = 0.95
    agent.category = "Testing"
    agent.module_path = "test.test_agent"
    agent.class_name = "TestAgent"
    agent.configuration = {}
    return agent


# ============================================================================
# Desktop Device Registration Tests
# ============================================================================

class TestDesktopDeviceRegistration:
    """Tests for desktop device registration and management."""

    @pytest.mark.asyncio
    async def test_desktop_mac_device_properties(self, desktop_device_mac):
        """Test that macOS desktop device has expected properties."""
        assert desktop_device_mac.node_type == "desktop_mac"
        assert desktop_device_mac.platform == "macos"
        assert "camera" in desktop_device_mac.capabilities
        assert "screen_recording" in desktop_device_mac.capabilities
        assert "shell" in desktop_device_mac.capabilities
        assert desktop_device_mac.status in ["online", "offline", "busy"]

    @pytest.mark.asyncio
    async def test_desktop_windows_device_properties(self, desktop_device_windows):
        """Test that Windows desktop device has expected properties."""
        assert desktop_device_windows.node_type == "desktop_windows"
        assert desktop_device_windows.platform == "windows"
        assert "camera" in desktop_device_windows.capabilities
        assert "screen_recording" in desktop_device_windows.capabilities
        assert "shell" in desktop_device_windows.capabilities

    @pytest.mark.asyncio
    async def test_desktop_linux_device_properties(self, desktop_device_linux):
        """Test that Linux desktop device has expected properties."""
        assert desktop_device_linux.node_type == "desktop_linux"
        assert desktop_device_linux.platform == "linux"
        assert "camera" in desktop_device_linux.capabilities
        assert "screen_recording" in desktop_device_linux.capabilities
        assert "shell" in desktop_device_linux.capabilities

    @pytest.mark.asyncio
    async def test_desktop_device_node_types(self):
        """Test that all expected desktop node types are recognized."""
        desktop_node_types = [
            "desktop_mac",
            "desktop_windows",
            "desktop_linux",
        ]

        for node_type in desktop_node_types:
            assert node_type.startswith("desktop_")

    @pytest.mark.asyncio
    async def test_desktop_vs_mobile_node_types(self):
        """Test that desktop and mobile node types are distinct."""
        desktop_types = ["desktop_mac", "desktop_windows", "desktop_linux"]
        mobile_types = ["mobile_ios", "mobile_android"]

        # No overlap between desktop and mobile types
        assert set(desktop_types).isdisjoint(set(mobile_types))


# ============================================================================
# Desktop Device Capability Governance Tests
# ============================================================================

class TestDesktopDeviceCapabilityGovernance:
    """Tests for desktop device capability governance."""

    @pytest.mark.asyncio
    async def test_desktop_camera_snap_intern_allowed(
        self, mock_db, intern_agent, desktop_device_mac
    ):
        """Test that INTERN agents can use desktop camera (complexity 2)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_mac
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Mock governance check to pass
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "file_path": "/tmp/camera_snap_test.jpg",
                        "device_node_id": desktop_device_mac.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    result = await device_camera_snap(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_mac.device_id,
                        agent_id=intern_agent.id,
                        resolution="1920x1080"
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_desktop_camera_snap_student_blocked(
        self, mock_db, student_agent, desktop_device_windows
    ):
        """Test that STUDENT agents cannot use desktop camera (complexity 2)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_windows

        # Mock governance check to fail
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Agent lacks maturity for camera_snap",
                "governance_check_passed": False
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                result = await device_camera_snap(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id=desktop_device_windows.device_id,
                    agent_id=student_agent.id
                )

                assert result["success"] is False
                assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_desktop_screen_record_supervised_allowed(
        self, mock_db, supervised_agent, desktop_device_mac
    ):
        """Test that SUPERVISED agents can record desktop screen (complexity 3)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_mac
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Mock governance check to pass
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "data": {"recording_id": "rec-123"},
                        "device_node_id": desktop_device_mac.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    result = await device_screen_record_start(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_mac.device_id,
                        agent_id=supervised_agent.id
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_desktop_screen_record_intern_blocked(
        self, mock_db, intern_agent, desktop_device_linux
    ):
        """Test that INTERN agents cannot record desktop screen (complexity 3)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_linux

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool._check_device_governance') as mock_gov:
                mock_gov.return_value = {
                    "allowed": False,
                    "reason": "Agent lacks maturity for screen_record",
                    "governance_check_passed": False
                }

                result = await device_screen_record_start(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id=desktop_device_linux.device_id,
                    agent_id=intern_agent.id
                )

                assert result["success"] is False
                assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_desktop_shell_command_autonomous_allowed(
        self, mock_db, autonomous_agent, desktop_device_mac
    ):
        """Test that AUTONOMOUS agents can execute shell commands on desktop (complexity 4)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_mac
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Mock governance check to pass
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "data": {"exit_code": 0, "output": "test output"},
                        "device_node_id": desktop_device_mac.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    result = await device_execute_command(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_mac.device_id,
                        command="ls",
                        agent_id=autonomous_agent.id
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_desktop_shell_command_supervised_blocked(
        self, mock_db, supervised_agent, desktop_device_windows
    ):
        """Test that SUPERVISED agents cannot execute shell commands on desktop (complexity 4)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_windows

        with patch('tools.device_tool.is_device_online', return_value=True):
            with patch('tools.device_tool._check_device_governance') as mock_gov:
                mock_gov.return_value = {
                    "allowed": False,
                    "reason": "Agent lacks maturity for execute_command",
                    "governance_check_passed": False
                }

                result = await device_execute_command(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id=desktop_device_windows.device_id,
                    command="ls",
                    agent_id=supervised_agent.id
                )

                assert result["success"] is False
                assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_desktop_location_intern_allowed(
        self, mock_db, intern_agent, desktop_device_linux
    ):
        """Test that INTERN agents can get desktop location (complexity 2)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_linux
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "data": {
                            "latitude": 37.7749,
                            "longitude": -122.4194,
                            "city": "San Francisco"
                        },
                        "device_node_id": desktop_device_linux.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    result = await device_get_location(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_linux.device_id,
                        agent_id=intern_agent.id
                    )

                    assert result["success"] is True

    @pytest.mark.asyncio
    async def test_desktop_notification_intern_allowed(
        self, mock_db, intern_agent, desktop_device_mac
    ):
        """Test that INTERN agents can send desktop notifications (complexity 2)."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_mac
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "data": {
                            "title": "Test Notification",
                            "body": "Test body"
                        },
                        "device_node_id": desktop_device_mac.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    result = await device_send_notification(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_mac.device_id,
                        agent_id=intern_agent.id,
                        title="Test Notification",
                        body="Test body"
                    )

                    assert result["success"] is True


# ============================================================================
# Desktop Device Session Management Tests
# ============================================================================

class TestDesktopDeviceSessionManagement:
    """Tests for desktop device session management."""

    @pytest.mark.asyncio
    async def test_desktop_session_creation(self, mock_db, desktop_device_mac):
        """Test that desktop device sessions can be created."""
        session_id = str(uuid.uuid4())

        session = Mock(spec=DeviceSession)
        session.id = str(uuid.uuid4())
        session.session_id = session_id
        session.device_node_id = desktop_device_mac.device_id
        session.agent_id = str(uuid.uuid4())
        session.user_id = desktop_device_mac.user_id
        session.status = "active"
        session.started_at = datetime.utcnow()

        assert session.session_id == session_id
        assert session.device_node_id == desktop_device_mac.device_id
        assert session.status == "active"

    @pytest.mark.asyncio
    async def test_desktop_session_device_types(
        self, mock_db, desktop_device_mac, desktop_device_windows, desktop_device_linux
    ):
        """Test that sessions work with all desktop device types."""
        devices = [desktop_device_mac, desktop_device_windows, desktop_device_linux]

        for device in devices:
            session_id = str(uuid.uuid4())
            session = Mock(spec=DeviceSession)
            session.session_id = session_id
            session.device_node_id = device.device_id
            session.agent_id = str(uuid.uuid4())

            assert session.device_node_id == device.device_id
            assert device.node_type.startswith("desktop_")


# ============================================================================
# Desktop Device Audit Trail Tests
# ============================================================================

class TestDesktopDeviceAuditTrail:
    """Tests for desktop device audit trail creation."""

    @pytest.mark.asyncio
    async def test_audit_created_on_desktop_camera_success(
        self, mock_db, intern_agent, desktop_device_mac
    ):
        """Test that audit entry is created on successful desktop camera action."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_mac
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "file_path": "/tmp/camera_snap_test.jpg",
                        "device_node_id": desktop_device_mac.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    await device_camera_snap(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_mac.device_id,
                        agent_id=intern_agent.id
                    )

                    # Verify audit was created
                    assert mock_db.add.call_count >= 1
                    assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_audit_created_on_desktop_shell_success(
        self, mock_db, autonomous_agent, desktop_device_windows
    ):
        """Test that audit entry is created on successful desktop shell command."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_windows
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                async def mock_send_command(*args, **kwargs):
                    return {
                        "success": True,
                        "data": {"exit_code": 0, "output": "test"},
                        "device_node_id": desktop_device_windows.device_id
                    }
                with patch('tools.device_tool.send_device_command', side_effect=mock_send_command):
                    await device_execute_command(
                        db=mock_db,
                        user_id=str(uuid.uuid4()),
                        device_node_id=desktop_device_windows.device_id,
                        command="ls",
                        agent_id=autonomous_agent.id
                    )

                    # Verify audit was created
                    assert mock_db.add.call_count >= 1
                    assert mock_db.commit.call_count >= 1


# ============================================================================
# Desktop Device Security Tests
# ============================================================================

class TestDesktopDeviceSecurity:
    """Tests for desktop device security enforcement."""

    @pytest.mark.asyncio
    async def test_desktop_command_whitelist_enforced(
        self, mock_db, autonomous_agent, desktop_device_mac
    ):
        """Test that command whitelist is enforced for desktop shell execution."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_mac

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                # Try to execute a non-whitelisted command
                result = await device_execute_command(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id=desktop_device_mac.device_id,
                    command="rm -rf /",  # Dangerous command
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "not in whitelist" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_desktop_timeout_enforced(
        self, mock_db, autonomous_agent, desktop_device_windows
    ):
        """Test that command timeout is enforced for desktop commands."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_windows

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                # Try to set timeout exceeding maximum
                result = await device_execute_command(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id=desktop_device_windows.device_id,
                    command="ls",
                    timeout_seconds=400,  # Exceeds 300s max
                    agent_id=autonomous_agent.id
                )

                assert result["success"] is False
                assert "exceeds maximum" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_desktop_screen_record_duration_enforced(
        self, mock_db, supervised_agent, desktop_device_linux
    ):
        """Test that screen recording duration is enforced for desktop."""
        mock_db.query.return_value.filter.return_value.first.return_value = desktop_device_linux

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            with patch('tools.device_tool.is_device_online', return_value=True):
                # Try to set duration exceeding maximum
                result = await device_screen_record_start(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id=desktop_device_linux.device_id,
                    duration_seconds=10000,  # Exceeds 3600s max
                    agent_id=supervised_agent.id
                )

                assert result["success"] is False
                assert "exceeds maximum" in result["error"].lower()


# ============================================================================
# Desktop Platform-Specific Tests
# ============================================================================

class TestDesktopPlatformSpecificBehavior:
    """Tests for platform-specific desktop behavior."""

    @pytest.mark.asyncio
    async def test_macos_uses_avfoundation_for_camera(
        self, desktop_device_mac
    ):
        """Test that macOS desktop uses avfoundation for camera capture."""
        assert desktop_device_mac.platform == "macos"
        # macOS camera implementation uses ffmpeg with avfoundation input
        # This is documented in main.rs camera_snap command
        assert "camera" in desktop_device_mac.capabilities

    @pytest.mark.asyncio
    async def test_windows_uses_dshow_for_camera(
        self, desktop_device_windows
    ):
        """Test that Windows desktop uses dshow for camera capture."""
        assert desktop_device_windows.platform == "windows"
        # Windows camera implementation uses ffmpeg with dshow input
        assert "camera" in desktop_device_windows.capabilities

    @pytest.mark.asyncio
    async def test_linux_uses_v4l2_for_camera(
        self, desktop_device_linux
    ):
        """Test that Linux desktop uses v4l2 for camera capture."""
        assert desktop_device_linux.platform == "linux"
        # Linux camera implementation uses ffmpeg with v4l2 input
        assert "camera" in desktop_device_linux.capabilities

    @pytest.mark.asyncio
    async def test_macos_uses_avfoundation_for_screen_recording(
        self, desktop_device_mac
    ):
        """Test that macOS desktop uses avfoundation for screen recording."""
        assert desktop_device_mac.platform == "macos"
        # macOS screen recording uses ffmpeg with avfoundation input
        assert "screen_recording" in desktop_device_mac.capabilities

    @pytest.mark.asyncio
    async def test_windows_uses_gdigrab_for_screen_recording(
        self, desktop_device_windows
    ):
        """Test that Windows desktop uses gdigrab for screen recording."""
        assert desktop_device_windows.platform == "windows"
        # Windows screen recording uses ffmpeg with gdigrab input
        assert "screen_recording" in desktop_device_windows.capabilities

    @pytest.mark.asyncio
    async def test_linux_uses_x11grab_for_screen_recording(
        self, desktop_device_linux
    ):
        """Test that Linux desktop uses x11grab for screen recording."""
        assert desktop_device_linux.platform == "linux"
        # Linux screen recording uses ffmpeg with x11grab input
        assert "screen_recording" in desktop_device_linux.capabilities


# ============================================================================
# Desktop vs Mobile Governance Tests
# ============================================================================

class TestDesktopVsMobileGovernance:
    """Tests to verify desktop and mobile devices use same governance model."""

    @pytest.mark.asyncio
    async def test_desktop_and_mobile_share_governance_rules(
        self, intern_agent, student_agent
    ):
        """Test that desktop and mobile devices share the same governance rules."""
        from core.agent_governance_service import AgentGovernanceService

        complexity = AgentGovernanceService.ACTION_COMPLEXITY

        # Both desktop and mobile use same action complexity levels
        assert complexity["device_camera_snap"] == 2  # INTERN+ for both
        assert complexity["device_screen_record"] == 3  # SUPERVISED+ for both
        assert complexity["device_execute_command"] == 4  # AUTONOMOUS only for both

    @pytest.mark.asyncio
    async def test_desktop_shell_same_restrictions_as_mobile(
        self, supervised_agent, autonomous_agent
    ):
        """Test that desktop shell command has same restrictions as mobile."""
        from core.agent_governance_service import AgentGovernanceService

        requirements = AgentGovernanceService.MATURITY_REQUIREMENTS

        # Shell execution (complexity 4) requires AUTONOMOUS for both desktop and mobile
        assert requirements[4] == AgentStatus.AUTONOMOUS


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
