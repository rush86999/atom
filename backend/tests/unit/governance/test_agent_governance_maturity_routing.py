"""
Agent Governance Maturity Routing Tests

Comprehensive test suite for 4x4 maturity/complexity matrix:
- 4 maturity levels: STUDENT, INTERN, SUPERVISED, AUTONOMOUS
- 4 action complexity levels: 1 (low) to 4 (critical)

Test Coverage:
- TestStudentAgentRouting: 4 tests for complexity 1-4 actions (should allow 1, block 2-4)
- TestInternAgentRouting: 4 tests for complexity 1-4 actions (should allow 1-2, block 3-4)
- TestSupervisedAgentRouting: 4 tests for complexity 1-4 actions (should allow 1-3, block 4)
- TestAutonomousAgentRouting: 4 tests for complexity 1-4 actions (should allow all)
- TestMaturityTransitions: 4 tests for confidence-based status changes
- TestApprovalRequirements: 4 tests for require_approval flag behavior
- TestEdgeCases: 4 tests for boundary conditions (0.5, 0.7, 0.9 thresholds)

Total: 28 test cases
"""

import pytest
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus
from tests.factories import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory,
)


class TestStudentAgentRouting:
    """Test STUDENT agent (confidence <0.5) routing against all complexity levels."""

    def test_student_allowed_complexity_1(self, db_session: Session):
        """STUDENT agent should be allowed complexity 1 actions (low risk)."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.3)

        service = AgentGovernanceService(db_session)

        # Mock cache to force DB lookup
        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None  # Force DB lookup
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="present_chart"  # Complexity 1
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.STUDENT.value
        assert result["action_complexity"] == 1
        assert result["required_status"] == AgentStatus.STUDENT.value
        assert result["confidence_score"] == 0.3
        assert result["requires_human_approval"] is False
        assert "can perform" in result["reason"].lower()

    def test_student_blocked_complexity_2(self, db_session: Session):
        """STUDENT agent should be blocked from complexity 2 actions (analyze, stream)."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.4)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="analyze"  # Complexity 2
            )

        assert result["allowed"] is False
        assert result["agent_status"] == AgentStatus.STUDENT.value
        assert result["action_complexity"] == 2
        assert result["required_status"] == AgentStatus.INTERN.value
        assert result["requires_human_approval"] is True
        assert "lacks maturity" in result["reason"].lower()

    def test_student_blocked_complexity_3(self, db_session: Session):
        """STUDENT agent should be blocked from complexity 3 actions (create, update)."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.3)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="create"  # Complexity 3
            )

        assert result["allowed"] is False
        assert result["agent_status"] == AgentStatus.STUDENT.value
        assert result["action_complexity"] == 3
        assert result["required_status"] == AgentStatus.SUPERVISED.value
        assert result["requires_human_approval"] is True

    def test_student_blocked_complexity_4(self, db_session: Session):
        """STUDENT agent should be blocked from complexity 4 actions (delete, execute)."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.2)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="delete"  # Complexity 4
            )

        assert result["allowed"] is False
        assert result["agent_status"] == AgentStatus.STUDENT.value
        assert result["action_complexity"] == 4
        assert result["required_status"] == AgentStatus.AUTONOMOUS.value
        assert result["requires_human_approval"] is True


class TestInternAgentRouting:
    """Test INTERN agent (confidence 0.5-0.7) routing against all complexity levels."""

    def test_intern_allowed_complexity_1(self, db_session: Session):
        """INTERN agent should be allowed complexity 1 actions."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="search"  # Complexity 1
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.INTERN.value
        assert result["action_complexity"] == 1

    def test_intern_allowed_complexity_2(self, db_session: Session):
        """INTERN agent should be allowed complexity 2 actions."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.65)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="stream_chat"  # Complexity 2
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.INTERN.value
        assert result["action_complexity"] == 2
        assert result["required_status"] == AgentStatus.INTERN.value

    def test_intern_blocked_complexity_3(self, db_session: Session):
        """INTERN agent should be blocked from complexity 3 actions."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.55)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="update"  # Complexity 3
            )

        assert result["allowed"] is False
        assert result["agent_status"] == AgentStatus.INTERN.value
        assert result["action_complexity"] == 3
        assert result["required_status"] == AgentStatus.SUPERVISED.value
        assert result["requires_human_approval"] is True

    def test_intern_blocked_complexity_4(self, db_session: Session):
        """INTERN agent should be blocked from complexity 4 actions."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="execute"  # Complexity 4
            )

        assert result["allowed"] is False
        assert result["agent_status"] == AgentStatus.INTERN.value
        assert result["action_complexity"] == 4
        assert result["required_status"] == AgentStatus.AUTONOMOUS.value
        assert result["requires_human_approval"] is True


