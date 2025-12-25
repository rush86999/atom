from fastapi import APIRouter, Depends, HTTPException, Body
from typing import Dict, Any, List, Optional
from sqlalchemy.orm import Session
from pydantic import BaseModel

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

@router.get("/preferences", response_model=Dict[str, Any])
def get_all_preferences(
    user_id: str,
    workspace_id: str,
    db: Session = Depends(get_db)
):
    """Get all preferences for a user in a workspace"""
    service = UserPreferenceService(db)
    return service.get_all_preferences(user_id, workspace_id)

@router.get("/preferences/{key}")
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

@router.post("/preferences")
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
        raise HTTPException(status_code=500, detail=str(e))
