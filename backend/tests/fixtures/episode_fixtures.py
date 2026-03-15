"""
factory_boy-based test fixtures for Episode models.

This module provides factory classes for creating valid test data for:
- AgentEpisode (core episodic memory model)
- EpisodeSegment (individual segments within episodes)
- Artifact (canvas/feedback integration)
- CanvasAudit (canvas presentation tracking)
- AgentFeedback (user feedback tracking)

All factories handle NOT NULL constraints and foreign key relationships automatically.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from typing import Optional
from sqlalchemy.orm import Session

# Import actual models
from core.models import (
    AgentEpisode,
    EpisodeSegment,
    Artifact,
    AgentRegistry,
    CanvasAudit,
    AgentFeedback,
    Tenant
)


class TenantFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating valid Tenant instances."""

    class Meta:
        model = Tenant
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"tenant-{n}")
    name = factory.Faker('company')
    subdomain = factory.Sequence(lambda n: f"tenant-{n}")
    plan_type = "FREE"
    edition = "personal"
    memory_limit_mb = 50
    memory_used_mb = 0


class AgentFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating valid AgentRegistry instances."""

    class Meta:
        model = AgentRegistry
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"test-agent-{n}")
    name = factory.Faker('company')
    category = "test"
    status = "ACTIVE"
    maturity_level = "INTERN"
    confidence_score = 0.6
    constitutional_compliance_score = 0.8
    tenant_id = "default"  # Use default tenant instead of SubFactory


class ArtifactFactory(factory.alchemy.SQLAlchemyModelFactory):
    """Factory for creating valid Artifact instances."""

    class Meta:
        model = Artifact
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"artifact-{n}")
    artifact_type = "canvas_presentation"
    title = factory.Faker('sentence')
    metadata = factory.LazyFunction(dict)


class AgentEpisodeFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating valid AgentEpisode instances with required relationships.

    Handles all NOT NULL constraints including:
    - agent_id (foreign key to AgentRegistry)
    - tenant_id (foreign key to Tenant)
    - maturity_at_time (required field)
    - outcome (required field)
    - status (required field)
    """

    class Meta:
        model = AgentEpisode
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"episode-{n}")
    agent_id = factory.Sequence(lambda n: f"test-agent-{n}")  # Simple ID, not SubFactory
    tenant_id = "default"  # Use default tenant

    # Task description
    task_description = factory.Faker('text')
    maturity_at_time = "INTERN"

    # Constitutional compliance metrics
    constitutional_score = 0.8
    human_intervention_count = 0
    confidence_score = 0.6

    # Outcome tracking (required NOT NULL)
    outcome = "success"
    success = True
    step_efficiency = 1.0

    # Metadata
    metadata_json = factory.LazyFunction(dict)

    # Vector embedding (nullable, skipped for tests)
    embedding = None

    # Boundaries
    started_at = factory.LazyFunction(
        lambda: datetime.now() - timedelta(hours=1)
    )
    completed_at = factory.LazyFunction(datetime.now)
    duration_seconds = 3600

    # Session linkage
    session_id = factory.Sequence(lambda n: f"session-{n}")

    # Canvas linkage
    canvas_ids = factory.LazyFunction(list)
    canvas_action_count = 0

    # Supervision integration
    supervisor_type = None
    supervisor_id = None
    proposal_id = None
    supervision_decision = None
    supervision_reasoning = None
    execution_followed_proposal = None

    # Additional supervision metadata
    supervisor_rating = None
    intervention_types = factory.LazyFunction(list)
    supervision_feedback = None

    # Feedback linkage
    feedback_ids = factory.LazyFunction(list)
    aggregate_feedback_score = None

    # Content
    topics = factory.LazyFunction(list)
    entities = factory.LazyFunction(list)
    importance_score = 0.5

    # Lifecycle
    decay_score = 1.0
    access_count = 0
    archived_at = None

    # Episode consolidation
    consolidated_into = None


class EpisodeSegmentFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating valid EpisodeSegment instances.

    Handles foreign key relationship to AgentEpisode.
    """

    class Meta:
        model = EpisodeSegment
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"segment-{n}")
    episode = factory.SubFactory(AgentEpisodeFactory)

    segment_type = fuzzy.FuzzyChoice([
        "user_message",
        "agent_action",
        "observation",
        "canvas_presented",
        "form_submitted",
        "result",
        "conversation"
    ])
    sequence_order = factory.Sequence(lambda n: n)
    content = factory.Faker('text')
    content_summary = factory.Faker('sentence')

    source_type = fuzzy.FuzzyChoice(["slack", "canvas", "terminal", None])
    source_id = factory.Sequence(lambda n: f"source-{n}")

    # Canvas presentation context
    canvas_context = None


class CanvasAuditFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating valid CanvasAudit instances.

    Used for canvas integration tests.
    """

    class Meta:
        model = CanvasAudit
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"canvas-audit-{n}")
    canvas_id = factory.Sequence(lambda n: f"canvas-{n}")
    agent_id = factory.SubFactory(AgentFactory)
    action_type = "present"
    canvas_type = "chart"
    metadata = factory.LazyFunction(dict)


class AgentFeedbackFactory(factory.alchemy.SQLAlchemyModelFactory):
    """
    Factory for creating valid AgentFeedback instances.

    Used for feedback integration tests.
    """

    class Meta:
        model = AgentFeedback
        sqlalchemy_session_persistence = "commit"

    id = factory.Sequence(lambda n: f"feedback-{n}")
    agent_id = factory.SubFactory(AgentFactory)
    feedback_type = fuzzy.FuzzyChoice(["thumbs_up", "thumbs_down", "star_rating"])
    score = fuzzy.FuzzyFloat(-1.0, 1.0)
    comment = factory.Faker('text', locale=None)


# Helper functions for complex test scenarios

def create_episode_with_segments(
    db_session: Session,
    agent_id: str,
    segment_count: int = 5
) -> tuple:
    """
    Create a complete episode with multiple segments.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        segment_count: Number of segments to create

    Returns:
        Tuple of (episode, segments)

    Example:
        episode, segments = create_episode_with_segments(
            db_session, "test-agent", segment_count=5
        )
    """
    episode = AgentEpisodeFactory.create(agent_id=agent_id)
    segments = [
        EpisodeSegmentFactory.create(
            episode=episode,
            sequence_order=i
        )
        for i in range(segment_count)
    ]
    return episode, segments


def create_episode_batch(
    db_session: Session,
    agent_id: str,
    count: int = 10,
    days_back: int = 30
) -> list:
    """
    Create multiple episodes spread across time for retrieval testing.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episodes
        count: Number of episodes to create
        days_back: Spread episodes across this many days

    Returns:
        List of created episode instances

    Example:
        episodes = create_episode_batch(
            db_session, "test-agent", count=15, days_back=30
        )
    """
    episodes = []
    now = datetime.now()

    for i in range(count):
        days_ago = (i * days_back) // count
        start_time = now - timedelta(days=days_ago, hours=i % 24)
        end_time = start_time + timedelta(hours=1)

        episode = AgentEpisodeFactory.create(
            agent_id=agent_id,
            started_at=start_time,
            completed_at=end_time,
            duration_seconds=3600
        )
        episodes.append(episode)

    return episodes


def create_intervention_episode(
    db_session: Session,
    agent_id: str = "test-agent",
    intervention_count: int = 2
) -> AgentEpisode:
    """
    Create an episode with interventions for testing graduation logic.

    Args:
        db_session: Database session
        agent_id: Agent ID associated with episode
        intervention_count: Number of interventions

    Returns:
        Created episode with intervention_count set

    Example:
        episode = create_intervention_episode(
            db_session, "test-agent", intervention_count=3
        )
    """
    return AgentEpisodeFactory.create(
        agent_id=agent_id,
        task_description="Intervention Episode",
        human_intervention_count=intervention_count,
        outcome="partial" if intervention_count > 0 else "success"
    )
