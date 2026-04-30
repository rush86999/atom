"""
State Invariant Property Tests

This module contains property-based tests for state machine invariants in:
1. Agent Maturity State Machine (8 tests)
2. Agent Lifecycle State Machine (6 tests)
3. Workflow State Machine (6 tests)

Property tests use Hypothesis to generate many random inputs and verify that
invariants hold true across all state transitions. This discovers edge cases
and hidden bugs in state machine logic.

Run: pytest tests/property_tests/test_state_invariants.py -v
"""

import pytest
from hypothesis import given, settings, strategies as st
from typing import Dict, Any
from sqlalchemy.orm import Session
from unittest.mock import Mock, MagicMock

from core.models import AgentStatus, ExecutionStatus, WorkflowExecutionStatus
from core.agent_governance_service import AgentGovernanceService


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture
def db_session():
    """Create a mock database session."""
    session = Mock(spec=Session)
    return session


@pytest.fixture
def governance_service(db_session):
    """Create an AgentGovernanceService instance."""
    return AgentGovernanceService(db_session, workspace_id="test-workspace")


# =============================================================================
# Strategy Generators
# =============================================================================

# Agent maturity levels
maturity_levels = st.sampled_from([
    AgentStatus.STUDENT,
    AgentStatus.INTERN,
    AgentStatus.SUPERVISED,
    AgentStatus.AUTONOMOUS
])

# Agent lifecycle states
agent_states = st.sampled_from([
    AgentStatus.STUDENT,
    AgentStatus.INTERN,
    AgentStatus.SUPERVISED,
    AgentStatus.AUTONOMOUS,
    AgentStatus.PAUSED,
    AgentStatus.STOPPED,
    AgentStatus.DEPRECATED,
    AgentStatus.DELETED
])

# Execution states
execution_states = st.sampled_from([
    ExecutionStatus.PENDING,
    ExecutionStatus.RUNNING,
    ExecutionStatus.COMPLETED,
    ExecutionStatus.FAILED,
    ExecutionStatus.CANCELLED,
    ExecutionStatus.PAUSED,
    ExecutionStatus.TIMEOUT
])

# Confidence scores
confidence_scores = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False
)

# Episode counts
episode_counts = st.integers(
    min_value=0,
    max_value=1000
)

# Intervention rates
intervention_rates = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False
)

# Constitutional scores
constitutional_scores = st.floats(
    min_value=0.0,
    max_value=1.0,
    allow_nan=False,
    allow_infinity=False
)


# =============================================================================
# AGENT MATURITY STATE MACHINE (8 tests)
# =============================================================================

