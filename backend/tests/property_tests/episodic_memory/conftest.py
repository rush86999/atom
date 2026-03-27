"""
Fixtures for episodic memory property tests.

Imports shared fixtures from parent conftest to avoid duplication.
"""

import pytest
from datetime import datetime, timedelta
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, rule

# Import shared fixtures from parent conftest
from tests.property_tests.conftest import (
    db_session,
    DEFAULT_PROFILE,
    CI_PROFILE
)

# Import models for fixture creation
from core.models import (
    Episode,
    EpisodeSegment,
    ChatSession,
    ChatMessage,
    AgentExecution
)


# ============================================================================
# HYPOTHESIS SETTINGS FOR EPISODIC MEMORY TESTS
# ============================================================================

from hypothesis import settings, HealthCheck

# CRITICAL: Segmentation contiguity tests (max_examples=200)
# High coverage needed for contiguity invariants
HYPOTHESIS_SETTINGS_CRITICAL = settings(
    max_examples=200,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# STANDARD: Retrieval ranking tests (max_examples=100)
# Balance between coverage and test execution time
HYPOTHESIS_SETTINGS_STANDARD = settings(
    max_examples=100,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)

# IO-BOUND: Lifecycle transitions with DB (max_examples=50)
# Fewer examples due to database operations
HYPOTHESIS_SETTINGS_IO = settings(
    max_examples=50,
    deadline=None,
    suppress_health_check=list(HealthCheck)
)


# ============================================================================
# EPISODIC MEMORY TEST FIXTURES
# ============================================================================

@pytest.fixture(scope="function")
def test_episodes(db_session):
    """
    Create multiple Episode records with valid states for property testing.

    Returns:
        List of Episode objects with valid status values
    """
    episodes = []

    # Create episodes with different statuses
    for i in range(5):
        episode = Episode(
            id=f"test-episode-{i}",
            agent_id=f"test-agent-{i % 2}",  # Alternate between 2 agents
            tenant_id="default",
            task_description=f"Test episode {i}",
            status="active" if i < 3 else ("archived" if i < 4 else "deleted"),
            started_at=datetime.now() - timedelta(days=i),
            completed_at=datetime.now() - timedelta(days=i) + timedelta(hours=1),
            maturity_at_time="INTERN",
            human_intervention_count=i % 3,
            access_count=i * 10,
            decay_score=1.0 - (i * 0.1)
        )
        db_session.add(episode)
        episodes.append(episode)

    db_session.commit()

    # Refresh to get DB defaults
    for ep in episodes:
        db_session.refresh(ep)

    return episodes


@pytest.fixture(scope="function")
def test_episode_segments(db_session):
    """
    Create EpisodeSegment records with timestamps for property testing.

    Returns:
        List of EpisodeSegment objects with valid timestamps
    """
    segments = []
    base_time = datetime.now() - timedelta(days=1)

    # Create segments for 2 episodes
    for episode_idx in range(2):
        episode_id = f"test-episode-{episode_idx}"

        for i in range(5):
            segment = EpisodeSegment(
                id=f"test-segment-{episode_idx}-{i}",
                episode_id=episode_id,
                segment_type="conversation" if i % 2 == 0 else "execution",
                sequence_order=i,
                content=f"Test segment content {i}",
                content_summary=f"Segment {i} summary",
                source_type="chat_message" if i % 2 == 0 else "agent_execution",
                source_id=f"source-{i}",
                created_at=base_time + timedelta(hours=i)
            )
            db_session.add(segment)
            segments.append(segment)

    db_session.commit()

    # Refresh to get DB defaults
    for seg in segments:
        db_session.refresh(seg)

    return segments


@pytest.fixture(scope="session")
def sample_messages():
    """
    Hypothesis strategy for generating message lists.

    Returns:
        Strategy that generates lists of message timestamps
    """
    return st.lists(
        st.datetimes(
            min_value=datetime.now() - timedelta(days=30),
            max_value=datetime.now()
        ),
        min_size=2,
        max_size=50
    )


@pytest.fixture(scope="session")
def sample_timedeltas():
    """
    Hypothesis strategy for generating time gaps.

    Returns:
        Strategy that generates timedeltas for gap testing
    """
    return st.timedeltas(
        min_value=timedelta(minutes=1),
        max_value=timedelta(hours=2)
    )


@pytest.fixture(scope="session")
def episode_states():
    """
    Hypothesis strategy for generating valid episode states.

    Returns:
        Strategy for episode lifecycle states
    """
    return st.sampled_from(["active", "archived", "deleted"])
