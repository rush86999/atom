"""
Notification service stub for upstream.

This is a minimal stub implementation for upstream open-source version.
The full notification service with tenant-aware email providers is SaaS-specific.
"""

from typing import Dict, Any, Optional
from sqlalchemy.orm import Session

class NotificationService:
    """
    Stub notification service for upstream.

    The full SaaS version includes tenant-aware email provider integration.
    """

    def __init__(self, db_session: Optional[Session] = None):
        """
        Initialize the notification service stub.

        Args:
            db_session: Optional database session (unused in stub)
        """
        self.db = db_session

    async def send_notification(
        self,
        user_id: str,
        notification_type: str,
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """
        Stub method for sending notifications.

        In the SaaS version, this sends emails via tenant's email provider.
        In upstream, this is a no-op stub.

        Args:
            user_id: User identifier (unused in stub)
            notification_type: Type of notification (unused in stub)
            data: Notification data (unused in stub)

        Returns:
            Empty success response
        """
        # Stub: no-op in upstream
        return {"success": True, "message": "Notification stub (no-op in upstream)"}
