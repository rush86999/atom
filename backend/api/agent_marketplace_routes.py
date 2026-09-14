"""Agent marketplace × goal runs (docs/architecture/
AGENT_MARKETPLACE_GOAL_RUNS.md).

Selling an agent sells its VERIFIED goal-run track record. These routes
cover the seller side: packaging a trained agent into a listing
(``package_agent_for_sale``), the advisory readiness view, pushing a
packaged listing to the central SaaS marketplace, and the buyer-side
install from a central listing (``AgentMarketplaceService.install_agent``
— SaaS fetch + local fallback), which seeds evidence-honest confidence
and materializes the publisher's playbooks.

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
from core.personal_scope import resolve_tenant_id
from core.security.rbac import user_meets_role

router = BaseAPIRouter(prefix="/api/agent-marketplace", tags=["Agent Marketplace"])

logger = logging.getLogger(__name__)


class PublishBody(BaseModel):
    price: float = 0.0
    description: str = ""


class InstallRemoteBody(BaseModel):
    template_id: str
    # Paid listings only: asserts the purchase was completed with the
    # seller (the SaaS gates remote installs server-side via entitlements;
    # local paid listings have only this explicit override).
    paid_override: bool = False


def _service(db: Session):
    from core.agent_marketplace_service import AgentMarketplaceService
    return AgentMarketplaceService(db)


def _require_agent_owner_or_admin(db: Session, current_user: User,
                                  agent) -> None:
    """Owner-or-admin guard shared by the seller-facing routes (publish,
    sale-readiness, push): the evidence a listing would carry is this
    workspace's agent persona + verified process — not every member's call
    to make, and not other workspaces' business either."""
    from core.models import User as UserModel, UserRole

    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise router.not_found_error("User", str(current_user.id))
    if (str(agent.user_id or "") != str(current_user.id)
            and not user_meets_role(user, UserRole.ADMIN)):
        raise HTTPException(
            status_code=403,
            detail="Only the agent's owner (or an admin) can publish it "
                   "for sale",
        )


@router.get("/agents/{agent_id}/sale-readiness")
async def agent_sale_readiness(
    agent_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Advisory pre-publish view: the evidence a listing would carry and
    what blocks a paid listing. Never blocks anything itself. Owner or
    admin (same guard as publish — the evidence view leaks the agent's
    full track record and guidance counts to whoever reads it)."""
    from core.models import AgentRegistry as Model

    agent = db.query(Model).filter(Model.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)
    _require_agent_owner_or_admin(db, current_user, agent)
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
    from core.models import AgentRegistry as Model

    agent = db.query(Model).filter(Model.id == agent_id).first()
    if not agent:
        raise router.not_found_error("Agent", agent_id)
    _require_agent_owner_or_admin(db, current_user, agent)
    result = _service(db).package_agent_for_sale(
        agent_id, price=payload.price,
        description=payload.description or None,
        author_id=str(current_user.id))
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("error"))
    return result


@router.post("/templates/{template_id}/push")
async def push_listing_to_saas(
    template_id: str,
    force: bool = False,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Push a locally packaged listing to the central SaaS marketplace
    (POST /agents/api/agent-marketplace/ingest-listing under federation
    auth — X-Instance-ID + X-Federation-Key from the client config). The
    listing lands PENDING SaaS admin approval. Publisher-of-the-listing or
    admin; idempotent by default — a listing already pushed returns its
    recorded push state unless force=true (the server inserts a new
    pending listing on every push)."""
    from core.models import AgentTemplate, User as UserModel, UserRole

    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise router.not_found_error("User", str(current_user.id))
    template = db.query(AgentTemplate).filter(
        AgentTemplate.id == template_id).first()
    if not template:
        raise router.not_found_error("AgentTemplate", template_id)
    # The listing's publisher (its author), or an admin. Legacy templates
    # without an author fall back to admin-only.
    if not (str(template.author_id or "") == str(current_user.id)
            or user_meets_role(user, UserRole.ADMIN)):
        raise HTTPException(
            status_code=403,
            detail="Only the listing's publisher (or an admin) can push it "
                   "to the marketplace",
        )
    result = _service(db).publish_listing_to_saas(template_id, force=force)
    if not result.get("success"):
        raise HTTPException(status_code=409, detail=result.get("error"))
    return result


@router.post("/install-remote")
async def install_remote_agent(
    payload: InstallRemoteBody,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Install an agent from a central marketplace listing (SaaS fetch
    with local-listing fallback) as a MANAGED agent — evidence-honest
    seeding + the publisher's playbooks. Member and up (viewers/guests
    cannot add agents); paid listings additionally require the explicit
    paid_override assertion."""
    from core.models import User as UserModel, UserRole

    user = db.query(UserModel).filter(UserModel.id == current_user.id).first()
    if not user:
        raise router.not_found_error("User", str(current_user.id))
    if not user_meets_role(user, UserRole.MEMBER):
        raise HTTPException(
            status_code=403,
            detail="Installing a marketplace agent requires at least the "
                   "member role",
        )
    result = _service(db).install_agent(
        payload.template_id,
        tenant_id=resolve_tenant_id(current_user),
        user_id=str(current_user.id),
        paid_override=payload.paid_override)
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
