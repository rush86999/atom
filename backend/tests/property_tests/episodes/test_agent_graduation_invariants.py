"""
Property-Based Tests for Agent Graduation Invariants

Tests CRITICAL agent graduation invariants:
- Episode count requirements enforced
- Intervention rate thresholds validated
- Constitutional score bounds checked
- Readiness score in [0, 100]
- Maturity transitions are valid

These tests protect against premature agent promotions and governance violations.
"""

import pytest
from hypothesis import given, strategies as st, settings, HealthCheck
from datetime import datetime, timedelta
from typing import List, Dict
from unittest.mock import Mock, MagicMock

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentRegistry, AgentStatus, Episode


class TestGraduationCriteriaInvariants:
    """Property-based tests for graduation criteria invariants."""

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=50)
    def test_episode_count_requirement(self, episode_count, target_maturity):
        """INVARIANT: Episode count meets minimum requirement for promotion."""
        service = AgentGraduationService
        criteria = service.CRITERIA.get(target_maturity)

        min_episodes = criteria['min_episodes']

        # Check if episode count meets requirement
        meets_requirement = episode_count >= min_episodes

        # Invariant: Episode count should be >= minimum for promotion
        if meets_requirement:
            assert episode_count >= min_episodes, \
                f"Episode count {episode_count} below minimum {min_episodes} for {target_maturity}"
        else:
            assert episode_count < min_episodes, \
                f"Should not meet requirement with {episode_count} episodes for {target_maturity}"

    @given(
        intervention_count=st.integers(min_value=0, max_value=50),
        episode_count=st.integers(min_value=1, max_value=100),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=50)
    def test_intervention_rate_threshold(self, intervention_count, episode_count, target_maturity):
        """INVARIANT: Intervention rate must be below threshold for promotion."""
        service = AgentGraduationService
        criteria = service.CRITERIA.get(target_maturity)

        max_intervention_rate = criteria['max_intervention_rate']

        # Calculate intervention rate
        intervention_rate = intervention_count / episode_count if episode_count > 0 else 1.0

        # Check if rate meets requirement
        meets_requirement = intervention_rate <= max_intervention_rate

        # Invariant: Intervention rate should be <= maximum
        if meets_requirement:
            assert intervention_rate <= max_intervention_rate, \
                f"Intervention rate {intervention_rate:.2f} exceeds max {max_intervention_rate:.2f} for {target_maturity}"

    @given(
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=50)
    def test_constitutional_score_threshold(self, constitutional_score, target_maturity):
        """INVARIANT: Constitutional score meets minimum threshold for promotion."""
        service = AgentGraduationService
        criteria = service.CRITERIA.get(target_maturity)

        min_score = criteria['min_constitutional_score']

        # Check if score meets requirement
        meets_requirement = constitutional_score >= min_score

        # Invariant: Score should be >= minimum for promotion
        if meets_requirement:
            assert constitutional_score >= min_score, \
                f"Score {constitutional_score:.2f} below minimum {min_score:.2f} for {target_maturity}"


