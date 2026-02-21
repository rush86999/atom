"""
Autonomous Coding API Routes

Exposes endpoints for autonomous AI agent swarm development workflow:
- Parse natural language requirements into structured user stories
- Execute complete autonomous coding workflows via orchestrator
- Query workflow status and progress
- Pause/resume workflows with human feedback
- Rollback to checkpoints
- Track agent execution logs

Governance: AUTONOMOUS maturity required for execution.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.llm.byok_handler import BYOKHandler
from core.agent_governance_service import get_governance_cache, AgentMaturity
from core.requirement_parser_service import RequirementParserService
from core.autonomous_coding_orchestrator import AgentOrchestrator, WorkflowPhase
from core.models import AutonomousWorkflow, AgentLog

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/autonomous", tags=["Autonomous Coding"])


# ==================== Request/Response Models ====================

class ParseRequirementsRequest(BaseModel):
    """Request to parse feature requirements"""
    feature_request: str = Field(..., description="Natural language feature request", min_length=1)
    workspace_id: str = Field(default="default", description="Workspace identifier")
    context: Optional[Dict[str, Any]] = Field(default=None, description="Additional context (priority, deadline, etc.)")


class ParseRequirementsResponse(BaseModel):
    """Response with parsed requirements"""
    workflow_id: str = Field(..., description="Autonomous workflow ID")
    user_stories: list = Field(..., description="Parsed user stories")
    acceptance_criteria: list = Field(..., description="Gherkin scenarios")
    dependencies: list = Field(default=[], description="Identified dependencies")
    integration_points: list = Field(default=[], description="Integration points")
    complexity: str = Field(..., description="Estimated complexity")
    estimated_time: str = Field(..., description="Time estimate")


class WorkflowStatusResponse(BaseModel):
    """Response with workflow status"""
    workflow_id: str
    status: str  # pending, running, paused, completed, failed
    current_phase: Optional[str]
    completed_phases: list
    files_created: list
    files_modified: list
    test_results: Optional[Dict[str, Any]]
    started_at: str
    completed_at: Optional[str]
    error_message: Optional[str]


class WorkflowLogsResponse(BaseModel):
    """Response with agent execution logs"""
    workflow_id: str
    logs: list


class WorkflowRequest(BaseModel):
    """Request to start autonomous coding workflow"""
    feature_request: str = Field(..., description="Natural language feature request", min_length=1)
    workspace_id: str = Field(default="default", description="Workspace identifier")
    options: Optional[Dict[str, Any]] = Field(default=None, description="Options (auto_commit, checkpoints, etc.)")


class RollbackRequest(BaseModel):
    """Request to rollback workflow"""
    checkpoint_sha: Optional[str] = Field(None, description="Checkpoint SHA to rollback to")
    phase: Optional[str] = Field(None, description="Phase name to rollback to")


# ==================== Helper Functions ====================

async def check_autonomous_governance() -> None:
    """
    Check if current context has AUTONOMOUS maturity level.

    Raises:
        HTTPException: If maturity level is below AUTONOMOUS
    """
    governance_cache = get_governance_cache()

    # For now, we'll check if governance system allows autonomous operations
    # In production, this would check agent maturity, user permissions, etc.
    # TODO: Integrate with actual agent governance checks

    # Placeholder: always allow for development
    # In production, uncomment the following:
    # maturity = governance_cache.get_maturity_level("autonomous-coding-agent")
    # if maturity != AgentMaturity.AUTONOMOUS:
    #     raise HTTPException(
    #         status_code=status.HTTP_403_FORBIDDEN,
    #         detail="Autonomous coding requires AUTONOMOUS maturity level"
    #     )

    pass


def get_orchestrator(db: Session, workspace_id: str = "default") -> AgentOrchestrator:
    """
    Get or create orchestrator instance.

    In production, this would manage a pool of orchestrators.
    For now, we create a new one per request.
    """
    byok_handler = BYOKHandler(workspace_id=workspace_id)
    return AgentOrchestrator(db, byok_handler)


# ==================== API Endpoints ====================

@router.post("/parse-requirements", response_model=ParseRequirementsResponse)
async def parse_requirements(
    request: ParseRequirementsRequest,
    db: Session = Depends(get_db)
):
    """
    Parse natural language feature request into structured requirements.

    Creates autonomous workflow and returns parsed requirements:
    - User stories (role/action/value format)
    - Acceptance criteria (Gherkin: Given/When/Then)
    - Dependencies and integration points
    - Complexity estimation

    Governance: AUTONOMOUS maturity required.

    Example:
    ```json
    {
      "feature_request": "Add OAuth2 authentication with Google and GitHub",
      "workspace_id": "default",
      "context": {"priority": "high", "deadline": "2026-03-01"}
    }
    ```

    Returns:
    ```json
    {
      "workflow_id": "abc123",
      "user_stories": [...],
      "acceptance_criteria": [...],
      "complexity": "moderate",
      "estimated_time": "4-6 hours"
    }
    ```
    """
    # Governance check
    await check_autonomous_governance()

    try:
        # Initialize BYOK handler and parser service
        byok_handler = BYOKHandler(workspace_id=request.workspace_id)
        parser = RequirementParserService(db, byok_handler)

        # Parse requirements
        parsed = await parser.parse_requirements(
            feature_request=request.feature_request,
            workspace_id=request.workspace_id,
            context=request.context
        )

        # Create workflow record
        workflow = await parser.create_workflow(
            feature_request=request.feature_request,
            workspace_id=request.workspace_id,
            parsed_requirements=parsed
        )

        return ParseRequirementsResponse(
            workflow_id=workflow.id,
            user_stories=parsed.get("user_stories", []),
            acceptance_criteria=parsed.get("acceptance_criteria", []),
            dependencies=parsed.get("dependencies", []),
            integration_points=parsed.get("integration_points", []),
            complexity=parsed.get("estimated_complexity", "moderate"),
            estimated_time=parsed.get("estimated_time", "4-6 hours")
        )

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid request: {str(e)}"
        )
    except Exception as e:
        logger.error(f"Failed to parse requirements: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to parse requirements: {str(e)}"
        )


@router.get("/workflows/{workflow_id}", response_model=WorkflowStatusResponse)
async def get_workflow_status(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get autonomous workflow execution status and progress.

    Returns:
    - Current status (pending, running, paused, completed, failed)
    - Current phase (parse, research, plan, implement, test)
    - Completed phases list
    - Files created and modified
    - Test results
    - Start and completion timestamps

    Raises 404 if workflow not found.
    """
    workflow = db.query(AutonomousWorkflow).filter(
        AutonomousWorkflow.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )

    return WorkflowStatusResponse(
        workflow_id=workflow.id,
        status=workflow.status,
        current_phase=workflow.current_phase,
        completed_phases=workflow.completed_phases or [],
        files_created=workflow.files_created or [],
        files_modified=workflow.files_modified or [],
        test_results=workflow.test_results,
        started_at=workflow.started_at.isoformat() if workflow.started_at else None,
        completed_at=workflow.completed_at.isoformat() if workflow.completed_at else None,
        error_message=workflow.error_message
    )


