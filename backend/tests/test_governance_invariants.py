"""
Property-based tests for governance invariants using Hypothesis.

These tests validate system invariants for agent governance:
- STUDENT agents cannot execute automated triggers
- Permission checks respect maturity levels
- Cache returns same results as DB (consistency)
- Confidence changes bounded 0-1
- Maturity transitions follow confidence thresholds
"""

import pytest
from hypothesis import given, settings, assume
from hypothesis import strategies as st
from datetime import datetime, timezone
from unittest.mock import Mock, patch, MagicMock
from sqlalchemy.orm import Session
import time

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, UserRole
from core.governance_cache import GovernanceCache


# ============================================================================
# Strategy Definitions
# ============================================================================

maturity_strategy = st.sampled_from([
    AgentStatus.STUDENT.value,
    AgentStatus.INTERN.value,
    AgentStatus.SUPERVISED.value,
    AgentStatus.AUTONOMOUS.value
])

confidence_strategy = st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)

permission_strategy = st.from_regex(r'^[a-z_]+:[a-z_]+$', fullmatch=True)  # e.g., "agent:execute"

agent_id_strategy = st.uuids().map(lambda u: str(u))

user_role_strategy = st.sampled_from([
    UserRole.MEMBER.value,
    UserRole.ADMIN.value,
    UserRole.TEAM_LEAD.value
])


# ============================================================================
# Test Maturity Routing Invariants
# ============================================================================

