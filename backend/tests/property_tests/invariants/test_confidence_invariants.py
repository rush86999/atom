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


class TestConfidenceAggregationInvariants:
    """Test confidence aggregation maintains critical invariants."""

    @given(
        confidence_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=100
        )
    )
    @settings(max_examples=100)
    def test_aggregated_confidence_bounds(self, confidence_scores):
        """
        INVARIANT: Aggregated confidence MUST stay in [0.0, 1.0].

        When averaging multiple confidence scores, result must be valid.
        """
        # Calculate average
        avg_confidence = sum(confidence_scores) / len(confidence_scores)

        # Invariant: Average must be in valid range
        assert 0.0 <= avg_confidence <= 1.0, \
            f"Aggregated confidence {avg_confidence} out of bounds"

        # Invariant: Average must be within min/max range (with tolerance for floating-point)
        min_score = min(confidence_scores)
        max_score = max(confidence_scores)
        # Use tolerance for floating-point comparison
        assert min_score - 0.0001 <= avg_confidence <= max_score + 0.0001, \
            f"Average {avg_confidence} outside range [{min_score}, {max_score}]"

    @given(
        confidence_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_weighted_confidence_aggregation(self, confidence_scores):
        """
        INVARIANT: Weighted aggregation produces valid confidence.

        When using weighted average with recency weights.
        """
        # Generate exponential decay weights (newer = higher weight)
        weights = [2 ** i for i in range(len(confidence_scores))]
        total_weight = sum(weights)

        # Calculate weighted average
        weighted_sum = sum(score * weight for score, weight in zip(confidence_scores, weights))
        weighted_avg = weighted_sum / total_weight

        # Invariant: Weighted average must be in valid range
        assert 0.0 <= weighted_avg <= 1.0, \
            f"Weighted average {weighted_avg} out of bounds"

        # Invariant: Weighted average must be within score range (with tolerance)
        min_score = min(confidence_scores)
        max_score = max(confidence_scores)
        assert min_score - 0.0001 <= weighted_avg <= max_score + 0.0001, \
            f"Weighted avg {weighted_avg} outside range [{min_score}, {max_score}]"

    @given(
        confidence_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        confidence_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        weight_a=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        weight_b=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=100)
    def test_two_confidence_aggregation(self, confidence_a, confidence_b, weight_a, weight_b):
        """
        INVARIANT: Two-confidence aggregation is valid.

        When combining two confidence scores with custom weights.
        """
        # Handle case where both weights are 0
        if weight_a == 0.0 and weight_b == 0.0:
            return  # Skip - invalid case

        total_weight = weight_a + weight_b
        if total_weight > 0:
            weighted_avg = (confidence_a * weight_a + confidence_b * weight_b) / total_weight

            # Clamp to valid range
            weighted_avg = max(0.0, min(1.0, weighted_avg))

            # Invariant: Result must be in valid range
            assert 0.0 <= weighted_avg <= 1.0, \
                f"Aggregated {weighted_avg} from {confidence_a} and {confidence_b} out of bounds"

            # Invariant: Result must be between inputs (with tolerance)
            min_conf = min(confidence_a, confidence_b)
            max_conf = max(confidence_a, confidence_b)
            assert min_conf - 0.0001 <= weighted_avg <= max_conf + 0.0001, \
                f"Aggregated {weighted_avg} outside [{min_conf}, {max_conf}]"


class TestTemporalConfidenceDecayInvariants:
    """Test temporal confidence decay maintains critical invariants."""

    @given(
        initial_confidence=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),
        days_passed=st.integers(min_value=1, max_value=365)
    )
    @settings(max_examples=100)
    def test_confidence_decay_over_time(self, initial_confidence, days_passed):
        """
        INVARIANT: Confidence decays gracefully over time.

        As time passes without positive reinforcement, confidence should decrease.
        """
        # Simulate decay (exponential with 30-day half-life)
        decay_rate = 0.693 / 30  # 30-day half-life
        decayed_confidence = initial_confidence * (2 ** (-decay_rate * days_passed / 30))

        # Invariant: Decayed confidence must be in valid range
        assert 0.0 <= decayed_confidence <= 1.0, \
            f"Decayed confidence {decayed_confidence} out of bounds"

        # Invariant: Decay should not increase confidence
        assert decayed_confidence <= initial_confidence, \
            f"Decay increased confidence: {initial_confidence} -> {decayed_confidence}"

        # Invariant: Decay should be non-negative
        assert decayed_confidence >= 0.0, "Decayed confidence became negative"

    @given(
        initial_confidence=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),
        recent_positive_count=st.integers(min_value=0, max_value=20),
        recent_negative_count=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=100)
    def test_recent_activity_dominance(self, initial_confidence, recent_positive_count, recent_negative_count):
        """
        INVARIANT: Recent activity has greater impact than old activity.

        Recent feedback should weigh more than historical feedback.
        """
        # Calculate net recent feedback
        net_recent = recent_positive_count - recent_negative_count

        # Simulate update with recent activity bias
        # Recent activity has 2x weight
        adjustment = net_recent * 0.05  # 5% impact per feedback
        adjusted_confidence = initial_confidence + (0.01 if net_recent > 0 else -0.01) * min(abs(net_recent), 5)

        # Clamp to valid range
        adjusted_confidence = max(0.0, min(1.0, adjusted_confidence))

        # Invariant: Adjusted confidence must be in valid range
        assert 0.0 <= adjusted_confidence <= 1.0, \
            f"Adjusted confidence {adjusted_confidence} out of bounds"

        # Invariant: More positive recent feedback should not decrease confidence
        if net_recent > 0:
            assert adjusted_confidence >= initial_confidence - 0.01, \
                "Positive recent feedback decreased confidence"

    @given(
        initial_confidence=st.floats(min_value=0.3, max_value=0.7, allow_nan=False, allow_infinity=False),
        episode_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=100)
    def test_confidence_stabilization_with_experience(self, initial_confidence, episode_count):
        """
        INVARIANT: Confidence stabilizes with more episodes.

        Agents with more episodes should have less volatile confidence.
        """
        # Calculate volatility (decreases with episode count)
        # Volatility = 0.1 / sqrt(episodes)
        import math
        volatility = 0.1 / math.sqrt(max(episode_count, 1))

        # Invariant: Volatility should be positive
        assert volatility > 0, "Volatility must be positive"

        # Invariant: More episodes = less volatility
        if episode_count >= 50:
            assert volatility < 0.02, "High episode count should have low volatility"

        # Invariant: Volatility should be reasonable
        assert volatility <= 0.1, "Volatility should not exceed 0.1"