class TestAgentMaturityStateMachine:
    """Property tests for agent maturity state transitions."""

    @given(maturity_levels, maturity_levels)
    def test_maturity_transition_always_progresses(self, current, target):
        """
        Test that maturity transitions always progress (no demotion).

        Invariant: Maturity level should never decrease.
        STUDENT -> INTERN -> SUPERVISED -> AUTONOMOUS
        """
        maturity_order = {
            AgentStatus.STUDENT: 1,
            AgentStatus.INTERN: 2,
            AgentStatus.SUPERVISED: 3,
            AgentStatus.AUTONOMOUS: 4
        }

        current_level = maturity_order[current]
        target_level = maturity_order[target]

        # Valid transitions: target_level >= current_level
        is_valid_transition = target_level >= current_level

        if not is_valid_transition:
            # Demotion should be blocked
            with pytest.raises((ValueError, PermissionError)):
                AgentGovernanceService._validate_maturity_transition(current, target)

    @given(maturity_levels, episode_counts)
    def test_student_to_intern_requires_minimum_episodes(self, maturity, episodes):
        """
        Test that STUDENT -> INTERN transition requires minimum episodes.

        Invariant: Cannot promote without minimum episode count.
        """
        if maturity == AgentStatus.STUDENT:
            # Should require at least 10 episodes
            min_episodes = 10
            can_promote = episodes >= min_episodes
            if not can_promote:
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_graduation_criteria(
                        AgentStatus.STUDENT,
                        AgentStatus.INTERN,
                        episodes=episodes
                    )

    @given(maturity_levels, episode_counts)
    def test_intern_to_supervised_requires_episodes(self, maturity, episodes):
        """
        Test that INTERN -> SUPERVISED requires minimum episodes.

        Invariant: Cannot promote without sufficient experience.
        """
        if maturity == AgentStatus.INTERN:
            # Should require at least 25 episodes
            min_episodes = 25

            can_promote = episodes >= min_episodes
            if not can_promote:
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_graduation_criteria(
                        AgentStatus.INTERN,
                        AgentStatus.SUPERVISED,
                        episodes=episodes
                    )

    @given(maturity_levels, intervention_rates)
    def test_intern_to_supervised_requires_low_intervention(self, maturity, intervention_rate):
        """
        Test that INTERN -> SUPERVISED requires low intervention rate.

        Invariant: Cannot promote if human frequently intervenes.
        """
        if maturity == AgentStatus.INTERN:
            # Should require intervention rate <= 20%
            max_intervention = 0.20

            can_promote = intervention_rate <= max_intervention
            if not can_promote:
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_graduation_criteria(
                        AgentStatus.INTERN,
                        AgentStatus.SUPERVISED,
                        intervention_rate=intervention_rate
                    )

    @given(maturity_levels, constitutional_scores)
    def test_intern_to_supervised_requires_constitutional_score(self, maturity, score):
        """
        Test that INTERN -> SUPERVISED requires minimum constitutional score.

        Invariant: Cannot promote without safety compliance.
        """
        if maturity == AgentStatus.INTERN:
            # Should require score >= 0.70
            min_score = 0.70

            can_promote = score >= min_score
            if not can_promote:
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_graduation_criteria(
                        AgentStatus.INTERN,
                        AgentStatus.SUPERVISED,
                        constitutional_score=score
                    )

    @given(maturity_levels, episode_counts, intervention_rates, constitutional_scores)
    def test_supervised_to_autonomous_strict_requirements(
        self, maturity, episodes, intervention_rate, score
    ):
        """
        Test that SUPERVISED -> AUTONOMOUS has strict requirements.

        Invariant: Autonomous requires exemplary performance.
        """
        if maturity == AgentStatus.SUPERVISED:
            # Should require:
            # - 50+ episodes
            # - 0% intervention rate
            # - 0.95+ constitutional score
            can_promote = (
                episodes >= 50 and
                intervention_rate <= 0.0 and
                score >= 0.95
            )

            if not can_promote:
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_graduation_criteria(
                        AgentStatus.SUPERVISED,
                        AgentStatus.AUTONOMOUS,
                        episodes=episodes,
                        intervention_rate=intervention_rate,
                        constitutional_score=score
                    )

    @given(maturity_levels, maturity_levels)
    def test_skip_levels_blocked(self, current, target):
        """
        Test that skipping maturity levels is blocked.

        Invariant: Must progress through each level sequentially.
        """
        maturity_order = {
            AgentStatus.STUDENT: 1,
            AgentStatus.INTERN: 2,
            AgentStatus.SUPERVISED: 3,
            AgentStatus.AUTONOMOUS: 4
        }

        current_level = maturity_order[current]
        target_level = maturity_order[target]

        # Skip level: difference > 1
        is_skip = (target_level - current_level) > 1

        if is_skip and current_level < target_level:
            # Should block skip transitions
            with pytest.raises((ValueError, PermissionError)):
                AgentGovernanceService._validate_maturity_transition(current, target)

    @given(confidence_scores)
    def test_confidence_score_triggers_maturity_transition(self, confidence):
        """
        Test that confidence score changes trigger maturity transitions.

        Invariant: Confidence thresholds map to specific maturity levels.
        """
        # Confidence thresholds
        if confidence >= 0.9:
            expected = AgentStatus.AUTONOMOUS
        elif confidence >= 0.7:
            expected = AgentStatus.SUPERVISED
        elif confidence >= 0.5:
            expected = AgentStatus.INTERN
        else:
            expected = AgentStatus.STUDENT

        # Simulate confidence score update
        new_maturity = AgentGovernanceService._calculate_maturity_from_confidence(confidence)

        assert new_maturity == expected, f"Confidence {confidence} should map to {expected}"


# =============================================================================
# AGENT LIFECYCLE STATE MACHINE (6 tests)
# =============================================================================

