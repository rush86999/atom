"""Installation profile + trust-ramp report (Installation Adaptation Plan
Phases 1 & 5). The profile is per-install knowledge as data: identity,
people/roles, templates, and the facts registry the grounded-send gate
checks against. Tenant-scoped by the caller's account — a tenant can only
ever read/write its own row.
"""
from __future__ import annotations

from typing import Any, Dict, List, Optional

from fastapi import Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.personal_scope import resolve_tenant_id

router = BaseAPIRouter(prefix="/api/installation", tags=["installation"])


class FactEntry(BaseModel):
    claim: str
    source: str = ""
    verified: bool = True
    notes: Optional[str] = None


class PersonEntry(BaseModel):
    name: str
    role: str = ""
    email: Optional[str] = None
    notes: Optional[str] = None


class TemplateEntry(BaseModel):
    name: str
    description: str = ""
    questions: List[str] = Field(default_factory=list)
    notes: Optional[str] = None


class IdentitySection(BaseModel):
    company_name: Optional[str] = None
    sender_name: Optional[str] = None
    sender_email: Optional[str] = None
    reply_to: Optional[str] = None
    tone_notes: Optional[str] = None


class ProfilePayload(BaseModel):
    identity: Optional[IdentitySection] = None
    people: Optional[List[PersonEntry]] = None
    templates: Optional[List[TemplateEntry]] = None
    facts: Optional[List[FactEntry]] = None


@router.get("/profile")
async def get_profile(
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """The tenant's installation profile (created empty on first read)."""
    from core.installation_profile_service import InstallationProfileService

    tenant_id = resolve_tenant_id(current_user)
    return InstallationProfileService(db).get_payload(tenant_id)


@router.put("/profile")
async def update_profile(
    payload: ProfilePayload,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Merge-write the profile: sections present replace, absent sections
    are preserved (partial wizard steps can't wipe earlier entries)."""
    from core.installation_profile_service import InstallationProfileService

    tenant_id = resolve_tenant_id(current_user)
    workspace_id = getattr(current_user, "workspace_id", None) or "default"
    data: Dict[str, Any] = payload.model_dump(exclude_none=True)
    updated = InstallationProfileService(db).update_payload(
        tenant_id, data, workspace_id=workspace_id)
    return {"success": True, "profile": updated}


@router.get("/report")
async def installation_report(
    window_days: int = 30,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Trust-ramp metrics for the install (correction density, failure
    taxonomy, repeated-feedback rate, playbook pipeline, eval summary)."""
    from core.installation_metrics import report as metrics_report

    tenant_id = resolve_tenant_id(current_user)
    return metrics_report(db, tenant_id=tenant_id, window_days=window_days)
