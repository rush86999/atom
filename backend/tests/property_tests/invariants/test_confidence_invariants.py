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
