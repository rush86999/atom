from fastapi import APIRouter, Depends, HTTPException, BackgroundTasks
from sqlalchemy.orm import Session
from core.database import get_db
from core.agent_evolution_loop import AgentEvolutionLoop
from core.auth import get_current_user
from typing import Dict, Any, Optional, List

router = APIRouter(prefix="/evolution", tags=["Governance"])

@router.post("/run")
async def run_evolution(
    background_tasks: BackgroundTasks,
    tenant_id: str,
    target_agent_id: Optional[str] = None,
    group_size: int = 5,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Triggers a full GEA evolution cycle for a tenant.
    """
    loop = AgentEvolutionLoop(db)
    
    # Run in background to avoid timeout
    background_tasks.add_task(
        loop.run_evolution_cycle,
        tenant_id=tenant_id,
        group_size=group_size,
        target_agent_id=target_agent_id
    )
    
    return {
        "status": "started",
        "message": f"Evolution cycle started for tenant {tenant_id}",
        "tenant_id": tenant_id
    }

@router.get("/traces/{agent_id}")
async def get_evolution_traces(
    agent_id: str,
    db: Session = Depends(get_db),
    current_user = Depends(get_current_user)
):
    """
    Returns the evolution history (performance/novelty traces) for an agent.
    """
    from core.models import AgentEvolutionTrace
    traces = db.query(AgentEvolutionTrace).filter(
        AgentEvolutionTrace.agent_id == agent_id
    ).order_by(AgentEvolutionTrace.created_at.desc()).all()
    
    return [
        {
            "id": t.id,
            "generation": t.generation,
            "performance_score": t.performance_score,
            "novelty_score": t.novelty_score,
            "directives": t.evolving_requirements,
            "created_at": t.created_at
        }
        for t in traces
    ]
