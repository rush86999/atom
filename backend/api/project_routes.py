from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any
from core.external_integration_service import ConnectionService
from integrations.mcp_service import mcp_service
import logging

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)

@router.get("/unified-tasks")
async def get_unified_tasks(user_id: str = "default_user"):
    """
    Fetch tasks across all connected platforms using the unified MCP tool logic.
    """
    try:
        # We leverage the existing MCP tool logic to avoid code duplication
        tasks = await mcp_service.execute_tool(
            "local-tools", 
            "get_tasks", 
            {}, 
            {"user_id": user_id}
        )
        return tasks
    except Exception as e:
        logger.error(f"Error fetching unified tasks: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/unified-tasks")
async def create_unified_task(task_data: Dict[str, Any], user_id: str = "default_user"):
    """
    Create a task in the primary or specified connected platform.
    """
    try:
        result = await mcp_service.execute_tool(
            "local-tools",
            "create_task",
            task_data,
            {"user_id": user_id}
        )
        return result
    except Exception as e:
        logger.error(f"Error creating unified task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