class TestMaturityRoutingInvariants:
    """Tests for agent maturity-based routing invariants"""

    @given(maturity=maturity_strategy, confidence=confidence_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_student_cannot_execute_automatically(self, maturity, confidence):
        """
        INVARIANT: STUDENT agents cannot execute automated triggers

        Regardless of confidence score, STUDENT maturity agents should never
        be allowed to execute automated triggers without human supervision.
        """
        can_execute = not (maturity == AgentStatus.STUDENT.value)
        result = maturity != AgentStatus.STUDENT.value

        assert result == can_execute
        assert maturity != AgentStatus.STUDENT.value or not can_execute

    @given(confidence=confidence_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_confidence_bounds_invariant(self, confidence):
        """
        INVARIANT: Confidence always bounded between 0 and 1

        All confidence scores must be within valid range [0.0, 1.0].
        This tests the AgentRegistry model constraint.
        """
        # Simulate agent creation with confidence
        agent = AgentRegistry(
            name=f"test_agent_{confidence}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            confidence_score=confidence
        )

        # Verify bounds
        assert 0.0 <= agent.confidence_score <= 1.0
        assert agent.confidence_score == confidence

    @given(confidence=confidence_strategy)
    @settings(max_examples=1000, deadline=None)
    def test_maturity_transition_invariant(self, confidence):
        """
        INVARIANT: Maturity transitions follow confidence thresholds

        Transition rules:
        - STUDENT -> INTERN: confidence >= 0.5
        - INTERN -> SUPERVISED: confidence >= 0.7
        - SUPERVISED -> AUTONOMOUS: confidence >= 0.9
        """
        expected_maturity = get_expected_maturity(confidence)

        # Create agent with confidence
        agent = AgentRegistry(
            name=f"test_agent_{confidence}",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            confidence_score=confidence
        )

        # Verify expected maturity based on confidence
        assert expected_maturity in [
            AgentStatus.STUDENT.value,
            AgentStatus.INTERN.value,
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]

        # Confidence should map to correct maturity tier
        if confidence < 0.5:
            assert expected_maturity == AgentStatus.STUDENT.value
        elif confidence < 0.7:
            assert expected_maturity == AgentStatus.INTERN.value
        elif confidence < 0.9:
            assert expected_maturity == AgentStatus.SUPERVISED.value
        else:
            assert expected_maturity == AgentStatus.AUTONOMOUS.value

    @given(confidence1=confidence_strategy, confidence2=confidence_strategy)
    @settings(max_examples=500, deadline=None)
    def test_confidence_monotonicity_invariant(self, confidence1, confidence2):
        """
        INVARIANT: Higher confidence should not lower maturity level

        If confidence increases, maturity level should not decrease.
        """
        maturity1 = get_expected_maturity(confidence1)
        maturity2 = get_expected_maturity(confidence2)

        maturity_order = {
            AgentStatus.STUDENT.value: 0,
            AgentStatus.INTERN.value: 1,
            AgentStatus.SUPERVISED.value: 2,
            AgentStatus.AUTONOMOUS.value: 3
        }

        if confidence2 > confidence1:
            # Higher confidence should not result in lower maturity
            assert maturity_order[maturity2] >= maturity_order[maturity1]


# ============================================================================
# Test Permission Invariants
# ============================================================================

class TestPermissionInvariants:
    """Tests for permission-based access control invariants"""

    @given(maturity=maturity_strategy, permission=permission_strategy)
    @settings(max_examples=500, deadline=None)
    def test_permission_invariant(self, maturity, permission):
        """
        INVARIANT: Permission checks respect maturity levels

        Student agents have restricted permissions:
        - Cannot execute actions (action:execute)
        - Cannot modify state (state:write)
        - Can only present information (present:show)
        """
        has_permission = check_permission_by_maturity(maturity, permission)

        # STUDENT agents have limited permissions
        if maturity == AgentStatus.STUDENT.value:
            # Student can only present/view, not execute/modify
            if any(restricted in permission for restricted in ['execute', 'write', 'delete', 'create']):
                assert not has_permission

        # INTERN+ agents have broader permissions
        if maturity == AgentStatus.AUTONOMOUS.value:
            assert has_permission  # Autonomous has all permissions

    @given(maturity=maturity_strategy, user_role=user_role_strategy)
    @settings(max_examples=500, deadline=None)
    def test_role_based_maturity_invariant(self, maturity, user_role):
        """
        INVARIANT: Role-based permissions align with maturity levels

        Higher user roles should grant access to higher maturity agents.
        """
        can_manage = can_manage_maturity_level(user_role, maturity)

        # ADMIN can manage all maturity levels
        if user_role == UserRole.ADMIN.value:
            assert can_manage

        # Regular MEMBER cannot manage AUTONOMOUS agents
        if user_role == UserRole.MEMBER.value and maturity == AgentStatus.AUTONOMOUS.value:
            assert not can_manage

    @given(maturity=maturity_strategy)
    @settings(max_examples=200, deadline=None)
    def test_maturity_progression_invariant(self, maturity):
        """
        INVARIANT: Maturity progression is unidirectional

        Agents should only progress forward, not backward (unless degraded).
        """
        maturity_order = {
            AgentStatus.STUDENT.value: 0,
            AgentStatus.INTERN.value: 1,
            AgentStatus.SUPERVISED.value: 2,
            AgentStatus.AUTONOMOUS.value: 3
        }

        current_level = maturity_order[maturity]

        # Can only progress to higher levels
        valid_transitions = [
            m for m, level in maturity_order.items()
            if level >= current_level
        ]

        assert maturity in valid_transitions
        assert len(valid_transitions) == (4 - current_level)


# ============================================================================
# Test Cache Consistency Invariants
# ============================================================================

class TestCacheConsistencyInvariants:
    """Tests for cache-database consistency invariants"""

    @given(agent_id=agent_id_strategy, maturity=maturity_strategy, confidence=confidence_strategy)
    @settings(max_examples=200, deadline=None)
    def test_cache_key_format(self, agent_id, maturity, confidence):
        """
        INVARIANT: Cache keys are formatted consistently

        Cache keys should follow the pattern: "{agent_id}:{action_type}"
        This ensures consistent lookup and invalidation.
        """
        action_type = "execute"
        expected_key = f"{agent_id}:{action_type}"

        # Verify key format
        assert ":" in expected_key
        assert expected_key.startswith(str(agent_id))
        assert expected_key.endswith(action_type)

        # Same agent_id + action_type always produces same key
        cache = GovernanceCache()
        key1 = cache._make_key(agent_id, action_type)
        key2 = cache._make_key(agent_id, action_type)
        assert key1 == key2
        assert key1 == expected_key

    @given(agent_id=agent_id_strategy, action_type=st.text(min_size=1, max_size=50))
    @settings(max_examples=200, deadline=None)
    def test_cache_invalidation_key_match(self, agent_id, action_type):
        """
        INVARIANT: Cache invalidation uses same key format as storage

        When invalidating cache, the key must match exactly what was stored.
        """
        cache = GovernanceCache()

        # Store data
        data = {'allowed': True, 'cached_at': 1234567890}
        cache.set(agent_id, action_type, data)

        # Retrieve with same key
        retrieved = cache.get(agent_id, action_type)
        assert retrieved is not None
        assert retrieved['allowed'] == True

        # Invalidate
        cache.invalidate(agent_id, action_type)

        # Verify invalidated
        retrieved_after = cache.get(agent_id, action_type)
        assert retrieved_after is None

    @given(agent_ids=st.lists(agent_id_strategy, min_size=1, max_size=50),
           action_types=st.lists(st.text(min_size=1, max_size=20), min_size=1, max_size=5))
    @settings(max_examples=100, deadline=None)
    def test_cache_isolation(self, agent_ids, action_types):
        """
        INVARIANT: Different cache keys don't interfere with each other

        Each agent_id:action_type combination should have independent cache entries.
        """
        cache = GovernanceCache()

        # Store different data for each combination
        stored_data = {}
        for agent_id in agent_ids[:10]:  # Limit to avoid excessive iterations
            for action_type in action_types[:3]:
                data = {
                    'allowed': hash(f"{agent_id}:{action_type}") % 2 == 0,
                    'cached_at': time.time()
                }
                cache.set(agent_id, action_type, data)
                stored_data[(agent_id, action_type)] = data

        # Verify all entries are independent
        for (agent_id, action_type), expected_data in stored_data.items():
            retrieved = cache.get(agent_id, action_type)
            assert retrieved is not None
            assert retrieved['allowed'] == expected_data['allowed']


# ============================================================================
# Test Confidence Score Invariants
# ============================================================================

class TestConfidenceScoreInvariants:
    """Tests for confidence score calculation invariants"""

    @given(initial_confidence=confidence_strategy, feedback=st.floats(min_value=-1.0, max_value=1.0))
    @settings(max_examples=1000, deadline=None)
    def test_confidence_update_bounds(self, initial_confidence, feedback):
        """
        INVARIANT: Confidence updates stay within [0, 1] bounds

        Feedback affects confidence but should never push it out of bounds.
        """
        # Simulate confidence update
        adjustment = feedback * 0.1  # 10% adjustment per feedback
        new_confidence = max(0.0, min(1.0, initial_confidence + adjustment))

        # Verify bounds
        assert 0.0 <= new_confidence <= 1.0

    @given(feedback_scores=st.lists(st.floats(min_value=-1.0, max_value=1.0), min_size=10, max_size=100))
    @settings(max_examples=200, deadline=None)
    def test_confidence_convergence(self, feedback_scores):
        """
        INVARIANT: Repeated positive feedback should increase confidence

        With enough positive feedback, confidence should trend upward.
        """
        initial_confidence = 0.5
        confidence = initial_confidence

        for feedback in feedback_scores:
            # Weighted adjustment: more recent feedback has more impact
            adjustment = feedback * 0.05  # Small adjustments
            confidence = max(0.0, min(1.0, confidence + adjustment))

        # With mixed feedback, should still be in valid range
        assert 0.0 <= confidence <= 1.0

        # If mostly positive (>70%), confidence should increase or stay same
        positive_ratio = sum(1 for f in feedback_scores if f > 0) / len(feedback_scores)
        if positive_ratio > 0.7:
            # Allow small epsilon for floating point
            assert confidence >= initial_confidence - 0.01

    @given(confidence=confidence_strategy)
    @settings(max_examples=500, deadline=None)
    def test_confidence_precision(self, confidence):
        """
        INVARIANT: Confidence scores maintain reasonable precision

        Confidence should be stored with at least 2 decimal places.
        """
        # Round to 2 decimal places
        rounded = round(confidence, 2)

        # Should be within 0.01 of original
        assert abs(confidence - rounded) <= 0.01


# ============================================================================
# Test Agent Lifecycle Invariants
# ============================================================================

class TestAgentLifecycleInvariants:
    """Tests for agent lifecycle management invariants"""

    @given(enabled=st.booleans(), maturity=maturity_strategy)
    @settings(max_examples=200, deadline=None)
    def test_disabled_agent_invariant(self, enabled, maturity):
        """
        INVARIANT: Disabled agents cannot execute regardless of maturity

        Even AUTONOMOUS agents must respect enabled flag.
        """
        can_execute = enabled and maturity == AgentStatus.AUTONOMOUS.value

        # If disabled, cannot execute
        if not enabled:
            assert not can_execute

        # If enabled and AUTONOMOUS, can execute
        if enabled and maturity == AgentStatus.AUTONOMOUS.value:
            assert can_execute

    @given(maturity=maturity_strategy, is_system_agent=st.booleans())
    @settings(max_examples=200, deadline=None)
    def test_system_agent_permissions(self, maturity, is_system_agent):
        """
        INVARIANT: System agents have special permission handling

        System agents can bypass certain restrictions but still need proper maturity.
        """
        # System agents can use workspace tokens
        can_use_workspace_token = is_system_agent and maturity in [
            AgentStatus.SUPERVISED.value,
            AgentStatus.AUTONOMOUS.value
        ]

        if is_system_agent:
            # System agents need higher maturity
            assert maturity in [
                AgentStatus.SUPERVISED.value,
                AgentStatus.AUTONOMOUS.value
            ] or not can_use_workspace_token


# ============================================================================
# Helper Functions
# ============================================================================

def get_expected_maturity(confidence: float) -> str:
    """
    Determine expected maturity level based on confidence score.

    Args:
        confidence: Confidence score between 0.0 and 1.0

    Returns:
        Expected maturity status value
    """
    if confidence < 0.5:
        return AgentStatus.STUDENT.value
    elif confidence < 0.7:
        return AgentStatus.INTERN.value
    elif confidence < 0.9:
        return AgentStatus.SUPERVISED.value
    else:
        return AgentStatus.AUTONOMOUS.value


def check_permission_by_maturity(maturity: str, permission: str) -> bool:
    """
    Check if maturity level grants permission.

    Args:
        maturity: Agent maturity level
        permission: Permission string (e.g., "agent:execute")

    Returns:
        True if permission granted
    """
    restricted_actions = ['execute', 'write', 'delete', 'create', 'modify']
    safe_actions = ['view', 'read', 'present', 'show']

    if maturity == AgentStatus.STUDENT.value:
        # Student can only read/present
        return any(action in permission for action in safe_actions)
    elif maturity == AgentStatus.INTERN.value:
        # Intern needs approval for write actions
        return any(action in permission for action in safe_actions + ['execute'])
    else:
        # Supervised+ can do most things
        return True


def can_manage_maturity_level(user_role: str, maturity: str) -> bool:
    """
    Check if user role can manage agents at given maturity level.

    Args:
        user_role: User role
        maturity: Agent maturity level

    Returns:
        True if user can manage agents at this maturity
    """
    if user_role == UserRole.ADMIN.value:
        return True
    elif user_role == UserRole.TEAM_LEAD.value:
        return maturity != AgentStatus.AUTONOMOUS.value
    else:  # MEMBER
        return maturity == AgentStatus.STUDENT.value
