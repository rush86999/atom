"""
Notion Adapter for Upstream Orchestrator.
Wraps NotionService to provide a unified IntegrationService interface.
"""
from typing import Any, Dict, List, Optional
import logging
import asyncio

from core.integration_service import IntegrationService, OperationResult, IntegrationErrorCode
from integrations.notion_service import NotionService

logger = logging.getLogger(__name__)

class NotionAdapter(IntegrationService):
    """Adapter for Notion integration in Upstream."""

    def __init__(self, tenant_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        # Base A identity model: tenant_id is the scope string (the registry
        # passes its workspace_id here). Preserve a workspace_id alias for any
        # caller that still reads it.
        super().__init__(tenant_id or "default", config or {})
        self.workspace_id = self.tenant_id
        # NotionService uses the Base A (tenant_id, config) contract; the token
        # is read from config inside the service.
        self.service = NotionService(tenant_id=self.tenant_id, config=self.config)

    def get_capabilities(self) -> Dict[str, Any]:
        return {
            "operations": self.get_supported_operations(),
            "required_params": ["access_token"],
            "optional_params": [],
            "rate_limits": {},
            "supports_webhooks": False,
        }

    def health_check(self) -> Dict[str, Any]:
        return {"healthy": True, "message": "NotionAdapter ready", "last_check": None}

    async def execute_operation(
        self, 
        operation: str, 
        parameters: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """
        Execute Notion operations.
        Operations:
        - create_page: parent, properties, children
        - query_database: database_id, filter, sorts
        - search: query, filter
        """
        try:
            # Re-initialize service if token is provided in parameters
            if "access_token" in parameters:
                self.service = NotionService(
                    tenant_id=self.tenant_id,
                    config={**self.config, "access_token": parameters["access_token"]},
                )

            if operation == "create_page":
                parent = parameters.get("parent")
                properties = parameters.get("properties")
                if not parent or not properties:
                    return OperationResult(success=False, error=IntegrationErrorCode.INVALID_PARAMETERS, message="Missing parent or properties")
                
                # Service is sync, wrap in thread
                result = await asyncio.to_thread(
                    self.service.create_page, parent, properties, parameters.get("children")
                )
                return OperationResult(
                    success=result is not None,
                    data=result,
                    error=None if result else IntegrationErrorCode.API_ERROR
                )

            elif operation == "query_database":
                database_id = parameters.get("database_id")
                if not database_id:
                    return OperationResult(success=False, error=IntegrationErrorCode.INVALID_PARAMETERS, message="Missing database_id")
                
                result = await asyncio.to_thread(
                    self.service.query_database, database_id,
                    **{k: v for k, v in parameters.items() if k != "database_id"}
                )
                return OperationResult(
                    success=True, 
                    data={"results": result.get("results"), "has_more": result.get("has_more")}
                )

            elif operation == "search":
                query = parameters.get("query", "")
                result = await asyncio.to_thread(
                    self.service.search, query=query,
                    **{k: v for k, v in parameters.items() if k != "query"}
                )
                return OperationResult(
                    success=True, 
                    data={"results": result.get("results"), "has_more": result.get("has_more")}
                )

            else:
                return OperationResult(
                    success=False, 
                    error=IntegrationErrorCode.NOT_FOUND, 
                    message=f"Operation {operation} not supported by NotionAdapter"
                )

        except Exception as e:
            logger.error(f"NotionAdapter execution failed: {e}")
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.EXECUTION_EXCEPTION, 
                message=str(e)
            )

    def get_supported_operations(self) -> List[str]:
        return ["create_page", "query_database", "search", "update_page", "get_page"]
