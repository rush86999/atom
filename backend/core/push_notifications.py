"""
Push Notification Service Stub

This is a stub for upstream compatibility.
The full PushNotificationService is SaaS-specific and not included in upstream.
"""

import logging
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session

logger = logging.getLogger(__name__)


class PushNotificationService:
    """
    Stub PushNotificationService for upstream.

    The full push notification service with Firebase/APNS integration
    is SaaS-specific and not included in the open-source upstream version.
    """

    def __init__(self, db: Session, workspace_id: str = "default", tenant_id: Optional[str] = None):
        """
        Initialize the stub push notification service.

        Args:
            db: Database session
            workspace_id: Workspace identifier
            tenant_id: Tenant identifier (not used in upstream)
        """
        self.db = db
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        logger.debug("PushNotificationService stub initialized (push notifications not available in upstream)")

    async def send_push_notification(self, user_id: str, title: str, body: str, data: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
        """
        Stub method - push notifications not available in upstream.

        Returns:
            Dict indicating the feature is not available
        """
        logger.warning(f"Push notifications not available in upstream (would send to user {user_id})")
        return {"success": False, "error": "Push notifications not available in upstream version"}

    async def register_device(self, user_id: str, device_token: str, platform: str) -> Dict[str, Any]:
        """
        Stub method - device registration not available in upstream.

        Returns:
            Dict indicating the feature is not available
        """
        logger.warning(f"Device registration not available in upstream (user {user_id}, platform {platform})")
        return {"success": False, "error": "Push notifications not available in upstream version"}

    async def unregister_device(self, user_id: str, device_token: str) -> Dict[str, Any]:
        """
        Stub method - device unregistration not available in upstream.

        Returns:
            Dict indicating the feature is not available
        """
        logger.warning(f"Device unregistration not available in upstream")
        return {"success": False, "error": "Push notifications not available in upstream version"}
