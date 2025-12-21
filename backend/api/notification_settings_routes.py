"""
Notification Settings API Routes
Allows users to configure workflow notification preferences.
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class NotificationSettingsRequest(BaseModel):
    enabled: bool = True
    notify_on_success: bool = True
    notify_on_failure: bool = True
    slack_enabled: bool = True
    slack_channel: str = ""
    slack_mention_users: List[str] = []
    email_enabled: bool = False
    email_recipients: List[str] = []
    custom_success_message: Optional[str] = None
    custom_failure_message: Optional[str] = None

@router.get("/{workflow_id}")
async def get_notification_settings(workflow_id: str):
    """Get notification settings for a workflow"""
    from core.workflow_notifier import get_notification_settings
    
    settings = get_notification_settings(workflow_id)
    return settings.to_dict()

@router.put("/{workflow_id}")
async def update_notification_settings(workflow_id: str, request: NotificationSettingsRequest):
    """Update notification settings for a workflow"""
    from core.workflow_notifier import set_notification_settings, NotificationSettings
    
    settings = NotificationSettings(
        enabled=request.enabled,
        notify_on_success=request.notify_on_success,
        notify_on_failure=request.notify_on_failure,
        slack_enabled=request.slack_enabled,
        slack_channel=request.slack_channel,
        slack_mention_users=request.slack_mention_users,
        email_enabled=request.email_enabled,
        email_recipients=request.email_recipients,
        custom_success_message=request.custom_success_message,
        custom_failure_message=request.custom_failure_message
    )
    
    set_notification_settings(workflow_id, settings)
    
    return {
        "status": "success",
        "message": f"Notification settings updated for workflow {workflow_id}",
        "settings": settings.to_dict()
    }

@router.post("/{workflow_id}/test")
async def test_notification(workflow_id: str):
    """Send a test notification for a workflow"""
    from core.workflow_notifier import notifier, get_notification_settings
    
    settings = get_notification_settings(workflow_id)
    
    if not settings.enabled:
        return {"status": "skipped", "message": "Notifications disabled for this workflow"}
    
    try:
        await notifier.notify_completion(
            workflow_id=workflow_id,
            workflow_name="Test Workflow",
            execution_id="test-" + workflow_id,
            results={"test_step": {"status": "success"}},
            settings=settings
        )
        
        return {"status": "success", "message": "Test notification sent"}
        
    except Exception as e:
        logger.error(f"Test notification failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
