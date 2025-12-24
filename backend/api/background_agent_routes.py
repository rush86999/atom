"""
Background Agent API Routes - Phase 35
"""

from fastapi import APIRouter, HTTPException
from typing import Dict, Any, Optional
from pydantic import BaseModel
import logging

logger = logging.getLogger(__name__)

router = APIRouter()

class RegisterAgentRequest(BaseModel):
    interval_seconds: int = 3600

@router.post("/{agent_id}/register")
async def register_background_agent(agent_id: str, request: RegisterAgentRequest):
    """Register an agent for background execution"""
    from core.background_agent_runner import background_runner
    
    background_runner.register_agent(agent_id, request.interval_seconds)
    return {"status": "registered", "agent_id": agent_id, "interval": request.interval_seconds}

@router.post("/{agent_id}/start")
async def start_background_agent(agent_id: str):
    """Start periodic execution of an agent"""
    from core.background_agent_runner import background_runner
    
    try:
        await background_runner.start_agent(agent_id)
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
    from core.background_agent_runner import background_runner
    return background_runner.get_status()

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
