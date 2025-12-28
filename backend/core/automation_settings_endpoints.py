
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from core.automation_settings import get_automation_settings

router = APIRouter(prefix="/api/v1/settings/automations", tags=["Settings"])

class AutomationSettingsUpdate(BaseModel):
    enable_automatic_knowledge_extraction: Optional[bool] = None
    enable_out_of_workflow_automations: Optional[bool] = None
    document_processing_auto_trigger: Optional[bool] = None
    pipelines: Optional[Dict[str, Any]] = None

@router.get("/")
async def get_settings():
    """Get current automation settings"""
    manager = get_automation_settings()
    return manager.get_settings()

@router.post("/")
async def update_settings(update: AutomationSettingsUpdate):
    """Update global automation settings"""
    manager = get_automation_settings()
    
    # Only update provided fields
    update_data = {k: v for k, v in update.dict().items() if v is not None}
    
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
