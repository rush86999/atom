"""
Consolidated Slack Service
Built using BaseIntegrationService patterns for consistency and reduced duplication
"""

import asyncio
import logging
from typing import Dict, List, Any, Optional
from datetime import datetime

from integrations.base_integration_service import BaseIntegrationService

logger = logging.getLogger(__name__)

class SlackService(BaseIntegrationService):
    """
    Consolidated Slack service using BaseIntegrationService
    """

    def __init__(self):
        super().__init__("slack", {
            "slack": {
                "base_url": "https://slack.com/api",
                "auth_required": True,
                "scopes": ["chat:write", "channels:read"]
            }
        })

    async def send_message(self, user_email: str, channel: str, text: str, **kwargs) -> Dict[str, Any]:
        """
        Send message to Slack channel
        """
        try:
            payload = {
                "channel": channel,
                "text": text
            }
            payload.update(kwargs)

            response = await self.make_authenticated_request(
                provider="slack",
                endpoint="/chat.postMessage",
                method="POST",
                user_email=user_email,
                json_data=payload
            )

            return {
                "success": response.get("ok", False),
                "message_ts": response.get("ts"),
                "channel": response.get("channel")
            }

        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return {
                "success": False,
                "error": str(e)
            }

    async def get_channels(self, user_email: str, **kwargs) -> Dict[str, Any]:
        """
        Get Slack channels
        """
        try:
            response = await self.make_authenticated_request(
                provider="slack",
                endpoint="/conversations.list",
                user_email=user_email,
                params=kwargs
            )

            return {
                "success": True,
                "channels": response.get("channels", []),
                "total": len(response.get("channels", []))
            }

        except Exception as e:
            logger.error(f"Failed to get Slack channels: {e}")
            return {
                "success": False,
                "error": str(e)
            }

# Global instance
slack_service = SlackService()

def get_slack_service() -> SlackService:
    """Get Slack service instance"""
    return slack_service