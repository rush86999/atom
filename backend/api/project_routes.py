import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from sqlalchemy.orm import Session

from core.api_governance import require_governance, ActionComplexity
from core.database import get_db
from integrations.mcp_service import mcp_service

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
@require_governance(
    action_complexity=ActionComplexity.MODERATE,
    action_name="create_task",
    feature="project"
)
async def create_unified_task(
    task_data: Dict[str, Any],
    user_id: str = "default_user",
    request: Request = None,
    db: Session = Depends(get_db),
    agent_id: Optional[str] = None
):
    """
    Create a task in the primary or specified connected platform.

    **Governance**: Requires INTERN+ maturity (MODERATE complexity).
    - Task creation is a moderate action
    - Requires INTERN maturity or higher
    """
    try:
        result = await mcp_service.execute_tool(
            "local-tools",
            "create_task",
            task_data,
            {"user_id": user_id}
        )
        logger.info(f"Task created successfully")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating unified task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
