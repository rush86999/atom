from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Body, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db
from core.user_preference_service import UserPreferenceService

router = APIRouter()

class PreferenceSetRequest(BaseModel):
    user_id: str
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
@router.get("", response_model=Dict[str, Any])
def get_all_preferences(
    user_id: str,
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get all preferences for a user in a workspace"""
    service = UserPreferenceService(db)
    return service.get_all_preferences(user_id, workspace_id)

@router.get("/{key}")
def get_preference(
    key: str,
    user_id: str,
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get a specific preference"""
    service = UserPreferenceService(db)
    val = service.get_preference(user_id, workspace_id, key)
    return {"key": key, "value": val}

@router.post("")
def set_preference(
    request: PreferenceSetRequest,
    db: Session = Depends(get_db)
):
    """Set a preference (upsert)"""
    service = UserPreferenceService(db)
    try:
        service.set_preference(
            user_id=request.user_id,
            workspace_id=request.workspace_id,
            key=request.key,
            value=request.value
        )
        return {"success": True, "key": request.key, "value": request.value}
    except Exception as e:
        raise HTTPException(status_code=500, detail="Internal error")
