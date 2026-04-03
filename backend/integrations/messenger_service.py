"""
Messenger Service for ATOM Platform
Handles Facebook Messenger Messaging API interactions

Migrated to IntegrationService base class pattern for tenant isolation.
"""

from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional
import httpx

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)


class MessengerService(IntegrationService):
    """
    Facebook Messenger messaging service using Graph API.

    Migrated to IntegrationService base class pattern for tenant isolation.
    """

    def __init__(self, config: Dict[str, Any]):
        """
        Initialize Messenger service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with page_access_token, api_version
        """
        super().__init__(tenant_id, config)
        self.page_access_token = config.get("page_access_token") or os.getenv("MESSENGER_PAGE_ACCESS_TOKEN")
        self.api_version = config.get("api_version") or os.getenv("MESSENGER_API_VERSION", "v19.0")
        self.base_url = f"https://graph.facebook.com/{self.api_version}"
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        await self.client.aclose()

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return Messenger service capabilities.

        Returns:
            Dict with operations, parameters, rate limits
        """
        return {
            "operations": [
                {
                    "id": "send_message",
                    "name": "Send Message",
                    "description": "Send a text message via Facebook Messenger",
                    "parameters": {
                        "recipient_id": {
                            "type": "string",
                            "description": "PSID (Page-Scoped ID) of recipient",
                            "required": True
                        },
                        "message": {
                            "type": "string",
                            "description": "Message text",
                            "required": True
                        },
                        "messaging_type": {
                            "type": "string",
                            "description": "RESPONSE, UPDATE, or MESSAGE_TAG",
                            "required": False
                        }
                    },
                    "complexity": 3
                },
                {
                    "id": "get_webhook",
                    "name": "Get Webhook Info",
                    "description": "Get webhook configuration information",
                    "parameters": {
                        "webhook_url": {
                            "type": "string",
                            "description": "Webhook URL",
                            "required": False
                        }
                    },
                    "complexity": 1
                },
                {
                    "id": "subscribe",
                    "name": "Subscribe to Webhook",
                    "description": "Subscribe app to page webhook events",
                    "parameters": {
                        "fields": {
                            "type": "array",
                            "description": "List of webhook fields to subscribe to",
                            "required": False
                        }
                    },
                    "complexity": 2
                }
            ],
            "required_params": ["page_access_token"],
            "optional_params": ["api_version"],
            "rate_limits": {
                "requests_per_minute": 240,
                "requests_per_hour": 14400
            },
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check Messenger API connectivity.

        Returns:
            Dict with health status
        """
        return {
            "healthy": bool(self.page_access_token),
            "message": "Messenger service initialized" if self.page_access_token else "Page access token not configured",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "service": "messenger",
            "status": "healthy" if self.page_access_token else "degraded"
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Messenger operation with tenant context.

        Args:
            operation: Operation name (send_message, get_webhook, subscribe)
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
        elif operation == "get_webhook":
            return await self._get_webhook(parameters)
        elif operation == "subscribe":
            return await self._subscribe(parameters)
        else:
            raise NotImplementedError(f"Operation '{operation}' not supported by Messenger service")

    async def _send_message(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message via Facebook Messenger"""
        recipient_id = parameters.get("recipient_id")
        message = parameters.get("message")
        messaging_type = parameters.get("messaging_type", "RESPONSE")

        if not recipient_id or not message:
            return {
                "success": False,
                "error": "Missing required parameters: recipient_id and message",
                "details": {"provided_parameters": list(parameters.keys())}
            }

        if not self.page_access_token:
            return {
                "success": False,
                "error": "Messenger page access token not configured",
                "details": {"tenant_id": self.tenant_id}
            }

        try:
            url = f"{self.base_url}/me/messages"
            params = {"access_token": self.page_access_token}

            data = {
                "recipient": {"id": recipient_id},
                "message": {"text": message},
                "messaging_type": messaging_type
            }

            response = await self.client.post(url, params=params, json=data)
            response.raise_for_status()

            logger.info(f"Messenger message sent to {recipient_id} for tenant {self.tenant_id}")

            return {
                "success": True,
                "result": {"message_sent": True, "recipient_id": recipient_id},
                "details": {"service": "messenger", "tenant_id": self.tenant_id}
            }
        except Exception as e:
            logger.error(f"Failed to send Messenger message for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"service": "messenger", "tenant_id": self.tenant_id}
            }

<<<<<<< HEAD
    async def health_check(self) -> Dict[str, Any]:
=======
    async def _get_webhook(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Get webhook configuration information"""
        webhook_url = parameters.get("webhook_url")
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31

        return {
            "success": True,
            "result": {
                "message": "Messenger uses webhook-based message delivery",
                "webhook_url": webhook_url,
                "configure_webhook": f"{self.base_url}/me/subscribed_apps"
            },
            "details": {"service": "messenger", "tenant_id": self.tenant_id}
        }

    async def _subscribe(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Subscribe to webhook events"""
        fields = parameters.get("fields", ["messages", "messaging_postbacks"])

        if not self.page_access_token:
            return {
                "success": False,
                "error": "Messenger page access token not configured",
                "details": {"tenant_id": self.tenant_id}
            }

<<<<<<< HEAD
=======
        try:
            url = f"{self.base_url}/me/subscribed_apps"
            params = {"access_token": self.page_access_token}

            data = {
                "fields": fields
            }

            response = await self.client.post(url, params=params, json=data)
            response.raise_for_status()

            logger.info(f"Messenger webhook subscription created for tenant {self.tenant_id}")

            return {
                "success": True,
                "result": {"subscribed": True, "fields": fields},
                "details": {"service": "messenger", "tenant_id": self.tenant_id}
            }
        except Exception as e:
            logger.error(f"Failed to subscribe to Messenger webhook for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"service": "messenger", "tenant_id": self.tenant_id}
            }
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
