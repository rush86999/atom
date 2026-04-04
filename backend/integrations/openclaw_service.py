
from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class OpenClawService(IntegrationService):
    """
    Service for interacting with OpenClaw (self-hosted AI automation instances).
    Supports sending messages and triggering workflows via remote webhook.
    """
    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        super().__init__(tenant_id=tenant_id, config=config)
        self.webhook_url = self.config.get("openclaw_webhook_url")
        self.api_key = self.config.get("openclaw_api_key")
        self.client = httpx.AsyncClient(timeout=30.0)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": [{"id": "send_message", "name": "Send Message"}],
            "required_params": ["webhook_url"],
            "optional_params": ["api_key"],
            "rate_limits": {"requests_per_minute": 60},
            "supports_webhooks": True
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        try:
            if context and context.get("tenant_id") and context.get("tenant_id") != self.tenant_id:
                return {"success": False, "error": "Tenant mismatch validation failed", "details": {}}
                
            if operation == "send_message":
                recipient_id = parameters.get("recipient_id")
                content = parameters.get("content")
                if not recipient_id or not content:
                    return {"success": False, "error": "Missing recipient_id or content", "details": {}}
                thread_ts = parameters.get("thread_ts")
                res = await self.send_message(recipient_id, content, thread_ts)
                is_success = res.get("status") not in ["error", "skipped"]
                return {"success": is_success, "result": res, "error": res.get("message"), "details": {}}
            else:
                raise NotImplementedError(f"Operation {operation} not supported")
        except Exception as e:
            return {"success": False, "error": str(e), "details": {}}

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
            "timestamp": datetime.now(timezone.utc).isoformat()
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

    def health_check(self) -> Dict[str, Any]:
        """Check if OpenClaw webhook URL is reachable"""
        import requests
        if not self.webhook_url:
             return {
                "healthy": False,
                "status": "not_configured",
                "service": "openclaw",
                "message": "webhook_url not set in config",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
            
        try:
            response = requests.post(
                self.webhook_url,
                json={"type": "ping"},
                headers=self._get_headers(),
                timeout=10.0
            )
            is_healthy = response.status_code < 500
            return {
                "healthy": is_healthy,
                "status": "reachable" if is_healthy else "error",
                "service": "openclaw",
                "status_code": response.status_code,
                "message": "Connected" if is_healthy else f"Status {response.status_code}",
                "last_check": datetime.now(timezone.utc).isoformat()
            }
        except Exception as e:
            return {
                "healthy": False,
                "status": "unreachable",
                "service": "openclaw",
                "error": str(e),
                "last_check": datetime.now(timezone.utc).isoformat()
            }
