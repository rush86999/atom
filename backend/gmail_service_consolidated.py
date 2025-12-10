"""
Consolidated Gmail Service
Built using BaseIntegrationService patterns for consistency and reduced duplication
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from integrations.base_integration_service import BaseIntegrationService

logger = logging.getLogger(__name__)

class GmailService(BaseIntegrationService):
    """
    Consolidated Gmail service using BaseIntegrationService
    """

    def __init__(self):
        super().__init__("gmail", {
            "gmail": {
                "base_url": "https://gmail.googleapis.com",
                "auth_required": True,
                "scopes": ["https://www.googleapis.com/auth/gmail.readonly"]
            }
        })

    async def get_messages(self, user_email: str, **kwargs) -> Dict[str, Any]:
        """
        Get Gmail messages for the user
        """
        try:
            response = await self.make_authenticated_request(
                provider="gmail",
                endpoint="/gmail/v1/users/me/messages",
                user_email=user_email,
                params=kwargs
            )

            return {
                "success": True,
                "messages": response.get("messages", []),
                "total": response.get("resultSizeEstimate", 0)
            }

        except Exception as e:
            logger.error(f"Failed to get Gmail messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def send_message(self, user_email: str, message_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Send Gmail message
        """
        try:
            response = await self.make_authenticated_request(
                provider="gmail",
                endpoint="/gmail/v1/users/me/messages/send",
                method="POST",
                user_email=user_email,
                json_data=message_data
            )

            return {
                "success": True,
                "message_id": response.get("id"),
                "thread_id": response.get("threadId")
            }

        except Exception as e:
            logger.error(f"Failed to send Gmail message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
gmail_service = GmailService()

def get_gmail_service() -> GmailService:
    """Get Gmail service instance"""
    return gmail_service