@router.get("/workflows/{workflow_id}/logs", response_model=WorkflowLogsResponse)
async def get_workflow_logs(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get agent execution logs for workflow.

    Returns chronological list of agent actions:
    - Agent ID (parser-01, coder-backend, tester-01, etc.)
    - Phase and action
    - Status (running, completed, failed)
    - Duration in seconds

    Use cases:
    - Debugging failed workflows
    - Performance analysis
    - Audit trail for compliance

    Raises 404 if workflow not found.
    """
    # Verify workflow exists
    workflow = db.query(AutonomousWorkflow).filter(
        AutonomousWorkflow.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )

    # Query agent logs
    logs = db.query(AgentLog).filter(
        AgentLog.workflow_id == workflow_id
    ).order_by(AgentLog.started_at).all()

    return WorkflowLogsResponse(
        workflow_id=workflow_id,
        logs=[
            {
                "agent_id": log.agent_id,
                "phase": log.phase,
                "action": log.action,
                "status": log.status,
                "started_at": log.started_at.isoformat() if log.started_at else None,
                "completed_at": log.completed_at.isoformat() if log.completed_at else None,
                "duration_seconds": log.duration_seconds,
                "error_message": log.error_message
            }
            for log in logs
        ]
    )


@router.post("/workflows")
async def create_autonomous_workflow(
    request: WorkflowRequest,
    db: Session = Depends(get_db)
):
    """
    Start autonomous coding workflow.

    Executes complete SDLC through orchestrator:
    1. Parse Requirements
    2. Research Codebase
    3. Create Plan
    4. Generate Code
    5. Generate Tests
    6. Fix Tests
    7. Generate Docs (when implemented)
    8. Create Commit (when implemented)

    Governance: AUTONOMOUS maturity required.

    Example:
    ```json
    {
      "feature_request": "Add OAuth2 authentication with Google",
      "workspace_id": "default",
      "options": {"auto_commit": true}
    }
    ```
    """
    # Governance check
    await check_autonomous_governance()

    try:
        # Get orchestrator
        orchestrator = get_orchestrator(db, request.workspace_id)

        # Execute workflow (this may take time)
        result = await orchestrator.execute_feature(
            feature_request=request.feature_request,
            workspace_id=request.workspace_id,
            options=request.options
        )

        return result

    except Exception as e:
        logger.error(f"Failed to execute workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to execute workflow: {str(e)}"
        )


@router.get("/workflows")
async def list_workflows(
    status: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    List all workflows with optional status filter.

    Returns workflow IDs matching status filter.
    """
    query = db.query(AutonomousWorkflow)

    if status:
        query = query.filter(AutonomousWorkflow.status == status)

    workflows = query.order_by(AutonomousWorkflow.started_at.desc()).limit(100).all()

    return {
        "workflows": [
            {
                "workflow_id": w.id,
                "feature_request": w.feature_request,
                "status": w.status,
                "current_phase": w.current_phase,
                "started_at": w.started_at.isoformat() if w.started_at else None,
                "completed_at": w.completed_at.isoformat() if w.completed_at else None
            }
            for w in workflows
        ]
    }


@router.get("/workflows/{workflow_id}/audit")
async def get_workflow_audit_trail(
    workflow_id: str,
    db: Session = Depends(get_db)
):
    """
    Get complete audit trail for workflow.

    Returns all agent actions with:
    - Agent ID
    - Phase and action
    - Status (running, completed, failed)
    - Timestamps
    - Duration
    - Error messages

    Use cases:
    - Compliance auditing
    - Debugging failures
    - Performance analysis

    Raises 404 if workflow not found.
    """
    # Verify workflow exists
    workflow = db.query(AutonomousWorkflow).filter(
        AutonomousWorkflow.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )

    # Get orchestrator and audit trail
    orchestrator = get_orchestrator(db)
    audit_trail = await orchestrator.progress_tracker.get_audit_trail(workflow_id)

    return {
        "workflow_id": workflow_id,
        "audit_trail": audit_trail
    }


@router.post("/workflows/{workflow_id}/pause")
async def pause_workflow(
    workflow_id: str,
    reason: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Pause autonomous workflow for human review.

    Creates checkpoint with current state:
    - Git commit SHA for rollback
    - Agent states
    - Shared context

    Workflow can be resumed later with human feedback.

    Raises 404 if workflow not found.
    """
    try:
        # Get orchestrator
        orchestrator = get_orchestrator(db)

        # Pause workflow
        result = await orchestrator.pause_workflow(workflow_id, reason)

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to pause workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to pause workflow: {str(e)}"
        )


@router.post("/workflows/{workflow_id}/resume")
async def resume_workflow(
    workflow_id: str,
    feedback: Optional[str] = None,
    db: Session = Depends(get_db)
):
    """
    Resume paused workflow with optional human feedback.

    Args:
        workflow_id: Workflow identifier
        feedback: Optional human feedback to incorporate

    Raises 404 if workflow not found.
    """
    try:
        # Get orchestrator
        orchestrator = get_orchestrator(db)

        # Resume workflow
        result = await orchestrator.resume_workflow(workflow_id, feedback)

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to resume workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to resume workflow: {str(e)}"
        )


@router.post("/workflows/{workflow_id}/rollback")
async def rollback_workflow(
    workflow_id: str,
    request: RollbackRequest,
    db: Session = Depends(get_db)
):
    """
    Rollback workflow to checkpoint or phase.

    Args:
        workflow_id: Workflow identifier
        checkpoint_sha: Optional checkpoint SHA to rollback to
        phase: Optional phase name to rollback to

    Must specify either checkpoint_sha or phase.

    Raises 404 if workflow not found.
    """
    try:
        # Get orchestrator
        orchestrator = get_orchestrator(db)

        # Convert phase string to enum if provided
        phase_enum = None
        if request.phase:
            try:
                phase_enum = WorkflowPhase(request.phase)
            except ValueError:
                raise HTTPException(
                    status_code=status.HTTP_400_BAD_REQUEST,
                    detail=f"Invalid phase: {request.phase}"
                )

        # Rollback
        result = await orchestrator.rollback_workflow(
            workflow_id=workflow_id,
            checkpoint_sha=request.checkpoint_sha,
            phase=phase_enum
        )

        return result

    except ValueError as e:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=str(e)
        )
    except Exception as e:
        logger.error(f"Failed to rollback workflow: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=f"Failed to rollback workflow: {str(e)}"
        )

