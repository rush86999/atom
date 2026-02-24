"""
Factory for AgentOperationTracker model.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import AgentOperationTracker


class AgentOperationTrackerFactory(BaseFactory):
    """Factory for creating AgentOperationTracker instances."""

    class Meta:
        model = AgentOperationTracker

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    user_id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')

    # Operation details
    operation_type = fuzzy.FuzzyChoice([
        'workflow_execute',
        'integration_connect',
        'browser_automate',
        'report_generate',
        'human_feedback_received',
        'approval_requested',
        'agent_to_agent_call',
        'internal_check',
        'db_query'
    ])
    operation_id = factory.Faker('uuid4')

    # Step tracking
    current_step = factory.Faker('sentence', nb_words=3)
    total_steps = fuzzy.FuzzyInteger(1, 10)
    current_step_index = fuzzy.FuzzyInteger(0, 9)
    status = fuzzy.FuzzyChoice(['running', 'waiting', 'completed', 'failed'])
    progress = fuzzy.FuzzyInteger(0, 100)

    # Agent guidance context
    what_explanation = factory.Faker('text', max_nb_chars=200)
    why_explanation = factory.Faker('text', max_nb_chars=200)
    next_steps = factory.Faker('text', max_nb_chars=200)

    # Operation metadata
    operation_metadata = factory.LambdaFunction(lambda: {})
    logs = factory.LambdaFunction(lambda: [])

    # Timing
    started_at = factory.Faker('date_time_this_year')
    completed_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(seconds=fuzzy.FuzzyInteger(1, 300).fuzz())
        if o.status in ['completed', 'failed'] else None
    )
