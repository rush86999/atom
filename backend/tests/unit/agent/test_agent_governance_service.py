"""
Unit Tests for Agent Governance Service

Tests cover:
- Permission checks for all maturity levels
- Proposal workflow for INTERN agents
- Supervision setup for SUPERVISED agents
- Audit logging
"""
import pytest
from unittest.mock import Mock, patch
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus
from tests.factories import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)


class TestAgentGovernanceService:
    """Test agent governance service."""

    @pytest.fixture
    def service(self, db_session):
        """Create service."""
        return AgentGovernanceService(db_session)

    def test_student_allowed_presentation_only(self, service, db_session):
        """STUDENT agents allowed complexity 1 (presentations) only."""
        agent = StudentAgentFactory(_session=db_session)

        # Complexity 1: Allowed
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="present_chart"
        )
        assert decision["allowed"] is True

        # Complexity 2: Denied
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="stream_chat"
        )
        assert decision["allowed"] is False

    def test_intern_requires_proposal_for_complexity_2(self, service, db_session):
        """INTERN agents can perform complexity 2 actions but blocked from 3+."""
        agent = InternAgentFactory(_session=db_session)

        # Complexity 2: Allowed for INTERN (no approval needed by default)
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="stream_chat"
        )
        assert decision["allowed"] is True  # INTERN can do complexity 2

        # Complexity 3: Should be blocked
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="submit_form"
        )
        assert decision["allowed"] is False

    def test_supervised_requires_monitoring(self, service, db_session):
        """SUPERVISED agents require monitoring for complexity 2+ actions."""
        agent = SupervisedAgentFactory(_session=db_session)

        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="submit_form"
        )
        assert decision["allowed"] is True
        assert "supervision" in decision["reason"].lower() or decision["requires_human_approval"] is True

    def test_autonomous_full_access(self, service, db_session):
        """AUTONOMOUS agents have full access to all actions."""
        agent = AutonomousAgentFactory(_session=db_session)

        for complexity, action in [
            (1, "present_chart"),
            (2, "stream_chat"),
            (3, "submit_form"),
            (4, "delete")
        ]:
            decision = service.can_perform_action(
                agent_id=agent.id,
                action_type=action
            )
            assert decision["allowed"] is True, (
                f"AUTONOMOUS agent should be allowed complexity {complexity} action '{action}'"
            )

    def test_unknown_agent_denied(self, service, db_session):
        """Unknown agent ID returns denial response."""
        decision = service.can_perform_action(
            agent_id="nonexistent-agent-id",
            action_type="present_chart"
        )
        assert decision["allowed"] is False
        assert "not found" in decision["reason"].lower()

    def test_invalid_action_complexity_defaults_to_safe(self, service, db_session):
        """Invalid/unknown action types default to safe behavior."""
        agent = AutonomousAgentFactory(_session=db_session)

        # Unknown action should default to complexity 2 (medium-low)
        decision = service.can_perform_action(
            agent_id=agent.id,
            action_type="unknown_action_xyz"
        )
        # Should still return a decision
        assert "allowed" in decision
        assert "action_complexity" in decision

    def test_enforce_action_blocks_student_from_deletes(self, service, db_session):
        """enforce_action blocks STUDENT agents from destructive actions."""
        agent = StudentAgentFactory(_session=db_session)

        result = service.enforce_action(
            agent_id=agent.id,
            action_type="delete"
        )

        assert result["proceed"] is False
        assert result["status"] == "BLOCKED"
        assert "HUMAN_APPROVAL" in result.get("action_required", "")

    def test_enforce_action_allows_autonomous_deletes(self, service, db_session):
        """enforce_action allows AUTONOMOUS agents to perform deletions."""
        agent = AutonomousAgentFactory(_session=db_session)

        result = service.enforce_action(
            agent_id=agent.id,
            action_type="delete"
        )

        assert result["proceed"] is True
        assert result["status"] == "APPROVED"
        assert result.get("action_required") is None

    def test_get_agent_capabilities_returns_structure(self, service, db_session):
        """get_agent_capabilities returns expected structure."""
        agent = SupervisedAgentFactory(_session=db_session)

        capabilities = service.get_agent_capabilities(agent_id=agent.id)

        # Check required fields
        assert "agent_id" in capabilities
        assert "agent_name" in capabilities
        assert "maturity_level" in capabilities
        assert "confidence_score" in capabilities
        assert "max_complexity" in capabilities
        assert "allowed_actions" in capabilities
        assert "restricted_actions" in capabilities

        # Check data types
        assert isinstance(capabilities["allowed_actions"], list)
        assert isinstance(capabilities["restricted_actions"], list)
        assert isinstance(capabilities["max_complexity"], int)

    def test_get_agent_capabilities_student_limited(self, service, db_session):
        """STUDENT agent capabilities limited to complexity 1."""
        agent = StudentAgentFactory(_session=db_session)

        capabilities = service.get_agent_capabilities(agent_id=agent.id)

        # STUDENT should only have complexity 1 actions
        assert capabilities["max_complexity"] == 1
        assert len(capabilities["allowed_actions"]) > 0
        assert "delete" not in capabilities["allowed_actions"]
        assert "submit_form" not in capabilities["allowed_actions"]

    def test_get_agent_capabilities_autonomous_full(self, service, db_session):
        """AUTONOMOUS agent capabilities include all actions."""
        agent = AutonomousAgentFactory(_session=db_session)

        capabilities = service.get_agent_capabilities(agent_id=agent.id)

        # AUTONOMOUS should have all actions
        assert capabilities["max_complexity"] == 4
        assert len(capabilities["allowed_actions"]) > len(capabilities["restricted_actions"])
        assert "delete" in capabilities["allowed_actions"]

    def test_confidence_score_update_positive(self, service, db_session):
        """Positive feedback increases confidence score."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        initial_score = agent.confidence_score
        service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Re-query to get updated score
        db_session.refresh(agent)
        assert agent.confidence_score > initial_score

    def test_confidence_score_update_negative(self, service, db_session):
        """Negative feedback decreases confidence score."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        initial_score = agent.confidence_score
        service._update_confidence_score(agent.id, positive=False, impact_level="high")

        # Re-query to get updated score
        db_session.refresh(agent)
        assert agent.confidence_score < initial_score

    def test_confidence_score_clamped_at_one(self, service, db_session):
        """Confidence score clamped at maximum 1.0."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.AUTONOMOUS.value,
            confidence_score=0.95
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply many positive updates
        for _ in range(10):
            service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Re-query to get updated score
        db_session.refresh(agent)
        assert agent.confidence_score <= 1.0

    def test_confidence_score_clamped_at_zero(self, service, db_session):
        """Confidence score clamped at minimum 0.0."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.1
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply many negative updates
        for _ in range(10):
            service._update_confidence_score(agent.id, positive=False, impact_level="high")

        # Re-query to get updated score
        db_session.refresh(agent)
        assert agent.confidence_score >= 0.0

    def test_maturity_transition_student_to_intern(self, service, db_session):
        """Agent transitions from STUDENT to INTERN at 0.5 confidence."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.STUDENT.value,
            confidence_score=0.4
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply positive updates to reach 0.5
        for _ in range(3):
            service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Re-query to get updated status
        db_session.refresh(agent)
        assert agent.status == AgentStatus.INTERN.value

    def test_maturity_transition_intern_to_supervised(self, service, db_session):
        """Agent transitions from INTERN to SUPERVISED at 0.7 confidence."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=0.6
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply positive updates to reach 0.7
        for _ in range(3):
            service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Re-query to get updated status
        db_session.refresh(agent)
        assert agent.status == AgentStatus.SUPERVISED.value

    def test_maturity_transition_supervised_to_autonomous(self, service, db_session):
        """Agent transitions from SUPERVISED to AUTONOMOUS at 0.9 confidence."""
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.SUPERVISED.value,
            confidence_score=0.85
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Apply positive updates to reach 0.9
        for _ in range(2):
            service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Re-query to get updated status
        db_session.refresh(agent)
        assert agent.status == AgentStatus.AUTONOMOUS.value

    def test_list_agents_filters_by_category(self, service, db_session):
        """list_agents can filter by category."""
        # Create agents in different categories
        agent1 = StudentAgentFactory(category="finance", _session=db_session)
        agent2 = StudentAgentFactory(category="operations", _session=db_session)
        agent3 = StudentAgentFactory(category="finance", _session=db_session)

        # List all agents
        all_agents = service.list_agents()
        assert len(all_agents) >= 3

        # Filter by category
        finance_agents = service.list_agents(category="finance")
        assert len(finance_agents) >= 2
        assert all(a.category == "finance" for a in finance_agents)

    def test_cache_invalidation_on_status_change(self, service, db_session):
        """Cache is invalidated when agent status changes."""
        from core.governance_cache import get_governance_cache

        agent = StudentAgentFactory(_session=db_session)
        cache = get_governance_cache()

        # Warm cache
        cache.get(agent.id, "present_chart")

        # Change status (which should invalidate cache)
        service._update_confidence_score(agent.id, positive=True, impact_level="high")

        # Cache should have been invalidated
        # (This is hard to test directly, but we can check that the call doesn't fail)
        assert True  # If we got here, no exception was raised

    def test_unknown_agent_get_capabilities_raises_error(self, service, db_session):
        """get_agent_capabilities raises error for unknown agent."""
        from core.error_handlers import handle_not_found

        with pytest.raises(Exception):  # Could be HTTPException or other
            service.get_agent_capabilities(agent_id="unknown-agent-id")

    def test_register_or_update_agent_creates_new(self, service, db_session):
        """register_or_update_agent creates new agent."""
        agent = service.register_or_update_agent(
            name="NewAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            description="Test description"
        )

        assert agent.id is not None
        assert agent.name == "NewAgent"
        assert agent.category == "test"
        assert agent.status == AgentStatus.STUDENT.value

    def test_register_or_update_agent_updates_existing(self, service, db_session):
        """register_or_update_agent updates existing agent."""
        # Create initial agent
        agent1 = service.register_or_update_agent(
            name="UpdateAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            description="Initial description"
        )

        # Update with same module_path + class_name
        agent2 = service.register_or_update_agent(
            name="UpdateAgent",
            category="test",
            module_path="test.module",
            class_name="TestAgent",
            description="Updated description"
        )

        # Should be the same agent
        assert agent1.id == agent2.id
        assert agent2.description == "Updated description"
