"""
Factories for Episode and EpisodeSegment models.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import Episode, EpisodeSegment


class EpisodeFactory(BaseFactory):
    """Factory for creating Episode instances."""

    class Meta:
        model = Episode

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')
    title = factory.Faker('sentence', nb_words=4)
    summary = factory.Faker('text', max_nb_chars=500)

    # Episode metadata
    maturity_at_time = fuzzy.FuzzyChoice(['STUDENT', 'INTERN', 'SUPERVISED', 'AUTONOMOUS'])
    status = fuzzy.FuzzyChoice(['active', 'completed', 'archived', 'consolidated'])

    # Timing
    started_at = factory.Faker('date_time_this_year')
    ended_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(hours=fuzzy.FuzzyInteger(1, 24).fuzz())
        if o.status in ['completed', 'archived', 'consolidated'] else None
    )

    # Intervention tracking
    intervention_count = fuzzy.FuzzyInteger(0, 10)
    constitutional_score = fuzzy.FuzzyFloat(0.0, 1.0)

    # Importance and lifecycle
    importance_score = fuzzy.FuzzyFloat(0.0, 1.0)
    decay_score = fuzzy.FuzzyFloat(0.0, 1.0)
    access_count = fuzzy.FuzzyInteger(0, 100)

    # Canvas and Feedback linkage
    canvas_ids = factory.LazyFunction(list)
    canvas_action_count = fuzzy.FuzzyInteger(0, 20)
    feedback_ids = factory.LazyFunction(list)
    aggregate_feedback_score = fuzzy.FuzzyFloat(-1.0, 1.0)

    # Topics and entities
    topics = factory.LazyFunction(list)
    entities = factory.LazyFunction(list)


class EpisodeSegmentFactory(BaseFactory):
    """Factory for creating EpisodeSegment instances."""

    class Meta:
        model = EpisodeSegment

    # Required fields
    id = factory.Faker('uuid4')
    episode_id = factory.Faker('uuid4')  # Link to episode
    segment_type = fuzzy.FuzzyChoice(['conversation', 'execution', 'reflection'])
    sequence_order = fuzzy.FuzzyInteger(0, 100)

    # Content
    content = factory.Faker('text', max_nb_chars=500)
    content_summary = factory.Faker('text', max_nb_chars=300)

    # Source tracking
    source_type = fuzzy.FuzzyChoice(['chat_message', 'agent_execution', 'manual'])
    source_id = factory.Faker('uuid4')
