"""
Messenger Service for ATOM Platform
Handles Facebook Messenger Messaging API interactions
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

class MessengerService:
    def __init__(self):
        self.page_access_token = os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")
        self.api_version = os.getenv("MESSENGER_API_VERSION", "v19.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def send_message(self, recipient_id: str, text: str) -> bool:
        """Send a message via Facebook Messenger Send API"""
        if not self.page_access_token:
            logger.error("MESSENGER_PAGE_ACCESS_TOKEN not set")
            return False

        url = f"{self.base_url}/me/messages"
        params = {"access_token": self.page_access_token}
        
        data = {
            "recipient": {"id": recipient_id},
            "message": {"text": text}
        }
        
        try:
            response = await self.client.post(url, params=params, json=data)
            response.raise_for_status()
            logger.info(f"Messenger message sent to {recipient_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Messenger message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "status": "healthy" if self.page_access_token else "degraded",
            "service": "messenger",
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
messenger_service = MessengerService()
