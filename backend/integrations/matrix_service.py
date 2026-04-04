"""
Matrix Service for ATOM Platform
Simple Matrix client implementation for sending messages

Migrated to IntegrationService base class pattern for tenant isolation.
"""

from datetime import datetime, timezone
import logging
import os
from typing import Any, Dict, Optional
import httpx

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)


class MatrixService(IntegrationService):
    """
    Matrix messaging service using Matrix Client-Server API.

    Migrated to IntegrationService base class pattern for tenant isolation.
    """

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize Matrix service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with homeserver, access_token, user_id
        """
        super().__init__(tenant_id=tenant_id, config=config)
        self.homeserver = config.get("homeserver") or os.getenv("MATRIX_HOMESERVER", "https://matrix.org")
        self.access_token = config.get("access_token") or os.getenv("MATRIX_ACCESS_TOKEN")
        self.user_id = config.get("user_id") or os.getenv("MATRIX_USER_ID")
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        await self.client.aclose()

    def get_capabilities(self) -> Dict[str, Any]:
        """
        Return Matrix service capabilities.

        Returns:
            Dict with operations, parameters, rate limits
        """
        return {
            "operations": [
                {
                    "id": "send_message",
                    "name": "Send Message",
                    "description": "Send a text message to a Matrix room",
                    "parameters": {
                        "room_id": {
                            "type": "string",
                            "description": "Matrix room ID",
                            "required": True
                        },
                        "text": {
                            "type": "string",
                            "description": "Message text",
                            "required": True
                        }
                    },
                    "complexity": 3
                },
                {
                    "id": "create_room",
                    "name": "Create Room",
                    "description": "Create a new Matrix room",
                    "parameters": {
                        "name": {
                            "type": "string",
                            "description": "Room name",
                            "required": False
                        },
                        "invite": {
                            "type": "array",
                            "description": "List of user IDs to invite",
                            "required": False
                        }
                    },
                    "complexity": 3
                },
                {
                    "id": "invite_user",
                    "name": "Invite User",
                    "description": "Invite a user to a room",
                    "parameters": {
                        "room_id": {
                            "type": "string",
                            "description": "Matrix room ID",
                            "required": True
                        },
                        "user_id": {
                            "type": "string",
                            "description": "Matrix user ID to invite",
                            "required": True
                        }
                    },
                    "complexity": 2
                }
            ],
            "required_params": ["homeserver", "access_token"],
            "optional_params": ["user_id"],
            "rate_limits": {
                "requests_per_minute": 60,
                "requests_per_hour": 1000
            },
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """
        Check Matrix API connectivity.

        Returns:
            Dict with health status
        """
        return {
            "healthy": bool(self.access_token),
            "message": "Matrix service initialized" if self.access_token else "Access token not configured",
            "last_check": datetime.now(timezone.utc).isoformat(),
            "service": "matrix",
            "status": "healthy" if self.access_token else "degraded"
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Matrix operation with tenant context.

        Args:
            operation: Operation name (send_message, create_room, invite_user)
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
        elif operation == "create_room":
            return await self._create_room(parameters)
        elif operation == "invite_user":
            return await self._invite_user(parameters)
        else:
            raise NotImplementedError(f"Operation '{operation}' not supported by Matrix service")

    async def _send_message(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Send a message to a Matrix room"""
        room_id = parameters.get("room_id")
        text = parameters.get("text")

        if not room_id or not text:
            return {
                "success": False,
                "error": "Missing required parameters: room_id and text",
                "details": {"provided_parameters": list(parameters.keys())}
            }

        if not self.access_token:
            return {
                "success": False,
                "error": "Matrix access token not configured",
                "details": {"tenant_id": self.tenant_id}
            }

        try:
            txn_id = f"atom_{int(datetime.now(timezone.utc).timestamp() * 1000)}"
            url = f"{self.homeserver}/_matrix/client/r0/rooms/{room_id}/send/m.room.message/{txn_id}"

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            data = {
                "msgtype": "m.text",
                "body": text
            }

            response = await self.client.put(url, headers=headers, json=data)
            response.raise_for_status()

            logger.info(f"Matrix message sent to {room_id} for tenant {self.tenant_id}")

            return {
                "success": True,
                "result": {"message_sent": True, "room_id": room_id, "txn_id": txn_id},
                "details": {"service": "matrix", "tenant_id": self.tenant_id}
            }
        except Exception as e:
            logger.error(f"Failed to send Matrix message for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"service": "matrix", "tenant_id": self.tenant_id}
            }

    async def _create_room(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Create a new Matrix room"""
        name = parameters.get("name")
        invite = parameters.get("invite", [])

        if not self.access_token:
            return {
                "success": False,
                "error": "Matrix access token not configured",
                "details": {"tenant_id": self.tenant_id}
            }

        try:
            url = f"{self.homeserver}/_matrix/client/r0/createRoom"

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            data = {}
            if name:
                data["name"] = name
            if invite:
                data["invite"] = invite

            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()

            result = response.json()

            logger.info(f"Matrix room created for tenant {self.tenant_id}: {result.get('room_id')}")

            return {
                "success": True,
                "result": result,
                "details": {"service": "matrix", "tenant_id": self.tenant_id}
            }
        except Exception as e:
            logger.error(f"Failed to create Matrix room for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"service": "matrix", "tenant_id": self.tenant_id}
            }

    async def _invite_user(self, parameters: Dict[str, Any]) -> Dict[str, Any]:
        """Invite a user to a Matrix room"""
        room_id = parameters.get("room_id")
        user_id = parameters.get("user_id")

        if not room_id or not user_id:
            return {
                "success": False,
                "error": "Missing required parameters: room_id and user_id",
                "details": {"provided_parameters": list(parameters.keys())}
            }

        if not self.access_token:
            return {
                "success": False,
                "error": "Matrix access token not configured",
                "details": {"tenant_id": self.tenant_id}
            }

        try:
            url = f"{self.homeserver}/_matrix/client/r0/rooms/{room_id}/invite"

            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }

            data = {
                "user_id": user_id
            }

            response = await self.client.post(url, headers=headers, json=data)
            response.raise_for_status()

            logger.info(f"User {user_id} invited to room {room_id} for tenant {self.tenant_id}")

            return {
                "success": True,
                "result": {"invited": True, "room_id": room_id, "user_id": user_id},
                "details": {"service": "matrix", "tenant_id": self.tenant_id}
            }
        except Exception as e:
            logger.error(f"Failed to invite user to Matrix room for tenant {self.tenant_id}: {e}")
            return {
                "success": False,
                "error": str(e),
                "details": {"service": "matrix", "tenant_id": self.tenant_id}
            }
