"""
Factory for CanvasAudit model.
"""

import factory
from factory import fuzzy
from datetime import timedelta
from tests.factories import BaseFactory
from core.models import CanvasAudit


class CanvasAuditFactory(BaseFactory):
    """Factory for creating CanvasAudit instances."""

    class Meta:
        model = CanvasAudit

    # Required fields
    id = factory.Faker('uuid4')
    workspace_id = factory.Faker('uuid4')
    agent_id = factory.Faker('uuid4')
    user_id = factory.Faker('uuid4')
    canvas_type = fuzzy.FuzzyChoice(['generic', 'docs', 'email', 'sheets', 'orchestration', 'terminal', 'coding'])

    # Component type and action
    component_type = fuzzy.FuzzyChoice(['chart', 'markdown', 'form', 'sheet', 'terminal'])
    component_name = fuzzy.FuzzyChoice(['line_chart', 'bar_chart', 'pie_chart', 'text', 'data_table'])
    action = fuzzy.FuzzyChoice(['present', 'submit', 'close', 'update', 'execute'])

    # Metadata
    audit_metadata = factory.LazyFunction(dict)

    # Timing
    created_at = factory.Faker('date_time_this_year')
