"""
Factory for AgentFeedback model.
"""

import factory
from factory import fuzzy
from datetime import datetime
from tests.factories.base import BaseFactory
from core.models import AgentFeedback, FeedbackStatus


class AgentFeedbackFactory(BaseFactory):
    """Factory for creating AgentFeedback instances."""

    class Meta:
        model = AgentFeedback

    # Required fields
    id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    user_id = factory.Faker('uuid4')

    # The interaction
    original_output = factory.Faker('text', max_nb_chars=500)
    user_correction = factory.Faker('text', max_nb_chars=500)

    # Enhanced feedback
    feedback_type = fuzzy.FuzzyChoice(['correction', 'rating', 'approval', 'comment'])
    thumbs_up_down = fuzzy.FuzzyChoice([True, False, None])
    rating = fuzzy.FuzzyInteger(1, 5)  # 1-5 stars

    # Adjudication
    status = fuzzy.FuzzyChoice([s.value for s in FeedbackStatus])
    ai_reasoning = factory.Faker('text', max_nb_chars=300)
    adjudicated_at = factory.LazyAttribute(
        lambda o: datetime.now() if o.status == FeedbackStatus.ADJUDICATED.value else None
    )
