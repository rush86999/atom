"""
Asana Adapter for Upstream Orchestrator.
Wraps AsanaService to provide a unified IntegrationService interface.
"""
from typing import Any, Dict, List, Optional
import logging

from core.integration_base import IntegrationService, OperationResult, IntegrationErrorCode
from integrations.asana_service import AsanaService

logger = logging.getLogger(__name__)

class AsanaAdapter(IntegrationService):
    """Adapter for Asana integration in Upstream."""
    
    def __init__(self, workspace_id: Optional[str] = None, config: Optional[Dict[str, Any]] = None):
        super().__init__(workspace_id, config)
        self.service = AsanaService()

    async def execute_operation(
        self, 
        operation: str, 
        parameters: Dict[str, Any], 
        context: Optional[Dict[str, Any]] = None
    ) -> OperationResult:
        """
        Execute Asana operations.
        Expected parameters:
        - access_token: str (Required)
        - task_data: dict (For create_task)
        - project_gid: str (For get_tasks)
        """
        access_token = self.config.get("access_token") or parameters.get("access_token")
        if not access_token:
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.AUTH_EXPIRED, 
                message="Missing access token for Asana"
            )

        try:
            if operation == "create_task":
                task_data = parameters.get("task_data", {})
                if not task_data:
                    return OperationResult(success=False, error=IntegrationErrorCode.INVALID_PARAMETERS, message="Missing task_data")
                
                result = await self.service.create_task(access_token, task_data)
                return OperationResult(
                    success=result.get("ok", False),
                    data=result.get("task"),
                    error=None if result.get("ok") else IntegrationErrorCode.API_ERROR,
                    message=result.get("error")
                )

            elif operation == "get_tasks":
                project_gid = parameters.get("project_gid")
                result = await self.service.get_tasks(access_token, project_gid=project_gid)
                return OperationResult(
                    success=result.get("ok", False),
                    data={"tasks": result.get("tasks")},
                    error=None if result.get("ok") else IntegrationErrorCode.API_ERROR,
                    message=result.get("error")
                )

            elif operation == "get_projects":
                workspace_gid = parameters.get("workspace_gid")
                result = await self.service.get_projects(access_token, workspace_gid=workspace_gid)
                return OperationResult(
                    success=result.get("ok", False),
                    data={"projects": result.get("projects")},
                    error=None if result.get("ok") else IntegrationErrorCode.API_ERROR,
                    message=result.get("error")
                )

            else:
                return OperationResult(
                    success=False, 
                    error=IntegrationErrorCode.NOT_FOUND, 
                    message=f"Operation {operation} not supported by AsanaAdapter"
                )

        except Exception as e:
            logger.error(f"AsanaAdapter execution failed: {e}")
            return OperationResult(
                success=False, 
                error=IntegrationErrorCode.EXECUTION_EXCEPTION, 
                message=str(e)
            )

    def get_supported_operations(self) -> List[str]:
        return ["create_task", "get_tasks", "get_projects", "create_project"]
