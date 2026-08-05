"""Workspace-scoped curated context + skill assignment (Phase P8, Cloudflare G8).

Admin-only routes to manage per-workspace curated knowledge that pre-loads
into that workspace's agents, and to assign/unassign skills to a workspace.

Conventions:
* Curated context lives in ``Workspace.metadata_json["curated_context"]`` as a
  ``list[str]`` of curated context blobs (no dedicated column).
* Skill assignment is stored in the ``workspace_skills`` association table
  (many-to-many between Workspace and Skill).
"""
import logging
from typing import List

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.admin_endpoints import get_super_admin
from core.database import get_db
from core.models import Skill, User, Workspace, workspace_skills

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/workspaces", tags=["Workspace Context"])


class CuratedContextUpdate(BaseModel):
    curated_context: List[str] = []


def _assigned_skill_names(db: Session, workspace_id: str) -> List[str]:
    """Names of the skills assigned to ``workspace_id`` (sorted, unique)."""
    rows = (
        db.query(Skill.name)
        .join(workspace_skills, workspace_skills.c.skill_id == Skill.id)
        .filter(workspace_skills.c.workspace_id == workspace_id)
        .all()
    )
    return sorted({row[0] for row in rows if row[0]})


def _get_workspace_or_404(db: Session, workspace_id: str) -> Workspace:
    workspace = db.query(Workspace).filter(Workspace.id == workspace_id).first()
    if workspace is None:
        raise HTTPException(status_code=404, detail="Workspace not found")
    return workspace


@router.get("/{workspace_id}/context")
def get_workspace_context(
    workspace_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    """Return the workspace's curated context blobs + assigned skill names."""
    workspace = _get_workspace_or_404(db, workspace_id)
    meta = workspace.metadata_json or {}
    curated_context = meta.get("curated_context") or []
    if isinstance(curated_context, str):
        curated_context = [curated_context]
    curated_context = [c for c in curated_context if c]
    return {
        "success": True,
        "data": {
            "workspace_id": workspace.id,
            "curated_context": curated_context,
            "skill_names": _assigned_skill_names(db, workspace_id),
        },
        "message": "Workspace context retrieved",
    }


@router.put("/{workspace_id}/context")
def update_workspace_context(
    workspace_id: str,
    payload: CuratedContextUpdate,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    """Set the workspace's curated context blobs in ``metadata_json``."""
    workspace = _get_workspace_or_404(db, workspace_id)
    # Fresh dict copy so SQLAlchemy detects the change (mutating the loaded
    # dict in place + reassigning the same object is treated as unchanged).
    meta = dict(workspace.metadata_json or {})
    meta["curated_context"] = [c for c in payload.curated_context if c]
    workspace.metadata_json = meta
    db.add(workspace)
    db.commit()
    return {
        "success": True,
        "data": {
            "workspace_id": workspace.id,
            "curated_context": meta["curated_context"],
        },
        "message": "Workspace curated context updated",
    }


@router.post("/{workspace_id}/skills/{skill_id}")
def assign_skill_to_workspace(
    workspace_id: str,
    skill_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    """Assign a skill to the workspace (idempotent)."""
    _get_workspace_or_404(db, workspace_id)
    skill = db.query(Skill).filter(Skill.id == skill_id).first()
    if skill is None:
        raise HTTPException(status_code=404, detail="Skill not found")

    existing = (
        db.query(workspace_skills.c.skill_id)
        .filter(
            workspace_skills.c.workspace_id == workspace_id,
            workspace_skills.c.skill_id == skill_id,
        )
        .first()
    )
    if existing is None:
        db.execute(
            workspace_skills.insert().values(
                workspace_id=workspace_id, skill_id=skill_id
            )
        )
        db.commit()
    return {
        "success": True,
        "data": {"workspace_id": workspace_id, "skill_id": skill_id, "assigned": True},
        "message": "Skill assigned to workspace",
    }


@router.delete("/{workspace_id}/skills/{skill_id}")
def unassign_skill_from_workspace(
    workspace_id: str,
    skill_id: str,
    db: Session = Depends(get_db),
    admin: User = Depends(get_super_admin),
):
    """Unassign a skill from the workspace (idempotent)."""
    _get_workspace_or_404(db, workspace_id)
    db.execute(
        workspace_skills.delete().where(
            workspace_skills.c.workspace_id == workspace_id,
            workspace_skills.c.skill_id == skill_id,
        )
    )
    db.commit()
    return {
        "success": True,
        "data": {"workspace_id": workspace_id, "skill_id": skill_id, "assigned": False},
        "message": "Skill unassigned from workspace",
    }
