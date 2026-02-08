"""
Property-Based Tests for Agent Governance Service

Tests CRITICAL invariants for AI agent behavior control:
- Agent maturity levels enforce correct action permissions
- Governance decisions are deterministic
- Cache consistency
- Security boundaries are never bypassed

These tests protect users from AI doing harmful/unauthorized actions.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime
from typing import List, Dict
from unittest.mock import Mock, MagicMock, patch

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, User, UserRole


class TestAgentMaturityInvariants:
    """Property-based tests for agent maturity invariants."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        session = Mock()
        session.add = Mock()
        session.commit = Mock()
        session.refresh = Mock()
        return session

    @pytest.fixture
    def service(self, db_session):
        """Create service with mock DB."""
        return AgentGovernanceService(db_session)

    @given(
        status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                               AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]),
        action_type=st.sampled_from(['search', 'read', 'present_chart', 'stream_chat',
                                     'submit_form', 'delete', 'execute'])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_maturity_action_compliance(self, service, db_session, status, action_type):
        """INVARIANT: Each maturity level only allows permitted actions."""
        # Clear the cache to avoid cached results from previous tests
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        # Create mock agent
        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "test_agent"
        mock_agent.name = "Test Agent"
        mock_agent.status = status
        mock_agent.confidence_score = 0.7

        # Patch the query to return our mock
        with patch.object(db_session, 'query') as mock_query_class:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_agent
            mock_query_class.return_value = mock_query

            # Check governance
            result = service.can_perform_action("test_agent", action_type)

        # Define what actions each maturity level can perform
        student_allowed = ['search', 'read', 'present_chart']
        intern_allowed = student_allowed + ['stream_chat']
        supervised_allowed = intern_allowed + ['submit_form']
        autonomous_allowed = supervised_allowed + ['delete', 'execute']

        allowed_actions = {
            AgentStatus.STUDENT.value: set(student_allowed),
            AgentStatus.INTERN.value: set(intern_allowed),
            AgentStatus.SUPERVISED.value: set(supervised_allowed),
            AgentStatus.AUTONOMOUS.value: set(autonomous_allowed)
        }

        # Invariant: Decision must respect maturity permissions
        if action_type in allowed_actions[status]:
            # Action is allowed for this maturity level
            assert result["allowed"] in [True, False], "Decision must be boolean"
        else:
            # Action not allowed for this maturity
            assert not result["allowed"], \
                f"Action {action_type} should be rejected for {status}, got {result}"
            assert "lacks maturity" in result["reason"].lower() or \
                   "required" in result["reason"].lower()

    @given(
        status=st.sampled_from([AgentStatus.INTERN.value, AgentStatus.SUPERVISED.value,
                               AgentStatus.AUTONOMOUS.value]),
        confidence=st.floats(min_value=0.01, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_bounds(self, service, db_session, status, confidence):
        """INVARIANT: Confidence scores are always within valid range."""
        # Clear the cache to avoid cached results from previous tests
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "test_agent"
        mock_agent.name = "Test Agent"
        mock_agent.status = status
        mock_agent.confidence_score = confidence

        # Patch the query to return our mock
        with patch.object(db_session, 'query') as mock_query_class:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_agent
            mock_query_class.return_value = mock_query

            result = service.can_perform_action("test_agent", "search")

        # Invariant: Confidence should be in result and match what we set
        assert "confidence_score" in result
        # Note: Service uses `or 0.5` so 0.0 becomes 0.5, but all other values pass through
        assert result["confidence_score"] == confidence, \
            f"Expected {confidence}, got {result['confidence_score']}"

    @given(
        status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                               AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_action_complexity_levels(self, service, db_session, status):
        """INVARIANT: Action complexity levels are consistent."""
        # Clear the cache to avoid cached results from previous tests
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "test_agent"
        mock_agent.name = "Test Agent"
        mock_agent.status = status
        mock_agent.confidence_score = 0.7

        # Patch the query to return our mock
        with patch.object(db_session, 'query') as mock_query_class:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_agent
            mock_query_class.return_value = mock_query

            # Test various actions
            actions_to_test = ['search', 'stream_chat', 'submit_form', 'delete']

            for action in actions_to_test:
                result = service.can_perform_action("test_agent", action)

                # Invariant: Action complexity should be 1-4
                assert "action_complexity" in result
                assert 1 <= result["action_complexity"] <= 4, \
                    f"Action complexity {result['action_complexity']} for {action} out of range"

                # Invariant: Required status should be valid
                assert "required_status" in result
                assert result["required_status"] in [AgentStatus.STUDENT.value,
                                                      AgentStatus.INTERN.value,
                                                      AgentStatus.SUPERVISED.value,
                                                      AgentStatus.AUTONOMOUS.value]


class TestGovernanceDecisionInvariants:
    """Property-based tests for governance decision invariants."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        session = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def service(self, db_session):
        """Create service with mock DB."""
        return AgentGovernanceService(db_session)

    @given(
        status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                               AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]),
        action_type=st.sampled_from(['search', 'stream_chat', 'submit_form', 'delete'])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_decision_structure_consistency(self, service, db_session, status, action_type):
        """INVARIANT: Governance decisions have consistent structure."""
        # Clear the cache to avoid cached results from previous tests
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "test_agent"
        mock_agent.name = "Test Agent"
        mock_agent.status = status
        mock_agent.confidence_score = 0.7

        # Patch the query to return our mock
        with patch.object(db_session, 'query') as mock_query_class:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_agent
            mock_query_class.return_value = mock_query

            result = service.can_perform_action("test_agent", action_type)

        # Invariant: All required fields must be present
        required_fields = ["allowed", "reason", "agent_status", "action_complexity",
                          "required_status", "requires_human_approval", "confidence_score"]

        for field in required_fields:
            assert field in result, f"Missing required field: {field}"

        # Invariant: Types must be correct
        assert isinstance(result["allowed"], bool)
        assert isinstance(result["reason"], str)
        assert isinstance(result["agent_status"], str)
        assert isinstance(result["action_complexity"], int)
        assert isinstance(result["requires_human_approval"], bool)
        assert isinstance(result["confidence_score"], (int, float))

    @given(
        allowed=st.booleans(),
        requires_approval=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_enforce_action_logic(self, db_session, allowed, requires_approval):
        """INVARIANT: enforce_action returns correct structure."""
        service = AgentGovernanceService(db_session)

        # Mock can_perform_action to return specific values
        service.can_perform_action = Mock(return_value={
            "allowed": allowed,
            "reason": "Test reason",
            "agent_status": AgentStatus.INTERN.value,
            "action_complexity": 2,
            "required_status": AgentStatus.INTERN.value,
            "requires_human_approval": requires_approval,
            "confidence_score": 0.7
        })

        result = service.enforce_action("test_agent", "test_action")

        # Invariant: Must have required fields
        assert "proceed" in result
        assert "status" in result
        assert "reason" in result
        assert "action_required" in result

        # Invariant: If not allowed, should not proceed
        if not allowed:
            assert result["proceed"] is False
            assert result["status"] == "BLOCKED"
            assert result["action_required"] == "HUMAN_APPROVAL"

        # Invariant: If allowed but requires approval, should wait
        if allowed and requires_approval:
            assert result["proceed"] is True
            assert result["action_required"] == "WAIT_FOR_APPROVAL"

        # Invariant: If allowed and no approval needed, should be approved
        if allowed and not requires_approval:
            assert result["proceed"] is True
            assert result["status"] == "APPROVED"
            assert result["action_required"] is None


class TestSecurityInvariants:
    """Property-based tests for security invariants."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        session = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def service(self, db_session):
        """Create service with mock DB."""
        return AgentGovernanceService(db_session)

    @given(
        agent_status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                                      AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]),
        action_type=st.sampled_from(['delete', 'execute', 'deploy', 'payment', 'approve',
                                     'device_execute_command', 'canvas_execute_javascript'])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_critical_actions_require_autonomous(self, service, db_session, agent_status, action_type):
        """INVARIANT: Critical actions (complexity 4) require AUTONOMOUS status."""
        # Clear the cache to avoid cached results from previous tests
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "test_agent"
        mock_agent.name = "Test Agent"
        mock_agent.status = agent_status
        mock_agent.confidence_score = 0.95

        # Patch the query to return our mock
        with patch.object(db_session, 'query') as mock_query_class:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_agent
            mock_query_class.return_value = mock_query

            result = service.can_perform_action("test_agent", action_type)

        # Invariant: Critical actions should have complexity 4
        assert result["action_complexity"] == 4

        # Invariant: Only AUTONOMOUS agents can perform critical actions
        if agent_status != AgentStatus.AUTONOMOUS.value:
            assert not result["allowed"], \
                f"Critical action {action_type} should be blocked for {agent_status}"
            assert result["required_status"] == AgentStatus.AUTONOMOUS.value

    @given(
        status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                               AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_agent_capabilities_consistency(self, service, db_session, status):
        """INVARIANT: get_agent_capabilities returns consistent allowed actions."""
        # Clear the cache to avoid cached results from previous tests
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        mock_agent = Mock(spec=AgentRegistry)
        mock_agent.id = "test_agent"
        mock_agent.name = "Test Agent"
        mock_agent.status = status
        mock_agent.confidence_score = 0.7

        # Patch the query to return our mock
        with patch.object(db_session, 'query') as mock_query_class:
            mock_query = Mock()
            mock_query.filter.return_value = mock_query
            mock_query.first.return_value = mock_agent
            mock_query_class.return_value = mock_query

            capabilities = service.get_agent_capabilities("test_agent")

        # Invariant: Must have required fields
        assert "agent_id" in capabilities
        assert "maturity_level" in capabilities
        assert "max_complexity" in capabilities
        assert "allowed_actions" in capabilities
        assert "restricted_actions" in capabilities

        # Invariant: Maturity level should match
        assert capabilities["maturity_level"] == status

        # Invariant: Max complexity should be 1-4
        assert 1 <= capabilities["max_complexity"] <= 4

        # Invariant: Allowed and restricted actions should be disjoint
        allowed_set = set(capabilities["allowed_actions"])
        restricted_set = set(capabilities["restricted_actions"])
        assert len(allowed_set & restricted_set) == 0, \
            "Actions cannot be both allowed and restricted"


class TestAgentSpecialtyAccess:
    """Property-based tests for agent specialty access control."""

    @pytest.fixture
    def db_session(self):
        """Mock database session."""
        session = Mock()
        session.query = Mock()
        return session

    @pytest.fixture
    def service(self, db_session):
        """Create service with mock DB."""
        return AgentGovernanceService(db_session)

    @given(
        user_role=st.sampled_from([UserRole.WORKSPACE_ADMIN, UserRole.SUPER_ADMIN,
                                   UserRole.MEMBER, UserRole.GUEST]),
        has_specialty=st.booleans()
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_admin_can_access_any_agent(self, service, db_session, user_role, has_specialty):
        """INVARIANT: Admins can access any agent data."""
        user = Mock(spec=User)
        user.id = "test_user"
        user.role = user_role
        user.specialty = "Finance" if has_specialty else None

        agent = Mock(spec=AgentRegistry)
        agent.id = "test_agent"
        agent.category = "Finance"

        # Mock query to return user then agent
        call_count = [0]
        def mock_query_impl(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query

            def mock_first():
                call_count[0] += 1
                if call_count[0] == 1:
                    return user
                else:
                    return agent

            mock_query.first = Mock(side_effect=mock_first)
            return mock_query

        with patch.object(db_session, 'query', side_effect=mock_query_impl):
            result = service.can_access_agent_data("test_user", "test_agent")

        # Invariant: Admins should always have access
        if user_role in [UserRole.SUPER_ADMIN, UserRole.WORKSPACE_ADMIN]:
            assert result is True, f"Admin {user_role} should have access"

    @given(
        specialty_match=st.booleans()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_specialty_match_grants_access(self, service, db_session, specialty_match):
        """INVARIANT: Specialty match grants access."""
        user = Mock(spec=User)
        user.id = "test_user"
        user.role = UserRole.MEMBER  # Non-admin
        user.specialty = "Finance" if specialty_match else "Engineering"

        agent = Mock(spec=AgentRegistry)
        agent.id = "test_agent"
        agent.category = "Finance"

        # Mock query to return user then agent
        call_count = [0]
        def mock_query_impl(model):
            mock_query = Mock()
            mock_query.filter.return_value = mock_query

            def mock_first():
                call_count[0] += 1
                if call_count[0] == 1:
                    return user
                else:
                    return agent

            mock_query.first = Mock(side_effect=mock_first)
            return mock_query

        with patch.object(db_session, 'query', side_effect=mock_query_impl):
            result = service.can_access_agent_data("test_user", "test_agent")

        # Invariant: Specialty match should grant access
        if specialty_match:
            assert result is True, "Specialty match should grant access"
        else:
            assert result is False, "No specialty match should deny access for non-admin"