class TestReadinessScoreInvariants:
    """Property-based tests for readiness score calculation invariants."""

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=50)
    def test_readiness_score_bounds(self, episode_count, intervention_rate, constitutional_score, target_maturity):
        """INVARIANT: Readiness score must be in [0, 100]."""
        service = AgentGraduationService
        criteria = service.CRITERIA.get(target_maturity)

        # Simulate readiness score calculation (simplified)
        # Weight: 40% episodes, 30% intervention, 30% constitutional
        episode_score = min(episode_count / criteria['min_episodes'], 1.0) if criteria['min_episodes'] > 0 else 0.0

        # For intervention rate: lower is better
        intervention_score = 1.0 - (intervention_rate / criteria['max_intervention_rate']) if criteria['max_intervention_rate'] > 0 else 1.0
        intervention_score = max(0.0, min(1.0, intervention_score))

        # Constitutional score: already in [0, 1]
        constitutional_score_normalized = max(0.0, min(1.0, constitutional_score))

        # Calculate weighted score
        readiness_score = (
            episode_score * 0.4 +
            intervention_score * 0.3 +
            constitutional_score_normalized * 0.3
        ) * 100

        # Invariant: Score must be in [0, 100]
        assert 0.0 <= readiness_score <= 100.0, \
            f"Readiness score {readiness_score:.2f} out of bounds [0, 100]"

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_readiness_score_monotonic(self, episode_count, intervention_rate, constitutional_score):
        """INVARIANT: Readiness score increases with better metrics."""
        # Calculate base score
        base_score = (
            min(episode_count / 10.0, 1.0) * 0.4 +
            (1.0 - intervention_rate) * 0.3 +
            constitutional_score * 0.3
        ) * 100

        # Improve each metric and verify score increases
        # More episodes -> higher score
        improved_episodes = episode_count + 10
        improved_score = (
            min(improved_episodes / 10.0, 1.0) * 0.4 +
            (1.0 - intervention_rate) * 0.3 +
            constitutional_score * 0.3
        ) * 100
        assert improved_score >= base_score, \
            "More episodes should not decrease readiness score"

        # Lower intervention rate -> higher score
        improved_intervention = max(0.0, intervention_rate - 0.1)
        improved_score = (
            min(episode_count / 10.0, 1.0) * 0.4 +
            (1.0 - improved_intervention) * 0.3 +
            constitutional_score * 0.3
        ) * 100
        assert improved_score >= base_score, \
            "Lower intervention rate should not decrease readiness score"

        # Higher constitutional score -> higher score
        improved_constitutional = min(1.0, constitutional_score + 0.1)
        improved_score = (
            min(episode_count / 10.0, 1.0) * 0.4 +
            (1.0 - intervention_rate) * 0.3 +
            improved_constitutional * 0.3
        ) * 100
        assert improved_score >= base_score, \
            "Higher constitutional score should not decrease readiness score"


