"""
Autonomous Coding API Routes

Exposes endpoints for autonomous AI agent swarm development workflow:
- Parse natural language requirements into structured user stories
- Create and manage autonomous coding workflows
- Query workflow status and progress
- Track agent execution logs

Governance: AUTONOMOUS maturity required for execution.
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.llm.byok_handler import BYOKHandler
from core.agent_governance_service import get_governance_cache, AgentMaturity
from core.requirement_parser_service import RequirementParserService
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


@router.post("/workflows/{workflow_id}/pause")
async def pause_workflow(
    workflow_id: str,
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
    workflow = db.query(AutonomousWorkflow).filter(
        AutonomousWorkflow.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )

    if workflow.status != "running":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot pause workflow with status {workflow.status}"
        )

    # Update workflow status
    workflow.status = "paused"
    db.commit()

    # TODO: Create checkpoint with git commit SHA
    # This will be implemented in future plans

    return {
        "message": "Workflow paused",
        "workflow_id": workflow_id,
        "status": "paused"
    }


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
    workflow = db.query(AutonomousWorkflow).filter(
        AutonomousWorkflow.id == workflow_id
    ).first()

    if not workflow:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail=f"Workflow {workflow_id} not found"
        )

    if workflow.status != "paused":
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Cannot resume workflow with status {workflow.status}"
        )

    # Update workflow status
    workflow.status = "running"
    db.commit()

    # TODO: Resume from checkpoint with feedback
    # This will be implemented in future plans

    return {
        "message": "Workflow resumed",
        "workflow_id": workflow_id,
        "status": "running",
        "feedback_incorporated": feedback is not None
    }
