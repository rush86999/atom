"""
Mobile Workflow API Endpoints
Mobile-optimized endpoints for workflow access on mobile devices
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, BackgroundTasks, Depends, HTTPException, Query
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import WorkflowExecution, WorkflowExecutionLog

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
        # Load workflows from JSON file
        import json
        import os

        workflows_file = os.path.join(
            os.path.dirname(os.path.dirname(__file__)),
            "workflows.json"
        )

        if not os.path.exists(workflows_file):
            return []

        with open(workflows_file, 'r') as f:
            workflows_json = json.load(f)

        # Filter workflows
        workflows = workflows_json
        if status:
            workflows = [w for w in workflows if w.get("status") == status]
        if category:
            workflows = [w for w in workflows if w.get("category") == category]
        if search:
            search_lower = search.lower()
            workflows = [
                w for w in workflows
                if search_lower in w.get("name", "").lower() or
                   search_lower in w.get("description", "").lower()
            ]

        # Apply sorting
        if sort_order == "desc":
            workflows.sort(key=lambda x: x.get(sort_by, ""), reverse=True)
        else:
            workflows.sort(key=lambda x: x.get(sort_by, ""))

        # Apply pagination
        workflows = workflows[offset:offset + limit]

        # Transform to mobile format
        mobile_workflows = []
        for wf in workflows:
            workflow_id = wf.get('id', '')
            # Calculate execution stats
            executions = db.query(WorkflowExecution).filter(
                WorkflowExecution.workflow_id == workflow_id
            ).all()

            total_execs = len(executions)
            successful_execs = len([e for e in executions if e.status == 'completed'])
            success_rate = (successful_execs / total_execs * 100) if total_execs > 0 else 0.0

            # Get last execution
            last_exec = max(executions, key=lambda e: e.started_at, default=None)
            last_execution = last_exec.started_at.isoformat() if last_exec else None

            mobile_workflows.append(MobileWorkflowSummary(
                id=workflow_id,
                name=wf.get("name", ""),
                description=wf.get("description", ""),
                category=wf.get("category", ""),
                status=wf.get("status", "unknown"),
                created_at=wf.get("created_at", ""),
                last_execution=last_execution,
                execution_count=total_execs,
                success_rate=round(success_rate, 1),
                tags=wf.get("tags", [])
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
        # Load workflow from JSON file
        workflow_dict = _load_workflow_definition(db, workflow_id)

        if not workflow_dict:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Get recent executions (last 10)
        recent_executions = db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id
        ).order_by(WorkflowExecution.started_at.desc()).limit(10).all()

        return {
            "id": workflow_dict.get("id"),
            "name": workflow_dict.get("name", ""),
            "description": workflow_dict.get("description", ""),
            "category": workflow_dict.get("category", ""),
            "status": workflow_dict.get("status", "unknown"),
            "tags": workflow_dict.get("tags", []),
            "created_at": workflow_dict.get("created_at", ""),
            "updated_at": workflow_dict.get("updated_at", ""),
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
    background_tasks: BackgroundTasks,
    user_id: str = Query(..., description="User ID triggering the workflow"),
    db: Session = Depends(get_db)
):
    """
    Trigger workflow execution (mobile-optimized)

    Returns execution ID immediately. Workflow runs in background.
    """
    try:
        # Verify workflow exists
        workflow_dict = _load_workflow_definition(db, request.workflow_id)
        if not workflow_dict:
            raise HTTPException(status_code=404, detail="Workflow not found")

        if workflow_dict.get("status") != 'active':
            raise HTTPException(
                status_code=400,
                detail=f"Cannot trigger workflow with status: {workflow_dict.get('status')}"
            )

        # Create execution record
        execution = WorkflowExecution(
            execution_id=f"exec_{datetime.now().strftime('%Y%m%d_%H%M%S_%f')}",
            workflow_id=request.workflow_id,
            triggered_by=user_id,
            status='running',
            started_at=datetime.now(),
            input_data=str(request.parameters) if request.parameters else None
        )

        db.add(execution)
        db.commit()
        db.refresh(execution)

        # Start workflow in background (non-blocking)
        if request.synchronous:
            # Run synchronously (wait for completion)
            import asyncio

            from core.workflow_engine import get_workflow_engine

            engine = get_workflow_engine()

            if not workflow_dict:
                raise HTTPException(status_code=404, detail="Workflow definition not found")

            # Create completion event
            completion_event = asyncio.Event()

            async def run_with_completion():
                try:
                    await engine._run_execution(execution.execution_id, workflow_dict)
                finally:
                    completion_event.set()

            # Start execution
            asyncio.create_task(run_with_completion())

            # Wait for completion (5 min timeout)
            try:
                await asyncio.wait_for(completion_event.wait(), timeout=300.0)
                db.refresh(execution)
                return TriggerResponse(
                    execution_id=execution.execution_id,
                    status="completed" if execution.status == "completed" else execution.status,
                    message="Workflow completed",
                    workflow_id=request.workflow_id
                )
            except asyncio.TimeoutError:
                return TriggerResponse(
                    execution_id=execution.execution_id,
                    status="timeout",
                    message="Workflow execution timed out",
                    workflow_id=request.workflow_id
                )
        else:
            # Run asynchronously using background task
            from core.workflow_engine import get_workflow_engine

            engine = get_workflow_engine()

            if workflow_dict:
                background_tasks.add_task(
                    engine._run_execution,
                    execution.execution_id,
                    workflow_dict
                )
            else:
                raise HTTPException(status_code=404, detail="Workflow definition not found")

        logger.info(f"Mobile trigger: workflow={request.workflow_id}, execution={execution.execution_id}")

        return TriggerResponse(
            execution_id=execution.execution_id,
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
            WorkflowExecution.execution_id == execution_id
        ).first()

        if not execution:
            raise HTTPException(status_code=404, detail="Execution not found")

        # Get workflow name
        workflow_dict = _load_workflow_definition(db, execution.workflow_id)
        workflow_name = workflow_dict.get("name", "Unknown") if workflow_dict else "Unknown"

        # Get recent logs (last 20)
        logs = db.query(WorkflowExecutionLog).filter(
            WorkflowExecutionLog.execution_id == execution_id
        ).order_by(WorkflowExecutionLog.timestamp.desc()).limit(20).all()

        # Calculate progress percentage
        progress_percentage = 0

        return {
            "id": execution.execution_id,
            "workflow_id": execution.workflow_id,
            "workflow_name": workflow_name,
            "status": execution.status,
            "started_at": execution.created_at.isoformat(),
            "completed_at": execution.updated_at.isoformat() if execution.updated_at else None,
            "duration_seconds": None,
            "triggered_by": execution.triggered_by,
            "current_step": None,
            "total_steps": None,
            "progress_percentage": progress_percentage,
            "error_message": execution.error,
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
        workflow_dict = _load_workflow_definition(db, workflow_id)

        if not workflow_dict:
            raise HTTPException(status_code=404, detail="Workflow not found")

        # Get executions
        executions = db.query(WorkflowExecution).filter(
            WorkflowExecution.workflow_id == workflow_id
        ).order_by(WorkflowExecution.created_at.desc()).limit(limit).all()

        return [
            {
                "id": exec.execution_id,
                "workflow_id": exec.workflow_id,
                "status": exec.status,
                "started_at": exec.created_at.isoformat(),
                "completed_at": exec.updated_at.isoformat() if exec.updated_at else None,
                "duration_seconds": None,
                "error_message": exec.error,
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
        # Query step executions
        from core.models import WorkflowStepExecution

        step_executions = db.query(WorkflowStepExecution).filter(
            WorkflowStepExecution.execution_id == execution_id
        ).order_by(WorkflowStepExecution.sequence_order).all()

        steps_data = [
            {
                "step_id": s.step_id,
                "step_name": s.step_name,
                "step_type": s.step_type,
                "sequence_order": s.sequence_order,
                "status": s.status,
                "started_at": s.started_at.isoformat() if s.started_at else None,
                "completed_at": s.completed_at.isoformat() if s.completed_at else None,
                "duration_ms": s.duration_ms,
                "error_message": s.error_message
            }
            for s in step_executions
        ]

        total = len(step_executions)
        completed = len([s for s in step_executions if s.status == "completed"])
        progress = int((completed / total) * 100) if total > 0 else 0

        return {
            "execution_id": execution_id,
            "current_step": completed,
            "total_steps": total,
            "progress_percentage": progress,
            "steps": steps_data
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
            WorkflowExecution.execution_id == execution_id
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
        execution.updated_at = datetime.now()

        db.commit()

        # Send cancellation signal to workflow engine
        from core.workflow_engine import get_workflow_engine

        engine = get_workflow_engine()
        await engine.cancel_execution(execution_id)

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


def _load_workflow_definition(db: Session, workflow_id: str) -> Optional[Dict[str, Any]]:
    """Load workflow definition from workflows.json"""
    import json
    import os

    workflows_file = os.path.join(
        os.path.dirname(os.path.dirname(__file__)),
        "workflows.json"
    )

    if not os.path.exists(workflows_file):
        return None

    try:
        with open(workflows_file, 'r') as f:
            workflows = json.load(f)
        return next((w for w in workflows if w.get('id') == workflow_id), None)
    except Exception as e:
        logger.error(f"Error loading workflow {workflow_id}: {e}")
        return None