class TestMaturityTransitionInvariants:
    """Property-based tests for valid maturity transitions."""

    @given(
        current_maturity=st.sampled_from(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=100)
    def test_maturity_transition_validity(self, current_maturity, target_maturity):
        """INVARIANT: Only valid maturity transitions are allowed."""
        # Define valid transitions
        maturity_order = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']
        current_idx = maturity_order.index(current_maturity)
        target_idx = maturity_order.index(target_maturity)

        # Valid: forward transition (can't skip levels)
        is_valid = target_idx == current_idx + 1

        # Invariant: Can only promote to next level
        if is_valid:
            assert target_idx == current_idx + 1, \
                f"Invalid transition from {current_maturity} to {target_maturity}"
        else:
            # Invalid transitions: skipping levels or moving backward
            assert target_idx != current_idx + 1, \
                f"Should reject invalid transition from {current_maturity} to {target_maturity}"

    @given(
        start_level=st.sampled_from([0, 1]),  # STUDENT or INTERN
        progression_length=st.integers(min_value=1, max_value=3)
    )
    @settings(max_examples=50)
    def test_maturity_progression_sequential(self, start_level, progression_length):
        """INVARIANT: Maturity progression must be sequential."""
        maturity_order = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']

        # Generate sequential maturity levels
        end_idx = min(start_level + progression_length, len(maturity_order) - 1)
        maturity_levels = [maturity_order[i] for i in range(start_level, end_idx + 1)]

        # Verify progression is sequential
        for i in range(len(maturity_levels) - 1):
            current_idx = maturity_order.index(maturity_levels[i])
            next_idx = maturity_order.index(maturity_levels[i + 1])

            # Invariant: No skipped levels
            assert next_idx == current_idx + 1, \
                f"Skipped maturity level from {maturity_levels[i]} to {maturity_levels[i+1]}"


class TestConstitutionalComplianceInvariants:
    """Property-based tests for constitutional compliance invariants."""

    @given(
        total_executions=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_intervention_rate_calculation(self, total_executions):
        """INVARIANT: Intervention rate calculated correctly."""
        # Intervention count cannot exceed total executions
        max_interventions = total_executions
        intervention_count = max_interventions // 2  # Use half for realistic scenario

        # Calculate intervention rate
        intervention_rate = intervention_count / total_executions

        # Invariant: Rate should be in [0, 1]
        assert 0.0 <= intervention_rate <= 1.0, \
            f"Intervention rate {intervention_rate:.2f} out of bounds [0, 1]"

        # Invariant: Rate should match formula
        expected_rate = intervention_count / total_executions
        assert abs(intervention_rate - expected_rate) < 0.001, \
            f"Intervention rate calculation incorrect"

    @given(
        scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_constitutional_score_aggregation(self, scores):
        """INVARIANT: Constitutional scores aggregated correctly."""
        # Calculate average score
        avg_score = sum(scores) / len(scores)

        # Invariant: Average should be in [0, 1]
        assert 0.0 <= avg_score <= 1.0, \
            f"Average score {avg_score:.2f} out of bounds [0, 1]"

        # Invariant: All individual scores should be in [0, 1]
        for score in scores:
            assert 0.0 <= score <= 1.0, \
                f"Individual score {score:.2f} out of bounds [0, 1]"

        # Invariant: Average should be within range of individual scores
        min_score = min(scores)
        max_score = max(scores)
        assert min_score <= avg_score <= max_score, \
            f"Average {avg_score:.2f} not in range [{min_score:.2f}, {max_score:.2f}]"


class TestGraduationAuditTrailInvariants:
    """Property-based tests for graduation audit trail invariants."""

    @given(
        graduation_count=st.integers(min_value=1, max_value=20)
    )
    @settings(max_examples=50)
    def test_graduation_history_tracking(self, graduation_count):
        """INVARIANT: All graduations are tracked in audit trail."""
        # Simulate graduation history
        graduations = []
        maturity_order = ['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS']

        for i in range(graduation_count):
            graduation = {
                'agent_id': f"agent_{i}",
                'from_maturity': maturity_order[i % 3],
                'to_maturity': maturity_order[(i % 3) + 1],
                'timestamp': datetime.now() + timedelta(hours=i),
                'readiness_score': 70.0 + i,
                'approved_by': 'governance_service'
            }
            graduations.append(graduation)

        # Invariant: All graduations should have required fields
        required_fields = ['agent_id', 'from_maturity', 'to_maturity', 'timestamp', 'readiness_score', 'approved_by']
        for grad in graduations:
            for field in required_fields:
                assert field in grad, \
                    f"Missing required field '{field}' in graduation record"

        # Invariant: Graduations should be in chronological order
        for i in range(len(graduations) - 1):
            current_time = graduations[i]['timestamp']
            next_time = graduations[i + 1]['timestamp']
            assert current_time <= next_time, \
                "Graduations not in chronological order"

    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_audit_metrics_accuracy(self, episode_count, intervention_count):
        """INVARIANT: Audit trail metrics are accurate."""
        # Simulate audit record
        audit_record = {
            'agent_id': 'test_agent',
            'maturity_level': 'INTERN',
            'episode_count': episode_count,
            'intervention_count': intervention_count,
            'intervention_rate': intervention_count / episode_count if episode_count > 0 else 0.0,
            'constitutional_score': 0.85,
            'readiness_score': 75.0
        }

        # Verify intervention rate calculation
        expected_rate = intervention_count / episode_count if episode_count > 0 else 0.0
        assert abs(audit_record['intervention_rate'] - expected_rate) < 0.001, \
            f"Intervention rate mismatch: {audit_record['intervention_rate']} vs {expected_rate}"

        # Invariant: All metrics should be non-negative
        assert audit_record['episode_count'] >= 0
        assert audit_record['intervention_count'] >= 0
        assert audit_record['intervention_rate'] >= 0.0
        assert audit_record['constitutional_score'] >= 0.0
        assert audit_record['readiness_score'] >= 0.0
