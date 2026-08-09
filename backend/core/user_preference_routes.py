import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import User
from core.user_preference_service import UserPreferenceService

logger = logging.getLogger(__name__)

router = APIRouter()

class PreferenceSetRequest(BaseModel):
    # ``user_id`` is accepted for frontend backward compatibility but NEVER
    # trusted — identity always comes from the authenticated token (R77
    # unauthenticated-IDOR fix). The service is called with current_user.id.
    user_id: Optional[str] = None
    workspace_id: str
    key: str
    value: Any

class PreferenceResponse(BaseModel):
    key: str
    value: Any

# NOTE: this router is mounted at prefix="/api/v1/preferences" in main_api_app.py.
# Routes use "/" (not "/preferences") so the final paths are
# /api/v1/preferences and /api/v1/preferences/{key} — matching the frontend
# (PreferencesTab.tsx calls GET/POST /api/v1/preferences).
# R77: all three endpoints now require authentication; the effective user_id is
# always current_user.id — the client-supplied user_id (query/body) is ignored.
@router.get("", response_model=Dict[str, Any])
def get_all_preferences(
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get all preferences for the authenticated user in a workspace"""
    service = UserPreferenceService(db)
    return service.get_all_preferences(str(current_user.id), workspace_id)

@router.get("/{key}")
def get_preference(
    key: str,
    workspace_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Get a specific preference for the authenticated user"""
    service = UserPreferenceService(db)
    val = service.get_preference(str(current_user.id), workspace_id, key)
    return {"key": key, "value": val}

@router.post("")
def set_preference(
    request: PreferenceSetRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """Set a preference (upsert) for the authenticated user"""
    service = UserPreferenceService(db)
    try:
        service.set_preference(
            user_id=str(current_user.id),
            workspace_id=request.workspace_id,
            key=request.key,
            value=request.value
        )
        return {"success": True, "key": request.key, "value": request.value}
    except Exception as e:
        logger.error("set_preference failed for user %s: %s", current_user.id, e)
        raise HTTPException(status_code=500, detail="Internal error")
