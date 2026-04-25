"""
Tests for AgentGovernanceService - agent maturity checks and governance enforcement.

Tests cover:
- Agent registration and updates
- Action permission checks (can_perform_action)
- Action complexity determination
- Maturity level enforcement
- Workspace handling
"""

import os
os.environ["TESTING"] = "1"

import pytest
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus


class TestAgentRegistration:
    """Test agent registration and updates."""

    def test_register_new_agent(self):
        """Test registering a new agent."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        # Mock query to return None (agent doesn't exist)
        mock_query = Mock()
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            agent = service.register_or_update_agent(
                name="Test Agent",
                category="Testing",
                module_path="test.module",
                class_name="TestAgent",
                description="A test agent"
            )

            # Verify agent was added to database
            mock_db.add.assert_called_once()
            mock_db.commit.assert_called_once()
            mock_db.refresh.assert_called_once()

    def test_update_existing_agent(self):
        """Test updating an existing agent."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        # Mock query to return existing agent
        existing_agent = AgentRegistry(
            id="existing-001",
            name="Old Name",
            category="Old Category",
            module_path="test.module",
            class_name="TestAgent",
            workspace_id="test"
        )
        mock_query = Mock()
        mock_query.first.return_value = existing_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            agent = service.register_or_update_agent(
                name="Updated Name",
                category="Updated Category",
                module_path="test.module",
                class_name="TestAgent",
                description="Updated description"
            )

            # Verify agent metadata was updated
            assert agent.name == "Updated Name"
            assert agent.category == "Updated Category"
            assert agent.description == "Updated description"
            # Verify commit was called
            mock_db.commit.assert_called_once()


class TestActionPermissions:
    """Test action permission checks."""

    def test_student_can_perform_level_1_actions(self):
        """Test that STUDENT agents can perform level 1 (read) actions."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        # Mock query to return STUDENT agent
        student_agent = AgentRegistry(
            id="student-001",
            name="Student Agent",
            status=AgentStatus.STUDENT,
            confidence_score=0.4,
            workspace_id="test"
        )
        mock_query = Mock()
        mock_query.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            result = service.can_perform_action(
                agent_id="student-001",
                action_type="get_status"
            )

            assert result["allowed"] is True

    def test_student_blocked_from_level_3_actions(self):
        """Test that STUDENT agents are blocked from level 3 actions."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        student_agent = AgentRegistry(
            id="student-002",
            name="Student Agent",
            status=AgentStatus.STUDENT,
            confidence_score=0.4,
            workspace_id="test"
        )
        mock_query = Mock()
        mock_query.first.return_value = student_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            result = service.can_perform_action(
                agent_id="student-002",
                action_type="update_record"
            )

            assert result["allowed"] is False
            assert result["requires_approval"] is True

    def test_autonomous_can_perform_critical_actions(self):
        """Test that AUTONOMOUS agents can perform level 4 (critical) actions."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        autonomous_agent = AgentRegistry(
            id="autonomous-001",
            name="Autonomous Agent",
            status=AgentStatus.AUTONOMOUS,
            confidence_score=0.95,
            workspace_id="test"
        )
        mock_query = Mock()
        mock_query.first.return_value = autonomous_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            result = service.can_perform_action(
                agent_id="autonomous-001",
                action_type="delete"
            )

            assert result["allowed"] is True

    def test_supervised_requires_approval_for_critical_actions(self):
        """Test that SUPERVISED agents require approval for critical actions."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        supervised_agent = AgentRegistry(
            id="supervised-001",
            name="Supervised Agent",
            status=AgentStatus.SUPERVISED,
            confidence_score=0.8,
            workspace_id="test"
        )
        mock_query = Mock()
        mock_query.first.return_value = supervised_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            result = service.can_perform_action(
                agent_id="supervised-001",
                action_type="execute"
            )

            # Should be blocked or require approval
            assert result["allowed"] is False or result["requires_approval"] is True


class TestActionComplexity:
    """Test action complexity determination."""

    def test_action_complexity_mapping(self):
        """Test that actions are mapped to correct complexity levels."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            # Level 1: Read operations
            assert service.ACTION_COMPLEXITY.get("get_status") == 1
            assert service.ACTION_COMPLEXITY.get("list_records") == 1

            # Level 2: Streaming
            assert service.ACTION_COMPLEXITY.get("stream_response") == 2
            assert service.ACTION_COMPLEXITY.get("chat") == 2

            # Level 3: State changes
            assert service.ACTION_COMPLEXITY.get("create_record") == 3
            assert service.ACTION_COMPLEXITY.get("update_record") == 3

            # Level 4: Critical operations
            assert service.ACTION_COMPLEXITY.get("delete") == 4
            assert service.ACTION_COMPLEXITY.get("execute") == 4


class TestMaturityRequirements:
    """Test maturity level requirements."""

    def test_maturity_requirements_mapping(self):
        """Test that complexity levels map to correct maturity requirements."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            # Level 1 -> STUDENT
            assert service.MATURITY_REQUIREMENTS[1] == AgentStatus.STUDENT
            # Level 2 -> INTERN
            assert service.MATURITY_REQUIREMENTS[2] == AgentStatus.INTERN
            # Level 3 -> SUPERVISED
            assert service.MATURITY_REQUIREMENTS[3] == AgentStatus.SUPERVISED
            # Level 4 -> AUTONOMOUS
            assert service.MATURITY_REQUIREMENTS[4] == AgentStatus.AUTONOMOUS


class TestWorkspaceHandling:
    """Test workspace ID handling."""

    def test_initialization_with_default_workspace(self):
        """Test service initialization with default workspace."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="default",
                activity_publisher=mock_activity_publisher
            )

            assert service.workspace_id == "default"

    def test_initialization_with_custom_workspace(self):
        """Test service initialization with custom workspace."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="custom-workspace",
                activity_publisher=mock_activity_publisher
            )

            assert service.workspace_id == "custom-workspace"


class TestErrorHandling:
    """Test error handling."""

    def test_agent_not_found_returns_denied(self):
        """Test that non-existent agents return permission denied."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        # Mock query to return None (agent not found)
        mock_query = Mock()
        mock_query.first.return_value = None
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            result = service.can_perform_action(
                agent_id="nonexistent-001",
                action_type="get_status"
            )

            assert result["allowed"] is False
            assert "not found" in result["reason"].lower()

    def test_paused_agent_blocked_from_actions(self):
        """Test that PAUSED agents are blocked from actions."""
        mock_db = Mock(spec=Session)
        mock_activity_publisher = Mock()

        paused_agent = AgentRegistry(
            id="paused-001",
            name="Paused Agent",
            status=AgentStatus.PAUSED,
            confidence_score=0.8,
            workspace_id="test"
        )
        mock_query = Mock()
        mock_query.first.return_value = paused_agent
        mock_db.query.return_value = mock_query

        with patch('core.agent_governance_service.ContinuousLearningService'):
            service = AgentGovernanceService(
                db=mock_db,
                workspace_id="test",
                activity_publisher=mock_activity_publisher
            )

            result = service.can_perform_action(
                agent_id="paused-001",
                action_type="get_status"
            )

            assert result["allowed"] is False
            assert "paused" in result["reason"].lower()
