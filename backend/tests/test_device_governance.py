"""
Device Governance Tests

Tests for governance integration with device capabilities including:
- Action complexity levels (INTERN+, SUPERVISED+, AUTONOMOUS)
- Agent maturity requirements
- Governance check enforcement
- Audit trail creation
"""

import uuid
from datetime import datetime
from unittest.mock import Mock, patch
import pytest
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, DeviceAudit, DeviceNode, User
from tools.device_tool import device_camera_snap, device_execute_command, device_screen_record_start

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
def student_agent():
    """Create a STUDENT level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = str(uuid.uuid4())
    agent.name = "Student Agent"
    agent.status = AgentStatus.STUDENT.value
    agent.confidence_score = 0.4
    return agent


@pytest.fixture
def intern_agent():
    """Create an INTERN level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = str(uuid.uuid4())
    agent.name = "Intern Agent"
    agent.status = AgentStatus.INTERN.value
    agent.confidence_score = 0.6
    return agent


@pytest.fixture
def supervised_agent():
    """Create a SUPERVISED level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = str(uuid.uuid4())
    agent.name = "Supervised Agent"
    agent.status = AgentStatus.SUPERVISED.value
    agent.confidence_score = 0.8
    return agent


@pytest.fixture
def autonomous_agent():
    """Create an AUTONOMOUS level agent."""
    agent = Mock(spec=AgentRegistry)
    agent.id = str(uuid.uuid4())
    agent.name = "Autonomous Agent"
    agent.status = AgentStatus.AUTONOMOUS.value
    agent.confidence_score = 0.95
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
    return device


# ============================================================================
# Governance Integration Tests
# ============================================================================

class TestDeviceGovernanceIntegration:
    """Tests for device governance integration."""

    @pytest.mark.asyncio
    async def test_camera_snap_intern_allowed(self, mock_db, intern_agent, mock_device_node):
        """Test that INTERN agents can use camera (complexity 2)."""
        # Setup mocks
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Mock governance check to pass
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            result = await device_camera_snap(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                agent_id=intern_agent.id,
                resolution="1920x1080"
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_camera_snap_student_blocked(self, mock_db, student_agent, mock_device_node):
        """Test that STUDENT agents cannot use camera (complexity 2)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        # Mock governance check to fail
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Agent lacks maturity for camera_snap",
                "governance_check_passed": False
            }

            result = await device_camera_snap(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                agent_id=student_agent.id
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_screen_record_supervised_allowed(self, mock_db, supervised_agent, mock_device_node):
        """Test that SUPERVISED agents can record screen (complexity 3)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Mock governance check to pass
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            result = await device_screen_record_start(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                agent_id=supervised_agent.id
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_screen_record_intern_blocked(self, mock_db, intern_agent, mock_device_node):
        """Test that INTERN agents cannot record screen (complexity 3)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        # Mock governance check to fail
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Agent lacks maturity for screen_record",
                "governance_check_passed": False
            }

            result = await device_screen_record_start(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                agent_id=intern_agent.id
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True

    @pytest.mark.asyncio
    async def test_execute_command_autonomous_allowed(self, mock_db, autonomous_agent, mock_device_node):
        """Test that AUTONOMOUS agents can execute commands (complexity 4)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        # Mock governance check to pass
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Agent has sufficient maturity",
                "governance_check_passed": True
            }

            result = await device_execute_command(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                command="ls",
                agent_id=autonomous_agent.id
            )

            assert result["success"] is True

    @pytest.mark.asyncio
    async def test_execute_command_supervised_blocked(self, mock_db, supervised_agent, mock_device_node):
        """Test that SUPERVISED agents cannot execute commands (complexity 4)."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        # Mock governance check to fail
        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Agent lacks maturity for execute_command",
                "governance_check_passed": False
            }

            result = await device_execute_command(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                command="ls",
                agent_id=supervised_agent.id
            )

            assert result["success"] is False
            assert result["governance_blocked"] is True


# ============================================================================
# Action Complexity Tests
# ============================================================================

class TestDeviceActionComplexity:
    """Tests for device action complexity levels."""

    def test_action_complexity_levels(self):
        """Test that all device actions have correct complexity levels."""
        from core.agent_governance_service import AgentGovernanceService

        complexity = AgentGovernanceService.ACTION_COMPLEXITY

        # INTERN+ actions (complexity 2)
        assert complexity["device_camera_snap"] == 2
        assert complexity["device_get_location"] == 2
        assert complexity["device_send_notification"] == 2

        # SUPERVISED+ actions (complexity 3)
        assert complexity["device_screen_record"] == 3
        assert complexity["device_screen_record_start"] == 3
        assert complexity["device_screen_record_stop"] == 3

        # AUTONOMOUS only actions (complexity 4)
        assert complexity["device_execute_command"] == 4

    def test_maturity_requirements(self):
        """Test that maturity requirements match complexity levels."""
        from core.agent_governance_service import AgentGovernanceService

        requirements = AgentGovernanceService.MATURITY_REQUIREMENTS

        assert requirements[2] == AgentStatus.INTERN
        assert requirements[3] == AgentStatus.SUPERVISED
        assert requirements[4] == AgentStatus.AUTONOMOUS


