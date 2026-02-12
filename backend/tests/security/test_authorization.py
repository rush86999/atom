"""
Authorization security tests (SECU-02).

Tests cover:
- Agent maturity permission matrix (4x4 combinations)
- Action complexity enforcement
- Governance checks
- Permission boundaries
"""
import pytest
from fastapi.testclient import TestClient
from sqlalchemy.orm import Session
from tests.factories.agent_factory import (
    StudentAgentFactory,
    InternAgentFactory,
    SupervisedAgentFactory,
    AutonomousAgentFactory
)
from tests.factories.user_factory import AdminUserFactory
from core.models import AgentStatus
from core.auth import get_password_hash, create_access_token


# Test data: Maturity level x Action complexity = expected result
# Note: Complexity based on agent_governance_service.ACTION_COMPLEXITY
MATURITY_ACTION_MATRIX = [
    # (agent_factory, action_type, complexity, allowed, description)
    # STUDENT agents - blocked from all but read-only
    (StudentAgentFactory, "search", 1, True, "STUDENT can search (read-only)"),
    (StudentAgentFactory, "read", 1, True, "STUDENT can read (read-only)"),
    (StudentAgentFactory, "list", 1, True, "STUDENT can list (read-only)"),
    (StudentAgentFactory, "stream", 2, False, "STUDENT blocked from streaming"),
    (StudentAgentFactory, "analyze", 2, False, "STUDENT blocked from analyze"),
    (StudentAgentFactory, "delete", 4, False, "STUDENT blocked from deletions"),
    (StudentAgentFactory, "execute", 4, False, "STUDENT blocked from execute"),
    (StudentAgentFactory, "update", 3, False, "STUDENT blocked from state changes"),

    # INTERN agents - can do level 1-2, blocked from 3-4
    (InternAgentFactory, "search", 1, True, "INTERN can search"),
    (InternAgentFactory, "analyze", 2, True, "INTERN can analyze"),
    (InternAgentFactory, "draft", 2, True, "INTERN can draft"),
    (InternAgentFactory, "delete", 4, False, "INTERN blocked from deletions"),
    (InternAgentFactory, "execute", 4, False, "INTERN blocked from execute"),
    (InternAgentFactory, "update", 3, False, "INTERN blocked from state changes"),
    (InternAgentFactory, "send_email", 3, False, "INTERN blocked from send_email"),
    (InternAgentFactory, "submit", 2, True, "INTERN can submit (complexity 2 - not submit_form)"),

    # SUPERVISED agents - can do level 1-3, blocked from 4
    (SupervisedAgentFactory, "search", 1, True, "SUPERVISED can search"),
    (SupervisedAgentFactory, "stream", 2, True, "SUPERVISED can stream"),
    (SupervisedAgentFactory, "analyze", 2, True, "SUPERVISED can analyze"),
    (SupervisedAgentFactory, "update", 3, True, "SUPERVISED can update state"),
    (SupervisedAgentFactory, "submit_form", 3, True, "SUPERVISED can submit_form"),
    (SupervisedAgentFactory, "delete", 4, False, "SUPERVISED blocked from deletions"),
    (SupervisedAgentFactory, "execute", 4, False, "SUPERVISED blocked from execute"),
    (SupervisedAgentFactory, "send_email", 3, True, "SUPERVISED can send_email"),

    # AUTONOMOUS agents - full execution
    (AutonomousAgentFactory, "search", 1, True, "AUTONOMOUS can search"),
    (AutonomousAgentFactory, "stream", 2, True, "AUTONOMOUS can stream"),
    (AutonomousAgentFactory, "update", 3, True, "AUTONOMOUS can update state"),
    (AutonomousAgentFactory, "delete", 4, True, "AUTONOMOUS can delete"),
    (AutonomousAgentFactory, "execute", 4, True, "AUTONOMOUS can execute"),
    (AutonomousAgentFactory, "submit", 2, True, "AUTONOMOUS can submit"),
    (AutonomousAgentFactory, "send_email", 3, True, "AUTONOMOUS can send_email"),
    (AutonomousAgentFactory, "analyze", 2, True, "AUTONOMOUS can analyze"),
]


