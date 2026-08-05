"""
Gatekeeper config routes — P3 (Cloudflare OS G3).

Admin surface to view and override per-service gatekeeper policy (rate limits,
masked fields, required scopes, actions requiring HITL approval). Backs the
``governance_middleware`` singleton's ``_config`` overrides.

Auth: ``Permission.SYSTEM_ADMIN`` (admin-only).
"""
from __future__ import annotations

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.database import get_db
from core.rbac_service import Permission
from core.security_dependencies import require_permission

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/gatekeeper", tags=["gatekeeper"])


class GatekeeperPolicyUpdate(BaseModel):
    """Override policy for a single service."""
    rate_limit: int | None = None
    masked_fields: list[str] | None = None
    required_scopes: list[str] | None = None
    require_approval_for: list[str] | None = None
    mutations: list[str] | None = None


@router.get("/config")
async def get_gatekeeper_config(
    user: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Return the current per-service gatekeeper policy overrides."""
    from middleware.governance_middleware import governance_middleware
    return {
        "success": True,
        "data": governance_middleware._config,
        "message": "Gatekeeper configuration retrieved",
    }


@router.put("/config/{service}")
async def update_gatekeeper_config(
    service: str,
    policy: GatekeeperPolicyUpdate,
    user: User = Depends(require_permission(Permission.SYSTEM_ADMIN)),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Set or replace the gatekeeper policy override for a service."""
    from middleware.governance_middleware import governance_middleware

    override: Dict[str, Any] = {}
    if policy.rate_limit is not None:
        override["rate_limit"] = policy.rate_limit
    if policy.masked_fields is not None:
        override["masked_fields"] = set(policy.masked_fields)
    if policy.required_scopes is not None:
        override["required_scopes"] = set(policy.required_scopes)
    if policy.require_approval_for is not None:
        override["require_approval_for"] = set(policy.require_approval_for)
    if policy.mutations is not None:
        override["mutations"] = set(policy.mutations)

    governance_middleware.configure(service, override)
    logger.info("Gatekeeper policy updated for %s by %s", service, current_user.id)
    return {
        "success": True,
        "data": {"service": service, "policy": {k: sorted(v) if isinstance(v, set) else v for k, v in override.items()}},
        "message": f"Gatekeeper policy updated for {service}",
    }
