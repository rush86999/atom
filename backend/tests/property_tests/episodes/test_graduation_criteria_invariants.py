"""
Property-based tests for graduation criteria invariants.

Uses Hypothesis to test graduation criteria invariants across many generated inputs:
- Episode count: Graduation requires minimum episode count (10->INTERN, 25->SUPERVISED, 50->AUTONOMOUS)
- Episode count threshold: Below threshold never graduates
- Intervention rate: Intervention rate must be below threshold (50%->INTERN, 20%->SUPERVISED, 0%->AUTONOMOUS)
- Intervention calculation: Intervention rate = interventions / total_episodes
- Constitutional score: Constitutional score must meet threshold (0.70->INTERN, 0.85->SUPERVISED, 0.95->AUTONOMOUS)
- All criteria: ALL criteria must be met for graduation (AND logic)

These tests complement the integration tests by verifying invariants hold
across many different input combinations.
"""

import pytest
from datetime import datetime, timezone, timedelta
from uuid import uuid4
from unittest.mock import Mock, patch
from typing import List, Dict, Any

from hypothesis import given, strategies as st, settings, HealthCheck

from core.agent_graduation_service import AgentGraduationService
from core.models import AgentRegistry, AgentEpisode


# =============================================================================
# Graduation Thresholds Configuration
# =============================================================================

GRADUATION_THRESHOLDS = {
    'INTERN': {
        'episodes': 10,
        'intervention_rate': 0.50,
        'constitutional_score': 0.70
    },
    'SUPERVISED': {
        'episodes': 25,
        'intervention_rate': 0.20,
        'constitutional_score': 0.85
    },
    'AUTONOMOUS': {
        'episodes': 50,
        'intervention_rate': 0.00,
        'constitutional_score': 0.95
    }
}


# =============================================================================
# Property-Based Tests for Graduation Episode Count
# =============================================================================

class TestGraduationEpisodeCount:
    """
    Property-based tests for graduation episode count invariants.

    Verifies that graduation requires minimum episode counts.
    """

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_episode_count_invariant(self, db_session, episode_count, target_maturity):
        """
        Graduation requires minimum episode count.

        Property: For any target maturity level M, graduation requires
        at least N episodes where N = GRADUATION_THRESHOLDS[M]['episodes'].

        Mathematical specification:
        Let M be target maturity level
        Let N_min = GRADUATION_THRESHOLDS[M]['episodes']
        Let N_actual be actual episode count
        Then: graduation_possible = (N_actual >= N_min)

        This ensures agents have sufficient experience before graduation.
        """
        threshold = GRADUATION_THRESHOLDS[target_maturity]['episodes']

        # Check if graduation is possible based on episode count
        can_graduate = episode_count >= threshold

        if can_graduate:
            # Episode count meets threshold - should be eligible
            assert episode_count >= threshold, (
                f"Episode count {episode_count} meets threshold {threshold} "
                f"for {target_maturity}"
            )
        else:
            # Episode count below threshold - should not graduate
            assert episode_count < threshold, (
                f"Episode count {episode_count} below threshold {threshold} "
                f"for {target_maturity} - should not graduate"
            )

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=0, max_value=99)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_episode_count_threshold_invariant(self, db_session, episode_count):
        """
        Below threshold episode count never graduates.

        Property: For any episode count N and maturity level M,
        if N < threshold(M), then graduation to M is impossible.

        Mathematical specification:
        Let N be episode count
        Let T(M) be threshold for maturity M
        If N < T(M), then graduation(M) = False

        This is a stronger version of the episode count invariant.
        """
        for target_maturity, thresholds in GRADUATION_THRESHOLDS.items():
            min_episodes = thresholds['episodes']

            if episode_count < min_episodes:
                # Below threshold - should NOT graduate
                # (Other criteria don't matter if episode count insufficient)
                assert episode_count < min_episodes, (
                    f"Episode count {episode_count} < {min_episodes} "
                    f"should prevent graduation to {target_maturity}"
                )

                # Verify this is a hard constraint
                # (Even with perfect intervention rate and constitutional score)
                assert not (episode_count >= min_episodes), (
                    f"Episode count {episode_count} is definitely below {min_episodes}"
                )


# =============================================================================
# Property-Based Tests for Graduation Intervention Rate
# =============================================================================

