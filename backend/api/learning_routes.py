
from fastapi import Depends, Query
from sqlalchemy.orm import Session
from typing import Any, Dict, List, Optional

from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import User
from core.security_dependencies import get_current_user
from core.continuous_learning_service import ContinuousLearningService

router = BaseAPIRouter(prefix="/api/learning", tags=["continuous-learning"])

@router.get("/progress/{agent_id}")
async def get_agent_learning_progress(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get aggregate learning progress for a specific agent.
    Includes success rates and current tuned LLM parameters.
    """
    service = ContinuousLearningService(db)
    progress = service.get_learning_progress(
        tenant_id=current_user.tenant_id,
        agent_id=agent_id
    )
    
    if not progress:
        return router.not_found_response(f"Learning data for agent {agent_id} not found")
        
    return router.success_response(data=progress)

@router.get("/adaptations/{agent_id}")
async def get_learning_adaptations(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Generate AI adaptations based on recent feedback patterns.
    """
    service = ContinuousLearningService(db)
    adaptations = service.generate_adaptations(
        tenant_id=current_user.tenant_id,
        agent_id=agent_id
    )
    
    return router.success_response(data={"adaptations": adaptations})

@router.get("/tenant/summary")
async def get_tenant_learning_summary(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    """
    Get a summary of continuous learning progress across all agents for the tenant.
    """
    service = ContinuousLearningService(db)
    # get_learning_progress without agent_id returns tenant-wide summary
    summary = service.get_learning_progress(
        tenant_id=current_user.tenant_id
    )
    
    return router.success_response(data=summary)
