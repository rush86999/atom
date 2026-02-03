"""
Background Agent API Routes - Phase 35
"""

import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/background-agents", tags=["Background Agents"])

# Governance feature flags
BACKGROUND_AGENT_GOVERNANCE_ENABLED = os.getenv("BACKGROUND_AGENT_GOVERNANCE_ENABLED", "true").lower() == "true"
EMERGENCY_GOVERNANCE_BYPASS = os.getenv("EMERGENCY_GOVERNANCE_BYPASS", "false").lower() == "true"

class RegisterAgentRequest(BaseModel):
    interval_seconds: int = 3600

@router.get("/tasks")
async def list_background_tasks():
    """List all background agent tasks"""
    try:
        from core.background_agent_runner import background_runner
        status = background_runner.get_status()
        return {
            "tasks": list(status.get("agents", {}).values()),
            "total": len(status.get("agents", {})),
            "active": sum(1 for a in status.get("agents", {}).values() if a.get("running")),
            "timestamp": status.get("timestamp")
        }
    except ImportError:
        return {
            "tasks": [],
            "total": 0,
            "active": 0,
            "message": "Background runner not initialized"
        }

@router.post("/{agent_id}/register")
async def register_background_agent(agent_id: str, request: RegisterAgentRequest, requesting_agent_id: Optional[str] = None):
    """
    Register an agent for background execution.

    **Governance**: Requires SUPERVISED+ maturity to register background agents.
    """
    # Governance check for background agent registration
    if BACKGROUND_AGENT_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and requesting_agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=requesting_agent_id,
                action="register_background_agent",
                resource_type="background_agent",
                complexity=3  # HIGH - background execution control
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for register_background_agent by agent {requesting_agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    from core.background_agent_runner import background_runner

    background_runner.register_agent(agent_id, request.interval_seconds)
    logger.info(f"Background agent registered: {agent_id} by {requesting_agent_id or 'system'}")
    return {"status": "registered", "agent_id": agent_id, "interval": request.interval_seconds}

@router.post("/{agent_id}/start")
async def start_background_agent(agent_id: str, requesting_agent_id: Optional[str] = None):
    """
    Start periodic execution of an agent.

    **Governance**: Requires SUPERVISED+ maturity to start background agents.
    """
    # Governance check for starting background agents
    if BACKGROUND_AGENT_GOVERNANCE_ENABLED and not EMERGENCY_GOVERNANCE_BYPASS and requesting_agent_id:
        from core.agent_governance_service import AgentGovernanceService
        from core.database import get_db

        db = next(get_db())
        try:
            governance = AgentGovernanceService(db)
            check = governance.can_perform_action(
                agent_id=requesting_agent_id,
                action="start_background_agent",
                resource_type="background_agent",
                complexity=3  # HIGH - background execution control
            )

            if not check["allowed"]:
                logger.warning(f"Governance check failed for start_background_agent by agent {requesting_agent_id}: {check['reason']}")
                raise HTTPException(
                    status_code=403,
                    detail=f"Governance check failed: {check['reason']}"
                )
        finally:
            db.close()

    from core.background_agent_runner import background_runner

    try:
        await background_runner.start_agent(agent_id)
        logger.info(f"Background agent started: {agent_id} by {requesting_agent_id or 'system'}")
        return {"status": "started", "agent_id": agent_id}
    except ValueError as e:
        raise HTTPException(status_code=404, detail=str(e))

@router.post("/{agent_id}/stop")
async def stop_background_agent(agent_id: str):
    """Stop periodic execution of an agent"""
    from core.background_agent_runner import background_runner
    
    await background_runner.stop_agent(agent_id)
    return {"status": "stopped", "agent_id": agent_id}

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

