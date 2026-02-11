"""
Factory for AgentExecution model.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import AgentExecution


class AgentExecutionFactory(BaseFactory):
    """Factory for creating AgentExecution instances."""

    class Meta:
        model = AgentExecution

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')

    # Execution metadata
    status = fuzzy.FuzzyChoice(['running', 'completed', 'failed', 'cancelled'])
    triggered_by = fuzzy.FuzzyChoice(['manual', 'schedule', 'websocket', 'event'])

    # Input/Output
    input_summary = factory.Faker('text', max_nb_chars=200)
    output_summary = factory.LazyAttribute(
        lambda o: factory.Faker('text', max_nb_chars=500).generate() if o.status in ['completed', 'running'] else None
    )

    # Timing
    started_at = factory.Faker('date_time_this_year')
    completed_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(seconds=fuzzy.FuzzyInteger(1, 300).fuzz())
        if o.status in ['completed', 'failed', 'cancelled'] else None
    )

    # Results
    result_summary = factory.LazyAttribute(
        lambda o: factory.Faker('text', max_nb_chars=500).generate() if o.status == 'completed' else None
    )
    error_message = factory.LazyAttribute(
        lambda o: factory.Faker('sentence') if o.status == 'failed' else None
    )

    # Resource tracking
    duration_seconds = fuzzy.FuzzyFloat(0.0, 300.0)