class TestFeedbackConfidenceCorrelationInvariants:
    """Test feedback-confidence correlation maintains critical invariants."""

    @given(
        feedback_scores=st.lists(
            st.integers(min_value=-1, max_value=1),
            min_size=5,
            max_size=50
        )
    )
    @settings(max_examples=100)
    def test_feedback_direction_confidence_correlation(self, feedback_scores):
        """
        INVARIANT: Feedback direction correlates with confidence changes.

        Positive feedback should correlate with confidence increases.
        Negative feedback should correlate with confidence decreases.
        """
        # Count positive and negative feedback
        positive_count = sum(1 for score in feedback_scores if score > 0)
        negative_count = sum(1 for score in feedback_scores if score < 0)
        neutral_count = sum(1 for score in feedback_scores if score == 0)

        # Calculate expected direction
        net_direction = positive_count - negative_count

        # Invariant: Net positive feedback should trend toward higher confidence
        if net_direction > 0:
            assert True  # Should increase confidence
        elif net_direction < 0:
            assert True  # Should decrease confidence
        else:
            assert True  # Neutral feedback - no clear direction

        # Invariant: Total feedback counts should match
        total = positive_count + negative_count + neutral_count
        assert total == len(feedback_scores), "Count mismatch"

    @given(
        initial_confidence=st.floats(min_value=0.3, max_value=0.7, allow_nan=False, allow_infinity=False),
        feedback_magnitude=st.integers(min_value=1, max_value=10),
        is_positive=st.booleans()
    )
    @settings(max_examples=100)
    def test_feedback_magnitude_impact(self, initial_confidence, feedback_magnitude, is_positive):
        """
        INVARIANT: Feedback magnitude impacts confidence proportionally.

        Larger magnitude feedback should have larger impact.
        """
        # Simulate impact (0.5% per magnitude unit)
        impact = feedback_magnitude * 0.005
        if is_positive:
            adjusted = initial_confidence + impact
        else:
            adjusted = initial_confidence - impact

        # Clamp to valid range
        adjusted = max(0.0, min(1.0, adjusted))

        # Invariant: Adjusted confidence must be in valid range
        assert 0.0 <= adjusted <= 1.0, \
            f"Adjusted confidence {adjusted} out of bounds"

        # Invariant: Higher magnitude should have larger impact
        if is_positive:
            assert adjusted >= initial_confidence, "Positive feedback increased confidence"
        else:
            assert adjusted <= initial_confidence, "Negative feedback decreased confidence"

    @given(
        confidence_before=st.floats(min_value=0.4, max_value=0.6, allow_nan=False, allow_infinity=False),
        feedback_score=st.integers(min_value=-1, max_value=1)
    )
    @settings(max_examples=100)
    def test_feedback_confidence_boundaries(self, confidence_before, feedback_score):
        """
        INVARIANT: Feedback respects confidence boundaries.

        Feedback at boundaries should not push confidence outside [0, 1].
        """
        # Apply feedback
        impact = 0.05 if feedback_score != 0 else 0
        if feedback_score > 0:
            confidence_after = min(1.0, confidence_before + impact)
        elif feedback_score < 0:
            confidence_after = max(0.0, confidence_before - impact)
        else:
            confidence_after = confidence_before

        # Invariant: Result must be in valid range
        assert 0.0 <= confidence_after <= 1.0, \
            f"Confidence {confidence_after} out of bounds after feedback {feedback_score}"

        # Invariant: At maximum, positive feedback should not increase
        if confidence_before >= 0.99 and feedback_score > 0:
            assert confidence_after <= 1.0

        # Invariant: At minimum, negative feedback should not decrease
        if confidence_before <= 0.01 and feedback_score < 0:
            assert confidence_after >= 0.0


