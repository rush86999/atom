
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional
from core.automation_settings import get_automation_settings

router = APIRouter(prefix="/api/v1/settings/automations", tags=["Settings"])

class AutomationSettingsUpdate(BaseModel):
    enable_automatic_knowledge_extraction: Optional[bool] = None
    enable_out_of_workflow_automations: Optional[bool] = None
    document_processing_auto_trigger: Optional[bool] = None

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
    return {
        "status": "success",
        "message": "Automation settings updated",
        "settings": updated
    }
