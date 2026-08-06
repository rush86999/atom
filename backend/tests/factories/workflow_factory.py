"""
Factories for WorkflowExecution and WorkflowStepExecution models.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import WorkflowExecution, WorkflowExecutionStatus, WorkflowStepExecution


class WorkflowExecutionFactory(BaseFactory):
    """Factory for creating WorkflowExecution instances."""

    class Meta:
        model = WorkflowExecution

    # Required fields
    execution_id = factory.Faker('uuid4')
    workflow_id = factory.Faker('uuid4')
    status = fuzzy.FuzzyChoice([s.value for s in WorkflowExecutionStatus])

    # Data fields
    input_data = factory.LazyFunction(lambda: None)
    steps = factory.LazyFunction(lambda: None)
    outputs = factory.LazyFunction(lambda: None)
    context = factory.LazyFunction(lambda: None)
    error = factory.LazyFunction(lambda: None)


class WorkflowStepExecutionFactory(BaseFactory):
    """Factory for creating WorkflowStepExecution instances.

    Matches the restored WorkflowStepExecution model (core.models), which is
    referenced by api/mobile_workflows.py step-progress endpoint and by
    tests/test_models_coverage.py.
    """

    class Meta:
        model = WorkflowStepExecution

    # Required fields
    execution_id = factory.Faker('uuid4')
    workflow_id = factory.Faker('uuid4')
    step_id = factory.Faker('uuid4')

    # Data fields
    step_name = factory.Faker('word')
    step_type = factory.Faker('word')
    sequence_order = factory.Sequence(lambda n: n)
    status = "pending"
    input_data = factory.LazyFunction(lambda: None)
    output_data = factory.LazyFunction(lambda: None)
