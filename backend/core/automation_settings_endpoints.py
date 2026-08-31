
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel

from core.auth import get_current_user, User
from core.automation_settings import get_automation_settings

router = APIRouter(prefix="/api/v1/settings/automations", tags=["Settings"])

class AutomationSettingsUpdate(BaseModel):
    enable_automatic_knowledge_extraction: Optional[bool] = None
    enable_out_of_workflow_automations: Optional[bool] = None
    document_processing_auto_trigger: Optional[bool] = None
    # Per-integration initial-sync history windows (days); the shared
    # email_history_days covers any mail integration without its own key.
    outlook_history_days: Optional[int] = None
    gmail_history_days: Optional[int] = None
    email_history_days: Optional[int] = None
    pipelines: Optional[Dict[str, Any]] = None

@router.get("/")
async def get_settings(current_user: User = Depends(get_current_user)):
    """Get current automation settings"""
    manager = get_automation_settings()
    return manager.get_settings()

@router.post("/")
async def update_settings(
    update: AutomationSettingsUpdate,
    current_user: User = Depends(get_current_user),
):
    """Update global automation settings"""
    manager = get_automation_settings()

    # Only update provided fields
    update_data = {k: v for k, v in update.dict().items() if v is not None}

    history_fields = ("outlook_history_days", "gmail_history_days", "email_history_days")
    for field in history_fields:
        if field in update_data:
            days = update_data[field]
            if not isinstance(days, int) or not (1 <= days <= 3650):
                raise HTTPException(
                    status_code=422,
                    detail=f"{field} must be an integer between 1 and 3650",
                )

    updated = manager.update_settings(update_data)
    
    # Trigger scheduler refresh if pipelines were updated
    if "pipelines" in update_data:
        try:
            from ai.workflow_scheduler import workflow_scheduler
            workflow_scheduler.reschedule_system_pipelines()
        except Exception as e:
            # Don't fail the request if scheduler update fails, but log it
            import logging
            logging.getLogger(__name__).error(f"Failed to refresh scheduler pipelines: {e}")

    return {
        "status": "success",
        "message": "Automation settings updated",
        "settings": updated
    }
