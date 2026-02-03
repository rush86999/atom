from fastapi import APIRouter, Depends, HTTPException
from typing import List, Dict, Any, Optional
from integrations.mcp_service import mcp_service
import logging
import os

router = APIRouter(prefix="/api/projects", tags=["projects"])
logger = logging.getLogger(__name__)

# Governance feature flags
PROJECT_GOVERNANCE_ENABLED = os.getenv("PROJECT_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

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
async def create_unified_task(task_data: Dict[str, Any], user_id: str = "default_user", agent_id: Optional[str] = None):
    """
    Create a task in the primary or specified connected platform.

    **Governance**: Requires INTERN+ maturity for task creation.
    """
    # Governance check for task creation
    if PROJECT_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=agent_id,
                action="create_task",
                resource_type="task",
                complexity=2  # MODERATE - task creation
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for create_unified_task by agent {agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    try:
        result = await mcp_service.execute_tool(
            "local-tools",
            "create_task",
            task_data,
            {"user_id": user_id}
        )
        logger.info(f"Task created by agent {agent_id or 'system'}")
        return result
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error creating unified task: {e}")
        raise HTTPException(status_code=500, detail=str(e))
