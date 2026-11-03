"""Auto-Dev review routes — the supervisor surface for the evolution
harness (Memento skills + AlphaEvolver tool mutations).

Journey gap closed (2026-09-02): the harness now auto-proposes fixes when a
hire's tool errors repeat (ReflectionEngine → AlphaEvolver/Memento), and
tool-error signals accumulate on executions — but there was no API and no UI
to SEE pending candidates or tool-error patterns, let alone approve them.
Pending candidates without a review surface are exactly the "silent
auto-deploy" risk the capability gate exists to prevent.

Lifecycle honored:
  - SkillCandidate: pending → validated (approve) / rejected → promoted via
    the existing skill promote flow (api/skill_routes /promote).
  - ToolMutation: pending → approved / rejected (sandbox validation can run
    separately via AlphaEvolverEngine.sandbox_execute_mutation).
  - GET /tool-errors aggregates the structured tool_error entries recorded
    by the integration chokepoint, so a supervisor sees WHICH tool keeps
    failing for their hire before deciding on a candidate.
"""
import logging
from datetime import datetime, timezone
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException, status
from sqlalchemy.orm import Session

from core.auto_dev.models import SkillCandidate, ToolMutation
from core.auth import get_current_tenant, get_current_user
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.models import (
    AgentExecution,
    AgentFeedEvent,
    AgentRegistry,
    Tenant,
    User,
    UserRole,
)
from core.reviewed_improvement import (
    apply_reviewed_skill,
    review_binding,
    review_revision,
    review_revision_predicate,
)
from core.security.rbac import require_role, role_level

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/autodev", tags=["Auto-Dev Review"])


def _iso(dt: Any) -> Optional[str]:
    return dt.isoformat() if dt else None




def _candidate_agent(
    db: Session, tenant: Tenant, current_user: User, candidate: Any,
) -> AgentRegistry:
    """Authorize the candidate's CURRENT employee and return it.

    Tenant filtering alone is not workspace authority. TEAM_LEAD and
    WORKSPACE_ADMIN may only review/apply employees in their own workspace;
    ADMIN+ may operate across the tenant (explicit tenant-admin policy).
    """
    if candidate is None:
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND, detail="Candidate not found")
    if not candidate.agent_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate has no target employee")
    agent = db.query(AgentRegistry).filter(
        AgentRegistry.id == candidate.agent_id).first()
    if agent is None or str(agent.tenant_id) != str(tenant.id):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Candidate target employee not found")
    if role_level(getattr(current_user, "role", None)) < role_level(UserRole.ADMIN):
        if str(getattr(current_user, "workspace_id", "") or "") != str(
                agent.workspace_id or ""):
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail=(
                    "Reviewer workspace does not own this employee; "
                    "cross-workspace review is not permitted"))
    return agent

