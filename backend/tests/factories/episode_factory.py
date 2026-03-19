"""
Factories for Episode and EpisodeSegment models.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import Episode, EpisodeSegment


class EpisodeFactory(BaseFactory):
    """Factory for creating Episode (AgentEpisode) instances.

    Matches AgentEpisode schema from core.models:
    - Required: agent_id, tenant_id, maturity_at_time, outcome, status
    - Optional: task_description, execution_id, metadata_json
    """

    class Meta:
        model = Episode

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    tenant_id = "default"  # Use default tenant

    # Task description (optional)
    task_description = factory.Faker('text', max_nb_chars=500)

    # Episode metadata (required)
    maturity_at_time = fuzzy.FuzzyChoice(['student', 'intern', 'supervised', 'autonomous'])
    outcome = fuzzy.FuzzyChoice(['success', 'failure', 'partial'])
    status = fuzzy.FuzzyChoice(['active', 'completed', 'failed', 'cancelled'])

    # Timing
    started_at = factory.Faker('date_time_this_year')
    completed_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(hours=fuzzy.FuzzyInteger(1, 24).fuzz())
        if o.status in ['completed', 'failed', 'cancelled'] else None
    )

    # Constitutional compliance metrics
    human_intervention_count = fuzzy.FuzzyInteger(0, 10)
    constitutional_score = fuzzy.FuzzyFloat(0.0, 1.0)
    confidence_score = fuzzy.FuzzyFloat(0.0, 1.0)

    # Outcome tracking
    success = factory.LazyAttribute(lambda o: o.outcome == 'success')
    step_efficiency = fuzzy.FuzzyFloat(0.5, 1.0)

    # Optional foreign key
    execution_id = None

    # Metadata
    metadata_json = factory.LazyFunction(dict)


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
