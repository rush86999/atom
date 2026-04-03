import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime, timezone
from fastapi import HTTPException
import httpx
from core.integration_service import IntegrationService

logger = logging.getLogger(__name__)

class OktaService(IntegrationService):
    """Okta Identity API Service"""

    def __init__(self, config: Dict[str, Any]):
        super().__init__(tenant_id, config)
        self.org_url = self.config.get("okta_org_url") or os.getenv("OKTA_ORG_URL")
        self.api_token = self.config.get("okta_api_token") or os.getenv("OKTA_API_TOKEN")
        self.client = httpx.AsyncClient(timeout=30.0)

    def _get_headers(self) -> Dict[str, str]:
        return {
            "Authorization": f"SSWS {self.api_token}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }

    async def list_users(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List users from Okta"""
        try:
            if not self.api_token or not self.org_url:
                # Stub data
                return [{
                    "id": "mock_id",
                    "profile": {"firstName": "Admin", "lastName": "User", "email": "admin@example.com"},
                    "status": "ACTIVE (MOCK)"
                }]

            url = f"{self.org_url}/api/v1/users"
            params = {"limit": limit}
            response = await self.client.get(url, headers=self._get_headers(), params=params)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Okta list_users failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """Check Okta connectivity"""
<<<<<<< HEAD

=======
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
        return {
            "status": "active" if self.api_token else "partially_configured",
            "service": "okta",
            "mode": "real" if self.api_token else "mock"
        }

    def get_capabilities(self) -> Dict[str, Any]:
        """Return Okta integration capabilities"""
        return {
            "operations": [
                {"id": "create_user", "name": "Create User"},
                {"id": "get_user", "name": "Get User"},
                {"id": "update_user", "name": "Update User"},
                {"id": "assign_role", "name": "Assign Role"},
                {"id": "get_groups", "name": "Get Groups"},
                {"id": "list_users", "name": "List Users"}
            ],
            "required_params": ["api_token"],
            "optional_params": ["limit"],
            "rate_limits": {"requests_per_minute": 200},
            "supports_webhooks": True
        }

<<<<<<< HEAD
=======
    def health_check(self) -> Dict[str, Any]:
        """Synchronous health check for Okta service"""
        try:
            is_healthy = bool(self.org_url)
            return {
                "ok": is_healthy,
                "status": "healthy" if is_healthy else "unhealthy",
                "healthy": is_healthy,
                "service": "okta",
                "timestamp": datetime.now(timezone.utc).isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "healthy": False,
                "service": "okta",
                "error": str(e),
                "timestamp": datetime.now(timezone.utc).isoformat(),
            }

    async def execute_operation(
        self,
        operation: str,
        parameters: Dict[str, Any],
        context: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """Execute an Okta operation"""
        try:
            if operation == "list_users":
                res = await self.list_users(parameters.get("limit", 50))
                return {"success": True, "result": res}
            elif operation == "create_user":
                # Stub implementation
                return {"success": True, "result": {"id": "new_user", "email": parameters.get("email")}}
            elif operation == "get_user":
                # Stub implementation
                return {"success": True, "result": {"id": parameters.get("user_id")}}
            elif operation == "update_user":
                # Stub implementation
                return {"success": True, "result": {"id": parameters.get("user_id"), "updated": True}}
            elif operation == "assign_role":
                # Stub implementation
                return {"success": True, "result": {"user_id": parameters.get("user_id"), "role_id": parameters.get("role_id")}}
            elif operation == "get_groups":
                # Stub implementation
                return {"success": True, "result": {"groups": []}}
            else:
                raise NotImplementedError(f"Operation {operation} not supported for Okta")
        except Exception as e:
            return {"success": False, "error": str(e)}

# Global instance removed - use IntegrationRegistry instead
# okta_service = OktaService()
>>>>>>> 03749d7d07192ccb2b61838cf322e7a67aecae31