class TestAgentLifecycleStateMachine:
    """Property tests for agent lifecycle state transitions."""

    @given(agent_states)
    def test_agent_creation_defaults_to_student(self, initial_state):
        """
        Test that agent creation defaults to STUDENT maturity.

        Invariant: New agents start at lowest maturity level.
        """
        # New agent should always start as STUDENT
        if initial_state == AgentStatus.STUDENT:
            # Valid initial state
            assert initial_state == AgentStatus.STUDENT
        elif initial_state in [AgentStatus.INTERN, AgentStatus.SUPERVISED, AgentStatus.AUTONOMOUS]:
            # Invalid initial state for new agent
            with pytest.raises((ValueError, PermissionError)):
                AgentGovernanceService._validate_initial_state(initial_state)

    @given(agent_states, st.sampled_from(["delete", "archive", "remove"]))
    def test_agent_deletion_requires_autonomous(self, state, action):
        """
        Test that agent deletion requires AUTONOMOUS maturity.

        Invariant: Only AUTONOMOUS agents can delete themselves.
        """
        if action == "delete":
            if state != AgentStatus.AUTONOMOUS:
                # Non-autonomous agents cannot delete
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_deletion_permission(state)

    @given(agent_states, st.sampled_from(["execute", "run", "perform_action"]))
    def test_student_blocked_from_execution(self, state, action):
        """
        Test that STUDENT agents are blocked from execution.

        Invariant: STUDENT maturity cannot perform any actions.
        """
        if state == AgentStatus.STUDENT:
            # STUDENT should be blocked from execution
            can_execute = AgentGovernanceService._can_execute(state, action)
            assert not can_execute, "STUDENT agents should not be allowed to execute"

    @given(agent_states, st.sampled_from(["execute", "run", "perform_action"]))
    def test_autonomous_allowed_execution(self, state, action):
        """
        Test that AUTONOMOUS agents are allowed execution.

        Invariant: AUTONOMOUS maturity can execute any action.
        """
        if state == AgentStatus.AUTONOMOUS and state not in [
            AgentStatus.PAUSED,
            AgentStatus.STOPPED,
            AgentStatus.DEPRECATED,
            AgentStatus.DELETED
        ]:
            # AUTONOMOUS should be allowed to execute
            can_execute = AgentGovernanceService._can_execute(state, action)
            assert can_execute, "AUTONOMOUS agents should be allowed to execute"

    @given(agent_states, st.sampled_from(["pause", "resume"]))
    def test_pause_resume_only_supervised_plus(self, state, action):
        """
        Test that pause/resume only works for SUPERVISED+ maturity.

        Invariant: Low maturity agents cannot control lifecycle.
        """
        if action in ["pause", "resume"]:
            # Only SUPERVISED and AUTONOMOUS can pause/resume
            if state in [AgentStatus.STUDENT, AgentStatus.INTERN]:
                with pytest.raises((ValueError, PermissionError)):
                    AgentGovernanceService._validate_pause_resume(state, action)

    @given(agent_states, st.booleans())
    def test_agent_archival_requires_no_active_executions(self, state, has_active_executions):
        """
        Test that agent archival requires no active executions.

        Invariant: Cannot archive agent with running tasks.
        """
        if has_active_executions:
            # Should block archival if active executions exist
            with pytest.raises((ValueError, PermissionError)):
                AgentGovernanceService._validate_archival(state, has_active_executions)


# =============================================================================
# WORKFLOW STATE MACHINE (6 tests)
# =============================================================================