class TestSupervisedAgentRouting:
    """Test SUPERVISED agent (confidence 0.7-0.9) routing against all complexity levels."""

    def test_supervised_allowed_complexity_1(self, db_session: Session):
        """SUPERVISED agent should be allowed complexity 1 actions."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.8)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="read"  # Complexity 1
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.SUPERVISED.value
        assert result["action_complexity"] == 1

    def test_supervised_allowed_complexity_2(self, db_session: Session):
        """SUPERVISED agent should be allowed complexity 2 actions."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.75)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="browser_navigate"  # Complexity 2
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.SUPERVISED.value
        assert result["action_complexity"] == 2

    def test_supervised_allowed_complexity_3(self, db_session: Session):
        """SUPERVISED agent should be allowed complexity 3 actions."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.85)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="submit_form"  # Complexity 3
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.SUPERVISED.value
        assert result["action_complexity"] == 3
        assert result["required_status"] == AgentStatus.SUPERVISED.value
        # SUPERVISED agents require approval for complexity 3+
        assert result["requires_human_approval"] is True

    def test_supervised_blocked_complexity_4(self, db_session: Session):
        """SUPERVISED agent should be blocked from complexity 4 actions."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.8)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="deploy"  # Complexity 4
            )

        assert result["allowed"] is False
        assert result["agent_status"] == AgentStatus.SUPERVISED.value
        assert result["action_complexity"] == 4
        assert result["required_status"] == AgentStatus.AUTONOMOUS.value
        assert result["requires_human_approval"] is True


class TestAutonomousAgentRouting:
    """Test AUTONOMOUS agent (confidence >0.9) routing against all complexity levels."""

    def test_autonomous_allowed_complexity_1(self, db_session: Session):
        """AUTONOMOUS agent should be allowed complexity 1 actions."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.95)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="summarize"  # Complexity 1
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.AUTONOMOUS.value
        assert result["action_complexity"] == 1
        assert result["requires_human_approval"] is False

    def test_autonomous_allowed_complexity_2(self, db_session: Session):
        """AUTONOMOUS agent should be allowed complexity 2 actions."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.92)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="llm_stream"  # Complexity 2
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.AUTONOMOUS.value
        assert result["action_complexity"] == 2
        assert result["requires_human_approval"] is False

    def test_autonomous_allowed_complexity_3(self, db_session: Session):
        """AUTONOMOUS agent should be allowed complexity 3 actions."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.96)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="send_email"  # Complexity 3
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.AUTONOMOUS.value
        assert result["action_complexity"] == 3
        # AUTONOMOUS agents don't require approval even for complexity 3+
        assert result["requires_human_approval"] is False

    def test_autonomous_allowed_complexity_4(self, db_session: Session):
        """AUTONOMOUS agent should be allowed complexity 4 actions."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.98)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="device_execute_command"  # Complexity 4
            )

        assert result["allowed"] is True
        assert result["agent_status"] == AgentStatus.AUTONOMOUS.value
        assert result["action_complexity"] == 4
        assert result["required_status"] == AgentStatus.AUTONOMOUS.value
        assert result["requires_human_approval"] is False


class TestMaturityTransitions:
    """Test confidence-based maturity transitions at thresholds."""

    def test_student_to_intern_transition(self, db_session: Session):
        """Agent should transition from STUDENT to INTERN at confidence 0.5."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.49)

        service = AgentGovernanceService(db_session)

        # Boost confidence to cross threshold
        service._update_confidence_score(agent.id, positive=True, impact_level="high")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.INTERN.value
        assert agent.confidence_score >= 0.5

    def test_intern_to_supervised_transition(self, db_session: Session):
        """Agent should transition from INTERN to SUPERVISED at confidence 0.7."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.69)

        service = AgentGovernanceService(db_session)

        # Boost confidence to cross threshold
        service._update_confidence_score(agent.id, positive=True, impact_level="high")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.SUPERVISED.value
        assert agent.confidence_score >= 0.7

    def test_supervised_to_autonomous_transition(self, db_session: Session):
        """Agent should transition from SUPERVISED to AUTONOMOUS at confidence 0.9."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.89)

        service = AgentGovernanceService(db_session)

        # Boost confidence to cross threshold
        service._update_confidence_score(agent.id, positive=True, impact_level="high")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.AUTONOMOUS.value
        assert agent.confidence_score >= 0.9

    def test_autonomous_to_supervised_demotion(self, db_session: Session):
        """Agent should demote from AUTONOMOUS to SUPERVISED below confidence 0.9."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.95)

        service = AgentGovernanceService(db_session)

        # Apply penalty to drop below threshold
        service._update_confidence_score(agent.id, positive=False, impact_level="high")
        service._update_confidence_score(agent.id, positive=False, impact_level="high")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.SUPERVISED.value
        assert agent.confidence_score < 0.9


