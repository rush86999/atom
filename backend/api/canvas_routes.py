"""
Canvas Routes Backend

Handles form submissions and canvas-related API endpoints.

Now includes governance integration with:
- Agent permission validation for form submissions
- Linking submissions to originating agent executions
- Complete audit trail for state-changing operations

Migrated to BaseAPIRouter for standardized responses and error handling.
Refactored to use standardized decorators and service factory.
"""

from datetime import datetime
from typing import Any, Dict, Optional
import uuid
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.error_handler_decorator import handle_errors
from core.error_handlers import ErrorCode
from core.feature_flags import FeatureFlags
from core.models import AgentExecution, AgentRegistry, CanvasAudit, User
from core.security_dependencies import get_current_user
from core.service_factory import ServiceFactory
from core.structured_logger import get_logger
from core.websockets import manager as ws_manager

logger = get_logger(__name__)

router = BaseAPIRouter(prefix="/api/canvas", tags=["canvas"])


class FormSubmission(BaseModel):
    canvas_id: str
    form_data: Dict[str, Any]
    agent_execution_id: Optional[str] = None  # Link to originating execution
    agent_id: Optional[str] = None  # Agent submitting on behalf of


@router.post("/submit")
@handle_errors(error_code=ErrorCode.INTERNAL_SERVER_ERROR)
async def submit_form(
    submission: FormSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle form submission from canvas with governance integration.

    - Validates agent permissions (submit_form = complexity 3, SUPERVISED+)
    - Links submission to originating agent execution
    - Creates submission execution record for audit trail
    - Broadcasts with agent context

    Args:
        submission: Form data with canvas_id and form_data
        current_user: Authenticated user
        db: Database session

    Returns:
        Submission confirmation with governance context
    """
    agent = None
    originating_execution = None
    governance_check = None
    submission_execution = None

    # ============================================
    # GOVERNANCE: Agent Resolution & Validation
    # ============================================
    if FeatureFlags.should_enforce_governance('form'):
        governance = ServiceFactory.get_governance_service(db)

        # Get originating execution if provided
        if submission.agent_execution_id:
            originating_execution = db.query(AgentExecution).filter(
                AgentExecution.id == submission.agent_execution_id
            ).first()

        # Resolve agent - prefer originating execution's agent
        agent_id = submission.agent_id
        if originating_execution and not agent_id:
            agent_id = originating_execution.agent_id

        if agent_id:
            # Query AgentRegistry (not AgentExecution) for agent details
            agent = db.query(AgentRegistry).filter(
                AgentRegistry.id == agent_id
            ).first()

            # Perform governance check (submit_form = complexity 3, SUPERVISED+)
            if agent:
                governance_check = governance.can_perform_action(
                    agent_id=agent.id if hasattr(agent, 'id') else agent_id,
                    action_type="submit_form"
                )

                if not governance_check["allowed"]:
                    logger.warning(
                        "Governance blocked form submission",
                        agent_id=agent.id if hasattr(agent, 'id') else agent_id,
                        reason=governance_check['reason']
                    )
                    raise router.governance_denied_error(
                        agent_id=agent.id if hasattr(agent, 'id') else agent_id,
                        action="submit_form",
                        maturity_level=agent.maturity_level if hasattr(agent, 'maturity_level') else "UNKNOWN",
                        required_level="SUPERVISED",
                        reason=governance_check['reason']
                    )

                submission_execution = AgentExecution(
                    agent_id=agent.id if hasattr(agent, 'id') else agent_id,
                    workspace_id="default",
                    status="running",
                    input_summary=f"Form submission for canvas {submission.canvas_id}",
                    triggered_by="form_submission",
                    result_summary=f"Submitted {len(submission.form_data)} fields"
                )
                db.add(submission_execution)
                db.commit()
                db.refresh(submission_execution)

                logger.info(
                    "Agent submission execution created",
                    submission_execution_id=submission_execution.id,
                    canvas_id=submission.canvas_id
                )

        audit = CanvasAudit(
            id=str(uuid.uuid4()),
            workspace_id="default",
            agent_id=agent.id if agent and hasattr(agent, 'id') else (submission.agent_id if submission.agent_id else None),
            agent_execution_id=submission_execution.id if submission_execution else submission.agent_execution_id,
            user_id=current_user.id,
            canvas_id=submission.canvas_id,
            component_type="form",
            component_name=None,
            action="submit",
            audit_metadata={
                "form_data": submission.form_data,
                "field_count": len(submission.form_data),
                "originating_execution_id": submission.agent_execution_id
            },
            governance_check_passed=governance_check["allowed"] if governance_check else None
        )
        db.add(audit)
        db.commit()

        logger.info(
            "Form submission received",
            user_id=current_user.id,
            canvas_id=submission.canvas_id,
            field_count=len(submission.form_data),
            agent_id=agent.id if agent and hasattr(agent, 'id') else None
        )

        # Notify agent via WebSocket with full context
        user_channel = f"user:{current_user.id}"
        await ws_manager.broadcast(user_channel, {
            "type": "canvas:form_submitted",
            "canvas_id": submission.canvas_id,
            "data": submission.form_data,
            "user_id": current_user.id,
            "agent_id": agent.id if agent and hasattr(agent, 'id') else None,
            "agent_execution_id": submission_execution.id if submission_execution else None,
            "submission_id": audit.id,
            "governance_check": governance_check
        })

        # Mark submission execution as completed
        if submission_execution and FeatureFlags.should_enforce_governance('form'):
            try:
                submission_execution.status = "completed"
                submission_execution.output_summary = f"Form submitted successfully with {len(submission.form_data)} fields"
                submission_execution.completed_at = datetime.now()
                submission_execution.duration_seconds = (
                    submission_execution.completed_at - submission_execution.started_at
                ).total_seconds()
                db.commit()

                # Record outcome for confidence scoring
                if agent:
                    await governance.record_outcome(
                        agent.id if hasattr(agent, 'id') else agent_id,
                        success=True
                    )

                logger.info(f"Submission execution {submission_execution.id} completed")
            except Exception as completion_error:
                logger.error(
                    "Failed to mark submission execution as completed",
                    submission_execution_id=submission_execution.id,
                    error=str(completion_error)
                )

        return router.success_response(
            data={
                "submission_id": audit.id,
                "agent_execution_id": submission_execution.id if submission_execution else None,
                "agent_id": agent.id if agent and hasattr(agent, 'id') else None,
                "governance_check": governance_check
            },
            message="Form submitted successfully"
        )


@router.get("/status")
@handle_errors()
async def get_canvas_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get canvas status for the current user.
    """
    logger.info("Canvas status requested", user_id=current_user.id)
    return router.success_response(
        data={
            "status": "active",
            "user_id": current_user.id,
            "features": ["markdown", "status_panel", "form", "line_chart", "bar_chart", "pie_chart"]
        }
    )
