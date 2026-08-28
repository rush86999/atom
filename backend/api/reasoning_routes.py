import json
from typing import Any, Dict, Optional
import uuid
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.agent_governance_service import AgentGovernanceService
from core.auth import get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import AgentFeedback, User, UserRole

router = BaseAPIRouter(prefix="/api/reasoning", tags=["reasoning"])


class ReasoningStepFeedback(BaseModel):
    agent_id: str
    run_id: str
    step_index: int
    step_content: Dict[str, Any]  # The thought/action/observation payload
    feedback_type: str  # "thumbs_up", "thumbs_down"
    comment: Optional[str] = None
    # When the step came from a persisted run, these identify the
    # AgentReasoningStep row so the feedback is stamped directly on the trace
    # (consumed by harness evolution / failure-pattern mining).
    execution_id: Optional[str] = None
    step_number: Optional[int] = None


@router.get("/chain/{chain_id}")
async def get_reasoning_chain(
    chain_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """Get a reasoning chain by id for the Reasoning Audit dialog.

    W45: the frontend called /api/v1/voice/reasoning/{chain_id} which never
    existed (404) — the audit dialog was dead. The tracker is in-memory
    (core.reasoning_chain.ReasoningTracker), so serve what it holds.
    """
    from core.reasoning_chain import get_reasoning_tracker

    chain = get_reasoning_tracker().get_chain(chain_id)
    if not chain:
        raise router.not_found_error("ReasoningChain", chain_id)
    return router.success_response(
        data=chain.dict() if hasattr(chain, "dict") else chain.__dict__,
        message="Reasoning chain retrieved",
    )

@router.post("/feedback")
async def submit_step_feedback(
    feedback: ReasoningStepFeedback,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Submit feedback for a specific reasoning step.
    This reuses the AgentFeedback model by storing step details in input_context.
    """
    
    # Context payload describing the step being reviewed. feedback_type is
    # stored explicitly (R82): user_correction prefers the comment, so without
    # this the thumbs_up/thumbs_down polarity would be lost for adjudication.
    context_payload = {
        "run_id": feedback.run_id,
        "step_index": feedback.step_index,
        "feedback_type": feedback.feedback_type,
        "step_content": feedback.step_content
    }

    governance_service = AgentGovernanceService(db)
    
    # original_output is the thought being judged
    original_output = json.dumps(feedback.step_content.get('thought', ''))
    
    # user_correction is the feedback type (thumbs_up/down) or comment
    user_correction = feedback.comment or feedback.feedback_type
    
    # input_context is the full step details
    input_context = json.dumps(context_payload)

    try:
        # Submit feedback (this will trigger async adjudication and confidence updates)
        db_feedback = await governance_service.submit_feedback(
            agent_id=feedback.agent_id,
            user_id=current_user.id,
            original_output=original_output,
            user_correction=user_correction,
            input_context=input_context
        )

        # Write-through: when the reviewed step belongs to a persisted run,
        # stamp the polarity + comment directly on the reasoning-step row so
        # training consumers (harness evolution, failure-pattern mining) can
        # query it without parsing AgentFeedback input_context blobs.
        if feedback.execution_id and feedback.step_number is not None:
            from core.models import AgentReasoningStep

            step_row = (
                db.query(AgentReasoningStep)
                .filter(
                    AgentReasoningStep.execution_id == feedback.execution_id,
                    AgentReasoningStep.step_number == feedback.step_number,
                )
                .first()
            )
            if step_row is not None:
                step_row.feedback_score = (
                    1 if feedback.feedback_type == "thumbs_up" else -1
                )
                if feedback.comment:
                    step_row.feedback_text = feedback.comment
                db.commit()

        return router.success_response(
            data={"id": db_feedback.id},
            message="Feedback submitted and processed by governance engine",
        )

    except Exception as e:
        raise router.internal_error("Internal error")