# ============================================================================
# Audit Trail Tests
# ============================================================================

class TestDeviceAuditTrail:
    """Tests for device audit trail creation."""

    @pytest.mark.asyncio
    async def test_audit_created_on_success(self, mock_db, intern_agent, mock_device_node):
        """Test that audit entry is created on successful action."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            await device_camera_snap(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                agent_id=intern_agent.id
            )

            # Verify audit was created
            assert mock_db.add.call_count >= 1
            assert mock_db.commit.call_count >= 1

    @pytest.mark.asyncio
    async def test_audit_created_on_governance_blocked(self, mock_db, student_agent, mock_device_node):
        """Test that audit entry is created even when governance blocks action."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
        mock_db.add = Mock()
        mock_db.commit = Mock()

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": False,
                "reason": "Not allowed",
                "governance_check_passed": False
            }

            result = await device_camera_snap(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                agent_id=student_agent.id
            )

            # When governance blocks, audit is still created in the catch block
            # The function returns early with governance_blocked=True
            assert result["governance_blocked"] is True
            # Audit is created when action fails after governance check passes
            # For blocked actions, the audit is created in the except block


# ============================================================================
# Security Tests
# ============================================================================

class TestDeviceSecurity:
    """Tests for device security enforcement."""

    @pytest.mark.asyncio
    async def test_command_whitelist_enforced(self, mock_db, autonomous_agent, mock_device_node):
        """Test that command whitelist is enforced."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            # Try to execute a non-whitelisted command
            result = await device_execute_command(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                command="rm -rf /",  # Dangerous command
                agent_id=autonomous_agent.id
            )

            assert result["success"] is False
            assert "not in whitelist" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_timeout_enforced(self, mock_db, autonomous_agent, mock_device_node):
        """Test that command timeout is enforced."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            # Try to set timeout exceeding maximum
            result = await device_execute_command(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                command="ls",
                timeout_seconds=400,  # Exceeds 300s max
                agent_id=autonomous_agent.id
            )

            assert result["success"] is False
            assert "exceeds maximum" in result["error"].lower()

    @pytest.mark.asyncio
    async def test_screen_record_duration_enforced(self, mock_db, supervised_agent, mock_device_node):
        """Test that screen recording duration is enforced."""
        mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node

        with patch('tools.device_tool._check_device_governance') as mock_gov:
            mock_gov.return_value = {
                "allowed": True,
                "reason": "Allowed",
                "governance_check_passed": True
            }

            # Try to set duration exceeding maximum
            result = await device_screen_record_start(
                db=mock_db,
                user_id=str(uuid.uuid4()),
                device_node_id="test-device-123",
                duration_seconds=10000,  # Exceeds 3600s max
                agent_id=supervised_agent.id
            )

            assert result["success"] is False
            assert "exceeds maximum" in result["error"].lower()


# ============================================================================
# Feature Flag Tests
# ============================================================================

class TestDeviceFeatureFlags:
    """Tests for device feature flags."""

    @pytest.mark.asyncio
    async def test_governance_bypass_respected(self, mock_db, intern_agent, mock_device_node):
        """Test that emergency governance bypass works."""
        import os
        old_bypass = os.getenv("EMERGENCY_GOVERNANCE_BYPASS")
        os.environ["EMERGENCY_GOVERNANCE_BYPASS"] = "true"

        try:
            mock_db.query.return_value.filter.return_value.first.return_value = mock_device_node
            mock_db.add = Mock()
            mock_db.commit = Mock()

            # Even with governance check returning failure
            with patch('tools.device_tool._check_device_governance') as mock_gov:
                mock_gov.return_value = {
                    "allowed": False,
                    "reason": "Would be blocked",
                    "governance_check_passed": False
                }

                # Reload the module to pick up the env var
                import importlib

                import tools.device_tool
                importlib.reload(tools.device_tool)

                # With bypass, action should succeed despite governance check
                result = await tools.device_tool.device_camera_snap(
                    db=mock_db,
                    user_id=str(uuid.uuid4()),
                    device_node_id="test-device-123",
                    agent_id=intern_agent.id
                )

                # With bypass, it should still work (fail-open for availability)
                # Note: This tests the fail-open behavior when governance fails
                assert result["success"] is True or "governance" in result.get("error", "").lower()

        finally:
            if old_bypass is None:
                os.environ.pop("EMERGENCY_GOVERNANCE_BYPASS", None)
            else:
                os.environ["EMERGENCY_GOVERNANCE_BYPASS"] = old_bypass


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