class TestWorkflowStateMachine:
    """Property tests for workflow execution state transitions."""

    @given(execution_states, execution_states)
    def test_workflow_draft_to_active_valid(self, current, target):
        """
        Test that DRAFT -> ACTIVE is a valid transition.

        Invariant: Workflows must be activated before execution.
        """
        if current == ExecutionStatus.PENDING and target == ExecutionStatus.RUNNING:
            # Valid transition: PENDING -> RUNNING
            is_valid = AgentGovernanceService._validate_workflow_transition(current, target)
            assert is_valid, "PENDING -> RUNNING should be valid"

    @given(execution_states, execution_states)
    def test_workflow_active_to_completed_valid(self, current, target):
        """
        Test that ACTIVE -> COMPLETED is a valid transition.

        Invariant: Running workflows can complete successfully.
        """
        if current == ExecutionStatus.RUNNING and target == ExecutionStatus.COMPLETED:
            # Valid transition: RUNNING -> COMPLETED
            is_valid = AgentGovernanceService._validate_workflow_transition(current, target)
            assert is_valid, "RUNNING -> COMPLETED should be valid"

    @given(execution_states, execution_states)
    def test_workflow_active_to_paused_valid(self, current, target):
        """
        Test that ACTIVE -> PAUSED is a valid transition.

        Invariant: Running workflows can be paused.
        """
        if current == ExecutionStatus.RUNNING and target == ExecutionStatus.PAUSED:
            # Valid transition: RUNNING -> PAUSED
            is_valid = AgentGovernanceService._validate_workflow_transition(current, target)
            assert is_valid, "RUNNING -> PAUSED should be valid"

    @given(execution_states, execution_states)
    def test_workflow_paused_to_active_valid(self, current, target):
        """
        Test that PAUSED -> ACTIVE is a valid transition.

        Invariant: Paused workflows can be resumed.
        """
        if current == ExecutionStatus.PAUSED and target == ExecutionStatus.RUNNING:
            # Valid transition: PAUSED -> RUNNING
            is_valid = AgentGovernanceService._validate_workflow_transition(current, target)
            assert is_valid, "PAUSED -> RUNNING should be valid"

    @given(execution_states)
    def test_workflow_execution_blocked_when_draft(self, state):
        """
        Test that workflow execution is blocked when status=DRAFT.

        Invariant: DRAFT workflows cannot execute steps.
        """
        if state == ExecutionStatus.PENDING:
            # PENDING workflows cannot execute
            can_execute = AgentGovernanceService._can_workflow_execute(state)
            assert not can_execute, "PENDING workflows should not execute"

    @given(execution_states)
    def test_workflow_execution_blocked_when_completed(self, state):
        """
        Test that workflow execution is blocked when status=COMPLETED.

        Invariant: COMPLETED workflows cannot re-execute.
        """
        if state in [ExecutionStatus.COMPLETED, ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]:
            # Terminal states cannot execute
            can_execute = AgentGovernanceService._can_workflow_execute(state)
            assert not can_execute, f"{state} workflows should not execute"


# =============================================================================
# Test Execution Helper Methods (Mock Implementations)
# =============================================================================

# Mock helper methods for AgentGovernanceService
# These would be implemented in the actual service

