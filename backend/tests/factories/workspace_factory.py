"""
Factory for Workspace and Team models.
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from core.models import Workspace, Team


class WorkspaceFactory(BaseFactory):
    """Factory for creating Workspace instances."""

    class Meta:
        model = Workspace

    # Required fields
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    description = factory.Faker('text', max_nb_chars=500)

    # Business info
    industry = fuzzy.FuzzyChoice(['Technology', 'Healthcare', 'Finance', 'Retail', 'Other'])
    company_size = fuzzy.FuzzyChoice(['1-10', '11-50', '51-200', '201-500', '500+'])

    # Metadata
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

    # Team type
    team_type = fuzzy.FuzzyChoice(['operations', 'sales', 'marketing', 'finance', 'general'])
