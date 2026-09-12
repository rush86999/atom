"""Agent marketplace × goal runs (docs/architecture/
AGENT_MARKETPLACE_GOAL_RUNS.md).

Selling an agent sells its VERIFIED goal-run track record. These routes
cover the seller side: packaging a trained agent into a listing
(``package_agent_for_sale``), the advisory readiness view, and the
buyer-safe listing read. Installation stays on
``AgentMarketplaceService.install_agent`` (SaaS fetch + local fallback),
which seeds evidence-honest confidence and materializes the publisher's
playbooks.

The listing read NEVER serves the manifest or memory bundle — the
managed-agent model keeps prompts/experience server-side
(core.marketplace_runtime resolves them at execution time); only the
platform-computed verified_record and aggregate guidance counts are
buyer-visible.
"""
from __future__ import annotations

import logging

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.security.rbac import user_meets_role

router = BaseAPIRouter(prefix="/api/agent-marketplace", tags=["Agent Marketplace"])

logger = logging.getLogger(__name__)


class PublishBody(BaseModel):
    price: float = 0.0
    description: str = ""


def _service(db: Session):
    from core.agent_marketplace_service import AgentMarketplaceService
    return AgentMarketplaceService(db)


@router.get("/agents/{agent_id}/sale-readiness")
async def agent_sale_readiness(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advisory pre-publish view: the evidence a listing would carry and
    what blocks a paid listing. Never blocks anything itself."""
    out = _service(db).sale_readiness(agent_id)
    if not out.get("success"):
        raise router.not_found_error("Agent", agent_id)
    return out


@router.post("/agents/{agent_id}/publish")
async def publish_agent_for_sale(
    agent_id: str,
    payload: PublishBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Package a trained agent into a marketplace listing. Owner or admin:
    publishing sells this workspace's agent persona + verified process —
    not every member's call to make."""
    from core.models import AgentRegistry as Model, User as UserModel, UserRole

    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise router.not_found_error("User", str(current_user.id))
    agent = db.query(Model).filter(Model.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)
    if (str(agent.user_id or "") != str(current_user.id)
            and not user_meets_role(user, UserRole.ADMIN)):
        raise HTTPException(
            status_code=403,
            detail="Only the agent's owner (or an admin) can publish it "
                   "for sale",
        )
    result = _service(db).package_agent_for_sale(
        agent_id, price=payload.price,
        description=payload.description or None,
        author_id=str(current_user.id))
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("error"))
    return result


@router.get("/templates/{template_id}")
async def template_listing(
    template_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Buyer-safe listing view: identity, price, ratings, the
    platform-computed verified_record, and aggregate guidance counts —
    never the manifest or memory bundle."""
    from core.models import AgentTemplate

    template = db.query(AgentTemplate).filter(
        AgentTemplate.id == template_id).first()
    if not template or not template.is_active:
        raise router.not_found_error("AgentTemplate", template_id)
    bundle = template.anonymized_memory_bundle or {}
    return {
        "id": template.id,
        "name": template.name,
        "description": template.description,
        "category": template.category,
        "version": template.version,
        "price": template.price,
        "rating": template.rating,
        "rating_count": template.rating_count,
        "installs": template.installs,
        "verified_record": template.verified_record,
        "guidance": {
            "golden_paths": len(bundle.get("golden_paths") or []),
            "heuristics": len(bundle.get("heuristics") or []),
            "playbooks": len((template.configuration or {}).get("playbooks") or []),
        },
    }
