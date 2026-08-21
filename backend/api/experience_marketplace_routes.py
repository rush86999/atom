"""Experience Marketplace API Routes.

Export / import of signed, sanitized agent lesson packs
(docs/architecture/EXPERIENCE_MARKETPLACE.md), plus agent reputation cards.

Gates: export = CRITICAL (exfiltration surface), import = HIGH; both audited
(ExperienceExport / ExperienceImport rows).
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, Query, Request
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.api_governance import ActionComplexity, require_governance
from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.experience_marketplace import (
    ExperiencePackService,
    PackError,
    experience_marketplace_enabled,
)
from core.models import ExperienceImport

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/experience-marketplace", tags=["Experience Marketplace"])


def _require_experience_marketplace():
    if not experience_marketplace_enabled():
        raise router.permission_denied_error(
            "experience marketplace",
            details={"reason": "ATOM_EXPERIENCE_MARKETPLACE_ENABLED is false"},
        )


def _workspace_id(request: Request) -> str:
    from core.personal_scope import resolve_workspace_id

    workspace_id = resolve_workspace_id(getattr(request, "state", None))
    return str(workspace_id or "default")


class ExportExperienceRequest(BaseModel):
    agent_id: str
    sensitivity_ceiling: str = "internal"
    destination: Optional[str] = None
    include: Optional[List[str]] = None
    since: Optional[str] = None  # cursor (ISO timestamp), for delta exports


class ImportExperienceRequest(BaseModel):
    pack: Dict[str, Any]


@router.get("/status")
def experience_marketplace_status(
    request: Request,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Feature status + last import audit rows (due-diligence surface)."""
    _require_experience_marketplace()
    workspace_id = _workspace_id(request)
    try:
        from core.org_sharing_crypto import fingerprint, public_key_b64, get_or_create_private_key

        fingerprint_value = fingerprint(public_key_b64(get_or_create_private_key()))
    except Exception:
        fingerprint_value = None
    cursor = {}
    try:
        from core.experience_marketplace.pack_service import _read_cursor

        cursor = _read_cursor(db, workspace_id)
    except Exception:
        cursor = {}
    last_imports = (
        db.query(ExperienceImport)
        .filter(ExperienceImport.workspace_id == workspace_id)
        .order_by(ExperienceImport.created_at.desc())
        .limit(5)
        .all()
    )
    return {
        "success": True,
        "data": {
            "enabled": True,
            "public_key_fingerprint": fingerprint_value,
            "cursor": cursor,
            "last_imports": [
                {
                    "source_agent_id": row.source_agent_id,
                    "signature_valid": row.signature_valid,
                    "item_applied": row.item_applied,
                    "item_excluded": row.item_excluded,
                    "failure_reason": row.failure_reason,
                    "created_at": row.created_at,
                }
                for row in last_imports
            ],
        },
        "message": "Experience Marketplace status",
        "timestamp": None,
    }


@router.post("/pack/export")
@require_governance(ActionComplexity.CRITICAL, "export_experience_pack", feature="experience_marketplace")
def export_experience_pack(
    request: Request,
    body: ExportExperienceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Sign + audit a sanitized experience pack for an agent."""
    _require_experience_marketplace()
    workspace_id = _workspace_id(request)
    try:
        envelope = ExperiencePackService().export_pack(
            db,
            workspace_id=workspace_id,
            agent_id=body.agent_id,
            sensitivity_ceiling=body.sensitivity_ceiling,
            destination=body.destination,
            include=body.include,
            since=body.since,
            tenant_id=getattr(current_user, "tenant_id", None),
            performed_by=getattr(current_user, "email", None),
        )
    except PackError as e:
        logger.info(f"Experience pack export refused: {e}")
        raise HTTPException(status_code=400, detail="Experience pack export refused")
    return {
        "success": True,
        "data": envelope,
        "message": "Experience pack exported (signed)",
        "timestamp": None,
    }


@router.post("/pack/import")
@require_governance(ActionComplexity.HIGH, "import_experience_pack", feature="experience_marketplace")
async def import_experience_pack(
    request: Request,
    body: ImportExperienceRequest,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Verify + idempotently apply a signed experience pack."""
    _require_experience_marketplace()
    workspace_id = _workspace_id(request)
    try:
        result = await ExperiencePackService().import_pack(
            db,
            envelope=body.pack,
            workspace_id=workspace_id,
            tenant_id=getattr(current_user, "tenant_id", None),
            performed_by=getattr(current_user, "email", None),
        )
    except PackError as e:
        logger.info(f"Experience pack import refused: {e}")
        raise HTTPException(status_code=400, detail="Experience pack import refused")
    return {
        "success": True,
        "data": result,
        "message": "Experience pack applied",
        "timestamp": None,
    }


@router.get("/reputation/{agent_id}")
def agent_reputation(
    request: Request,
    agent_id: str,
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reputation card for one agent (verified-evidence due diligence)."""
    _require_experience_marketplace()
    workspace_id = _workspace_id(request)
    try:
        card = ExperiencePackService().reputation_for_agent(db, workspace_id, agent_id)
    except PackError as e:
        raise HTTPException(status_code=404, detail="Agent not found")
    return {
        "success": True,
        "data": card,
        "message": "Agent reputation",
        "timestamp": None,
    }


@router.get("/reputation")
def reputations_list(
    request: Request,
    limit: int = Query(50, ge=1, le=200),
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user),
):
    """Reputation cards for all agents with episodes in this workspace."""
    _require_experience_marketplace()
    workspace_id = _workspace_id(request)
    cards = ExperiencePackService().list_reputations(db, workspace_id, limit=limit)
    return {
        "success": True,
        "data": {"cards": cards},
        "message": "Agent reputations",
        "timestamp": None,
    }