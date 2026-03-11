"""
Factories for WorkflowExecution and WorkflowStepExecution models.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import WorkflowExecution, WorkflowExecutionStatus
# NOTE: WorkflowStepExecution doesn't exist in core.models - commented out


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


# NOTE: WorkflowStepExecutionFactory commented out - WorkflowStepExecution model doesn't exist
# class WorkflowStepExecutionFactory(BaseFactory):
#     """Factory for creating WorkflowStepExecution instances."""
#     ...
