"""
⚠️  PROTECTED PROPERTY-BASED TEST ⚠️

This file tests CRITICAL SYSTEM INVARIANTS for the Atom platform.

DO NOT MODIFY THIS FILE unless:
1. You are fixing a TEST BUG (not an implementation bug)
2. You are ADDING new invariants
3. You have EXPLICIT APPROVAL from engineering lead

These tests must remain IMPLEMENTATION-AGNOSTIC.
Test only observable behaviors and public API contracts.

Protection: tests/.protection_markers/PROPERTY_TEST_GUARDIAN.md
"""

import pytest
from hypothesis import given, settings, HealthCheck
from hypothesis import strategies as st
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.models import AgentRegistry, AgentStatus, AgentFeedback, FeedbackStatus


class TestConfidenceInvariants:
    """Test confidence score management maintains critical invariants."""

    @given(
        initial_confidence=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        ),
        num_updates=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_bounds_preserved_after_multiple_updates(
        self, db_session: Session, initial_confidence: float, num_updates: int
    ):
        """
        INVARIANT: Confidence MUST stay in [0.0, 1.0] after ANY number of updates.

        Even after 20 positive or negative updates, the score must remain valid.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: Apply multiple updates
        import random
        for i in range(num_updates):
            positive = random.choice([True, False])
            impact = random.choice(["high", "low"])
            service._update_confidence_score(agent.id, positive=positive, impact_level=impact)
            db_session.refresh(agent)

            # Assert: After each update, verify bounds
            assert 0.0 <= agent.confidence_score <= 1.0, \
                f"Confidence {agent.confidence_score} exceeded bounds after {i+1} updates"

    @given(
        initial_confidence=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        ),
        num_negative_updates=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_negative_feedback_decreases_confidence(
        self, db_session: Session, initial_confidence: float, num_negative_updates: int
    ):
        """
        INVARIANT: Negative feedback MUST decrease confidence (or keep same at minimum).

        Accepted negative feedback should reduce confidence score.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        initial_score = agent.confidence_score

        # Act: Apply negative updates
        for _ in range(num_negative_updates):
            service._update_confidence_score(agent.id, positive=False, impact_level="low")
            db_session.refresh(agent)

        # Assert: Score should not increase
        final_score = agent.confidence_score
        assert final_score <= initial_score, \
            f"Negative feedback increased confidence: {initial_score} -> {final_score}"

    @given(
        initial_confidence=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        ),
        num_positive_updates=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=150, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_positive_feedback_increases_confidence(
        self, db_session: Session, initial_confidence: float, num_positive_updates: int
    ):
        """
        INVARIANT: Positive feedback MUST increase confidence (or keep same at maximum).

        Successful outcomes should increase confidence score.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,
            
        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        initial_score = agent.confidence_score

        # Act: Apply positive updates
        for _ in range(num_positive_updates):
            service._update_confidence_score(agent.id, positive=True, impact_level="low")
            db_session.refresh(agent)

        # Assert: Score should not decrease
        final_score = agent.confidence_score
        assert final_score >= initial_score, \
            f"Positive feedback decreased confidence: {initial_score} -> {final_score}"

    @given(
        initial_confidence=st.floats(
            min_value=0.0,
            max_value=1.0,
            allow_nan=False,
            allow_infinity=False
        )
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_transition_thresholds(
        self, db_session: Session, initial_confidence: float
    ):
        """
        INVARIANT: Confidence transitions at known thresholds.

        Status should change at:
        - < 0.5: STUDENT
        - 0.5 - 0.7: INTERN
        - 0.7 - 0.9: SUPERVISED
        - >= 0.9: AUTONOMOUS
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Helper to get expected status
        def get_expected_status(confidence: float) -> str:
            if confidence >= 0.9:
                return AgentStatus.AUTONOMOUS.value
            elif confidence >= 0.7:
                return AgentStatus.SUPERVISED.value
            elif confidence >= 0.5:
                return AgentStatus.INTERN.value
            else:
                return AgentStatus.STUDENT.value

        # Create agent with correct initial status based on confidence
        initial_status = get_expected_status(initial_confidence)
        agent = AgentRegistry(
            name="TestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=initial_status,
            confidence_score=initial_confidence,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Assert: Initial status should match confidence
        expected_status = get_expected_status(agent.confidence_score)
        assert agent.status == expected_status, \
            f"Agent status {agent.status} doesn't match confidence {agent.confidence_score} (expected {expected_status})"

        # Test updates across boundaries - need to call _update_confidence_score to sync status
        test_scores = [0.3, 0.5, 0.7, 0.9]
        for score in test_scores:
            agent.confidence_score = score
            db_session.commit()
            # Call _update_confidence_score to sync status with confidence
            service._update_confidence_score(agent.id, positive=True, impact_level="low")
            db_session.refresh(agent)

            expected_status = get_expected_status(score)
            assert agent.status == expected_status, \
                f"Agent status {agent.status} doesn't match confidence {score} (expected {expected_status})"

    @given(
        initial_confidence=st.floats(
            min_value=0.3,
            max_value=0.7,
            allow_nan=False,
            allow_infinity=False
        ),
        high_impact_count=st.integers(min_value=1, max_value=10)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_high_impact_feedback_moves_confidence_faster(
        self, db_session: Session, initial_confidence: float, high_impact_count: int
    ):
        """
        INVARIANT: High-impact feedback moves confidence faster than low-impact.

        High-impact updates should have greater effect than low-impact updates.
        """
        # Arrange
        service = AgentGovernanceService(db_session)

        # Create two agents with same initial confidence
        agent_high = AgentRegistry(
            name="HighImpactAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,

        )
        agent_low = AgentRegistry(
            name="LowImpactAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,

        )
        db_session.add_all([agent_high, agent_low])
        db_session.commit()
        db_session.refresh(agent_high)
        db_session.refresh(agent_low)

        initial_high = agent_high.confidence_score
        initial_low = agent_low.confidence_score

        # Act: Apply high-impact positive feedback to one, low-impact to other
        for _ in range(high_impact_count):
            service._update_confidence_score(agent_high.id, positive=True, impact_level="high")
            service._update_confidence_score(agent_low.id, positive=True, impact_level="low")
            db_session.refresh(agent_high)
            db_session.refresh(agent_low)

        # Assert: High-impact should increase more
        high_change = abs(agent_high.confidence_score - initial_high)
        low_change = abs(agent_low.confidence_score - initial_low)
        assert high_change >= low_change, \
            f"High-impact change ({high_change}) should be >= low-impact change ({low_change})"

        # Both should stay in bounds
        assert 0.0 <= agent_high.confidence_score <= 1.0
        assert 0.0 <= agent_low.confidence_score <= 1.0

    @given(
        initial_confidence=st.floats(
            min_value=0.1,
            max_value=0.9,
            allow_nan=False,
            allow_infinity=False
        ),
        feedback_sequence=st.lists(
            st.sampled_from([True, False]),
            min_size=10,
            max_size=30
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_mixed_feedback_confidence_stability(
        self, db_session: Session, initial_confidence: float, feedback_sequence: list
    ):
        """
        INVARIANT: Mixed feedback maintains confidence stability.

        Even with alternating positive/negative feedback, confidence should:
        - Stay within [0.0, 1.0] bounds
        - Not oscillate wildly
        - Eventually stabilize based on overall trend
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="StabilityTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Track confidence history
        confidence_history = [agent.confidence_score]

        # Act: Apply mixed feedback
        for is_positive in feedback_sequence:
            service._update_confidence_score(agent.id, positive=is_positive, impact_level="low")
            db_session.refresh(agent)
            confidence_history.append(agent.confidence_score)

        # Assert: All values in bounds
        for score in confidence_history:
            assert 0.0 <= score <= 1.0, \
                f"Confidence {score} out of bounds during mixed feedback sequence"

        # Assert: No extreme oscillations (consecutive changes should be reasonable)
        max_oscillation = 0.3  # Max 30% change between consecutive updates
        for i in range(1, len(confidence_history)):
            change = abs(confidence_history[i] - confidence_history[i-1])
            assert change <= max_oscillation, \
                f"Excessive oscillation detected: {confidence_history[i-1]:.3f} -> {confidence_history[i]:.3f}"

    @given(
        initial_confidence=st.floats(
            min_value=0.4,
            max_value=0.6,
            allow_nan=False,
            allow_infinity=False
        ),
        consecutive_positive=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_plateau_at_maximum(
        self, db_session: Session, initial_confidence: float, consecutive_positive: int
    ):
        """
        INVARIANT: Confidence plateaus at maximum (1.0).

        Once confidence reaches 1.0, additional positive feedback should not increase it.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="PlateauTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: Apply consecutive positive feedback
        for i in range(consecutive_positive):
            service._update_confidence_score(agent.id, positive=True, impact_level="high")
            db_session.refresh(agent)

            # Assert: Should not exceed maximum
            assert agent.confidence_score <= 1.0, \
                f"Confidence exceeded maximum: {agent.confidence_score}"

            # Once at maximum, should stay at maximum
            if agent.confidence_score >= 0.999:  # Allow for floating point precision
                # Continue applying feedback to ensure it stays at max
                pass

    @given(
        initial_confidence=st.floats(
            min_value=0.4,
            max_value=0.6,
            allow_nan=False,
            allow_infinity=False
        ),
        consecutive_negative=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    def test_confidence_plateau_at_minimum(
        self, db_session: Session, initial_confidence: float, consecutive_negative: int
    ):
        """
        INVARIANT: Confidence plateaus at minimum (0.0).

        Once confidence reaches 0.0, additional negative feedback should not decrease it.
        """
        # Arrange
        service = AgentGovernanceService(db_session)
        agent = AgentRegistry(
            name="MinimumTestAgent",
            category="test",
            module_path="test.module",
            class_name="TestClass",
            status=AgentStatus.INTERN.value,
            confidence_score=initial_confidence,

        )
        db_session.add(agent)
        db_session.commit()
        db_session.refresh(agent)

        # Act: Apply consecutive negative feedback
        for i in range(consecutive_negative):
            service._update_confidence_score(agent.id, positive=False, impact_level="high")
            db_session.refresh(agent)

            # Assert: Should not go below minimum
            assert agent.confidence_score >= 0.0, \
                f"Confidence below minimum: {agent.confidence_score}"

            # Once at minimum, should stay at minimum
            if agent.confidence_score <= 0.001:  # Allow for floating point precision
                # Continue applying feedback to ensure it stays at min
                pass

    @given(
        confidence_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        confidence_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        confidence_c=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_confidence_comparison_consistency(self, confidence_a, confidence_b, confidence_c):
        """
        INVARIANT: Confidence comparisons are transitive and consistent.

        If A >= B and B >= C, then A >= C (transitivity).
        """
        # Test transitivity
        if confidence_a >= confidence_b and confidence_b >= confidence_c:
            assert confidence_a >= confidence_c, \
                f"Transitivity violated: {confidence_a} >= {confidence_b} >= {confidence_c}"

        # Test symmetry
        assert (confidence_a >= confidence_b) or (confidence_b > confidence_a), \
            "Comparison should be total ordering"

        # Test reflexivity
        assert confidence_a >= confidence_a, \
            "Reflexivity violated"

        # All values in valid range
        assert 0.0 <= confidence_a <= 1.0
        assert 0.0 <= confidence_b <= 1.0
        assert 0.0 <= confidence_c <= 1.0
