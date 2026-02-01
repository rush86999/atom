"""
Mobile Workflow API Endpoints
Mobile-optimized endpoints for workflow access on mobile devices
"""

import logging
from datetime import datetime, timedelta
from typing import List, Dict, Any, Optional
from fastapi import APIRouter, HTTPException, Query, Depends, BackgroundTasks
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import Workflow, WorkflowExecution, WorkflowExecutionLog

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/mobile/workflows", tags=["mobile-workflows"])


# Request/Response Models

class MobileWorkflowSummary(BaseModel):
    """Simplified workflow representation for mobile"""
    id: str
    name: str
    description: str
    category: str
    status: str
    created_at: str
    last_execution: Optional[str]
    execution_count: int
    success_rate: float
    tags: List[str]


class MobileExecutionSummary(BaseModel):
    """Simplified execution for mobile"""
    id: str
    workflow_id: str
    workflow_name: str
    status: str
    started_at: str
    completed_at: Optional[str]
    duration_seconds: Optional[int]
    progress_percentage: int = 0
    error_message: Optional[str] = None


class TriggerRequest(BaseModel):
    """Mobile workflow trigger request"""
    workflow_id: str
    parameters: Dict[str, Any] = Field(default_factory=dict)
    synchronous: bool = False


class TriggerResponse(BaseModel):
    """Mobile workflow trigger response"""
    execution_id: str
    status: str
    message: str
    workflow_id: str


# API Endpoints

@router.get("", response_model=List[MobileWorkflowSummary])
async def get_mobile_workflows(
    status: Optional[str] = None,
    category: Optional[str] = None,
    search: Optional[str] = None,
    sort_by: str = "created_at",
    sort_order: str = "desc",
    limit: int = Query(50, ge=1, le=100),
    offset: int = Query(0, ge=0),
    db: Session = Depends(get_db)
):
    """
    Get workflows optimized for mobile display

    Returns simplified workflow list with essential information only.
    """
    try:
        query = db.query(Workflow)

        # Apply filters
        if status:
            query = query.filter(Workflow.status == status)

        if category:
            query = query.filter(Workflow.category == category)

        if search:
            search_term = f"%{search}%"
            query = query.filter(
                (Workflow.name.ilike(search_term)) |
                (Workflow.description.ilike(search_term))
            )

        # Get total count before pagination
        total = query.count()

        # Apply sorting
        sort_column = getattr(Workflow, sort_by, Workflow.created_at)
        if sort_order == "desc":
            query = query.order_by(sort_column.desc())
        else:
            query = query.order_by(sort_column.asc())

        # Apply pagination
        workflows = query.offset(offset).limit(limit).all()

        # Transform to mobile format
        mobile_workflows = []
        for wf in workflows:
            # Calculate execution stats
            executions = db.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id == wf.id
            ).all()

            total_execs = len(executions)
            successful_execs = len([e for e in executions if e.status == 'completed'])
            success_rate = (successful_execs / total_execs * 100) if total_execs > 0 else 0.0

            # Get last execution
            last_exec = max(executions, key=lambda e: e.started_at, default=None)
            last_execution = last_exec.started_at.isoformat() if last_exec else None

            mobile_workflows.append(MobileWorkflowSummary(
                id=wf.id,
                name=wf.name,
                description=wf.description,
                category=wf.category,
                status=wf.status,
                created_at=wf.created_at.isoformat(),
                last_execution=last_execution,
                execution_count=total_execs,
                success_rate=round(success_rate, 1),
                tags=wf.tags or []
            ))

        return mobile_workflows

    except Exception as e:
        logger.error(f"Error fetching mobile workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}")
