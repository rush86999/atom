
from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from core.auth import get_current_user
from core.models import User
from core.stakeholder_engine import get_stakeholder_engine

router = APIRouter(prefix="/api/v1/stakeholders", tags=["Stakeholders"])

@router.get("/silent")
async def get_silent_stakeholders(current_user: User = Depends(get_current_user)):
    """Get list of silent stakeholders for the current user"""
    try:
        engine = get_stakeholder_engine()
        silent_stakeholders = await engine.identify_silent_stakeholders(current_user.id)
        
        return {
            "success": True,
            "user_id": current_user.id,
            "silent_stakeholders": silent_stakeholders,
            "count": len(silent_stakeholders)
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/all")
async def get_all_stakeholders(current_user: User = Depends(get_current_user)):
    """Get all identified stakeholders (for debugging/ui purposes)"""
    try:
        engine = get_stakeholder_engine()
        stakeholders = await engine.get_stakeholders_for_user(current_user.id)
        
        return {
            "success": True,
            "stakeholders": stakeholders
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