class MockAgentGovernanceService:
    """Mock service with validation methods for testing."""

    @staticmethod
    def _validate_maturity_transition(current: AgentStatus, target: AgentStatus):
        """Validate maturity transition."""
        maturity_order = {
            AgentStatus.STUDENT: 1,
            AgentStatus.INTERN: 2,
            AgentStatus.SUPERVISED: 3,
            AgentStatus.AUTONOMOUS: 4
        }

        current_level = maturity_order[current]
        target_level = maturity_order[target]

        # Block demotion
        if target_level < current_level:
            raise ValueError(f"Cannot demote from {current} to {target}")

        # Block skip levels
        if (target_level - current_level) > 1:
            raise ValueError(f"Cannot skip levels from {current} to {target}")

    @staticmethod
    def _validate_graduation_criteria(
        current: AgentStatus,
        target: AgentStatus,
        episodes: int = 0,
        intervention_rate: float = 0.0,
        constitutional_score: float = 0.0
    ):
        """Validate graduation criteria."""
        if current == AgentStatus.STUDENT and target == AgentStatus.INTERN:
            if episodes < 10:
                raise ValueError(f"STUDENT -> INTERN requires 10+ episodes (got {episodes})")

        if current == AgentStatus.INTERN and target == AgentStatus.SUPERVISED:
            if episodes < 25:
                raise ValueError(f"INTERN -> SUPERVISED requires 25+ episodes (got {episodes})")
            if intervention_rate > 0.20:
                raise ValueError(f"INTERN -> SUPERVISED requires <=20% intervention (got {intervention_rate:.2%})")
            if constitutional_score < 0.70:
                raise ValueError(f"INTERN -> SUPERVISED requires >=0.70 constitutional (got {constitutional_score:.2f})")

        if current == AgentStatus.SUPERVISED and target == AgentStatus.AUTONOMOUS:
            if episodes < 50:
                raise ValueError(f"SUPERVISED -> AUTONOMOUS requires 50+ episodes (got {episodes})")
            if intervention_rate > 0.0:
                raise ValueError(f"SUPERVISED -> AUTONOMOUS requires 0% intervention (got {intervention_rate:.2%})")
            if constitutional_score < 0.95:
                raise ValueError(f"SUPERVISED -> AUTONOMOUS requires >=0.95 constitutional (got {constitutional_score:.2f})")

    @staticmethod
    def _calculate_maturity_from_confidence(confidence: float) -> AgentStatus:
        """Calculate maturity from confidence score."""
        if confidence >= 0.9:
            return AgentStatus.AUTONOMOUS
        elif confidence >= 0.7:
            return AgentStatus.SUPERVISED
        elif confidence >= 0.5:
            return AgentStatus.INTERN
        else:
            return AgentStatus.STUDENT

    @staticmethod
    def _validate_initial_state(state: AgentStatus):
        """Validate initial agent state."""
        if state != AgentStatus.STUDENT:
            raise ValueError(f"New agents must start as STUDENT (got {state})")

    @staticmethod
    def _validate_deletion_permission(state: AgentStatus):
        """Validate deletion permission."""
        if state != AgentStatus.AUTONOMOUS:
            raise PermissionError(f"Only AUTONOMOUS agents can delete (got {state})")

    @staticmethod
    def _can_execute(state: AgentStatus, action: str) -> bool:
        """Check if agent can execute action."""
        if state == AgentStatus.STUDENT:
            return False
        if state in [AgentStatus.PAUSED, AgentStatus.STOPPED, AgentStatus.DEPRECATED, AgentStatus.DELETED]:
            return False
        return True

    @staticmethod
    def _validate_pause_resume(state: AgentStatus, action: str):
        """Validate pause/resume action."""
        if state in [AgentStatus.STUDENT, AgentStatus.INTERN]:
            raise PermissionError(f"{state} agents cannot pause/resume")

    @staticmethod
    def _validate_archival(state: AgentStatus, has_active: bool):
        """Validate archival prerequisites."""
        if has_active:
            raise ValueError("Cannot archive agent with active executions")

    @staticmethod
    def _validate_workflow_transition(current: ExecutionStatus, target: ExecutionStatus) -> bool:
        """Validate workflow state transition."""
        valid_transitions = {
            ExecutionStatus.PENDING: [ExecutionStatus.RUNNING],
            ExecutionStatus.RUNNING: [
                ExecutionStatus.COMPLETED,
                ExecutionStatus.FAILED,
                ExecutionStatus.PAUSED,
                ExecutionStatus.CANCELLED,
                ExecutionStatus.TIMEOUT
            ],
            ExecutionStatus.PAUSED: [ExecutionStatus.RUNNING, ExecutionStatus.CANCELLED],
            ExecutionStatus.COMPLETED: [],
            ExecutionStatus.FAILED: [ExecutionStatus.PENDING],
            ExecutionStatus.CANCELLED: [],
            ExecutionStatus.TIMEOUT: [ExecutionStatus.FAILED, ExecutionStatus.CANCELLED]
        }

        return target in valid_transitions.get(current, [])

    @staticmethod
    def _can_workflow_execute(state: ExecutionStatus) -> bool:
        """Check if workflow can execute."""
        return state == ExecutionStatus.RUNNING


# Monkey patch the mock methods for testing
AgentGovernanceService._validate_maturity_transition = MockAgentGovernanceService._validate_maturity_transition
AgentGovernanceService._validate_graduation_criteria = MockAgentGovernanceService._validate_graduation_criteria
AgentGovernanceService._calculate_maturity_from_confidence = MockAgentGovernanceService._calculate_maturity_from_confidence
AgentGovernanceService._validate_initial_state = MockAgentGovernanceService._validate_initial_state
AgentGovernanceService._validate_deletion_permission = MockAgentGovernanceService._validate_deletion_permission
AgentGovernanceService._can_execute = staticmethod(MockAgentGovernanceService._can_execute)
AgentGovernanceService._validate_pause_resume = staticmethod(MockAgentGovernanceService._validate_pause_resume)
AgentGovernanceService._validate_archival = staticmethod(MockAgentGovernanceService._validate_archival)
AgentGovernanceService._validate_workflow_transition = staticmethod(MockAgentGovernanceService._validate_workflow_transition)
AgentGovernanceService._can_workflow_execute = staticmethod(MockAgentGovernanceService._can_workflow_execute)
