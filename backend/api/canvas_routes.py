"""
Canvas Routes Backend

Handles form submissions and canvas-related API endpoints.

Now includes governance integration with:
- Agent permission validation for form submissions
- Linking submissions to originating agent executions
- Complete audit trail for state-changing operations
"""

import logging
import os
import uuid
from datetime import datetime
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_context_resolver import AgentContextResolver
from core.agent_governance_service import AgentGovernanceService
from core.database import get_db
from core.models import AgentExecution, CanvasAudit, User
from core.security_dependencies import get_current_user
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/canvas", tags=["canvas"])

# Feature flags
FORM_GOVERNANCE_ENABLED = os.getenv("FORM_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"


class FormSubmission(BaseModel):
    canvas_id: str
    form_data: Dict[str, Any]
    agent_execution_id: Optional[str] = None  # Link to originating execution
    agent_id: Optional[str] = None  # Agent submitting on behalf of


@router.post("/submit")
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

    try:
        # ============================================
        # GOVERNANCE: Agent Resolution & Validation
        # ============================================
        if FORM_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS:
            resolver = AgentContextResolver(db)
            governance = AgentGovernanceService(db)

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
                from core.models import AgentRegistry
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
                        f"Governance blocked form submission: {governance_check['reason']}"
                    )
                    return {
                        "success": False,
                        "error": f"Agent not permitted to submit form: {governance_check['reason']}",
                        "governance_check": governance_check
                    }

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
                    f"Agent submission execution {submission_execution.id} created "
                    f"for form submission"
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
            f"Form submission from user {current_user.id}: "
            f"{len(submission.form_data)} fields" +
            (f" (agent: {agent.name if hasattr(agent, 'name') else agent_id})" if agent else "")
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
        if submission_execution and FORM_GOVERNANCE_ENABLED:
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
                logger.error(f"Failed to mark submission execution as completed: {completion_error}")

        return {
            "status": "success",
            "submission_id": audit.id,
            "message": "Form submitted successfully",
            "agent_execution_id": submission_execution.id if submission_execution else None,
            "agent_id": agent.id if agent and hasattr(agent, 'id') else None,
            "governance_check": governance_check
        }

    except Exception as e:
        logger.error(f"Form submission failed: {e}")

        # Mark submission execution as failed if it exists
        if submission_execution and FORM_GOVERNANCE_ENABLED:
            try:
                submission_execution.status = "failed"
                submission_execution.error_message = str(e)
                submission_execution.completed_at = datetime.now()
                db.commit()

                if agent:
                    governance = AgentGovernanceService(db)
                    await governance.record_outcome(
                        agent.id if hasattr(agent, 'id') else submission.agent_id,
                        success=False
                    )
            except Exception as inner_e:
                logger.error(f"Failed to record submission failure: {inner_e}")

        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def get_canvas_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get canvas status for the current user.
    """
    return {
        "status": "active",
        "user_id": current_user.id,
        "features": ["markdown", "status_panel", "form", "line_chart", "bar_chart", "pie_chart"]
    }
