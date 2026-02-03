from typing import Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user
from core.database import get_db
from core.models import User

router = APIRouter()

class OnboardingUpdate(BaseModel):
    step: Optional[str] = None
    completed: Optional[bool] = None

@router.post("/update")
async def update_onboarding_status(
    update_data: OnboardingUpdate,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    """
    Update the authenticated user's onboarding progress.
    """
    if update_data.step is not None:
        current_user.onboarding_step = update_data.step
    
    if update_data.completed is not None:
        current_user.onboarding_completed = update_data.completed
        
    db.commit()
    db.refresh(current_user)
    
    return {
        "status": "success",
        "onboarding_step": current_user.onboarding_step,
        "onboarding_completed": current_user.onboarding_completed
    }

@router.get("/status")
async def get_onboarding_status(
    current_user: User = Depends(get_current_user)
):
    """
    Get the authenticated user's current onboarding status.
    """
    return {
        "onboarding_step": current_user.onboarding_step,
        "onboarding_completed": current_user.onboarding_completed
    }
