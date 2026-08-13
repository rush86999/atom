"""
HubSpot Adapter for Upstream Orchestrator.
Wraps HubSpotService to provide a unified IntegrationService interface.
"""
from typing import Any, Dict, List, Optional
import logging

from core.integration_service import IntegrationService, OperationResult, IntegrationErrorCode
from integrations.hubspot_service import HubSpotService

logger = logging.getLogger(__name__)

class HubSpotAdapter(IntegrationService):
    """Adapter for HubSpot integration in Upstream."""

    def __init__(self, tenant_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(tenant_id or "default", config or {})
        self.workspace_id = self.tenant_id
        self.service = HubSpotService()

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": self.get_supported_operations(),
            "required_params": ["access_token"],
            "optional_params": [],
            "rate_limits": {},
            "supports_webhooks": True,
        }

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "message": "HubSpotAdapter ready", "last_check": None}

    async def execute_operation(
        self, 
        operation: str, 
        parameters: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """
        Execute HubSpot operations.
        Operations:
        - get_contacts: limit
        - create_contact: properties
        - get_deals: limit
        """
        access_token = self.config.get("access_token") or parameters.get("access_token")
        if not access_token:
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.AUTH_EXPIRED, 
                message="Missing HubSpot access token"
            )

        try:
            if operation == "get_contacts":
                limit = parameters.get("limit", 10)
                # BUG (this wave): the token was passed positionally — the
                # service signature is (limit, offset, token) — so the token
                # landed in `limit` and the API was never authenticated, and
                # `asyncio.to_thread` over an `async def` returned an
                # unawaited coroutine instead of the data. Await directly and
                # pass the token by keyword.
                result = await self.service.get_contacts(token=access_token, limit=limit)
                return OperationResult(success=True, data={"contacts": result})

            elif operation == "create_contact":
                properties = parameters.get("properties", {})
                # BUG (this wave): `properties` was passed positionally as
                # `first_name` and the token as `email`; the service signature
                # is (email, first_name, last_name, company, phone, token).
                # Map the properties dict onto the named parameters.
                result = await self.service.create_contact(
                    email=properties.get("email") or "",
                    first_name=properties.get("first_name") or properties.get("firstname"),
                    last_name=properties.get("last_name") or properties.get("lastname"),
                    company=properties.get("company"),
                    phone=properties.get("phone"),
                    token=access_token,
                )
                return OperationResult(success=True, data=result)

            else:
                return OperationResult(
                    success=False, 
                    error=IntegrationErrorCode.NOT_FOUND, 
                    message=f"Operation {operation} not supported by HubSpotAdapter"
                )

        except Exception as e:
            logger.error(f"HubSpotAdapter execution failed: {e}")
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.EXECUTION_EXCEPTION, 
                message=str(e)
            )

    def get_supported_operations(self) -> List[str]:
        return ["get_contacts", "create_contact", "get_deals", "create_deal"]