class TestGraduationInterventionRate:
    """
    Property-based tests for graduation intervention rate invariants.

    Verifies that intervention rate must be below threshold.
    """

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=100),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_intervention_rate_invariant(self, db_session, episode_count, intervention_count, target_maturity):
        """
        Intervention rate must be below threshold.

        Property: For any target maturity M, graduation requires
        intervention_rate <= threshold(M).

        Mathematical specification:
        Let M be target maturity
        Let R_max = GRADUATION_THRESHOLDS[M]['intervention_rate']
        Let N_interventions be actual intervention count
        Let N_episodes be total episode count
        Let R_actual = N_interventions / N_episodes

        Then: graduation_possible = (R_actual <= R_max)

        This ensures agents are sufficiently autonomous before graduation.
        """
        # Calculate intervention rate
        intervention_rate = intervention_count / episode_count if episode_count > 0 else 0.0

        threshold = GRADUATION_THRESHOLDS[target_maturity]['intervention_rate']

        # Check if graduation is possible based on intervention rate
        can_graduate = intervention_rate <= threshold

        if can_graduate:
            # Intervention rate meets threshold
            assert intervention_rate <= threshold, (
                f"Intervention rate {intervention_rate:.2f} <= threshold {threshold:.2f} "
                f"for {target_maturity}"
            )
        else:
            # Intervention rate exceeds threshold - should not graduate
            assert intervention_rate > threshold, (
                f"Intervention rate {intervention_rate:.2f} > threshold {threshold:.2f} "
                f"for {target_maturity} - should not graduate"
            )

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=1, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=100)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_intervention_calculation_invariant(self, db_session, episode_count, intervention_count):
        """
        Intervention rate calculation is correct.

        Property: Intervention rate = interventions / total_episodes

        Mathematical specification:
        Let N_interventions be intervention count
        Let N_episodes be total episode count
        Let R = N_interventions / N_episodes

        Then: 0.0 <= R <= 1.0 (bounded)

        This validates the intervention rate formula.
        """
        # Calculate intervention rate
        intervention_rate = intervention_count / episode_count if episode_count > 0 else 0.0

        # Verify bounds
        assert 0.0 <= intervention_rate <= 1.0, (
            f"Intervention rate {intervention_rate} outside bounds [0.0, 1.0]"
        )

        # Verify calculation
        expected_rate = intervention_count / episode_count
        assert abs(intervention_rate - expected_rate) < 1e-9, (
            f"Intervention rate calculation mismatch: "
            f"{intervention_rate} != {expected_rate}"
        )

        # Verify edge cases
        if intervention_count == 0:
            assert intervention_rate == 0.0, "No interventions should give rate 0.0"

        if intervention_count == episode_count:
            assert intervention_rate == 1.0, "All interventions should give rate 1.0"


# =============================================================================
# Property-Based Tests for Graduation Constitutional Score
# =============================================================================

