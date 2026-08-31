"""Autonomy policy API — the owner decides which agent-action topics always
require a human in the loop and which the agent may handle autonomously once
mature. Backs the Autonomy panel on the canvas page (reusable anywhere).
"""
import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.autonomy_policy import list_topics, set_mode
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User

router = BaseAPIRouter(prefix="/api/autonomy", tags=["Autonomy"])
logger = logging.getLogger(__name__)


class AutonomyModeRequest(BaseModel):
    mode: str  # human_always | auto_if_mature


@router.get("/topics")
async def get_autonomy_topics(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All action topics with the caller's effective mode."""
    return {"topics": list_topics(str(current_user.id), db)}


@router.put("/topics/{topic}")
async def set_autonomy_mode(
    topic: str,
    request: AutonomyModeRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set the caller's mode for a topic."""
    if not set_mode(db, str(current_user.id), topic, request.mode):
        raise HTTPException(status_code=400, detail=f"Unknown topic or mode: {topic}/{request.mode}")
    return {"success": True, "topic": topic, "mode": request.mode}
