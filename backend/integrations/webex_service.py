import logging
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException
import httpx

from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class WebexService(IntegrationService):
    """Cisco Webex API Service"""

    def __init__(self, tenant_id: str = "default", config: Dict[str, Any] = None):
        if config is None:
            config = {}
        """
        Initialize Webex service for a specific tenant.

        Args:
            tenant_id: Tenant UUID for multi-tenancy
            config: Tenant-specific configuration with access_token
        """
        super().__init__(tenant_id=tenant_id, config=config)
        self.base_url = "https://webexapis.com/v1"
        self.access_token = config.get("access_token")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }

    async def list_rooms(self) -> List[Dict[str, Any]]:
        """List Webex rooms (now called Spaces)"""
        try:
            if not self.access_token:
                # Stub data
                return [{
                    "id": "mock_room_id",
                    "title": "Strategy Room (MOCK)",
                    "type": "group",
                    "isLocked": False
                }]

            url = f"{self.base_url}/rooms"
            response = await self.client.get(url, headers=self._get_headers())
            response.raise_for_status()
            return response.json().get("items", [])
        except Exception as e:
            logger.error(f"Webex list_rooms failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Webex integration capabilities"""
        return {
            "operations": [
                {
                    "id": "list_rooms",
                    "name": "List Rooms",
                    "description": "List Webex rooms (Spaces)",
                    "complexity": 1
                },
                {
                    "id": "send_message",
                    "name": "Send Message",
                    "description": "Send message to a Webex room",
                    "complexity": 3
                }
            ],
            "required_params": ["access_token"],
            "optional_params": [],
            "rate_limits": {"requests_per_minute": 100},
            "supports_webhooks": True
        }

    def health_check(self) -> Dict[str, Any]:
        """Check Webex connectivity"""
        return {
            "healthy": bool(self.access_token),
            "message": "Webex service is operational" if self.access_token else "Webex access token not configured",
            "last_check": datetime.now(timezone.utc).isoformat()
        }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Execute a Webex operation with tenant context.

        Args:
            operation: Operation name (e.g., "list_rooms", "send_message")
            parameters: Operation parameters
            context: Tenant context dict

        Returns:
            Dict with success, result, error, details
        """
        try:
            if operation == "list_rooms":
                result = await self.list_rooms()
                return {
                    "success": True,
                    "result": result,
                    "details": {"operation": "list_rooms", "tenant_id": self.tenant_id}
                }
            else:
                return {
                    "success": False,
                    "error": f"Unknown operation: {operation}",
                    "details": {"operation": operation}
                }
        except Exception as e:
            return {
                "success": False,
                "error": str(e),
                "details": {"operation": operation, "tenant_id": self.tenant_id}
            }
