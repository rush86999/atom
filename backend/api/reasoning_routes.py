from fastapi import APIRouter, Depends, HTTPException, status
from sqlalchemy.orm import Session
from pydantic import BaseModel
from typing import Optional, Dict, Any
import json
import uuid

from core.database import get_db
from core.models import AgentFeedback, User, UserRole
from core.security import get_current_user

router = APIRouter(prefix="/api/reasoning", tags=["reasoning"])

class ReasoningStepFeedback(BaseModel):
    agent_id: str
    run_id: str
    step_index: int
    step_content: Dict[str, Any]  # The thought/action/observation payload
    feedback_type: str  # "thumbs_up", "thumbs_down"
    comment: Optional[str] = None

@router.post("/feedback")
def submit_step_feedback(
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

    # Determine status based on feedback type
    feedback_status = "accepted" if feedback.feedback_type == "thumbs_up" else "rejected"

    # Create feedback entry
    db_feedback = AgentFeedback(
        id=str(uuid.uuid4()),
        agent_id=feedback.agent_id,
        user_id=current_user.id,
        input_context=json.dumps(context_payload),
        original_output=json.dumps(feedback.step_content.get('thought', '')), # Main thing being judged
        user_correction=feedback.comment or feedback.feedback_type, # Comment or simple rating
        status=feedback_status
    )

    db.add(db_feedback)
    db.commit()
    db.refresh(db_feedback)

    return {"status": "success", "id": db_feedback.id}
