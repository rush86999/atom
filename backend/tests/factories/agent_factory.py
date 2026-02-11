"""
Factory for AgentRegistry model.
"""

import factory
from factory import fuzzy
from tests.factories.base import BaseFactory
from core.models import AgentRegistry, AgentStatus


class AgentFactory(BaseFactory):
    """Factory for creating AgentRegistry instances."""

    class Meta:
        model = AgentRegistry

    # Required fields with dynamic values
    id = factory.Faker('uuid4')
    name = factory.Faker('company')
    category = factory.Iterator(['testing', 'automation', 'integration', 'workflow'])
    module_path = "test.module"
    class_name = "TestClass"

    # Status with fuzzy choice
    status = fuzzy.FuzzyChoice([s.value for s in AgentStatus])

    # Confidence score in valid range
    confidence_score = fuzzy.FuzzyFloat(0.0, 1.0)

    # Optional fields
    description = factory.Faker('text', max_nb_chars=200)
    version = factory.Faker('numerify', text='#.##.##')
    created_at = factory.Faker('date_time_this_year')

    # Configuration
    configuration = factory.LazyFunction(dict)
    schedule_config = factory.LazyFunction(dict)


class StudentAgentFactory(AgentFactory):
    """Factory for STUDENT maturity agents."""

    status = AgentStatus.STUDENT.value
    confidence_score = fuzzy.FuzzyFloat(0.0, 0.5)


class InternAgentFactory(AgentFactory):
    """Factory for INTERN maturity agents."""

    status = AgentStatus.INTERN.value
    confidence_score = fuzzy.FuzzyFloat(0.5, 0.7)


class SupervisedAgentFactory(AgentFactory):
    """Factory for SUPERVISED maturity agents."""

    status = AgentStatus.SUPERVISED.value
    confidence_score = fuzzy.FuzzyFloat(0.7, 0.9)


class AutonomousAgentFactory(AgentFactory):
    """Factory for AUTONOMOUS maturity agents."""

    status = AgentStatus.AUTONOMOUS.value
    confidence_score = fuzzy.FuzzyFloat(0.9, 1.0)
