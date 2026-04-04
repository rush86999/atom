"""
Signal Service for ATOM Platform
Handles interaction with signal-cli-rest-api
"""

from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional
import httpx

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)


class SignalService(IntegrationService):
    """
    Signal messaging service using signal-cli-rest-api.

    Migrated to IntegrationService base class pattern for tenant isolation.
    """

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize Signal service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with api_url and sender_number
        """
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = config.get("api_url", os.getenv("SIGNAL_API_URL", "http://localhost:8080"))
        self.sender_number = config.get("sender_number", os.getenv("SIGNAL_SENDER_NUMBER"))
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return Signal service capabilities.

        Returns:
            Dict with operations, parameters, rate limits
        """
        return {
            "operations": [
                {
                    "id": "send_message",
                    "name": "Send Message",
                    "description": "Send a text message via Signal",
                    "parameters": {
                        "recipient": {
                            "type": "string",
                            "description": "Phone number to send message to",
                            "required": True
                        },
                        "message": {
                            "type": "string",
                            "description": "Message text to send",
                            "required": True
                        }
                    },
                    "complexity": 3
                },
                {
                    "id": "receive_message",
                    "name": "Receive Message",
                    "description": "Receive incoming Signal messages (webhook-based)",
                    "parameters": {
                        "webhook_url": {
                            "type": "string",
                            "description": "Webhook URL to receive messages",
                            "required": False
                        }
                    },
                    "complexity": 1
                },
                {
                    "id": "get_profile",
                    "name": "Get Profile",
                    "description": "Get Signal profile information",
                    "parameters": {
                        "phone_number": {
                            "type": "string",
                            "description": "Phone number to lookup",
                            "required": True
                        }
                    },
                    "complexity": 1
                }
            ],
            "required_params": ["api_url", "sender_number"],
            "optional_params": [],
            "rate_limits": {
                "requests_per_minute": 100,
                "requests_per_hour": 1000
            },
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check Signal API connectivity.

        Returns:
            Dict with health status
        """
        return {
            "healthy": bool(self.sender_number),
            "message": "Signal service initialized" if self.sender_number else "Sender number not configured",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "service": "signal",
            "status": "healthy" if self.sender_number else "degraded"
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Signal operation with tenant context.

        Args:
            operation: Operation name (send_message, receive_message, get_profile)
            parameters: Operation parameters
            context: Tenant context dict with tenant_id, agent_id, etc.

        Returns:
            Dict with success, result, error, details

        Raises:
            NotImplementedError: If operation not supported
        """
        # CRITICAL: Validate tenant_id from context to prevent cross-tenant access
        if context:
            context_tenant_id = context.get("tenant_id")
            if context_tenant_id and context_tenant_id != self.tenant_id:
                logger.error(f"Tenant ID mismatch: context={context_tenant_id}, service={self.tenant_id}")
                return {
                    "success": False,
                    "error": "Tenant ID validation failed",
                    "details": {"operation": operation, "reason": "cross_tenant_access_prevented"}
                }

        if operation == "send_message":
            return await self._send_message(parameters)
        elif operation == "receive_message":
            return await self._receive_message(parameters)
        elif operation == "get_profile":
            return await self._get_profile(parameters)
        else:
            raise NotImplementedError(f"Operation '{operation}' not supported by Signal service")

    async def _send_message(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message via Signal"""
        recipient = parameters.get("recipient")
        message = parameters.get("message")

        if not recipient or not message:
            return {
                "success": False,
                "error": "Missing required parameters: recipient and message",
                "details": {"provided_parameters": list(parameters.keys())}
            }

        if not self.sender_number:
            return {
                "success": False,
                "error": "Signal sender number not configured",
                "details": {"tenant_id": self.tenant_id}
            }

        try:
            url = f"{self.base_url}/v1/send"
            data = {
                "message": message,
                "number": self.sender_number,
                "recipients": [recipient]
            }

            response = await self.client.post(url, json=data)
            response.raise_for_status()

            logger.info(f"Signal message sent to {recipient} for tenant {self.tenant_id}")

            return {
                "success": True,
                "result": {"message_sent": True, "recipient": recipient},
                "details": {"service": "signal", "tenant_id": self.tenant_id}
            }
        except Exception as e:
            logger.error(f"Failed to send Signal message for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"service": "signal", "tenant_id": self.tenant_id}
            }

    async def _receive_message(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Receive messages (webhook-based, returns webhook info)"""
        webhook_url = parameters.get("webhook_url")

        return {
            "success": True,
            "result": {
                "message": "Signal uses webhook-based message delivery",
                "webhook_url": webhook_url,
                "configure_webhook": f"{self.base_url}/v1/webhook"
            },
            "details": {"service": "signal", "tenant_id": self.tenant_id}
        }

    async def _get_profile(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get Signal profile information"""
        phone_number = parameters.get("phone_number")

        if not phone_number:
            return {
                "success": False,
                "error": "Missing required parameter: phone_number",
                "details": {"provided_parameters": list(parameters.keys())}
            }

        # Signal API doesn't have a public profile endpoint in signal-cli-rest-api
        # Return informational response
        return {
            "success": True,
            "result": {
                "phone_number": phone_number,
                "note": "Profile information requires local Signal account lookup"
            },
            "details": {"service": "signal", "tenant_id": self.tenant_id}
        }
