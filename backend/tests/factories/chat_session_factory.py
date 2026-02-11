"""
Factories for ChatSession model.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import ChatSession


class ChatSessionFactory(BaseFactory):
    """Factory for creating ChatSession instances."""

    class Meta:
        model = ChatSession

    # Required fields
    id = factory.Faker('uuid4')
    user_id = factory.Faker('uuid4')
    title = factory.Faker('sentence', nb_words=4)

    # Metadata
    metadata_json = factory.LazyFunction(lambda: {
        'source': fuzzy.FuzzyChoice(['agent', 'user', 'system', 'import']).fuzz(),
        'context': factory.Faker('text', max_nb_chars=200),
    })

    # Timing
    created_at = factory.Faker('date_time_this_year')
    updated_at = factory.LazyAttribute(
        lambda o: o.created_at + timedelta(minutes=fuzzy.FuzzyInteger(1, 60).fuzz())
    )

    # Message count
    message_count = fuzzy.FuzzyInteger(0, 1000)
