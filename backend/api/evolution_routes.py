from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session
from core.database import get_db
from core.self_evolution_service import self_evolution_service
from core.auth import get_current_user
from typing import Dict, Any

router = APIRouter(prefix="/evolution", tags=["Governance"])

@router.get("/analyze/{agent_id}")
async def analyze_agent(agent_id: str, current_user = Depends(get_current_user)):
    """
    Triggers an analysis of agent performance.
    """
    insight = await self_evolution_service.analyze_agent_performance(agent_id)
    if "error" in insight:
        raise HTTPException(status_code=404, detail=insight["error"])
    return insight

@router.post("/tune/{agent_id}")
async def tune_agent(agent_id: str, insight: str, current_user = Depends(get_current_user)):
    """
    Applies auto-tuning to an agent.
    """
    await self_evolution_service.apply_auto_tune(agent_id, insight)
    return {"status": "success", "message": f"Agent {agent_id} tuned successfully."}