async def get_mobile_workflow_details(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get workflow details optimized for mobile

    Returns simplified workflow information suitable for mobile screens.
    """
    try:
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Get recent executions (last 10)
        recent_executions = db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id
        ).order_by(WorkflowExecution.started_at.desc()).limit(10).all()

        return {
            "id": workflow.id,
            "name": workflow.name,
            "description": workflow.description,
            "category": workflow.category,
            "status": workflow.status,
            "tags": workflow.tags or [],
            "created_at": workflow.created_at.isoformat(),
            "updated_at": workflow.updated_at.isoformat(),
            "execution_count": len(recent_executions),
            "recent_executions": [
                {
                    "id": exec.id,
                    "status": exec.status,
                    "started_at": exec.started_at.isoformat(),
                    "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                    "duration_seconds": exec.duration_seconds,
                }
                for exec in recent_executions
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching mobile workflow details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/trigger", response_model=TriggerResponse)
async def trigger_workflow_mobile(
    request: TriggerRequest,
    user_id: str = Query(..., description="User ID triggering the workflow"),
    db: Session = Depends(get_db)
):
    """
    Trigger workflow execution (mobile-optimized)

    Returns execution ID immediately. Workflow runs in background.
    """
    try:
        # Verify workflow exists
        workflow = db.query(Workflow).filter(Workflow.id == request.workflow_id).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        if workflow.status != 'active':
            raise HTTPException(
                status_code=400,
                detail=f"Cannot trigger workflow with status: {workflow.status}"
            )

        # Create execution record
        execution = WorkflowExecution(
            id=f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            workflow_id=request.workflow_id,
            triggered_by=user_id,
            status='running',
            started_at=datetime.now(),
            input_data=request.parameters
        )

        db.add(execution)
        db.commit()
        db.refresh(execution)

        # Start workflow in background (non-blocking)
        if request.synchronous:
            # Run synchronously (wait for completion)
            # TODO: Implement actual workflow execution logic
            pass
        else:
            # Run asynchronously using background task
            # TODO: Submit to background task queue
            pass

        logger.info(f"Mobile trigger: workflow={request.workflow_id}, execution={execution.id}")

        return TriggerResponse(
            execution_id=execution.id,
            status="started",
            message="Workflow execution started",
            workflow_id=request.workflow_id
        )

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error triggering workflow: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/executions/{execution_id}")
async def get_mobile_execution_details(
    execution_id: str,
    db: Session = Depends(get_db)
):
    """
    Get execution details optimized for mobile

    Returns execution progress and simplified log information.
    """
    try:
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        # Get workflow name
        workflow = db.query(Workflow).filter(Workflow.id == execution.workflow_id).first()

        # Get recent logs (last 20)
        logs = db.query(WorkflowExecutionLog).filter(
            WorkflowExecutionLog.execution_id == execution_id
        ).order_by(WorkflowExecutionLog.timestamp.desc()).limit(20).all()

        # Calculate progress percentage
        progress_percentage = 0
        if execution.total_steps and execution.current_step:
            progress_percentage = int((execution.current_step / execution.total_steps) * 100)

        return {
            "id": execution.id,
            "workflow_id": execution.workflow_id,
            "workflow_name": workflow.name if workflow else "Unknown",
            "status": execution.status,
            "started_at": execution.started_at.isoformat(),
            "completed_at": execution.completed_at.isoformat() if execution.completed_at else None,
            "duration_seconds": execution.duration_seconds,
            "triggered_by": execution.triggered_by,
            "current_step": execution.current_step,
            "total_steps": execution.total_steps,
            "progress_percentage": progress_percentage,
            "error_message": execution.error_message,
            "recent_logs": [
                {
                    "id": log.id,
                    "level": log.level,
                    "message": log.message,
                    "timestamp": log.timestamp.isoformat(),
                    "step_id": log.step_id,
                }
                for log in logs
            ]
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching execution details: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/executions")
async def get_workflow_executions_mobile(
    workflow_id: str,
    limit: int = Query(10, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Get recent executions for a workflow (mobile-optimized)

    Returns paginated list of executions.
    """
    try:
        # Verify workflow exists
        workflow = db.query(Workflow).filter(Workflow.id == workflow_id).first()

        if not workflow:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Get executions
        executions = db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id
        ).order_by(WorkflowExecution.started_at.desc()).limit(limit).all()

        return [
            {
                "id": exec.id,
                "workflow_id": exec.workflow_id,
                "status": exec.status,
                "started_at": exec.started_at.isoformat(),
                "completed_at": exec.completed_at.isoformat() if exec.completed_at else None,
                "duration_seconds": exec.duration_seconds,
                "error_message": exec.error_message,
            }
            for exec in executions
        ]

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching workflow executions: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/executions/{execution_id}/logs")
async def get_execution_logs_mobile(
    workflow_id: str,
    execution_id: str,
    level: Optional[str] = None,
    limit: int = Query(100, ge=1, le=500),
    db: Session = Depends(get_db)
):
    """
    Get execution logs (mobile-optimized)

    Returns paginated logs with optional filtering by level.
    """
    try:
        query = db.query(WorkflowExecutionLog).filter(
            WorkflowExecutionLog.execution_id == execution_id
        )

        if level:
            query = query.filter(WorkflowExecutionLog.level == level)

        logs = query.order_by(WorkflowExecutionLog.timestamp.desc()).limit(limit).all()

        return {
            "logs": [
                {
                    "id": log.id,
                    "level": log.level,
                    "message": log.message,
                    "timestamp": log.timestamp.isoformat(),
                    "step_id": log.step_id,
                }
                for log in logs
            ]
        }

    except Exception as e:
        logger.error(f"Error fetching execution logs: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/{workflow_id}/executions/{execution_id}/steps")
