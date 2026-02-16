"""
Factories for WorkflowExecution and WorkflowStepExecution models.
"""

import factory
from factory import fuzzy
from datetime import datetime, timedelta
from tests.factories.base import BaseFactory
from core.models import WorkflowExecution, WorkflowStepExecution, WorkflowExecutionStatus


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
    """Factory for creating WorkflowStepExecution instances."""

    class Meta:
        model = WorkflowStepExecution

    # Required fields
    id = factory.Faker('uuid4')
    execution_id = factory.Faker('uuid4')  # Foreign key to workflow_executions.execution_id
    workflow_id = factory.Faker('uuid4')
    sequence_order = fuzzy.FuzzyInteger(1, 10)
    step_id = factory.Faker('uuid4')
    step_name = factory.Faker('word')
    step_type = fuzzy.FuzzyChoice(['trigger', 'action', 'condition'])
    status = fuzzy.FuzzyChoice(['pending', 'running', 'completed', 'failed', 'skipped'])

    # Step execution
    input_data = factory.LazyFunction(lambda: None)
    output_data = factory.LazyFunction(lambda: None)
    error_message = factory.LazyFunction(lambda: None)

    # Timing
    started_at = factory.Faker('date_time_this_year')
    completed_at = factory.LazyAttribute(
        lambda o: o.started_at + timedelta(seconds=fuzzy.FuzzyInteger(1, 30).fuzz())
        if o.status in ['completed', 'failed'] else None
    )
