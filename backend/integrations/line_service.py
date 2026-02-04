"""
Line Service for ATOM Platform
Handles Line Messaging API interactions
"""

import logging
import os
from datetime import datetime
from typing import Any, Dict, Optional
import httpx

logger = logging.getLogger(__name__)

class LineService:
    def __init__(self):
        # Line uses Channel Access Token
        self.channel_access_token = os.getenv("LINE_CHANNEL_ACCESS_TOKEN")
        self.base_url = "https://api.line.me/v2/bot/message"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def send_message(self, to: str, text: str) -> bool:
        """Send a push message via Line Messaging API"""
        if not self.channel_access_token:
            logger.error("LINE_CHANNEL_ACCESS_TOKEN not set")
            return False

        url = f"{self.base_url}/push"
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.channel_access_token}"
        }
        
        data = {
            "to": to,
            "messages": [
                {
                    "type": "text",
                    "text": text
                }
            ]
        }
        
        try:
            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Line message pushed to {to}")
            return True
        except Exception as e:
            logger.error(f"Failed to push Line message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "status": "healthy" if self.channel_access_token else "degraded",
            "service": "line",
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
line_service = LineService()