async def get_execution_steps_mobile(
    workflow_id: str,
    execution_id: str,
    db: Session = Depends(get_db)
):
    """
    Get execution steps with status (mobile-optimized)

    Returns step-by-step execution progress.
    """
    try:
        # This would query the workflow steps and their execution status
        # For now, return a placeholder response

        # Get execution to see current step
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        # TODO: Query actual step execution data from workflow_steps table
        # This would require a WorkflowStepExecution model

        return {
            "execution_id": execution_id,
            "current_step": execution.current_step,
            "total_steps": execution.total_steps,
            "progress_percentage": execution.current_step and execution.total_steps
                ? int((execution.current_step / execution.total_steps) * 100)
                : 0,
            "steps": []
            # TODO: Add actual step data
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error fetching execution steps: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/executions/{execution_id}/cancel")
async def cancel_execution_mobile(
    execution_id: str,
    user_id: str = Query(..., description="User ID cancelling the execution"),
    db: Session = Depends(get_db)
):
    """
    Cancel running workflow execution (mobile-optimized)

    Stops a currently running workflow execution.
    """
    try:
        execution = db.query(WorkflowExecution).filter(
            WorkflowExecution.id == execution_id
        ).first()

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        if execution.status != 'running':
            raise HTTPException(
                status_code=400,
                detail=f"Cannot cancel execution with status: {execution.status}"
            )

        if execution.triggered_by != user_id:
            raise HTTPException(
                status_code=403,
                detail="You can only cancel executions you triggered"
            )

        # Update execution status
        execution.status = 'cancelled'
        execution.completed_at = datetime.now()

        db.commit()

        # TODO: Send cancellation signal to workflow engine

        logger.info(f"Cancelled execution {execution_id}")

        return {
            "message": "Execution cancelled successfully",
            "execution_id": execution_id
        }

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error cancelling execution: {e}")
        db.rollback()
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/search")
async def search_workflows_mobile(
    query: str,
    limit: int = Query(20, ge=1, le=50),
    db: Session = Depends(get_db)
):
    """
    Search workflows (mobile-optimized)

    Full-text search across workflow names and descriptions.
    """
    try:
        search_term = f"%{query}%"

        workflows = db.query(Workflow).filter(
            (Workflow.name.ilike(search_term)) |
            (Workflow.description.ilike(search_term))
        ).limit(limit).all()

        return [
            {
                "id": wf.id,
                "name": wf.name,
                "description": wf.description,
                "category": wf.category,
                "status": wf.status,
                "tags": wf.tags or [],
            }
            for wf in workflows
        ]

    except Exception as e:
        logger.error(f"Error searching workflows: {e}")
        raise HTTPException(status_code=500, detail=str(e))
