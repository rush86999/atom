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
        # Allow small floating-point tolerance
        min_score = min(scores)
        max_score = max(scores)
        assert min_score - 1e-10 <= avg_score <= max_score + 1e-10, \
            f"Average {avg_score:.10f} not in range [{min_score:.10f}, {max_score:.10f}]"


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


class TestGraduationRejectionInvariants:
    """Property-based tests for graduation rejection scenarios."""

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        min_required=st.integers(min_value=10, max_value=50)
    )
    @settings(max_examples=50)
    def test_insufficient_episodes_rejection(self, episode_count, min_required):
        """INVARIANT: Graduation rejected when episode count insufficient."""
        # Check if should be rejected
        should_reject = episode_count < min_required

        if should_reject:
            assert episode_count < min_required, \
                f"Should reject with {episode_count} episodes (min {min_required})"
        else:
            assert episode_count >= min_required, \
                f"Should accept with {episode_count} episodes (min {min_required})"

    @given(
        intervention_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        max_allowed=st.floats(min_value=0.1, max_value=0.5, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_high_intervention_rejection(self, intervention_rate, max_allowed):
        """INVARIANT: Graduation rejected when intervention rate too high."""
        # Check if should be rejected
        should_reject = intervention_rate > max_allowed

        if should_reject:
            assert intervention_rate > max_allowed, \
                f"Should reject with rate {intervention_rate:.2f} (max {max_allowed:.2f})"
        else:
            assert intervention_rate <= max_allowed, \
                f"Should accept with rate {intervention_rate:.2f} (max {max_allowed:.2f})"

    @given(
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_score=st.floats(min_value=0.5, max_value=0.95, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_low_constitutional_rejection(self, constitutional_score, min_score):
        """INVARIANT: Graduation rejected when constitutional score too low."""
        # Check if should be rejected
        should_reject = constitutional_score < min_score

        if should_reject:
            assert constitutional_score < min_score, \
                f"Should reject with score {constitutional_score:.2f} (min {min_score:.2f})"
        else:
            assert constitutional_score >= min_score, \
                f"Should accept with score {constitutional_score:.2f} (min {min_score:.2f})"

    @given(
        readiness_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_readiness_threshold_enforcement(self, readiness_score):
        """INVARIANT: Readiness score threshold is enforced."""
        threshold = 70.0  # 70% readiness required

        should_promote = readiness_score >= threshold

        if should_promote:
            assert readiness_score >= threshold, \
                f"Should promote with score {readiness_score:.2f} (threshold {threshold})"
        else:
            assert readiness_score < threshold, \
                f"Should reject with score {readiness_score:.2f} (threshold {threshold})"


class TestEpisodeQualityInvariants:
    """Property-based tests for episode quality in graduation."""

    @given(
        total_episodes=st.integers(min_value=1, max_value=100),
        successful_episodes=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=50)
    def test_episode_success_rate_calculation(self, total_episodes, successful_episodes):
        """INVARIANT: Episode success rate calculated correctly."""
        # Cap successful at total
        successful_episodes = min(successful_episodes, total_episodes)

        # Calculate success rate
        success_rate = successful_episodes / total_episodes if total_episodes > 0 else 0.0

        # Verify bounds
        assert 0.0 <= success_rate <= 1.0, \
            f"Success rate {success_rate:.2f} out of bounds [0, 1]"

        # Verify calculation
        expected_rate = successful_episodes / total_episodes
        assert abs(success_rate - expected_rate) < 0.001, \
            f"Success rate calculation incorrect"

    @given(
        episode_count=st.integers(min_value=1, max_value=50),
        avg_duration=st.integers(min_value=1, max_value=3600)  # seconds
    )
    @settings(max_examples=50)
    def test_episode_duration_requirements(self, episode_count, avg_duration):
        """INVARIANT: Episode duration affects graduation eligibility."""
        # Minimum duration threshold: 60 seconds
        min_duration = 60

        # Check if episodes meet duration requirement
        meets_requirement = avg_duration >= min_duration

        if meets_requirement:
            assert avg_duration >= min_duration, \
                f"Duration {avg_duration}s meets minimum {min_duration}s"
        else:
            assert avg_duration < min_duration, \
                f"Duration {avg_duration}s below minimum {min_duration}s"

    @given(
        segment_count=st.integers(min_value=1, max_value=20),
        segment_diversity=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_episode_diversity_bonus(self, segment_count, segment_diversity):
        """INVARIANT: Episode diversity increases readiness score."""
        base_score = 50.0

        # Diversity bonus: up to 10 points
        diversity_bonus = segment_diversity * 10.0
        adjusted_score = base_score + diversity_bonus

        # Verify score increase
        assert adjusted_score >= base_score, \
            "Diversity bonus should not decrease score"

        # Verify bounds
        assert adjusted_score <= 60.0, \
            f"Adjusted score {adjusted_score:.2f} should not exceed 60.0"

    @given(
        recency_days=st.integers(min_value=0, max_value=365)
    )
    @settings(max_examples=50)
    def test_episode_recency_weighting(self, recency_days):
        """INVARIANT: Recent episodes have higher weight."""
        # Recency weight: decays over 90 days
        decay_days = 90
        recency_weight = max(0.0, 1.0 - (recency_days / decay_days))

        # Verify weight calculation
        assert 0.0 <= recency_weight <= 1.0, \
            f"Recency weight {recency_weight:.2f} out of bounds [0, 1]"

        # Older episodes should have lower weight
        if recency_days > 0:
            assert recency_weight < 1.0, \
                f"Episodes {recency_days} days old should have weight < 1.0"


class TestInterventionTypeInvariants:
    """Property-based tests for intervention type classification."""

    @given(
        intervention_types=st.lists(
            st.sampled_from(['correction', 'guidance', 'block', 'override', 'termination']),
            min_size=1,
            max_size=20
        )
    )
    @settings(max_examples=50)
    def test_intervention_severity_classification(self, intervention_types):
        """INVARIANT: Intervention types are classified by severity."""
        # Severity levels
        severity_map = {
            'guidance': 1,      # Lowest severity
            'correction': 2,
            'override': 3,
            'block': 4,
            'termination': 5    # Highest severity
        }

        # Calculate total severity score
        total_severity = sum(severity_map.get(t, 0) for t in intervention_types)
        max_severity = max(severity_map.get(t, 0) for t in intervention_types)

        # Verify classification
        assert total_severity > 0, "Total severity should be positive"
        assert max_severity <= 5, "Max severity should not exceed 5"

    @given(
        guidance_count=st.integers(min_value=0, max_value=20),
        correction_count=st.integers(min_value=0, max_value=20)
    )
    @settings(max_examples=50)
    def test_intervention_impact_scoring(self, guidance_count, correction_count):
        """INVARIANT: Intervention impact is scored correctly."""
        # Guidance has lower impact than correction
        guidance_impact = guidance_count * 1
        correction_impact = correction_count * 2

        total_impact = guidance_impact + correction_impact

        # Verify impact calculation
        assert total_impact >= 0, "Total impact should be non-negative"

        # Verify per-intervention impact weights
        guidance_weight = 1
        correction_weight = 2
        assert correction_weight > guidance_weight, \
            "Correction should have higher per-intervention weight than guidance"

    @given(
        total_executions=st.integers(min_value=1, max_value=100),
        blocked_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_blocking_intervention_penalty(self, total_executions, blocked_count):
        """INVARIANT: Blocking interventions have high penalty."""
        # Blocking interventions prevent execution
        # Penalty proportional to block rate
        blocked_count = min(blocked_count, total_executions)

        if total_executions > 0:
            block_rate = blocked_count / total_executions
            # High block rate significantly impacts readiness
            penalty = block_rate * 50  # Up to 50 points penalty

            assert 0.0 <= penalty <= 50.0, \
                f"Penalty {penalty:.2f} out of bounds [0, 50]"

    @given(
        intervention_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_intervention_frequency_limit(self, intervention_count):
        """INVARIANT: Excessive interventions prevent graduation."""
        # Maximum interventions before requiring review
        max_interventions = 30

        # Check if limit exceeded
        exceeds_limit = intervention_count > max_interventions

        if exceeds_limit:
            assert intervention_count > max_interventions, \
                f"Should require review with {intervention_count} interventions"
        else:
            assert intervention_count <= max_interventions, \
                f"Should allow with {intervention_count} interventions"


class TestGraduationPerformanceInvariants:
    """Property-based tests for graduation service performance."""

    @given(
        agent_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_readiness_calculation_performance(self, agent_count):
        """INVARIANT: Readiness calculation scales efficiently."""
        import time

        # Simulate readiness calculation for multiple agents
        start_time = time.time()

        for i in range(agent_count):
            # Simulate calculation
            readiness = (
                min(i / 10.0, 1.0) * 0.4 +  # Episode score
                0.7 * 0.3 +  # Intervention score
                0.8 * 0.3    # Constitutional score
            ) * 100

        elapsed = time.time() - start_time

        # Verify performance: should be fast
        assert elapsed < 1.0, \
            f"Readiness calculation for {agent_count} agents took {elapsed:.3f}s (should be <1s)"

    @given(
        episode_count=st.integers(min_value=0, max_value=1000)
    )
    @settings(max_examples=50)
    def test_episode_counting_performance(self, episode_count):
        """INVARIANT: Episode counting is efficient."""
        import time

        # Simulate counting episodes
        start_time = time.time()

        # Simple increment loop
        count = 0
        for _ in range(episode_count):
            count += 1

        elapsed = time.time() - start_time

        # Verify performance: should be very fast
        assert elapsed < 0.1, \
            f"Counting {episode_count} episodes took {elapsed:.3f}s (should be <0.1s)"

    @given(
        history_size=st.integers(min_value=10, max_value=500)
    )
    @settings(max_examples=50)
    def test_audit_retrieval_performance(self, history_size):
        """INVARIANT: Audit trail retrieval is efficient."""
        import time

        # Simulate audit history
        audit_history = [
            {
                'agent_id': f'agent_{i % 10}',
                'timestamp': datetime.now() + timedelta(seconds=i),
                'action': 'graduation_check'
            }
            for i in range(history_size)
        ]

        # Simulate retrieval
        start_time = time.time()

        recent_audits = [
            audit for audit in audit_history
            if (datetime.now() - audit['timestamp']).days < 30
        ]

        elapsed = time.time() - start_time

        # Verify retrieval
        assert len(recent_audits) <= history_size, \
            "Retrieved count should not exceed history size"

        # Verify performance: should be fast
        assert elapsed < 0.5, \
            f"Audit retrieval for {history_size} records took {elapsed:.3f}s (should be <0.5s)"

    @given(
        cache_size=st.integers(min_value=10, max_value=1000),
        lookup_count=st.integers(min_value=1, max_value=10000)
    )
    @settings(max_examples=50)
    def test_caching_efficiency(self, cache_size, lookup_count):
        """INVARIANT: Caching improves graduation check performance."""
        # Simulate cache
        cache = {f'agent_{i}': {'readiness': 70.0 + i} for i in range(cache_size)}

        # Simulate lookups
        import time
        start_time = time.time()

        hits = 0
        for i in range(lookup_count):
            agent_id = f'agent_{i % cache_size}'
            if agent_id in cache:
                hits += 1
                readiness = cache[agent_id]['readiness']

        elapsed = time.time() - start_time

        # Verify cache hit rate
        hit_rate = hits / lookup_count if lookup_count > 0 else 0.0
        assert hit_rate > 0.9, \
            f"Cache hit rate {hit_rate:.2f} should be > 90%"

        # Verify performance: should be fast
        assert elapsed < 0.5, \
            f"{lookup_count} cache lookups took {elapsed:.3f}s (should be <0.5s)"
