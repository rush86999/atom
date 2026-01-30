"""
Canvas Routes Backend

Handles form submissions and canvas-related API endpoints.
"""

import logging
import uuid
from datetime import datetime
from typing import Dict, Any
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import User
from core.websockets import manager as ws_manager
from core.security_dependencies import get_current_user

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/canvas", tags=["canvas"])


class FormSubmission(BaseModel):
    canvas_id: str
    form_data: Dict[str, Any]


@router.post("/submit")
async def submit_form(
    submission: FormSubmission,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Handle form submission from canvas.

    Stores submission and notifies agent to continue workflow.
    """
    try:
        # For now, we'll just log the submission and notify via WebSocket
        # In a full implementation, you'd store this in the database

        logger.info(f"Form submission from user {current_user.id}: {submission.form_data}")

        # Notify agent via WebSocket
        user_channel = f"user:{current_user.id}"
        await ws_manager.broadcast(user_channel, {
            "type": "canvas:form_submitted",
            "canvas_id": submission.canvas_id,
            "data": submission.form_data,
            "user_id": current_user.id
        })

        return {
            "status": "success",
            "submission_id": str(uuid.uuid4()),
            "message": "Form submitted successfully"
        }

    except Exception as e:
        logger.error(f"Form submission failed: {e}")
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
