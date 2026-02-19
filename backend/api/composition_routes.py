"""
Composition API Routes - Multi-skill workflow execution.

Endpoints:
- POST /composition/execute - Execute skill composition workflow
- POST /composition/validate - Validate workflow DAG
- GET /composition/status/{id} - Get workflow execution status

Reference: Phase 60 Plan 03
"""

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from typing import List, Optional, Dict, Any

from core.database import get_db
from core.skill_composition_engine import SkillCompositionEngine, SkillStep

router = APIRouter(prefix="/composition", tags=["composition"])


class StepModel(BaseModel):
    step_id: str = Field(..., description="Unique step identifier")
    skill_id: str = Field(..., description="Skill ID to execute")
    inputs: Dict[str, Any] = Field(default_factory=dict, description="Input parameters")
    dependencies: List[str] = Field(default_factory=list, description="Step IDs this depends on")
    condition: Optional[str] = Field(None, description="Conditional execution")
    timeout_seconds: int = Field(30, ge=1, le=300, description="Step timeout")


class WorkflowRequest(BaseModel):
    workflow_id: str = Field(..., description="Unique workflow identifier")
    agent_id: str = Field(..., description="Agent ID executing workflow")
    steps: List[StepModel] = Field(..., min_items=1, description="Workflow steps")


class WorkflowResponse(BaseModel):
    success: bool
    workflow_id: str
    execution_id: Optional[str] = None
    results: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    duration_seconds: Optional[float] = None


@router.post("/execute", response_model=WorkflowResponse)
async def execute_workflow(
    request: WorkflowRequest,
    db: Session = Depends(get_db)
):
    """Execute a skill composition workflow."""
    engine = SkillCompositionEngine(db)

    # Convert to SkillStep objects
    steps = [
        SkillStep(
            step_id=s.step_id,
            skill_id=s.skill_id,
            inputs=s.inputs,
            dependencies=s.dependencies,
            condition=s.condition,
            timeout_seconds=s.timeout_seconds
        )
        for s in request.steps
    ]

    result = await engine.execute_workflow(
        workflow_id=request.workflow_id,
        steps=steps,
        agent_id=request.agent_id
    )

    return result


@router.post("/validate")
def validate_workflow(
    request: WorkflowRequest,
    db: Session = Depends(get_db)
):
    """Validate workflow DAG without executing."""
    engine = SkillCompositionEngine(db)

    steps = [
        SkillStep(
            step_id=s.step_id,
            skill_id=s.skill_id,
            inputs=s.inputs,
            dependencies=s.dependencies
        )
        for s in request.steps
    ]

    result = engine.validate_workflow(steps)
    return result


@router.get("/status/{execution_id}")
def get_workflow_status(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """Get workflow execution status."""
    from core.models import SkillCompositionExecution

    workflow = db.query(SkillCompositionExecution).filter(
        SkillCompositionExecution.id == execution_id
    ).first()

    if not workflow:
        raise HTTPException(status_code=404, detail="Workflow execution not found")

    return {
        "execution_id": workflow.id,
        "workflow_id": workflow.workflow_id,
        "status": workflow.status,
        "validation_status": workflow.validation_status,
        "current_step": workflow.current_step,
        "completed_steps": workflow.completed_steps or [],
        "rollback_performed": workflow.rollback_performed,
        "started_at": workflow.started_at.isoformat(),
        "completed_at": workflow.completed_at.isoformat() if workflow.completed_at else None,
        "duration_seconds": workflow.duration_seconds,
        "error": workflow.error_message
    }
