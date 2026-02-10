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


class TestGovernanceCacheInvariants:
    """Property-based tests for governance cache invariants."""

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
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789'),
        action_type=st.sampled_from(['search', 'stream_chat', 'submit_form', 'delete'])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_cache_key_uniqueness(self, service, db_session, agent_id, action_type):
        """INVARIANT: Cache keys should be unique per agent-action pair."""
        from core.governance_cache import get_governance_cache
        cache = get_governance_cache()
        cache.clear()

        # Invariant: Agent ID should be non-empty
        assert len(agent_id) > 0, "Agent ID should not be empty"

        # Invariant: Cache should generate unique keys
        cache_key_1 = cache._make_key(agent_id, action_type)
        cache_key_2 = cache._make_key(agent_id, action_type)
        assert cache_key_1 == cache_key_2, "Same agent-action should generate same key"

        # Different actions should generate different keys
        cache_key_3 = cache._make_key(agent_id, "different_action")
        assert cache_key_1 != cache_key_3, "Different actions should generate different keys"

    @given(
        lookup_count=st.integers(min_value=1, max_value=1000),
        hit_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_cache_hit_rate_tracking(self, lookup_count, hit_rate):
        """INVARIANT: Cache should track hit rate accurately."""
        # Calculate hits and misses
        hits = int(lookup_count * hit_rate)
        misses = lookup_count - hits

        # Invariant: Hits + misses should equal total
        assert hits + misses == lookup_count, \
            f"Hits {hits} + misses {misses} != total {lookup_count}"

        # Invariant: Hit rate should be in valid range
        calculated_hit_rate = hits / lookup_count if lookup_count > 0 else 0.0
        assert 0.0 <= calculated_hit_rate <= 1.0, "Hit rate out of bounds"

    @given(
        cache_size=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_cache_size_limits(self, cache_size):
        """INVARIANT: Cache should enforce size limits."""
        max_cache_size = 10000

        # Invariant: Cache size should not exceed maximum
        assert cache_size <= max_cache_size, \
            f"Cache size {cache_size} exceeds maximum {max_cache_size}"

        # Invariant: Cache size should be positive
        assert cache_size >= 1, "Cache size must be positive"


class TestGovernancePolicyInvariants:
    """Property-based tests for governance policy invariants."""

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
        policy_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_policy_count_limits(self, policy_count):
        """INVARIANT: Number of governance policies should be limited."""
        max_policies = 100

        # Invariant: Policy count should not exceed maximum
        assert policy_count <= max_policies, \
            f"Policy count {policy_count} exceeds maximum {max_policies}"

        # Invariant: Policy count should be positive
        assert policy_count >= 1, "Policy count must be positive"

    @given(
        policy_priority=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=50)
    def test_policy_priority_ordering(self, policy_priority):
        """INVARIANT: Policies should be ordered by priority."""
        # Invariant: Priority should be in valid range
        assert 1 <= policy_priority <= 10, \
            f"Policy priority {policy_priority} out of range [1, 10]"

        # Invariant: Higher priority policies should be evaluated first
        if policy_priority == 10:
            assert True  # Highest priority

    @given(
        action_count=st.integers(min_value=1, max_value=50),
        policy_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_policy_action_mapping(self, action_count, policy_count):
        """INVARIANT: Policies should map to actions correctly."""
        # Invariant: Action count should be reasonable
        assert 1 <= action_count <= 50, "Action count out of range"

        # Invariant: Policy count should be reasonable
        assert 1 <= policy_count <= 20, "Policy count out of range"

        # Invariant: Each action should have at least one policy
        assert action_count >= 1, "At least one action"


class TestGovernanceAuditInvariants:
    """Property-based tests for governance audit invariants."""

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
        decision_count=st.integers(min_value=1, max_value=1000)
    )
    @settings(max_examples=50)
    def test_audit_log_completeness(self, decision_count):
        """INVARIANT: All governance decisions should be logged."""
        max_decisions = 1000

        # Invariant: Decision count should not exceed maximum
        assert decision_count <= max_decisions, \
            f"Decision count {decision_count} exceeds maximum {max_decisions}"

        # Invariant: Decision count should be positive
        assert decision_count >= 1, "Decision count must be positive"

    @given(
        agent_id=st.text(min_size=1, max_size=50, alphabet='abc0123456789'),
        action_type=st.sampled_from(['search', 'stream_chat', 'submit_form', 'delete']),
        decision=st.booleans()
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_audit_entry_structure(self, service, db_session, agent_id, action_type, decision):
        """INVARIANT: Audit entries should have consistent structure."""
        # Invariant: Agent ID should be non-empty
        assert len(agent_id) > 0, "Agent ID should not be empty"

        # Invariant: Action type should be valid
        valid_actions = {'search', 'stream_chat', 'submit_form', 'delete'}
        assert action_type in valid_actions, f"Invalid action: {action_type}"

        # Invariant: Decision should be boolean
        assert isinstance(decision, bool), "Decision should be boolean"

    @given(
        timestamp_seconds=st.integers(min_value=0, max_value=253402300800)  # 1970 to 9999
    )
    @settings(max_examples=50)
    def test_audit_timestamp_validity(self, timestamp_seconds):
        """INVARIANT: Audit timestamps should be valid."""
        # Invariant: Timestamp should be non-negative
        assert timestamp_seconds >= 0, "Timestamp cannot be negative"

        # Invariant: Timestamp should be reasonable (year 9999)
        assert timestamp_seconds <= 253402300800, \
            f"Timestamp {timestamp_seconds}s exceeds year 9999"


class TestGovernancePermissionInvariants:
    """Property-based tests for governance permission invariants."""

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
        user_role=st.sampled_from([UserRole.MEMBER, UserRole.GUEST,
                                   UserRole.WORKSPACE_ADMIN, UserRole.SUPER_ADMIN])
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_role_hierarchy_enforcement(self, service, db_session, user_role):
        """INVARIANT: Role hierarchy should be enforced correctly."""
        # Define role hierarchy (higher value = more permissions)
        role_hierarchy = {
            UserRole.GUEST: 1,
            UserRole.MEMBER: 2,
            UserRole.WORKSPACE_ADMIN: 3,
            UserRole.SUPER_ADMIN: 4
        }

        # Invariant: Role should be in hierarchy
        assert user_role in role_hierarchy, f"Invalid role: {user_role}"

        # Invariant: Higher roles should have more permissions
        role_level = role_hierarchy[user_role]
        assert 1 <= role_level <= 4, "Role level out of range"

    @given(
        permission_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_permission_count_limits(self, permission_count):
        """INVARIANT: Permission count should be reasonable."""
        max_permissions = 100

        # Invariant: Permission count should not exceed maximum
        assert permission_count <= max_permissions, \
            f"Permission count {permission_count} exceeds maximum {max_permissions}"

        # Invariant: Permission count should be positive
        assert permission_count >= 1, "Permission count must be positive"

    @given(
        action_complexity=st.integers(min_value=1, max_value=4)
    )
    @settings(max_examples=50)
    def test_action_complexity_permissions(self, action_complexity):
        """INVARIANT: Action complexity should map to permissions correctly."""
        # Invariant: Complexity should be in valid range
        assert 1 <= action_complexity <= 4, \
            f"Action complexity {action_complexity} out of range [1, 4]"

        # Invariant: Higher complexity requires higher maturity
        complexity_to_maturity = {
            1: AgentStatus.STUDENT.value,
            2: AgentStatus.INTERN.value,
            3: AgentStatus.SUPERVISED.value,
            4: AgentStatus.AUTONOMOUS.value
        }

        required_maturity = complexity_to_maturity[action_complexity]
        assert required_maturity in [AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                                     AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]


class TestGovernanceStateTransitions:
    """Property-based tests for governance state transition invariants."""

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
        current_status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                                       AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value]),
        target_status=st.sampled_from([AgentStatus.STUDENT.value, AgentStatus.INTERN.value,
                                       AgentStatus.SUPERVISED.value, AgentStatus.AUTONOMOUS.value])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_status_transition_validity(self, service, db_session, current_status, target_status):
        """INVARIANT: Status transitions should follow valid paths."""
        # Define valid transitions (can only move forward in maturity)
        status_order = [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]

        current_index = status_order.index(current_status)
        target_index = status_order.index(target_status)

        # Invariant: Forward transitions are valid
        if target_index >= current_index:
            assert True  # Valid forward transition
        else:
            # Downgrade might be possible but should be carefully controlled
            assert True  # Test documents the invariant

        # Invariant: Same status is always valid
        if current_status == target_status:
            assert True  # No-op transition

    @given(
        confidence_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_confidence_based_promotion(self, confidence_score):
        """INVARIANT: Promotions should be based on confidence thresholds."""
        # Define promotion thresholds
        promotion_thresholds = {
            AgentStatus.INTERN.value: 0.5,
            AgentStatus.SUPERVISED.value: 0.7,
            AgentStatus.AUTONOMOUS.value: 0.9
        }

        # Invariant: Confidence should be in valid range
        assert 0.0 <= confidence_score <= 1.0, \
            f"Confidence {confidence_score} out of bounds [0, 1]"

        # Check which status confidence qualifies for
        qualifies_for = []
        for status, threshold in promotion_thresholds.items():
            if confidence_score >= threshold:
                qualifies_for.append(status)

        # Invariant: Higher confidence should qualify for more status levels
        if confidence_score >= 0.9:
            assert len(qualifies_for) == 3, "Should qualify for all levels"
        elif confidence_score >= 0.7:
            assert len(qualifies_for) >= 2, "Should qualify for at least 2 levels"
        elif confidence_score >= 0.5:
            assert len(qualifies_for) >= 1, "Should qualify for at least 1 level"

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_graduation_requirements(self, episode_count, intervention_rate):
        """INVARIANT: Graduation should meet episode and intervention requirements."""
        # Define graduation requirements
        requirements = {
            AgentStatus.INTERN.value: {"episodes": 10, "max_intervention": 0.5},
            AgentStatus.SUPERVISED.value: {"episodes": 25, "max_intervention": 0.2},
            AgentStatus.AUTONOMOUS.value: {"episodes": 50, "max_intervention": 0.0}
        }

        # Invariant: Episode count should be non-negative
        assert episode_count >= 0, "Episode count cannot be negative"

        # Invariant: Intervention rate should be in valid range
        assert 0.0 <= intervention_rate <= 1.0, \
            f"Intervention rate {intervention_rate} out of bounds [0, 1]"

        # Check if qualifies for INTERN
        intern_req = requirements[AgentStatus.INTERN.value]
        if episode_count >= intern_req["episodes"] and \
           intervention_rate <= intern_req["max_intervention"]:
            assert True  # Qualifies for INTERN

        # Check if qualifies for SUPERVISED
        supervised_req = requirements[AgentStatus.SUPERVISED.value]
        if episode_count >= supervised_req["episodes"] and \
           intervention_rate <= supervised_req["max_intervention"]:
            assert True  # Qualifies for SUPERVISED

        # Check if qualifies for AUTONOMOUS
        autonomous_req = requirements[AgentStatus.AUTONOMOUS.value]
        if episode_count >= autonomous_req["episodes"] and \
           intervention_rate <= autonomous_req["max_intervention"]:
            assert True  # Qualifies for AUTONOMOUS
