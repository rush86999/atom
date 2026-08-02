"""
/learn endpoint — workflow→skill distillation (R72 Workstream B).

POST /api/v1/learn  {execution_id, skill_name?, description?}

Distills a completed agent execution into a reusable Python skill:
analyze → LLM-generate script → sandbox validate → write package →
register in the skill registry (discoverable/executable).
"""

import logging
from typing import Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_tenant, get_current_user, User
from core.auto_dev.memento_engine import MementoEngine
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import Tenant
from core.rbac_service import Permission
from core.security_dependencies import require_permission

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/v1", tags=["Learn"])


class LearnRequest(BaseModel):
    """Request to distill an agent execution into a skill."""
    execution_id: str = Field(
        ..., description="AgentExecution ID to distill into a skill"
    )
    skill_name: Optional[str] = Field(
        default=None, description="Optional skill name override"
    )
    description: Optional[str] = Field(
        default=None, description="Optional skill description"
    )


@router.post("/learn")
async def learn_from_execution(
    payload: LearnRequest,
    tenant: Tenant = Depends(get_current_tenant),
    user: User = Depends(require_permission(Permission.AGENT_MANAGE)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Distill a completed agent execution into a reusable Python skill."""
    try:
        engine = MementoEngine(db=db)
        result = await engine.learn_from_execution(
            tenant_id=str(tenant.id),
            agent_id=str(current_user.id) if current_user.id else None,
            execution_id=payload.execution_id,
            skill_name=payload.skill_name,
            description=payload.description,
        )
    except Exception as e:
        logger.error(f"Learn endpoint failed for execution {payload.execution_id}: {e}")
        raise HTTPException(status_code=500, detail="Skill distillation failed")

    if not result.get("success"):
        error = result.get("error", "Unknown error")
        if "not found" in str(error).lower():
            raise HTTPException(status_code=404, detail=error)
        logger.warning(
            f"Learn endpoint could not distill execution {payload.execution_id}: {error}"
        )
        raise HTTPException(status_code=422, detail=error)

    return router.success_response(
        data=result,
        message=f"Skill '{result.get('skill_name')}' distilled from execution "
                f"{payload.execution_id}",
    )