@router.get("/candidates")
async def list_candidates(
    agent_id: Optional[str] = None,
    status: str = "pending",
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(UserRole.TEAM_LEAD)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Pending Auto-Dev proposals for the reviewer's scope."""
    tenant_id = str(tenant.id)

    items: List[Dict[str, Any]] = []

    skill_q = db.query(SkillCandidate).filter(
        SkillCandidate.tenant_id == tenant_id,
        SkillCandidate.validation_status == status,
    )
    if agent_id:
        skill_q = skill_q.filter(SkillCandidate.agent_id == agent_id)
    if (role_level(getattr(current_user, "role", None))
            < role_level(UserRole.ADMIN)
            and getattr(current_user, "workspace_id", None)):
        skill_q = skill_q.join(
            AgentRegistry, AgentRegistry.id == SkillCandidate.agent_id,
        ).filter(
            AgentRegistry.workspace_id == str(current_user.workspace_id))
    for c in skill_q.order_by(SkillCandidate.created_at.desc()).limit(50):
        items.append({
            "kind": "skill",
            "id": str(c.id),
            "agent_id": str(c.agent_id) if c.agent_id else None,
            "name": c.skill_name,
            "description": c.skill_description or "",
            "failure": (c.failure_pattern or {}).get("failure_summary") or "",
            "code": (c.generated_code or "")[:2000],
            "status": c.validation_status,
            "created_at": _iso(c.created_at),
        })

    # Tool mutations are tenant-scoped (no agent_id column).
    mut_q = db.query(ToolMutation).filter(
        ToolMutation.tenant_id == tenant_id,
        ToolMutation.sandbox_status == status,
    )
    for m in mut_q.order_by(ToolMutation.created_at.desc()).limit(50):
        items.append({
            "kind": "mutation",
            "id": str(m.id),
            "agent_id": None,
            "name": m.tool_name,
            "description": f"Proposed fix for recurring tool failure in {m.tool_name}",
            "failure": (m.execution_error or "")[:300],
            "code": (m.mutated_code or "")[:2000],
            "status": m.sandbox_status,
            "created_at": _iso(m.created_at),
        })

    items.sort(key=lambda x: x["created_at"] or "", reverse=True)
    return router.success_response(data={"candidates": items, "count": len(items)})


@router.post("/skills/{candidate_id}/approve")
async def approve_skill_candidate(
    candidate_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(UserRole.TEAM_LEAD)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Reviewer approval binds the exact prompt material being reviewed.

    Approval does not apply anything. The binding is what ``apply`` later
    re-checks, so a material change after this point needs fresh review.
    """
    candidate = db.query(SkillCandidate).filter(
        SkillCandidate.id == candidate_id,
        SkillCandidate.tenant_id == str(tenant.id),
    ).populate_existing().first()
    agent = _candidate_agent(db, tenant, current_user, candidate)
    if candidate.validation_status in ("applying", "promoted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate is already being applied or promoted")
    revision = review_revision(candidate)
    review = review_binding(
        candidate, tenant_id=str(tenant.id),
        workspace_id=str(agent.workspace_id),
        agent_id=str(agent.id), reviewer_id=str(current_user.id),
        review_revision=revision + 1)
    updated = (
        db.query(SkillCandidate)
        .filter(
            SkillCandidate.id == candidate_id,
            SkillCandidate.tenant_id == str(tenant.id),
            SkillCandidate.validation_status.in_(["pending", "validated"]),
            review_revision_predicate(db, revision),
        )
        .update(
            {
                "validation_status": "validated",
                "validated_at": datetime.now(timezone.utc),
                "validation_result": {
                    **(candidate.validation_result or {}),
                    "review": review,
                },
            },
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=(
                "candidate changed while reviewing; reload and review the "
                "current snapshot"))
    db.commit()
    return router.success_response(
        data={
            "id": candidate_id,
            "status": "validated",
            "review_digest": review["digest"],
            "review_revision": review["review_revision"],
        },
        message=(
            "Skill candidate reviewed and validated; application is a "
            "separate explicit step"),
    )


@router.post("/skills/{candidate_id}/apply")
async def apply_skill_candidate(
    candidate_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(UserRole.TEAM_LEAD)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Explicitly apply a REVIEWED candidate as a typed prompt skill.

    Pending candidates are refused. Generated executable code is not applied;
    only the typed skill metadata/instructions are written and registered.
    """
    candidate = db.query(SkillCandidate).filter(
        SkillCandidate.id == candidate_id,
        SkillCandidate.tenant_id == str(tenant.id),
    ).first()
    agent = _candidate_agent(db, tenant, current_user, candidate)
    workspace_id = str(agent.workspace_id or "")
    if not workspace_id:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="target employee has no workspace")
    try:
        result = await apply_reviewed_skill(
            db, candidate, tenant_id=str(tenant.id),
            workspace_id=workspace_id)
    except ValueError as exc:
        message = str(exc)
        if message.startswith("workspace_mismatch"):
            code = status.HTTP_403_FORBIDDEN
        elif message.startswith(
                ("candidate_not_reviewed", "stale_review",
                 "candidate_state_conflict", "package_conflict")):
            code = status.HTTP_409_CONFLICT
        else:
            code = status.HTTP_400_BAD_REQUEST
        raise HTTPException(status_code=code, detail=message) from exc
    return router.success_response(
        data=result,
        message=(
            "Reviewed skill applied as a typed prompt skill"
            if not result.get("already_applied")
            else "Reviewed skill was already applied"),
    )


@router.post("/skills/{candidate_id}/reject")
async def reject_skill_candidate(
    candidate_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(require_role(UserRole.TEAM_LEAD)),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    candidate = db.query(SkillCandidate).filter(
        SkillCandidate.id == candidate_id,
        SkillCandidate.tenant_id == str(tenant.id),
    ).populate_existing().first()
    _candidate_agent(db, tenant, current_user, candidate)
    if candidate.validation_status in ("applying", "promoted"):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate is already being applied or promoted")
    updated = (
        db.query(SkillCandidate)
        .filter(
            SkillCandidate.id == candidate_id,
            SkillCandidate.tenant_id == str(tenant.id),
            SkillCandidate.validation_status.in_(["pending", "validated"]),
            review_revision_predicate(db, review_revision(candidate)),
        )
        .update(
            {"validation_status": "rejected"},
            synchronize_session=False,
        )
    )
    if updated != 1:
        db.rollback()
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="candidate changed while rejecting; reload")
    db.commit()
    return router.success_response(
        data={"id": candidate_id, "status": "rejected"},
        message="Skill candidate rejected",
    )


@router.post("/mutations/{mutation_id}/approve")
async def approve_tool_mutation(
    mutation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    mutation = db.query(ToolMutation).filter(
        ToolMutation.id == mutation_id,
        ToolMutation.tenant_id == str(tenant.id),
    ).first()
    if mutation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mutation not found")
    mutation.sandbox_status = "approved"
    db.commit()
    return router.success_response(
        data={"id": mutation_id, "status": "approved"},
        message="Tool mutation approved",
    )


@router.post("/mutations/{mutation_id}/reject")
async def reject_tool_mutation(
    mutation_id: str,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    mutation = db.query(ToolMutation).filter(
        ToolMutation.id == mutation_id,
        ToolMutation.tenant_id == str(tenant.id),
    ).first()
    if mutation is None:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="Mutation not found")
    mutation.sandbox_status = "rejected"
    db.commit()
    return router.success_response(
        data={"id": mutation_id, "status": "rejected"},
        message="Tool mutation rejected",
    )


@router.get("/guidance")
async def list_guidance(
    limit: int = 10,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Latest Auto-Dev guidance for the tenant: tool-error patterns and
    pending-fix proposals (the durable copy of the websocket pings)."""
    from core.auto_dev.guidance import EVENT_TYPE

    events = (
        db.query(AgentFeedEvent)
        .filter(
            AgentFeedEvent.tenant_id == str(tenant.id),
            AgentFeedEvent.event_type == EVENT_TYPE,
        )
        .order_by(AgentFeedEvent.timestamp.desc())
        .limit(max(1, min(limit, 50)))
        .all()
    )
    items = [
        {
            "id": str(e.id),
            "agent_id": str(e.agent_id),
            "kind": ((e.data or {}).get("kind") or "info"),
            "title": e.message,
            "detail": ((e.data or {}).get("detail") or ""),
            "importance": e.importance,
            "timestamp": _iso(e.timestamp),
        }
        for e in events
    ]
    return router.success_response(data={"guidance": items, "count": len(items)})


@router.get("/tool-errors")
async def list_tool_errors(
    agent_id: str,
    limit: int = 20,
    tenant: Tenant = Depends(get_current_tenant),
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Recent tool-error patterns for one agent — aggregated from the
    structured entries the integration chokepoint records on executions.
    This is what tells a supervisor WHICH tool keeps failing before they
    review a proposed fix."""
    executions = (
        db.query(AgentExecution)
        .filter(AgentExecution.agent_id == agent_id)
        .order_by(AgentExecution.started_at.desc())
        .limit(max(1, min(limit, 100)))
        .all()
    )
    agg: Dict[str, Dict[str, Any]] = {}
    for ex in executions:
        for err in (ex.metadata_json or {}).get("tool_errors") or []:
            if not isinstance(err, dict):
                continue
            sig = str(err.get("signature") or f"{err.get('service')}.{err.get('action')}")
            entry = agg.setdefault(
                sig,
                {"signature": sig, "count": 0, "last_error": "", "last_seen": ""},
            )
            entry["count"] += 1
            if entry["last_seen"] < str(err.get("at") or ""):
                entry["last_seen"] = str(err.get("at") or "")
                entry["last_error"] = str(err.get("error") or "")[:300]

    items = sorted(agg.values(), key=lambda x: (x["count"], x["last_seen"]), reverse=True)
    return router.success_response(data={"tool_errors": items, "count": len(items)})