class TestMaturityPermissionMatrix:
    """Test agent maturity permission matrix enforcement."""

    @pytest.mark.parametrize("agent_factory,action,complexity,allowed,description", MATURITY_ACTION_MATRIX)
    def test_maturity_action_combinations(
        self,
        db_session: Session,
        agent_factory,
        action,
        complexity,
        allowed,
        description
    ):
        """
        Test all maturity level x action complexity combinations.

        This is a CRITICAL security test ensuring governance enforcement.
        """
        # Given: Agent with specific maturity level
        agent = agent_factory(_session=db_session)

        # When: Check governance permission
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(
            agent_id=agent.id,
            action_type=action
        )

        # Then: Enforce expected permission
        assert result["allowed"] == allowed, \
            f"Failed for {description}: got allowed={result['allowed']}, expected allowed={allowed}"

        # Verify maturity level is correct
        assert result["agent_status"] == agent.status

        # Verify action complexity is detected
        assert result["action_complexity"] == complexity

        # Verify governance reason is provided
        assert "reason" in result
        assert len(result["reason"]) > 0

    def test_student_blocked_from_all_triggers(self, db_session: Session):
        """Test STUDENT agent is completely blocked from automated triggers."""
        agent = StudentAgentFactory(_session=db_session)

        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # STUDENT should be blocked from high-complexity actions
        for action in ["delete", "execute", "update", "send_email"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] == False, f"STUDENT should be blocked from {action}"
            assert "lacks maturity" in result["reason"].lower() or "blocked" in result["reason"].lower()

    def test_intern_requires_approval_for_state_changes(self, db_session: Session):
        """Test INTERN agent requires approval for state changes."""
        agent = InternAgentFactory(_session=db_session)

        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # INTERN should be blocked from high-complexity actions
        for action in ["delete", "execute", "update", "send_email", "submit_form"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] == False, f"INTERN should be blocked from {action}"

    def test_supervised_allowed_for_most_actions(self, db_session: Session):
        """Test SUPERVISED agent can perform most actions except critical."""
        agent = SupervisedAgentFactory(_session=db_session)

        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # SUPERVISED should be allowed for levels 1-3
        for action in ["search", "stream", "analyze", "update", "submit", "send_email"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] == True, f"SUPERVISED should be allowed to {action}"

        # But blocked from level 4
        for action in ["delete", "execute"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] == False, f"SUPERVISED should be blocked from {action}"

    def test_autonomous_full_execution(self, db_session: Session):
        """Test AUTONOMOUS agent has full execution权限."""
        agent = AutonomousAgentFactory(_session=db_session)

        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # AUTONOMOUS should be allowed for all actions
        for action in ["search", "stream", "analyze", "update", "submit", "delete", "execute", "send_email"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["allowed"] == True, \
                f"AUTONOMOUS agent should be allowed to {action}, got: {result}"


class TestGovernanceCaching:
    """Test governance cache doesn't bypass security."""

    def test_governance_cache_consistent_with_database(self, db_session: Session):
        """Test governance cache returns consistent decisions."""
        from core.governance_cache import get_governance_cache

        agent = StudentAgentFactory(_session=db_session)

        # First check - database
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        db_result = governance.can_perform_action(
            agent_id=agent.id,
            action_type="delete"
        )

        # Verify the result was cached
        cache = get_governance_cache()
        cached_result = cache.get(agent.id, "delete")

        # Both should agree (STUDENT blocked from delete)
        assert cached_result is not None
        assert cached_result["allowed"] == db_result["allowed"]
        assert db_result["allowed"] == False

    def test_cache_invalidation_on_maturity_change(self, db_session: Session):
        """Test cache invalidates when agent maturity changes."""
        agent = StudentAgentFactory(_session=db_session)

        from core.governance_cache import get_governance_cache
        from core.agent_governance_service import AgentGovernanceService

        cache = get_governance_cache()
        governance = AgentGovernanceService(db_session)

        # Check initial permission (should be blocked)
        result1 = governance.can_perform_action(agent.id, "delete")
        assert result1["allowed"] == False

        # Promote agent to AUTONOMOUS
        agent.status = AgentStatus.AUTONOMOUS.value
        agent.confidence_score = 0.95
        db_session.commit()

        # Invalidate cache
        cache.invalidate(agent.id)

        # Check new permission (should be allowed)
        result2 = governance.can_perform_action(agent.id, "delete")
        assert result2["allowed"] == True

    def test_cache_hit_returns_same_result(self, db_session: Session):
        """Test cache hit returns identical result."""
        agent = InternAgentFactory(_session=db_session)

        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # First call - cache miss
        result1 = governance.can_perform_action(agent.id, "stream")
        assert "action_complexity" in result1

        # Second call - cache hit
        result2 = governance.can_perform_action(agent.id, "stream")

        # Should return same result
        assert result1["allowed"] == result2["allowed"]
        assert result1["action_complexity"] == result2["action_complexity"]
        assert result1["agent_status"] == result2["agent_status"]


class TestPermissionBoundaries:
    """Test permission boundaries between maturity levels."""

    def test_maturity_hierarchy_enforced(self, db_session: Session):
        """Test maturity level hierarchy is properly enforced."""
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # Create one of each maturity level
        student = StudentAgentFactory(_session=db_session)
        intern = InternAgentFactory(_session=db_session)
        supervised = SupervisedAgentFactory(_session=db_session)
        autonomous = AutonomousAgentFactory(_session=db_session)

        # Test a high-complexity action (delete)
        for agent in [student, intern, supervised]:
            result = governance.can_perform_action(agent.id, "delete")
            assert result["allowed"] == False, \
                f"{agent.status} should not be allowed to delete"

        # Only AUTONOMOUS can delete
        result = governance.can_perform_action(autonomous.id, "delete")
        assert result["allowed"] == True

    def test_confidence_score_consistent_with_maturity(self, db_session: Session):
        """Test confidence scores match maturity levels."""
        student = StudentAgentFactory(_session=db_session)
        intern = InternAgentFactory(_session=db_session)
        supervised = SupervisedAgentFactory(_session=db_session)
        autonomous = AutonomousAgentFactory(_session=db_session)

        # STUDENT: <0.5
        assert 0.0 <= student.confidence_score < 0.5

        # INTERN: 0.5-0.7
        assert 0.5 <= intern.confidence_score < 0.7

        # SUPERVISED: 0.7-0.9
        assert 0.7 <= supervised.confidence_score < 0.9

        # AUTONOMOUS: >=0.9
        assert 0.9 <= autonomous.confidence_score <= 1.0

    def test_action_complexity_levels(self, db_session: Session):
        """Test action complexity is correctly classified."""
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        agent = AutonomousAgentFactory(_session=db_session)

        # Level 1 actions (low risk)
        for action in ["search", "read", "list", "get", "summarize", "present_chart"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["action_complexity"] == 1, \
                f"{action} should be complexity 1, got {result['action_complexity']}"

        # Level 2 actions (medium-low)
        for action in ["analyze", "suggest", "draft", "generate", "stream", "submit"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["action_complexity"] == 2, \
                f"{action} should be complexity 2, got {result['action_complexity']}"

        # Level 3 actions (high)
        for action in ["update", "submit_form", "send_email", "create", "post_message"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["action_complexity"] == 3, \
                f"{action} should be complexity 3, got {result['action_complexity']}"

        # Level 4 actions (critical)
        for action in ["delete", "execute", "deploy", "payment"]:
            result = governance.can_perform_action(agent.id, action)
            assert result["action_complexity"] == 4, \
                f"{action} should be complexity 4, got {result['action_complexity']}"

    def test_get_agent_capabilities(self, db_session: Session):
        """Test getting agent capabilities based on maturity."""
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        # Test STUDENT agent
        student = StudentAgentFactory(_session=db_session)

        capabilities = governance.get_agent_capabilities(student.id)

        assert capabilities["maturity_level"] == AgentStatus.STUDENT.value
        assert capabilities["max_complexity"] == 1
        assert len(capabilities["allowed_actions"]) > 0
        assert "search" in capabilities["allowed_actions"]
        assert "delete" not in capabilities["allowed_actions"]

        # Test AUTONOMOUS agent
        autonomous = AutonomousAgentFactory(_session=db_session)

        capabilities = governance.get_agent_capabilities(autonomous.id)

        assert capabilities["maturity_level"] == AgentStatus.AUTONOMOUS.value
        assert capabilities["max_complexity"] == 4
        assert "delete" in capabilities["allowed_actions"]
        assert "execute" in capabilities["allowed_actions"]


class TestGovernanceEnforcement:
    """Test governance enforcement at service level."""

    def test_enforce_action_blocks_unauthorized(self, db_session: Session):
        """Test enforce_action blocks unauthorized agents."""
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        student = StudentAgentFactory(_session=db_session)

        # Try to enforce a blocked action
        result = governance.enforce_action(
            agent_id=student.id,
            action_type="delete",
            action_details={"target": "test"}
        )

        assert result["proceed"] == False
        assert result["status"] in ["BLOCKED", "PENDING_APPROVAL"]

    def test_enforce_action_allows_authorized(self, db_session: Session):
        """Test enforce_action allows authorized agents."""
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        autonomous = AutonomousAgentFactory(_session=db_session)

        # Try to enforce an allowed action
        result = governance.enforce_action(
            agent_id=autonomous.id,
            action_type="delete",
            action_details={"target": "test"}
        )

        assert result["proceed"] == True
        assert result["status"] == "APPROVED"

    def test_agent_not_found_returns_error(self, db_session: Session):
        """Test governance check for non-existent agent."""
        from core.agent_governance_service import AgentGovernanceService
        governance = AgentGovernanceService(db_session)

        result = governance.can_perform_action(
            agent_id="nonexistent-agent-id",
            action_type="delete"
        )

        assert result["allowed"] == False
        assert "not found" in result["reason"].lower()


class TestTriggerInterceptor:
    """Test trigger interceptor maturity-based routing."""

    def test_routing_decision_exists(self, db_session: Session):
        """Test that RoutingDecision enum has expected values."""
        from core.trigger_interceptor import RoutingDecision

        # Verify all routing decisions exist
        assert hasattr(RoutingDecision, 'TRAINING')
        assert hasattr(RoutingDecision, 'PROPOSAL')
        assert hasattr(RoutingDecision, 'SUPERVISION')
        assert hasattr(RoutingDecision, 'EXECUTION')

    def test_maturity_level_exists(self, db_session: Session):
        """Test that MaturityLevel enum has expected values."""
        from core.trigger_interceptor import MaturityLevel

        # Verify all maturity levels exist
        assert hasattr(MaturityLevel, 'STUDENT')
        assert hasattr(MaturityLevel, 'INTERN')
        assert hasattr(MaturityLevel, 'SUPERVISED')
        assert hasattr(MaturityLevel, 'AUTONOMOUS')

    def test_trigger_source_exists(self, db_session: Session):
        """Test that TriggerSource enum has expected values."""
        from core.trigger_interceptor import TriggerSource

        # Verify trigger sources exist
        assert hasattr(TriggerSource, 'MANUAL')
        assert hasattr(TriggerSource, 'WORKFLOW_ENGINE')
        assert hasattr(TriggerSource, 'DATA_SYNC')

    def test_interceptor_initialization(self, db_session: Session):
        """Test TriggerInterceptor can be initialized."""
        from core.trigger_interceptor import TriggerInterceptor

        interceptor = TriggerInterceptor(db_session, "test_workspace")

        assert interceptor is not None
        assert interceptor.db == db_session
        assert interceptor.workspace_id == "test_workspace"
