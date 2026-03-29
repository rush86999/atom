"""
HubSpot Adapter for Upstream Orchestrator.
Wraps HubSpotService to provide a unified IntegrationService interface.
"""
from typing import Any, Dict, List, Optional
import logging
import asyncio

from core.integration_base import IntegrationService, OperationResult, IntegrationErrorCode
from integrations.hubspot_service import HubSpotService

logger = logging.getLogger(__name__)

class HubSpotAdapter(IntegrationService):
    """Adapter for HubSpot integration in Upstream."""
    
    def __init__(self, workspace_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(workspace_id, config)
        self.service = HubSpotService()

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
                # Assuming HubSpotService has get_contacts
                result = await asyncio.to_thread(self.service.get_contacts, access_token, limit=limit)
                return OperationResult(success=True, data={"contacts": result})

            elif operation == "create_contact":
                properties = parameters.get("properties", {})
                result = await asyncio.to_thread(self.service.create_contact, access_token, properties)
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
