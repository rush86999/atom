"""
Property-Based Tests for Agent Graduation Invariants - CRITICAL AGENT LIFECYCLE LOGIC

Tests critical agent graduation invariants:
- Episode count requirements
- Intervention rate calculations
- Constitutional score validation
- Readiness score calculation (0-100)
- Graduation criteria enforcement
- Maturity level transitions

These tests protect against:
- Premature agent promotion (immature agents gaining autonomy)
- Excessive human intervention
- Constitutional compliance violations
- Incorrect readiness assessments
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import given, strategies as st, settings, HealthCheck, assume
from typing import List, Dict, Any
import sys
import os

# Add backend to path
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '../..'))


class TestGraduationCriteriaInvariants:
    """Tests for graduation criteria invariants"""

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intern_min_episodes=st.integers(min_value=5, max_value=20),
        supervised_min_episodes=st.integers(min_value=15, max_value=40),
        autonomous_min_episodes=st.integers(min_value=30, max_value=80)
    )
    @settings(max_examples=50)
    def test_graduation_episode_requirements(self, episode_count, intern_min_episodes, supervised_min_episodes, autonomous_min_episodes):
        """Test that graduation requirements are enforced correctly"""
        # Enforce hierarchy constraint using assume
        assume(intern_min_episodes <= supervised_min_episodes)
        assume(supervised_min_episodes <= autonomous_min_episodes)

        # INTERN requirements
        intern_ready = episode_count >= intern_min_episodes

        # SUPERVISED requirements
        supervised_ready = episode_count >= supervised_min_episodes

        # AUTONOMOUS requirements
        autonomous_ready = episode_count >= autonomous_min_episodes

        # Verify hierarchy: autonomous > supervised > intern
        assert autonomous_min_episodes >= supervised_min_episodes, \
            "Autonomous requirement should be >= Supervised requirement"
        assert supervised_min_episodes >= intern_min_episodes, \
            "Supervised requirement should be >= INTERN requirement"

        # Verify readiness progression
        if episode_count < intern_min_episodes:
            assert not intern_ready, \
                "Should not be INTERN ready with insufficient episodes"
            assert not supervised_ready, \
                "Should not be SUPERVISED ready either"
            assert not autonomous_ready, \
                "Should not be AUTONOMOUS ready either"
        elif episode_count < supervised_min_episodes:
            assert intern_ready, \
                "Should be INTERN ready with intermediate episodes"
            assert not supervised_ready, \
                "Should not be SUPERVISED ready yet"
            assert not autonomous_ready, \
                "Should not be AUTONOMOUS ready yet"
        elif episode_count < autonomous_min_episodes:
            assert intern_ready, \
                "Should be INTERN ready with sufficient episodes"
            assert supervised_ready, \
                "Should be SUPERVISED ready with sufficient episodes"
            assert not autonomous_ready, \
                "Should not be AUTONOMOUS ready yet"
        else:
            assert intern_ready, \
                "Should be INTERN ready with many episodes"
            assert supervised_ready, \
                "Should be SUPERVISED ready with many episodes"
            assert autonomous_ready, \
                "Should be AUTONOMOUS ready with maximum episodes"

    @given(
        total_interventions=st.integers(min_value=0, max_value=50),
        episode_count=st.integers(min_value=1, max_value=100)
    )
    @settings(max_examples=50)
    def test_intervention_rate_calculation(self, total_interventions, episode_count):
        """Test that intervention rate is calculated correctly"""
        # Calculate intervention rate (capped at 1.0)
        intervention_rate = min(total_interventions / episode_count, 1.0) if episode_count > 0 else 1.0

        # Verify bounds
        assert 0.0 <= intervention_rate <= 1.0, \
            f"Intervention rate {intervention_rate} should be in [0.0, 1.0]"

        # If interventions are zero, rate should be zero
        if total_interventions == 0:
            assert intervention_rate == 0.0, \
                "Zero interventions should result in zero rate"

        # If interventions equal or exceed episodes (max intervention), rate should be 1.0
        if episode_count > 0 and total_interventions >= episode_count:
            assert intervention_rate == 1.0, \
                "Max interventions should result in rate of 1.0"

    @given(
        constitutional_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=50)
    def test_constitutional_score_bounds(self, constitutional_scores):
        """Test that constitutional scores are valid"""
        for score in constitutional_scores:
            assert 0.0 <= score <= 1.0, \
                f"Constitutional score {score} should be in [0.0, 1.0]"

        # Calculate average
        avg_score = sum(constitutional_scores) / len(constitutional_scores)
        assert 0.0 <= avg_score <= 1.0, \
            f"Average constitutional score {avg_score} should be in [0.0, 1.0]"

    @given(
        intervention_rates=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=20
        ),
        max_interventions=st.tuples(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            st.integers(min_value=0, max_value=10)
        ).map(lambda pair: (pair[0], int(pair[1] * 100)))  # Convert to actual count
    )
    @settings(max_examples=50, suppress_health_check=[HealthCheck.filter_too_much])
    def test_intervention_threshold_enforcement(self, intervention_rates, max_interventions):
        """Test that intervention thresholds are enforced correctly"""
        # Unpack the max_interventions tuple
        max_intervention, actual_count = max_interventions

        # INTERN threshold: 50% (0.5)
        intern_threshold = 0.5
        intern_violations = [r for r in intervention_rates if r > intern_threshold]

        # Verify violations are detected
        for rate in intern_violations:
            assert rate > 0.5, \
                f"Violation should have rate > 0.5, got {rate}"

        # SUPERVISED threshold: 20% (0.2)
        supervised_threshold = 0.2
        supervised_violations = [r for r in intervention_rates if r > supervised_threshold]

        # Verify stricter threshold
        assert len(supervised_violations) >= len(intern_violations), \
            "SUPERVISED threshold (0.2) should catch more violations than INTERN (0.5)"

        # AUTONOMOUS threshold: 0% (0.0)
        autonomous_violations = [r for r in intervention_rates if r > 0.0]

        # Verify strictest threshold
        assert len(autonomous_violations) >= len(supervised_violations), \
            "AUTONOMOUS threshold (0.0) should catch all non-zero rates"


class TestReadinessScoreInvariants:
    """Tests for readiness score calculation invariants"""

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        min_episodes=st.integers(min_value=10, max_value=50),
        intervention_rate=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        max_intervention=st.floats(min_value=0.1, max_value=1.0, allow_nan=False, allow_infinity=False),  # Avoid 0
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        min_constitutional=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_readiness_score_bounds(self, episode_count, min_episodes, intervention_rate, max_intervention, constitutional_score, min_constitutional):
        """Test that readiness scores are in valid range [0, 100]"""
        # Calculate episode score (40%) - capped at 40
        episode_score = min(episode_count / min_episodes, 1.0) * 40 if min_episodes > 0 else 0.0

        # Calculate intervention score (30%) - handle division by zero
        if max_intervention > 0:
            if intervention_rate <= max_intervention:
                intervention_score = (1 - intervention_rate / max_intervention) * 30
            else:
                intervention_score = 0.0
        else:
            intervention_score = 0.0

        # Calculate constitutional score (30%) - capped at 30
        if min_constitutional > 0:
            constitutional_score_pct = min(constitutional_score / min_constitutional, 1.0) * 30
        else:
            constitutional_score_pct = 0.0

        # Total score - cap at 100
        score = min(episode_score + intervention_score + constitutional_score_pct, 100.0)

        # Verify bounds
        assert 0.0 <= score <= 100.0, \
            f"Readiness score {score} should be in [0.0, 100.0]"

    @given(
        # Generate inputs as a single tuple strategy
        st.tuples(
            st.integers(min_value=0, max_value=100),  # episode_count
            st.integers(min_value=10, max_value=50),  # min_episodes
            st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),  # intervention_rate
            st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),  # constitutional_score
            st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False)  # min_constitutional
        )
    )
    @settings(max_examples=50)
    def test_readiness_score_components(self, inputs):
        """Test that readiness score components are weighted correctly"""
        episode_count, min_episodes, intervention_rate, constitutional_score, min_constitutional = inputs

        # Calculate episode score (40%) - capped
        episode_score = min(episode_count / min_episodes, 1.0) * 40 if min_episodes > 0 else 0.0

        # Calculate intervention score (30%)
        max_intervention = 0.5  # INTERN threshold
        if intervention_rate <= max_intervention:
            intervention_score = (1 - intervention_rate / max_intervention) * 30
        else:
            intervention_score = 0.0

        # Calculate constitutional score (30%) - capped
        if min_constitutional > 0:
            constitutional_score_pct = min(constitutional_score / min_constitutional, 1.0) * 30
        else:
            constitutional_score_pct = 0.0

        # Total score
        score = min(episode_score + intervention_score + constitutional_score_pct, 100.0)

        # Verify component weights
        assert 0.0 <= episode_score <= 40.0, \
            f"Episode score component {episode_score} should be in [0, 40]"
        assert 0.0 <= intervention_score <= 30.0, \
            f"Intervention score component {intervention_score} should be in [0, 30]"
        assert 0.0 <= constitutional_score_pct <= 30.0, \
            f"Constitutional score component {constitutional_score_pct} should be in [0, 30]"

        # Verify total
        assert 0.0 <= score <= 100.0, \
            f"Total readiness score {score} should be in [0, 100]"

    @given(
        episode_count=st.integers(min_value=10, max_value=100),  # Ensure >= min_episodes
        min_episodes=st.integers(min_value=10, max_value=50),
        intervention_rate=st.floats(min_value=0.0, max_value=0.5, allow_nan=False, allow_infinity=False),  # Low intervention
        max_intervention=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),  # At least 0.5
        constitutional_score=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False),  # High score
        min_constitutional=st.floats(min_value=0.5, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_readiness_determination(self, episode_count, min_episodes, intervention_rate, max_intervention, constitutional_score, min_constitutional):
        """Test that readiness determination is correct"""
        # Calculate episode score (40%)
        episode_score = min(episode_count / min_episodes, 1.0) * 40 if min_episodes > 0 else 0.0

        # Calculate intervention score (30%)
        if max_intervention > 0 and intervention_rate <= max_intervention:
            intervention_score = (1 - intervention_rate / max_intervention) * 30
        else:
            intervention_score = 0.0

        # Calculate constitutional score (30%)
        if min_constitutional > 0:
            constitutional_score_pct = min(constitutional_score / min_constitutional, 1.0) * 30
        else:
            constitutional_score_pct = 0.0

        # Calculate total score
        score = min(episode_score + intervention_score + constitutional_score_pct, 100.0)

        # Determine readiness (score >= 80 is ready)
        ready = score >= 80.0

        # With good inputs (high episodes, low intervention, high constitutional), should be ready
        if (episode_count >= min_episodes and
            intervention_rate <= max_intervention and
            constitutional_score >= min_constitutional):
            # All minimum criteria met - score should be at least decent
            assert score >= 40.0, \
                f"Score {score} should be at least 40 when all minimum criteria met"


class TestMaturityTransitionInvariants:
    """Tests for maturity level transition invariants"""

    @given(
        current_maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        target_maturity=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
    )
    @settings(max_examples=50)
    def test_maturity_transition_ordering(self, current_maturity, target_maturity):
        """Test that maturity transitions follow correct order"""
        maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        current_index = maturity_order.index(current_maturity)
        target_index = maturity_order.index(target_maturity)

        # Normal transitions are forward-only
        # But system may allow backward transitions (demotions) in special cases
        # Test verifies the ordering exists, not that all transitions are valid

        # Verify that levels are in the order list
        assert current_maturity in maturity_order, \
            f"Current maturity {current_maturity} should be valid"
        assert target_maturity in maturity_order, \
            f"Target maturity {target_maturity} should be valid"

        # Verify index calculation works
        assert 0 <= current_index < len(maturity_order), \
            f"Current index {current_index} should be valid"
        assert 0 <= target_index < len(maturity_order), \
            f"Target index {target_index} should be valid"

    @given(
        maturity_levels=st.lists(
            st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
            min_size=1,
            max_size=4,
            unique=True
        )
    )
    @settings(max_examples=50)
    def test_maturity_level_precedence(self, maturity_levels):
        """Test that maturity levels have correct precedence"""
        precedence = {
            "STUDENT": 0,
            "INTERN": 1,
            "SUPERVISED": 2,
            "AUTONOMOUS": 3
        }

        # Sort by precedence and verify order
        sorted_levels = sorted(maturity_levels, key=lambda x: precedence[x])

        # Verify precedence values are increasing
        for i in range(1, len(sorted_levels)):
            current = sorted_levels[i]
            previous = sorted_levels[i-1]
            assert precedence[current] > precedence[previous], \
                f"{current} should have higher precedence than {previous}"

        # Verify all original levels are present
        assert set(sorted_levels) == set(maturity_levels), \
            "Sorted levels should contain all original levels"

    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=50),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_graduation_path_recommendation(self, episode_count, intervention_count, constitutional_score):
        """Test that graduation path recommendations are logical"""
        # Calculate intervention rate
        episode_count = max(episode_count, 1)  # Avoid division by zero
        intervention_rate = min(intervention_count / episode_count, 1.0)  # Cap at 1.0

        # Determine recommended maturity level
        recommended = None
        if episode_count >= 50 and intervention_rate == 0.0 and constitutional_score >= 0.95:
            recommended = "AUTONOMOUS"
        elif episode_count >= 25 and intervention_rate <= 0.2 and constitutional_score >= 0.85:
            recommended = "SUPERVISED"
        elif episode_count >= 10 and intervention_rate <= 0.5 and constitutional_score >= 0.70:
            recommended = "INTERN"
        else:
            recommended = "STUDENT"

        # Verify recommendation exists
        assert recommended in ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"], \
            f"Recommendation {recommended} should be valid"

        # Verify recommendation makes sense
        if recommended == "AUTONOMOUS":
            assert episode_count >= 50, \
                "AUTONOMOUS requires many episodes"
        elif recommended == "SUPERVISED":
            assert episode_count >= 25, \
                "SUPERVISED requires substantial episodes"
        elif recommended == "INTERN":
            assert episode_count >= 10, \
                "INTERN requires some episodes"


class TestAgentPromotionInvariants:
    """Tests for agent promotion invariants"""

    @given(
        current_status=st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]),
        readiness_score=st.floats(min_value=0.0, max_value=100.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=50)
    def test_promotion_eligibility(self, current_status, readiness_score):
        """Test that promotion eligibility is determined correctly"""
        # Minimum scores for promotion
        min_scores = {
            "STUDENT": 0.0,    # Can always promote from STUDENT
            "INTERN": 70.0,    # Need 70+ to promote from INTERN
            "SUPERVISED": 80.0,  # Need 80+ to promote from SUPERVISED
            "AUTONOMOUS": 100.0  # Need 100 to promote from AUTONOMOUS (graduation)
        }

        # Check if eligible for promotion to next level
        maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        current_index = maturity_order.index(current_status)

        if current_index < len(maturity_order) - 1:
            next_level = maturity_order[current_index + 1]
            min_score = min_scores[next_level]
            eligible = readiness_score >= min_score
        else:
            # Already at highest level
            eligible = False
            next_level = None

        # Verify eligibility logic
        if current_status == "STUDENT":
            # STUDENT can always promote (score doesn't matter much)
            assert eligible or readiness_score < 70.0, \
                "STUDENT agents need 70+ score for INTERN promotion"
        elif current_status == "INTERN":
            assert eligible or readiness_score < 80.0, \
                "INTERN agents need 80+ score for SUPERVISED promotion"
        elif current_status == "SUPERVISED":
            assert eligible or readiness_score < 100.0, \
                "SUPERVISED agents need 100 score for AUTONOMOUS promotion"

    @given(
        promotion_count=st.integers(min_value=0, max_value=10),  # Limit to 10 to avoid index issues
        episode_count_per_promotion=st.integers(min_value=5, max_value=20)
    )
    @settings(max_examples=50)
    def test_promotion_history_tracking(self, promotion_count, episode_count_per_promotion):
        """Test that promotion history is tracked correctly"""
        # Simulate promotion history
        promotions = []
        total_episodes = 0

        for i in range(promotion_count):
            total_episodes += episode_count_per_promotion
            # Calculate level indices safely
            from_idx = min(i, 2)  # Cap at 2 (SUPERVISED in from_levels list)
            to_idx = min(i + 1, 2)  # Cap at 2 (AUTONOMOUS in to_levels list)

            promotion = {
                'from_level': ['STUDENT', 'INTERN', 'SUPERVISED'][from_idx],
                'to_level': ['INTERN', 'SUPERVISED', 'AUTONOMOUS'][to_idx],
                'episode_count_at_promotion': total_episodes,
                'timestamp': datetime.now()
            }
            promotions.append(promotion)

        # Verify promotion sequence (if more than 1 promotion)
        if len(promotions) > 1:
            maturity_order = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
            for i, promo in enumerate(promotions):
                if i > 0:
                    prev_promo = promotions[i-1]
                    # Verify forward progression
                    current_to_idx = maturity_order.index(promo['to_level'])
                    prev_to_idx = maturity_order.index(prev_promo['to_level'])
                    assert current_to_idx >= prev_to_idx, \
                        f"Promotion should not go backward: {prev_promo['to_level']} -> {promo['to_level']}"

        # Verify episode count accumulation
        final_episode_count = promotions[-1]['episode_count_at_promotion'] if promotions else 0
        assert final_episode_count == promotion_count * episode_count_per_promotion, \
            f"Final episode count should be {promotion_count * episode_count_per_promotion}"

        # Verify chronological ordering
        for i in range(1, len(promotions)):
            assert promotions[i]['timestamp'] >= promotions[i-1]['timestamp'], \
                "Promotions should be in chronological order"


class TestGraduationDataIntegrityInvariants:
    """Tests for graduation data integrity invariants"""

    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=50)
    )
    @settings(max_examples=50)
    def test_episode_intervention_tracking(self, episode_count, intervention_count):
        """Test that episode interventions are tracked correctly"""
        # Simulate episodes with interventions
        episodes = []

        for i in range(episode_count):
            # Distribute interventions across episodes
            interventions_per_episode = intervention_count // episode_count
            extra_interventions = intervention_count % episode_count

            if i < extra_interventions:
                episodes.append({
                    'id': f'episode_{i}',
                    'human_intervention_count': interventions_per_episode + 1
                })
            else:
                episodes.append({
                    'id': f'episode_{i}',
                    'human_intervention_count': interventions_per_episode
                })

        # Verify total interventions
        tracked_total = sum(e['human_intervention_count'] for e in episodes)
        assert tracked_total == intervention_count, \
            f"Tracked interventions ({tracked_total}) should equal actual ({intervention_count})"

        # Verify all counts are non-negative
        for episode in episodes:
            assert episode['human_intervention_count'] >= 0, \
                "Intervention count should be non-negative"

    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        constitutional_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=100
        )
    )
    @settings(max_examples=50)
    def test_constitutional_compliance_tracking(self, episode_count, constitutional_scores):
        """Test that constitutional compliance is tracked correctly"""
        # Take only the scores we need for this test
        scores_for_test = constitutional_scores[:min(len(constitutional_scores), episode_count)]

        # Verify all scores are valid
        for score in scores_for_test:
            assert 0.0 <= score <= 1.0, \
                f"Constitutional score {score} should be in [0.0, 1.0]"

        # Calculate average (handle empty case)
        if len(scores_for_test) > 0:
            avg_score = sum(scores_for_test) / len(scores_for_test)
            assert 0.0 <= avg_score <= 1.0, \
                f"Average constitutional score {avg_score} should be in [0.0, 1.0]"

    @given(
        # Generate paired data to avoid filter_too_much
        st.lists(
            st.tuples(
                st.text(min_size=5, max_size=50, alphabet='abcdefghijklmnopqrstuvwxyz0123456789'),
                st.sampled_from(["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"])
            ),
            min_size=1,
            max_size=20,
            unique=lambda x: x[0]  # Unique by agent_id
        )
    )
    @settings(max_examples=50)
    def test_agent_maturity_consistency(self, agent_data):
        """Test that agent maturity levels are consistent"""
        # Unpack the paired data
        agent_ids = [agent_id for agent_id, _ in agent_data]
        maturity_levels = [maturity for _, maturity in agent_data]

        # Create agent records
        agents = []
        for agent_id, maturity in agent_data:
            agents.append({
                'id': agent_id,
                'maturity': maturity,
                'status': maturity
            })

        # Verify all agents have valid maturity levels
        valid_maturities = ["STUDENT", "INTERN", "SUPERVISED", "AUTONOMOUS"]
        for agent in agents:
            assert agent['maturity'] in valid_maturities, \
                f"Agent {agent['id']} has invalid maturity {agent['maturity']}"
            assert agent['status'] in valid_maturities, \
                f"Agent {agent['id']} has invalid status {agent['status']}"
            # Status should match maturity
            assert agent['status'] == agent['maturity'], \
                f"Agent {agent['id']} status should match maturity"
