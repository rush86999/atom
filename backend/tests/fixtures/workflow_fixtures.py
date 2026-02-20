"""
Workflow test data factories.

Provides factory functions for creating test workflow data with minimal boilerplate.
"""

from datetime import datetime
from typing import Optional, Dict, Any, List
from sqlalchemy.orm import Session

from core.models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStatus,
    WorkflowStep
)


def create_test_workflow(
    db_session: Session,
    name: str = "TestWorkflow",
    status: str = "active",
    version: int = 1,
    **kwargs
) -> WorkflowDefinition:
    """Factory function to create test workflows with defaults.

    Args:
        db_session: Database session
        name: Workflow name
        status: Workflow status (active, draft, archived)
        version: Workflow version
        **kwargs: Additional WorkflowDefinition fields

    Returns:
        Created WorkflowDefinition instance

    Example:
        workflow = create_test_workflow(db_session, name="MyWorkflow")
    """
    workflow = WorkflowDefinition(
        name=name,
        description=kwargs.get("description", f"Test workflow {name}"),
        status=status,
        version=version,
        definition=kwargs.get("definition", {"steps": []}),
        created_by=kwargs.get("created_by", "test_user"),
        created_at=kwargs.get("created_at", datetime.utcnow()),
        updated_at=kwargs.get("updated_at", datetime.utcnow()),
        **{k: v for k, v in kwargs.items() if k not in [
            "description", "definition", "created_by", "created_at", "updated_at"
        ]}
    )
    db_session.add(workflow)
    db_session.commit()
    db_session.refresh(workflow)
    return workflow


def create_workflow_execution(
    db_session: Session,
    workflow_id: str,
    status: str = "pending",
    **kwargs
) -> WorkflowExecution:
    """Factory function to create test workflow executions.

    Args:
        db_session: Database session
        workflow_id: Parent workflow ID
        status: Execution status (pending, running, completed, failed)
        **kwargs: Additional WorkflowExecution fields

    Returns:
        Created WorkflowExecution instance
    """
    execution = WorkflowExecution(
        workflow_id=workflow_id,
        status=status,
        input_data=kwargs.get("input_data", {}),
        output_data=kwargs.get("output_data", {}),
        error_message=kwargs.get("error_message"),
        started_at=kwargs.get("started_at", datetime.utcnow()),
        completed_at=kwargs.get("completed_at"),
        agent_id=kwargs.get("agent_id"),
        **{k: v for k, v in kwargs.items() if k not in [
            "input_data", "output_data", "error_message",
            "started_at", "completed_at", "agent_id"
        ]}
    )
    db_session.add(execution)
    db_session.commit()
    db_session.refresh(execution)
    return execution


def create_workflow_step(
    db_session: Session,
    execution_id: str,
    step_name: str = "test_step",
    status: str = "pending",
    **kwargs
) -> WorkflowStep:
    """Factory function to create test workflow steps.

    Args:
        db_session: Database session
        execution_id: Parent execution ID
        step_name: Step name
        status: Step status (pending, running, completed, failed)
        **kwargs: Additional WorkflowStep fields

    Returns:
        Created WorkflowStep instance
    """
    step = WorkflowStep(
        execution_id=execution_id,
        step_name=step_name,
        status=status,
        step_data=kwargs.get("step_data", {}),
        result=kwargs.get("result"),
        error_message=kwargs.get("error_message"),
        started_at=kwargs.get("started_at", datetime.utcnow()),
        completed_at=kwargs.get("completed_at"),
        **{k: v for k, v in kwargs.items() if k not in [
            "step_data", "result", "error_message", "started_at", "completed_at"
        ]}
    )
    db_session.add(step)
    db_session.commit()
    db_session.refresh(step)
    return step


def create_workflow_with_steps(
    db_session: Session,
    workflow_name: str = "MultiStepWorkflow",
    step_count: int = 3
) -> tuple[WorkflowDefinition, WorkflowExecution, List[WorkflowStep]]:
    """Create a complete workflow with execution and steps.

    Args:
        db_session: Database session
        workflow_name: Workflow name
        step_count: Number of steps to create

    Returns:
        Tuple of (workflow, execution, steps)
    """
    workflow = create_test_workflow(db_session, name=workflow_name)
    execution = create_workflow_execution(
        db_session,
        workflow_id=workflow.id,
        status="running"
    )

    steps = []
    for i in range(step_count):
        step = create_workflow_step(
            db_session,
            execution_id=execution.id,
            step_name=f"step_{i+1}",
            status="completed" if i < step_count - 1 else "running"
        )
        steps.append(step)

    return workflow, execution, steps