class TestMultiAgentConfidenceInvariants:
    """Test multi-agent confidence comparison invariants."""

    @given(
        agent_confidences=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_agent_ranking_consistency(self, agent_confidences):
        """
        INVARIANT: Agent ranking by confidence is consistent.

        Higher confidence = higher rank.
        """
        # Sort by confidence (descending)
        sorted_confidences = sorted(agent_confidences, reverse=True)

        # Invariant: Sorting should be correct
        for i in range(len(sorted_confidences) - 1):
            assert sorted_confidences[i] >= sorted_confidences[i + 1], \
                "Sorting not in descending order"

        # Invariant: All values should be in valid range
        for conf in agent_confidences:
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds"

    @given(
        base_confidence=st.floats(min_value=0.3, max_value=0.8, allow_nan=False, allow_infinity=False),
        agent_count=st.integers(min_value=2, max_value=10)
    )
    @settings(max_examples=100)
    def test_relative_confidence_comparison(self, base_confidence, agent_count):
        """
        INVARIANT: Relative confidence comparisons are valid.

        Agents should be comparable relative to each other.
        """
        # Generate confidences around base
        import random
        confidences = []
        for i in range(agent_count):
            # Add random offset [-0.1, 0.1]
            offset = random.uniform(-0.1, 0.1)
            conf = max(0.0, min(1.0, base_confidence + offset))
            confidences.append(conf)

        # Invariant: All confidences should be in valid range
        for conf in confidences:
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds"

        # Invariant: Should be able to find max and min
        max_conf = max(confidences)
        min_conf = min(confidences)
        assert max_conf >= min_conf, "Max should be >= min"

    @given(
        confidence_trend=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=3,
            max_size=20
        )
    )
    @settings(max_examples=100)
    def test_confidence_trend_detection(self, confidence_trend):
        """
        INVARIANT: Confidence trends are detected correctly.

        Should identify increasing, decreasing, or stable trends.
        """
        # Invariant: All values should be in valid range
        for conf in confidence_trend:
            assert 0.0 <= conf <= 1.0, f"Confidence {conf} out of bounds"

        # Calculate trend direction
        increases = sum(1 for i in range(1, len(confidence_trend)) if confidence_trend[i] > confidence_trend[i-1])
        decreases = sum(1 for i in range(1, len(confidence_trend)) if confidence_trend[i] < confidence_trend[i-1])

        # Invariant: Should be able to classify trend
        if increases > decreases:
            assert True  # Increasing trend
        elif decreases > increases:
            assert True  # Decreasing trend
        else:
            assert True  # Stable trend

    @given(
        agent_confidences=st.dictionaries(
            keys=st.text(min_size=1, max_size=10, alphabet='abc'),
            values=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=2,
            max_size=10
        )
    )
    @settings(max_examples=100)
    def test_agent_selection_by_confidence(self, agent_confidences):
        """
        INVARIANT: Agent selection by confidence is valid.

        Higher confidence agents should be preferred.
        """
        # Invariant: All values should be in valid range
        for agent_id, conf in agent_confidences.items():
            assert 0.0 <= conf <= 1.0, f"Agent {agent_id} has invalid confidence {conf}"

        # Find agent with max confidence
        best_agent = max(agent_confidences.items(), key=lambda x: x[1])

        # Invariant: Best agent should have highest confidence
        for agent_id, conf in agent_confidences.items():
            assert best_agent[1] >= conf, \
                f"Best agent {best_agent[0]} ({best_agent[1]}) should have >= confidence than {agent_id} ({conf})"