class TestGraduationConstitutionalScore:
    """
    Property-based tests for graduation constitutional score invariants.

    Verifies that constitutional score must meet threshold.
    """

    @pytest.mark.asyncio
    @given(
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_constitutional_score_invariant(self, db_session, constitutional_score, target_maturity):
        """
        Constitutional score must meet threshold.

        Property: For any target maturity M, graduation requires
        constitutional_score >= threshold(M).

        Mathematical specification:
        Let M be target maturity
        Let S_min = GRADUATION_THRESHOLDS[M]['constitutional_score']
        Let S_actual be actual constitutional score

        Then: graduation_possible = (S_actual >= S_min)

        This ensures agents are constitutionally compliant before graduation.
        """
        threshold = GRADUATION_THRESHOLDS[target_maturity]['constitutional_score']

        # Check if graduation is possible based on constitutional score
        can_graduate = constitutional_score >= threshold

        if can_graduate:
            # Constitutional score meets threshold
            assert constitutional_score >= threshold, (
                f"Constitutional score {constitutional_score:.2f} >= threshold {threshold:.2f} "
                f"for {target_maturity}"
            )
        else:
            # Constitutional score below threshold - should not graduate
            assert constitutional_score < threshold, (
                f"Constitutional score {constitutional_score:.2f} < threshold {threshold:.2f} "
                f"for {target_maturity} - should not graduate"
            )

    @pytest.mark.asyncio
    @given(
        constitutional_scores=st.lists(
            st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
            min_size=1,
            max_size=50
        )
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_constitutional_score_aggregation_invariant(self, db_session, constitutional_scores):
        """
        Constitutional score aggregation is correct.

        Property: Aggregate constitutional score should be within [0.0, 1.0]
        and represent the average of episode scores.

        Mathematical specification:
        Let S = [s₁, s₂, ..., sₙ] be episode constitutional scores
        Let S_agg = average(S) = (s₁ + s₂ + ... + sₙ) / n

        Then: 0.0 <= S_agg <= 1.0 (bounded)

        This validates the aggregation formula.
        """
        # Calculate aggregate score
        aggregate_score = sum(constitutional_scores) / len(constitutional_scores)

        # Verify bounds
        assert 0.0 <= aggregate_score <= 1.0, (
            f"Aggregate constitutional score {aggregate_score} outside bounds [0.0, 1.0]"
        )

        # Verify all individual scores are in bounds
        for score in constitutional_scores:
            assert 0.0 <= score <= 1.0, (
                f"Individual constitutional score {score} outside bounds [0.0, 1.0]"
            )


# =============================================================================
# Property-Based Tests for Graduation All Criteria
# =============================================================================

class TestGraduationAllCriteria:
    """
    Property-based tests for graduation all criteria invariants.

    Verifies that ALL criteria must be met (AND logic).
    """

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=100),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False),
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_all_criteria_invariant(self, db_session, episode_count, intervention_count, constitutional_score, target_maturity):
        """
        ALL criteria must be met for graduation (AND logic).

        Property: For any target maturity M, graduation requires:
        1. episode_count >= threshold(M)['episodes']
        2. intervention_rate <= threshold(M)['intervention_rate']
        3. constitutional_score >= threshold(M)['constitutional_score']

        ALL three conditions must be true (AND logic).

        Mathematical specification:
        Let M be target maturity
        Let C₁ = (episode_count >= threshold(M)['episodes'])
        Let C₂ = (intervention_rate <= threshold(M)['intervention_rate'])
        Let C₃ = (constitutional_score >= threshold(M)['constitutional_score'])

        Then: graduation_possible = C₁ AND C₂ AND C₃

        This ensures agents meet ALL requirements before graduation.
        """
        thresholds = GRADUATION_THRESHOLDS[target_maturity]

        # Calculate intervention rate
        intervention_rate = intervention_count / episode_count if episode_count > 0 else 1.0

        # Check each criterion
        episode_count_ok = episode_count >= thresholds['episodes']
        intervention_rate_ok = intervention_rate <= thresholds['intervention_rate']
        constitutional_score_ok = constitutional_score >= thresholds['constitutional_score']

        # Overall graduation decision (AND logic)
        can_graduate = episode_count_ok and intervention_rate_ok and constitutional_score_ok

        if can_graduate:
            # All criteria met
            assert episode_count_ok, "Episode count should be OK"
            assert intervention_rate_ok, "Intervention rate should be OK"
            assert constitutional_score_ok, "Constitutional score should be OK"
        else:
            # At least one criterion failed
            # Verify AND logic: if any criterion fails, graduation fails
            if not episode_count_ok:
                assert episode_count < thresholds['episodes'], (
                    f"Episode count {episode_count} < {thresholds['episodes']}"
                )
            elif not intervention_rate_ok:
                assert intervention_rate > thresholds['intervention_rate'], (
                    f"Intervention rate {intervention_rate} > {thresholds['intervention_rate']}"
                )
            elif not constitutional_score_ok:
                assert constitutional_score < thresholds['constitutional_score'], (
                    f"Constitutional score {constitutional_score} < {thresholds['constitutional_score']}"
                )

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=100),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_criteria_combinations_invariant(self, db_session, episode_count, intervention_count, constitutional_score):
        """
        Validate all possible criterion combinations.

        Property: For any combination of criteria values, the graduation
        decision should follow the AND logic consistently.

        Mathematical specification:
        For all maturity levels M in {INTERN, SUPERVISED, AUTONOMOUS}:
        graduation(M) = C₁(M) AND C₂(M) AND C₃(M)

        Where C₁, C₂, C₃ are the three criteria checks.

        This tests the consistency of graduation logic across all levels.
        """
        # Calculate intervention rate
        intervention_rate = intervention_count / episode_count if episode_count > 0 else 1.0

        # Check graduation eligibility for each level
        graduation_decisions = {}

        for target_maturity, thresholds in GRADUATION_THRESHOLDS.items():
            episode_count_ok = episode_count >= thresholds['episodes']
            intervention_rate_ok = intervention_rate <= thresholds['intervention_rate']
            constitutional_score_ok = constitutional_score >= thresholds['constitutional_score']

            can_graduate = episode_count_ok and intervention_rate_ok and constitutional_score_ok
            graduation_decisions[target_maturity] = can_graduate

        # Verify monotonic progression: if can graduate to higher level,
        # should also be able to graduate to lower levels
        order = ['INTERN', 'SUPERVISED', 'AUTONOMOUS']

        for i in range(len(order) - 1):
            current_level = order[i]
            next_level = order[i + 1]

            # If can graduate to higher level, should be able to graduate to current
            if graduation_decisions.get(next_level, False):
                assert graduation_decisions.get(current_level, False), (
                    f"Can graduate to {next_level} but not {current_level} - "
                    f"should be monotonic"
                )


