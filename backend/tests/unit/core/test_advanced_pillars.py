import pytest
from unittest.mock import MagicMock
import json
from pathlib import Path

from core.orchestration.conductor_agent import (
    ConductorAgent, ConductorConfig, WorkflowStep, WorkflowExecutionContext,
    ExecutionStrategy, ExecutionStatus, StepType
)
from core.canvas_sheets_service import SpreadsheetCanvasService
from core.canvas_docs_service import DocumentationCanvasService
from core.memory.pomdp_memory_framework import MemoryManager
from core.models import CanvasAudit

@pytest.mark.asyncio
async def test_conductor_parallel_consensus():
    agent = ConductorAgent(config=ConductorConfig())
    
    step = WorkflowStep(
        step_id="step1",
        step_type=StepType.AGENT,
        capability="generate_code",
    )
    
    # Mock _execute_step to return different results (which self-consistency voter will select consensus from)
    call_count = 0
    async def mock_execute_step(s, ctx):
        nonlocal call_count
        call_count += 1
        if call_count == 1:
            return {"code": "print('hello')"}
        else:
            return {"code": "print('world')"} # Majority option (2 vs 1)
            
    agent._execute_step = mock_execute_step
    
    context = WorkflowExecutionContext(
        workflow_id="wf1",
        execution_id="exec1",
        steps=[step],
        start_step="step1",
        strategy=ExecutionStrategy.PARALLEL_CONSENSUS
    )
    
    from core.orchestration.conductor_agent import OrchestrationResult
    result = OrchestrationResult(workflow_id="wf1", execution_id="exec1")
    
    await agent._execute_parallel_consensus(context, result)
    
    assert step.status == ExecutionStatus.COMPLETED
    assert step.result == {"code": "print('world')"} # Consensus winner selected


def test_canvas_transactional_rollback():
    db = MagicMock()
    # Mock latest CanvasAudit retrieval
    audit = CanvasAudit(
        id="audit1",
        canvas_id="canvas1",
        canvas_type="sheets",
        details_json={"cells": {}}
    )
    db.query().filter().order_by().first.return_value = audit
    
    service = SpreadsheetCanvasService(db=db)
    
    # Test successful update
    res = service.update_cell_transactional(
        canvas_id="canvas1",
        user_id="user1",
        cell_ref="A1",
        value="test_val"
    )
    assert res is not None
    
    # Test failed update (rolls back sandbox transaction)
    with pytest.raises(ValueError):
        service.update_cell_transactional(
            canvas_id="canvas1",
            user_id="user1",
            cell_ref="A1",
            value="fail_val",
            should_fail=True
        )


def test_pomdp_arbor_persistence():
    db = MagicMock()
    manager = MemoryManager(db=db)
    
    manager.save_hypothesis_trajectory(
        task_query="optimize sort algorithm",
        winning_trajectory=[{"step": 1, "action": "quicksort"}],
        pruned_failure_branches=["bubblesort"]
    )
    
    recalled = manager.recall_hypothesis_trajectory("optimize sort algorithm")
    assert recalled is not None
    assert recalled["winning_trajectory"][0]["action"] == "quicksort"
    assert "bubblesort" in recalled["pruned_failure_branches"]
