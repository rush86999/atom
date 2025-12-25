from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import uuid


from core.database import get_db
from core.models import AgentFeedback, User, UserRole
from core.security import get_current_user
from core.agent_governance_service import AgentGovernanceService

router = APIRouter(prefix="/api/reasoning", tags=["reasoning"])


class ReasoningStepFeedback(BaseModel):
    agent_id: str
    run_id: str
    step_index: int
    step_content: Dict[str, Any]  # The thought/action/observation payload
    feedback_type: str  # "thumbs_up", "thumbs_down"
    comment: Optional[str] = None

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
    
    # Context payload describing the step being reviewed
    context_payload = {
        "run_id": feedback.run_id,
        "step_index": feedback.step_index,
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
        
        return {"status": "success", "id": db_feedback.id, "message": "Feedback submitted and processed by governance engine"}
        
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
