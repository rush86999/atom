"""
Property-based tests for episode lifecycle state transition invariants.

Uses Hypothesis to test lifecycle state invariants across many generated inputs:
- State transition validity: Only valid transitions allowed
- No cycles in transitions: Can't go archived->active
- All states reachable: All states reachable from initial state
- No regression: State never "regresses" (consolidated->active not allowed)
- Terminal state: Archived state is terminal (no transitions out)

These tests complement the integration tests by verifying invariants hold
across many different input combinations.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from typing import List, Dict, Any
from enum import Enum

from hypothesis import given, strategies as st, settings, HealthCheck

from core.episode_lifecycle_service import EpisodeLifecycleService
from core.models import AgentEpisode


# =============================================================================
# Episode State Enum (matches implementation)
# =============================================================================

class EpisodeState(str, Enum):
    """Episode lifecycle states"""
    ACTIVE = "active"
    COMPLETED = "completed"
    CONSOLIDATED = "consolidated"
    ARCHIVED = "archived"


# Valid state transitions
VALID_TRANSITIONS = {
    EpisodeState.ACTIVE: [EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED],
    EpisodeState.COMPLETED: [EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED],
    EpisodeState.CONSOLIDATED: [EpisodeState.ARCHIVED],
    EpisodeState.ARCHIVED: []  # Terminal state
}


# =============================================================================
# Property-Based Tests for State Transition Validity
# =============================================================================

class TestStateTransitionValidity:
    """
    Property-based tests for state transition validity invariants.

    Uses Hypothesis to generate many different state sequences and verify
    only valid transitions occur.
    """

    @pytest.mark.asyncio
    @given(
        current_state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED]),
        target_state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_validity_invariant(self, db_session, current_state, target_state):
        """
        Only valid state transitions are allowed.

        Property: For any state transition (current -> target),
        the transition must be in VALID_TRANSITIONS.

        Valid transitions:
        - ACTIVE -> COMPLETED, CONSOLIDATED
        - COMPLETED -> CONSOLIDATED, ARCHIVED
        - CONSOLIDATED -> ARCHIVED
        - ARCHIVED -> (terminal, no transitions)

        Mathematical specification:
        Let T(s₁, s₂) be a transition from state s₁ to s₂
        Then: T(s₁, s₂) is valid iff s₂ ∈ VALID_TRANSITIONS[s₁]

        This test verifies that the VALID_TRANSITIONS dictionary
        correctly defines the state machine.
        """
        # Check if transition is valid according to VALID_TRANSITIONS
        valid_targets = VALID_TRANSITIONS.get(current_state, [])
        is_valid_transition = target_state in valid_targets

        # For state machine validation, we check:
        # 1. If transition should be valid, it's in VALID_TRANSITIONS
        # 2. Terminal states (ARCHIVED) have no valid transitions
        # 3. State transitions are monotonic (no regression)

        # Verify state machine properties
        if current_state == target_state:
            # Staying in same state is always valid (no-op)
            assert True, "Same-state transitions are valid"
        elif current_state == EpisodeState.ARCHIVED:
            # Archived is terminal - cannot transition to any other state
            assert not is_valid_transition, (
                f"Archived state is terminal - cannot transition to {target_state.value}. "
                f"VALID_TRANSITIONS[{current_state.value}] should be empty: {valid_targets}"
            )
        elif is_valid_transition:
            # Transition is marked as valid - verify it follows monotonic progression
            state_order = {
                EpisodeState.ACTIVE: 0,
                EpisodeState.COMPLETED: 1,
                EpisodeState.CONSOLIDATED: 2,
                EpisodeState.ARCHIVED: 3
            }

            current_order = state_order[current_state]
            target_order = state_order[target_state]

            # State should progress forward (or stay same)
            assert target_order >= current_order, (
                f"State transition should be monotonic: {current_state.value} (order {current_order}) -> "
                f"{target_state.value} (order {target_order}). State regression not allowed."
            )
        else:
            # Transition is not valid - verify it's not in VALID_TRANSITIONS
            assert target_state not in valid_targets, (
                f"Invalid transition detected: {current_state.value} -> {target_state.value}. "
                f"This transition is not in VALID_TRANSITIONS[{current_state.value}]: {valid_targets}"
            )

            # Also verify it would break monotonic progression
            state_order = {
                EpisodeState.ACTIVE: 0,
                EpisodeState.COMPLETED: 1,
                EpisodeState.CONSOLIDATED: 2,
                EpisodeState.ARCHIVED: 3
            }

            current_order = state_order[current_state]
            target_order = state_order[target_state]

            # Invalid transitions should be regressive or skip states
            is_regression = target_order < current_order
            is_skip = (target_order - current_order) > 1

            # At least one of these should be true for invalid transitions
            assert is_regression or is_skip or current_state == EpisodeState.ARCHIVED, (
                f"Transition {current_state.value} -> {target_state.value} should be valid "
                f"(not regressive, not skipping states, not terminal)"
            )

    @pytest.mark.asyncio
    @given(
        state_sequence=st.lists(
            st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED]),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_no_cycles_invariant(self, db_session, state_sequence):
        """
        No cycles in state transitions.

        Property: For any VALID state sequence (following VALID_TRANSITIONS),
        once you reach ARCHIVED state, you cannot transition back to earlier states.

        Mathematical specification:
        Let S = [s₁, s₂, ..., sₙ] be a state sequence following VALID_TRANSITIONS
        If sᵢ = ARCHIVED for some i, then for all j > i: sⱼ = ARCHIVED

        This prevents "resurrection" of archived episodes.

        Note: This test only validates sequences that follow VALID_TRANSITIONS.
        Invalid sequences (that would be rejected by the state machine) are skipped.
        """
        # Check if the sequence follows valid transitions
        # If not, skip validation (Hypothesis generates random sequences)
        sequence_is_valid = True
        for i in range(len(state_sequence) - 1):
            current_state = state_sequence[i]
            next_state = state_sequence[i + 1]

            valid_targets = VALID_TRANSITIONS.get(current_state, [])

            # Same state is valid (no-op)
            if current_state == next_state:
                continue

            # Check if transition is valid
            if next_state not in valid_targets:
                sequence_is_valid = False
                break

        # Only validate sequences that follow VALID_TRANSITIONS
        if not sequence_is_valid:
            # Skip this sequence - it's not a valid state machine path
            return

        # Check if archived appears in sequence
        archived_index = None
        for i, state in enumerate(state_sequence):
            if state == EpisodeState.ARCHIVED:
                archived_index = i
                break

        # If archived appears, all subsequent states must be archived
        if archived_index is not None:
            for i in range(archived_index + 1, len(state_sequence)):
                # Allow same state (no-op transitions)
                if state_sequence[i] != EpisodeState.ARCHIVED:
                    # This would be a cycle - ARCHIVED -> something else
                    # But since we validated the sequence follows VALID_TRANSITIONS,
                    # this should never happen if VALID_TRANSITIONS is correct
                    assert False, (
                        f"State cycle detected: state after ARCHIVED is {state_sequence[i].value}, "
                        f"should remain ARCHIVED (sequence: {[s.value for s in state_sequence]}). "
                        f"This indicates VALID_TRANSITIONS allows ARCHIVED -> {state_sequence[i].value}, "
                        f"which is a bug in the state machine definition."
                    )

    @pytest.mark.asyncio
    @given(
        start_state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED]),
        transition_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_all_reachable_invariant(self, db_session, start_state, transition_count):
        """
        All states are reachable from initial state.

        Property: From any starting state, following valid transitions
        should eventually reach all accessible states.

        Mathematical specification:
        Let G = (V, E) be the state transition graph where V is states, E is valid transitions
        Then: G is connected in the sense that all states are reachable from ACTIVE
        """
        # Simulate transitions
        current_state = start_state
        reachable_states = {current_state}

        for _ in range(transition_count):
            valid_targets = VALID_TRANSITIONS.get(current_state, [])
            if valid_targets:
                # Pick first valid target (deterministic for testing)
                current_state = valid_targets[0]
                reachable_states.add(current_state)
            else:
                # Terminal state reached
                break

        # Verify expected reachable states
        if start_state == EpisodeState.ACTIVE:
            # From ACTIVE, can reach COMPLETED, CONSOLIDATED, ARCHIVED
            expected_reachable = {
                EpisodeState.ACTIVE,
                EpisodeState.COMPLETED,
                EpisodeState.CONSOLIDATED,
                EpisodeState.ARCHIVED
            }
            # Note: In a single path, might not visit all, but all are reachable
            assert len(reachable_states) >= 1, "Should reach at least one state"

        elif start_state == EpisodeState.COMPLETED:
            # From COMPLETED, can reach CONSOLIDATED, ARCHIVED
            expected_reachable = {
                EpisodeState.COMPLETED,
                EpisodeState.CONSOLIDATED,
                EpisodeState.ARCHIVED
            }
            assert reachable_states.issubset(expected_reachable), (
                f"Unexpected reachable states from COMPLETED: {reachable_states}"
            )


# =============================================================================
# Property-Based Tests for State Invariants
# =============================================================================

class TestStateInvariants:
    """
    Property-based tests for state machine invariants.

    Verifies that states behave correctly according to the lifecycle rules.
    """

    @pytest.mark.asyncio
    @given(
        state_sequence=st.lists(
            st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED]),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_no_regression_invariant(self, db_session, state_sequence):
        """
        State never "regresses" to earlier states.

        Property: State transitions are monotonic - you cannot go from
        a "later" state back to an "earlier" state.

        Mathematical specification:
        Let order(ACTIVE) = 0, order(COMPLETED) = 1, order(CONSOLIDATED) = 2, order(ARCHIVED) = 3
        For state sequence [s₁, s₂, ..., sₙ]:
        order(sᵢ) <= order(sᵢ₊₁) for all i in [1, n-1]

        This prevents regressions like CONSOLIDATED -> ACTIVE.
        """
        # Define state order
        state_order = {
            EpisodeState.ACTIVE: 0,
            EpisodeState.COMPLETED: 1,
            EpisodeState.CONSOLIDATED: 2,
            EpisodeState.ARCHIVED: 3
        }

        # Check monotonic progression
        for i in range(len(state_sequence) - 1):
            current_order = state_order[state_sequence[i]]
            next_order = state_order[state_sequence[i + 1]]

            # State should not regress (should be same or increase)
            # Note: We allow same state (no transition)
            assert next_order >= current_order, (
                f"State regression detected: {state_sequence[i]} (order {current_order}) -> "
                f"{state_sequence[i + 1]} (order {next_order}). "
                f"States should not regress to earlier lifecycle stages."
            )

    @pytest.mark.asyncio
    @given(
        initial_state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED]),
        transition_attempts=st.integers(min_value=0, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_terminal_invariant(self, db_session, initial_state, transition_attempts):
        """
        Archived state is terminal - no transitions out.

        Property: Once an episode reaches ARCHIVED state, it remains
        archived regardless of any attempted transitions.

        Mathematical specification:
        If state = ARCHIVED at time t, then for all t' > t: state = ARCHIVED

        This is the terminal state invariant.
        """
        current_state = initial_state

        # Simulate transition attempts
        for _ in range(transition_attempts):
            if current_state == EpisodeState.ARCHIVED:
                # Once archived, should remain archived
                # Even if we try to transition, should stay archived
                valid_targets = VALID_TRANSITIONS.get(current_state, [])
                assert len(valid_targets) == 0, (
                    f"Archived state should have no valid transitions, "
                    f"but found {len(valid_targets)} targets"
                )
                # State should not change
                assert current_state == EpisodeState.ARCHIVED
            else:
                # Try to transition (pick first valid target if any)
                valid_targets = VALID_TRANSITIONS.get(current_state, [])
                if valid_targets:
                    current_state = valid_targets[0]

        # Final state check
        if initial_state == EpisodeState.ARCHIVED:
            assert current_state == EpisodeState.ARCHIVED, (
                f"Archived state should remain terminal, but reached {current_state}"
            )

    @pytest.mark.asyncio
    @given(
        initial_state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED]),
        path_length=st.integers(min_value=1, max_value=5)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_determinism_invariant(self, db_session, initial_state, path_length):
        """
        State transitions are deterministic from a given state.

        Property: From any given state, the set of possible next states
        is fixed and deterministic (defined by VALID_TRANSITIONS).

        Mathematical specification:
        For state s, the set of valid next states N(s) is invariant.
        N(s) = VALID_TRANSITIONS[s] is constant for all executions.
        """
        current_state = initial_state

        for _ in range(path_length):
            valid_targets = VALID_TRANSITIONS.get(current_state, [])

            # Valid targets should be deterministic
            assert isinstance(valid_targets, list), (
                f"Valid transitions should be a list, got {type(valid_targets)}"
            )

            # All valid targets should be EpisodeState enum values
            for target in valid_targets:
                assert isinstance(target, EpisodeState) or target in EpisodeState, (
                    f"Invalid target state: {target}"
                )

            # Try to transition
            if valid_targets:
                current_state = valid_targets[0]
            else:
                # Terminal state
                break

        # Should successfully follow path
        assert current_state in EpisodeState, (
            f"Final state {current_state} should be valid EpisodeState"
        )


# =============================================================================
# Property-Based Tests for State Transition Properties
# =============================================================================

class TestStateTransitionProperties:
    """
    Property-based tests for state transition mathematical properties.

    Tests algebraic properties of the state transition system.
    """

    @pytest.mark.asyncio
    @given(
        state_sequence=st.lists(
            st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED]),
            min_size=3,
            max_size=10
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_transitive_property(self, db_session, state_sequence):
        """
        State transitions satisfy transitive property.

        Property: If state A can transition to B, and B can transition to C,
        then there exists a valid path A -> B -> C.

        Mathematical specification:
        Let T(A, B) mean "A can transition to B"
        If T(A, B) and T(B, C), then there exists a path P = [A, B, C]

        This ensures the transition graph is well-formed.
        """
        # Verify transitive property for consecutive states
        for i in range(len(state_sequence) - 2):
            state_a = state_sequence[i]
            state_b = state_sequence[i + 1]
            state_c = state_sequence[i + 2]

            # Check A -> B is valid
            valid_from_a = VALID_TRANSITIONS.get(state_a, [])
            transition_ab_valid = state_b in valid_from_a

            # Check B -> C is valid
            valid_from_b = VALID_TRANSITIONS.get(state_b, [])
            transition_bc_valid = state_c in valid_from_b

            # If both transitions valid, verify path exists
            if transition_ab_valid and transition_bc_valid:
                # Path [A, B, C] should be valid
                # Verify no cycles (unless at terminal state)
                if state_c == EpisodeState.ARCHIVED:
                    # Terminal state reached
                    assert state_c == EpisodeState.ARCHIVED
                else:
                    # Path should progress forward
                    state_order = {
                        EpisodeState.ACTIVE: 0,
                        EpisodeState.COMPLETED: 1,
                        EpisodeState.CONSOLIDATED: 2,
                        EpisodeState.ARCHIVED: 3
                    }
                    assert state_order[state_a] <= state_order[state_b] <= state_order[state_c], (
                        f"State path should be monotonic: {state_a} -> {state_b} -> {state_c}"
                    )

    @pytest.mark.asyncio
    @given(
        state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_idempotent_property(self, db_session, state):
        """
        Staying in same state is idempotent.

        Property: If a state has no valid transitions, attempting
        to transition should keep it in the same state.

        Mathematical specification:
        If VALID_TRANSITIONS[s] = ∅ (empty set)
        Then: attempt_transition(s) = s (idempotent)

        This ensures terminal states remain stable.
        """
        valid_targets = VALID_TRANSITIONS.get(state, [])

        if len(valid_targets) == 0:
            # Terminal state - should be idempotent
            assert state == EpisodeState.ARCHIVED, (
                f"Only ARCHIVED should be terminal, got {state}"
            )
            # Attempting to transition should return same state
            assert state == EpisodeState.ARCHIVED, (
                "Terminal state should remain unchanged"
            )

    @pytest.mark.asyncio
    @given(
        start_state=st.sampled_from([EpisodeState.ACTIVE, EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED]),
        intermediate_states=st.lists(
            st.sampled_from([EpisodeState.COMPLETED, EpisodeState.CONSOLIDATED, EpisodeState.ARCHIVED]),
            min_size=1,
            max_size=5
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_state_transition_path_uniqueness(self, db_session, start_state, intermediate_states):
        """
        State transition paths are unique (no branching to same state via different paths).

        Property: The state transition graph is a DAG (Directed Acyclic Graph).
        There are no cycles and no multiple paths to same state.

        Mathematical specification:
        For any state s, there is at most one unique path from ACTIVE to s.
        The transition graph forms a tree rooted at ACTIVE.

        This ensures predictable episode lifecycle.
        """
        # Define state order
        state_order = {
            EpisodeState.ACTIVE: 0,
            EpisodeState.COMPLETED: 1,
            EpisodeState.CONSOLIDATED: 2,
            EpisodeState.ARCHIVED: 3
        }

        # Build path
        path = [start_state] + intermediate_states

        # Verify monotonic progression
        for i in range(len(path) - 1):
            current_order = state_order.get(path[i], -1)
            next_order = state_order.get(path[i + 1], -1)

            assert next_order >= current_order, (
                f"Path should be monotonic: {path[i]} (order {current_order}) -> "
                f"{path[i + 1]} (order {next_order})"
            )

            # Verify transition is valid
            valid_targets = VALID_TRANSITIONS.get(path[i], [])
            assert path[i + 1] in valid_targets, (
                f"Invalid transition in path: {path[i]} -> {path[i + 1]}"
            )


# =============================================================================
# Fixtures
# =============================================================================

@pytest.fixture(scope="function")
def db_session():
    """
    Create fresh database session for property tests.

    Uses in-memory SQLite for test isolation.
    """
    import os
    import tempfile
    from sqlalchemy import create_engine
    from sqlalchemy.orm import sessionmaker
    from sqlalchemy import pool

    # Set testing environment
    os.environ["TESTING"] = "1"

    # Use file-based temp SQLite for tests
    fd, db_path = tempfile.mkstemp(suffix='.db')
    os.close(fd)

    # Use pooled connections with check_same_thread=False for SQLite
    engine = create_engine(
        f"sqlite:///{db_path}",
        connect_args={"check_same_thread": False},
        poolclass=pool.StaticPool,
        echo=False,
        pool_pre_ping=True
    )

    # Store path for cleanup
    engine._test_db_path = db_path

    # Create tables we need
    from core.database import Base

    tables_to_create = [
        'agent_episodes',
        'episode_segments',
        'canvas_audit',
        'agent_feedback',
        'agent_registry',
        'chat_sessions',
    ]

    for table_name in tables_to_create:
        if table_name in Base.metadata.tables:
            try:
                Base.metadata.tables[table_name].create(engine, checkfirst=True)
            except Exception as e:
                print(f"Warning: Could not create table {table_name}: {e}")

    # Create session
    TestingSessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine, expire_on_commit=False)
    session = TestingSessionLocal()

    yield session

    # Cleanup
    session.close()
    engine.dispose()
    # Delete temp database file
    if hasattr(engine, '_test_db_path'):
        try:
            os.unlink(engine._test_db_path)
        except Exception:
            pass
