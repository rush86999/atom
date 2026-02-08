
from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class OpenClawService:
    """
    Service for interacting with OpenClaw (self-hosted AI automation instances).
    Supports sending messages and triggering workflows via remote webhook.
    """
    def __init__(self):
        # The user should configure their OpenClaw gateway URL here
        # e.g. https://openclaw.my-domain.com/webhook/atom or an ngrok URL
        self.webhook_url = os.getenv("OPENCLAW_WEBHOOK_URL")
        self.api_key = os.getenv("OPENCLAW_API_KEY") # Optional auth
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        headers = {
            "Content-Type": "application/json",
            "User-Agent": "Atom-OpenClaw-Bridge/1.0"
        }
        if self.api_key:
            headers["Authorization"] = f"Bearer {self.api_key}"
        return headers

    async def send_message(self, recipient_id: str, content: str, thread_ts: Optional[str] = None) -> Dict[str, Any]:
        """
        Send a message to an OpenClaw instance.
        
        Args:
            recipient_id: The ID of the recipient on the OpenClaw side (or channel)
            content: The message text
            thread_ts: Optional thread ID to reply to
        """
        if not self.webhook_url:
            logger.warning("OPENCLAW_WEBHOOK_URL not configured. Cannot send message.")
            return {"status": "skipped", "reason": "configuration_missing"}

        payload = {
            "type": "message",
            "recipient_id": recipient_id,
            "content": content,
            "timestamp": datetime.utcnow().isoformat()
        }
        if thread_ts:
            payload["thread_ts"] = thread_ts

        try:
            logger.info(f"Sending message to OpenClaw at {self.webhook_url}")
            response = await self.client.post(
                self.webhook_url,
                json=payload,
                headers=self._get_headers()
            )
            response.raise_for_status()
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send message to OpenClaw: {e}")
            return {"status": "error", "message": str(e)}

    async def health_check(self) -> Dict[str, Any]:
        """Check if OpenClaw webhook URL is reachable"""
        if not self.webhook_url:
             return {
                "ok": False,
                "status": "not_configured",
                "service": "openclaw",
                "message": "OPENCLAW_WEBHOOK_URL not set"
            }
            
        try:
            # We assume the webhook endpoint accepts a health check ping or returns 405/200
            # Sending a dummy ping
            response = await self.client.post(
                self.webhook_url,
                json={"type": "ping"},
                headers=self._get_headers()
            )
            return {
                "ok": response.status_code < 500,
                "status": "reachable" if response.status_code < 500 else "error",
                "service": "openclaw",
                "status_code": response.status_code
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unreachable",
                "service": "openclaw",
                "error": str(e)
            }

# Singleton instance
openclaw_service = OpenClawService()