class TestApprovalRequirements:
    """Test require_approval flag behavior across maturity levels."""

    def test_student_never_auto_approves(self, db_session: Session):
        """STUDENT agent always requires approval regardless of action complexity."""
        agent = StudentAgentFactory(_session=db_session, confidence_score=0.3)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            # Even complexity 1 actions should require approval if explicitly requested
            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="search",
                require_approval=True  # Explicit approval request
            )

        # Agent is allowed but approval is required due to flag
        assert result["requires_human_approval"] is True

    def test_supervised_complexity_3_requires_approval(self, db_session: Session):
        """SUPERVISED agent requires approval for complexity 3+ actions."""
        agent = SupervisedAgentFactory(_session=db_session, confidence_score=0.8)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="create"  # Complexity 3
            )

        assert result["allowed"] is True
        assert result["requires_human_approval"] is True

    def test_autonomous_no_approval_required(self, db_session: Session):
        """AUTONOMOUS agent doesn't require approval for any action."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.95)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            # Even highest complexity action
            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="delete"  # Complexity 4
            )

        assert result["allowed"] is True
        assert result["requires_human_approval"] is False

    def test_enforce_action_returns_approval_status(self, db_session: Session):
        """enforce_action() should return correct approval workflow status."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            cache_inst.set = MagicMock()
            mock_cache.return_value = cache_inst

            result = service.enforce_action(
                agent_id=agent.id,
                action_type="create"  # Complexity 3 - blocked for INTERN
            )

        assert result["proceed"] is False
        assert result["status"] == "BLOCKED"
        assert result["action_required"] == "HUMAN_APPROVAL"
        assert result["agent_status"] == AgentStatus.INTERN.value


class TestEdgeCases:
    """Test boundary conditions and edge cases."""

    def test_exact_threshold_0_5(self, db_session: Session):
        """Agent at exact 0.5 confidence should be INTERN."""
        agent = AgentRegistry(
            name="Threshold Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            confidence_score=0.5,
            status=AgentStatus.STUDENT.value
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)

        # Trigger update to check transition
        service._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.INTERN.value

    def test_exact_threshold_0_7(self, db_session: Session):
        """Agent at exact 0.7 confidence should be SUPERVISED."""
        agent = AgentRegistry(
            name="Threshold Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            confidence_score=0.7,
            status=AgentStatus.INTERN.value
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)

        service._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.SUPERVISED.value

    def test_exact_threshold_0_9(self, db_session: Session):
        """Agent at exact 0.9 confidence should be AUTONOMOUS."""
        agent = AgentRegistry(
            name="Threshold Agent",
            category="testing",
            module_path="test.module",
            class_name="TestAgent",
            confidence_score=0.9,
            status=AgentStatus.SUPERVISED.value
        )
        db_session.add(agent)
        db_session.commit()

        service = AgentGovernanceService(db_session)

        service._update_confidence_score(agent.id, positive=True, impact_level="low")
        db_session.refresh(agent)

        assert agent.status == AgentStatus.AUTONOMOUS.value

    def test_unknown_action_defaults_to_complexity_2(self, db_session: Session):
        """Actions not in ACTION_COMPLEXITY dict should default to complexity 2."""
        agent = InternAgentFactory(_session=db_session, confidence_score=0.6)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="unknown_future_action"  # Not in matrix
            )

        # Should default to complexity 2 (INTERN level)
        assert result["allowed"] is True  # INTERN can do complexity 2
        assert result["action_complexity"] == 2
        assert result["required_status"] == AgentStatus.INTERN.value


class TestResponseStructure:
    """Test that response structure matches expected format."""

    def test_response_structure_all_fields(self, db_session: Session):
        """Verify response contains all required fields."""
        agent = AutonomousAgentFactory(_session=db_session, confidence_score=0.95)

        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id=agent.id,
                action_type="delete"
            )

        # Verify all expected fields are present
        assert "allowed" in result
        assert "reason" in result
        assert "agent_status" in result
        assert "action_complexity" in result
        assert "required_status" in result
        assert "requires_human_approval" in result
        assert "confidence_score" in result

        # Verify field types
        assert isinstance(result["allowed"], bool)
        assert isinstance(result["reason"], str)
        assert isinstance(result["agent_status"], str)
        assert isinstance(result["action_complexity"], int)
        assert isinstance(result["required_status"], str)
        assert isinstance(result["requires_human_approval"], bool)
        assert isinstance(result["confidence_score"], (int, float))

    def test_agent_not_found_response(self, db_session: Session):
        """Verify response when agent doesn't exist."""
        service = AgentGovernanceService(db_session)

        with patch('core.agent_governance_service.get_governance_cache') as mock_cache:
            cache_inst = MagicMock()
            cache_inst.get.return_value = None
            mock_cache.return_value = cache_inst

            result = service.can_perform_action(
                agent_id="nonexistent_agent",
                action_type="search"
            )

        assert result["allowed"] is False
        assert "not found" in result["reason"].lower()
        assert result["requires_human_approval"] is True