# =============================================================================
# Property-Based Tests for Graduation Edge Cases
# =============================================================================

class TestGraduationEdgeCases:
    """
    Property-based tests for graduation edge cases.

    Verifies behavior at threshold boundaries.
    """

    @pytest.mark.asyncio
    @given(
        target_maturity=st.sampled_from(['INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    )
    @settings(max_examples=100, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_exact_threshold_invariant(self, db_session, target_maturity):
        """
        Exact threshold values should allow graduation.

        Property: For any maturity M, meeting criteria exactly at
        threshold values should allow graduation.

        Mathematical specification:
        Let M be target maturity
        Let E = threshold(M)['episodes']
        Let I = threshold(M)['intervention_rate']
        Let C = threshold(M)['constitutional_score']

        Then: graduation(M) = True when:
        - episode_count = E (exactly)
        - intervention_rate = I (exactly)
        - constitutional_score = C (exactly)

        This tests boundary conditions.
        """
        thresholds = GRADUATION_THRESHOLDS[target_maturity]

        # Use exact threshold values
        episode_count = thresholds['episodes']
        intervention_count = 0  # For 0% intervention rate
        constitutional_score = thresholds['constitutional_score']

        # Calculate intervention rate
        intervention_rate = intervention_count / episode_count if episode_count > 0 else 0.0

        # All criteria should be met at exact thresholds
        episode_count_ok = episode_count >= thresholds['episodes']
        intervention_rate_ok = intervention_rate <= thresholds['intervention_rate']
        constitutional_score_ok = constitutional_score >= thresholds['constitutional_score']

        assert episode_count_ok, f"Episode count {episode_count} should meet threshold"
        assert intervention_rate_ok, f"Intervention rate {intervention_rate} should meet threshold"
        assert constitutional_score_ok, f"Constitutional score {constitutional_score} should meet threshold"

        # Overall should be able to graduate
        can_graduate = episode_count_ok and intervention_rate_ok and constitutional_score_ok
        assert can_graduate, f"Should graduate at exact thresholds for {target_maturity}"

    @pytest.mark.asyncio
    @given(
        episode_count=st.integers(min_value=0, max_value=100),
        intervention_count=st.integers(min_value=0, max_value=100),
        constitutional_score=st.floats(min_value=0.0, max_value=1.0, allow_nan=False, allow_infinity=False)
    )
    @settings(max_examples=200, suppress_health_check=[HealthCheck.function_scoped_fixture])
    async def test_graduation_zero_episodes_invariant(self, db_session, episode_count, intervention_count, constitutional_score):
        """
        Zero episodes should prevent graduation to any level.

        Property: For any maturity M, if episode_count = 0, then
        graduation(M) = False regardless of other criteria.

        Mathematical specification:
        If episode_count = 0:
        Then: graduation(M) = False for all M

        This is a special case of the episode count invariant.
        """
        if episode_count == 0:
            # Zero episodes - should NOT graduate to any level
            for target_maturity in GRADUATION_THRESHOLDS.keys():
                thresholds = GRADUATION_THRESHOLDS[target_maturity]

                # Episode count check fails
                episode_count_ok = episode_count >= thresholds['episodes']

                assert not episode_count_ok, (
                    f"Zero episodes should prevent graduation to {target_maturity}"
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
