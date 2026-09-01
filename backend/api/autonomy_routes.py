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
from core.models import AgentRegistry, Canvas, User

router = BaseAPIRouter(prefix="/api/autonomy", tags=["Autonomy"])
logger = logging.getLogger(__name__)


class AutonomyModeRequest(BaseModel):
    mode: str  # human_always | auto_if_mature


def _canvas_type_for_user(db: Session, user_id: str, canvas_id: str) -> Optional[str]:
    """The canvas's type when it belongs to the caller (shared/public canvases
    deliberately yield no canvas context — the panel degrades to the general
    set rather than leaking another user's canvas metadata)."""
    try:
        canvas = (
            db.query(Canvas)
            .filter(Canvas.id == canvas_id, Canvas.created_by == user_id)
            .first()
        )
        if canvas is not None:
            return canvas.canvas_type
    except Exception as e:
        logger.debug(f"autonomy canvas lookup skipped: {e}")
    return None


def _accessible_agent_id(db: Session, user_id: str, agent_id: Optional[str]) -> Optional[str]:
    """The agent_id only when it resolves to the caller's hire (or a legacy
    owner-less row) — trust/maturity stats must not leak across users."""
    if not agent_id:
        return None
    try:
        row = db.query(AgentRegistry).filter(AgentRegistry.id == agent_id).first()
        if row is None:
            return None
        if row.user_id and str(row.user_id) != user_id:
            return None
        return agent_id
    except Exception as e:
        logger.debug(f"autonomy agent lookup skipped: {e}")
        return None


@router.get("/topics")
async def get_autonomy_topics(
    canvas_id: Optional[str] = None,
    canvas_type: Optional[str] = None,
    agent_id: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """All action topics with the caller's effective mode.

    ``canvas_id`` (or a plain ``canvas_type`` fallback) groups the topics:
    those primary for the canvas's type come back flagged
    ``canvas_relevant`` so the Autonomy tab can lead with them. ``agent_id``
    attaches the hire's live trust×maturity gate per topic."""
    user_id = str(current_user.id)
    resolved_canvas_type = (
        _canvas_type_for_user(db, user_id, canvas_id) if canvas_id else None
    ) or canvas_type
    resolved_agent_id = _accessible_agent_id(db, user_id, agent_id)
    return {
        "topics": list_topics(
            user_id,
            db,
            canvas_type=resolved_canvas_type,
            agent_id=resolved_agent_id,
        ),
        "canvas_type": resolved_canvas_type,
    }


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
