"""
Background Agent API Routes - Phase 35
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import require_governance, ActionComplexity
from core.base_routes import BaseAPIRouter
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/background-agents", tags=["Background Agents"])

class RegisterAgentRequest(BaseModel):
    interval_seconds: int = 3600

@router.get("/tasks")
async def list_background_tasks():
    """List all background agent tasks"""
    try:
        from core.background_agent_runner import background_runner
        status = background_runner.get_status()
        return router.success_response(
            data={
                "tasks": list(status.get("agents", {}).values()),
                "total": len(status.get("agents", {})),
                "active": sum(1 for a in status.get("agents", {}).values() if a.get("running")),
                "timestamp": status.get("timestamp")
            }
        )
    except ImportError:
        return router.success_response(
            data={
                "tasks": [],
                "total": 0,
                "active": 0
            },
            message="Background runner not initialized"
        )

@router.post("/{agent_id}/register")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="register_background_agent",
    feature="background_agent"
)
async def register_background_agent(
    agent_id: str,
    request: RegisterAgentRequest,
    http_request: Request,
    db: Session = Depends(get_db),
    requesting_agent_id: Optional[str] = None
):
    """
    Register an agent for background execution.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Background agent registration is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    from core.background_agent_runner import background_runner

    background_runner.register_agent(agent_id, request.interval_seconds)
    logger.info(f"Background agent registered: {agent_id}")
    return router.success_response(
        data={"agent_id": agent_id, "interval": request.interval_seconds},
        message="Agent registered successfully"
    )

@router.post("/{agent_id}/start")
@require_governance(
    action_complexity=ActionComplexity.HIGH,
    action_name="start_background_agent",
    feature="background_agent"
)
async def start_background_agent(
    agent_id: str,
    http_request: Request,
    db: Session = Depends(get_db),
    requesting_agent_id: Optional[str] = None
):
    """
    Start periodic execution of an agent.

    **Governance**: Requires SUPERVISED+ maturity (HIGH complexity).
    - Starting background agents is a high-complexity action
    - Requires SUPERVISED maturity or higher
    """
    from core.background_agent_runner import background_runner

    try:
        await background_runner.start_agent(agent_id)
        logger.info(f"Background agent started: {agent_id}")
        return router.success_response(
            data={"agent_id": agent_id},
            message="Agent started successfully"
        )
    except ValueError as e:
        raise router.not_found_error("Background Agent", agent_id, details={"error": str(e)})

@router.post("/{agent_id}/stop")
async def stop_background_agent(agent_id: str):
    """Stop periodic execution of an agent"""
    from core.background_agent_runner import background_runner

    await background_runner.stop_agent(agent_id)
    return router.success_response(
        data={"agent_id": agent_id},
        message="Agent stopped successfully"
    )

@router.get("/status")
async def get_all_agent_status():
    """Get status of all background agents"""
    try:
        from core.background_agent_runner import background_runner
        return background_runner.get_status()
    except ImportError:
        return {"agents": {}, "message": "Background runner not available"}

@router.get("/{agent_id}/status")
async def get_agent_status(agent_id: str):
    """Get status of a specific agent"""
    from core.background_agent_runner import background_runner
    return background_runner.get_status(agent_id)

@router.get("/{agent_id}/logs")
async def get_agent_logs(agent_id: str, limit: int = 50):
    """Get recent logs for an agent"""
    from core.background_agent_runner import background_runner
    return background_runner.get_logs(agent_id, limit)

@router.get("/logs")
async def get_all_logs(limit: int = 100):
    """Get all recent agent logs"""
    from core.background_agent_runner import background_runner
    return background_runner.get_logs(limit=limit)

