"""
Notification Settings API Routes
Allows users to configure workflow notification preferences.
"""

import logging
from typing import Any, Dict, List, Optional
from pydantic import BaseModel

from core.base_routes import BaseAPIRouter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/notifications", tags=["Notification Settings"])

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
    return router.success_response(
        data=settings.to_dict(),
        message="Notification settings retrieved successfully"
    )

@router.put("/{workflow_id}")
async def update_notification_settings(workflow_id: str, request: NotificationSettingsRequest):
    """Update notification settings for a workflow"""
    from core.workflow_notifier import NotificationSettings, set_notification_settings

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

    return router.success_response(
        data={"settings": settings.to_dict()},
        message=f"Notification settings updated for workflow {workflow_id}"
    )

@router.post("/{workflow_id}/test")
async def test_notification(workflow_id: str):
    """Send a test notification for a workflow"""
    from core.workflow_notifier import get_notification_settings, notifier

    settings = get_notification_settings(workflow_id)

    if not settings.enabled:
        return router.success_response(
            data={"status": "skipped"},
            message="Notifications disabled for this workflow"
        )

    try:
        await notifier.notify_completion(
            workflow_id=workflow_id,
            workflow_name="Test Workflow",
            execution_id="test-" + workflow_id,
            results={"test_step": {"status": "success"}},
            settings=settings
        )

        return router.success_response(
            data={"status": "success"},
            message="Test notification sent"
        )

    except Exception as e:
        logger.error(f"Test notification failed: {e}")
        raise router.internal_error(str(e))
