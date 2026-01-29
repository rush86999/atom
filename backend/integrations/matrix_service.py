"""
Matrix Service for ATOM Platform
Simple Matrix client implementation for sending messages
"""

import logging
import os
import httpx
from typing import Any, Dict, Optional
from datetime import datetime

logger = logging.getLogger(__name__)

class MatrixService:
    def __init__(self):
        self.homeserver = os.getenv("MATRIX_HOMESERVER", "https://matrix.org")
        self.access_token = os.getenv("MATRIX_ACCESS_TOKEN")
        self.user_id = os.getenv("MATRIX_USER_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    async def send_message(self, room_id: str, text: str) -> bool:
        """Send a message to a Matrix room"""
        if not self.access_token:
            logger.error("MATRIX_ACCESS_TOKEN not set")
            return False

        txn_id = f"atom_{int(datetime.now().timestamp() * 1000)}"
        url = f"{self.homeserver}/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{txn_id}"
        
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        
        data = {
            "msgtype": "m.text",
            "body": text
        }
        
        try:
            response = await self.client.put(url, headers=headers, json=data)
            response.raise_for_status()
            logger.info(f"Matrix message sent to {room_id}")
            return True
        except Exception as e:
            logger.error(f"Failed to send Matrix message: {e}")
            return False

    async def health_check(self) -> Dict[str, Any]:
        return {
            "ok": True,
            "status": "healthy" if self.access_token else "degraded",
            "service": "matrix",
            "timestamp": datetime.now().isoformat()
        }

# Singleton instance
matrix_service = MatrixService()
