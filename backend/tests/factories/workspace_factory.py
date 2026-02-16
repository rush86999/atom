"""
Factory for Workspace and Team models.
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from core.models import Workspace, Team, WorkspaceStatus


class WorkspaceFactory(BaseFactory):
    """Factory for creating Workspace instances."""

    class Meta:
        model = Workspace

    # Required fields
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    description = factory.Faker('text', max_nb_chars=500)

    # Metadata
    status = factory.LazyAttribute(lambda o: WorkspaceStatus.ACTIVE.value)
    plan_tier = factory.LazyAttribute(lambda o: "standard")
    satellite_api_key = factory.LazyAttribute(lambda o: None)
    is_startup = fuzzy.FuzzyChoice([True, False])
    learning_phase_completed = fuzzy.FuzzyChoice([True, False])


class TeamFactory(BaseFactory):
    """Factory for creating Team instances."""

    class Meta:
        model = Team

    # Required fields
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    workspace_id = factory.Faker('uuid4')  # Will be overridden in tests
    description = factory.Faker('text', max_nb_chars=300)
