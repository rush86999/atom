"""
HITL Approvals — the surface the web UI actually calls.

The Approvals page (`pages/approvals.tsx`) and the GlobalChatWidget drive
decisions through ``GET /api/agents/approvals/pending`` (plain JSON array)
and ``POST /api/agents/approvals/{action_id}`` with
``{"decision": "approved"|"rejected", "modified_params": {...}}``. That
surface never existed on the backend — the only real endpoints lived under
``/api/agent-governance/*`` with a wrapped envelope and split
approve/reject paths — so the whole UI approval journey 404'd end to end
while the comment in main_api_app claimed it was live.

This module implements the UI contract on top of the same
InterventionService (role gates: supervisor band TEAM_LEAD+ at the route,
per-action ``required_role`` enforced inside the service).

2026-09-08 role-journey pass.
"""

import logging
from typing import Any, Dict, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.intervention_service import intervention_service
from core.models import HITLAction, UserRole
from core.security.rbac import user_meets_role

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/agents/approvals", tags=["HITL Approvals"])


class ApprovalDecision(BaseModel):
    decision: str  # "approved" | "rejected"
    modified_params: Optional[Dict[str, Any]] = None
    reason: Optional[str] = None


_ASSIGNMENT_BINDING_KEYS = (
    "run_id", "step_id", "operation_id", "payload_sha256",
    "artifact_revision", "authorization_revision",
)


def _validate_assignment_approval_payload(
    action: HITLAction, modified_params: Optional[Dict[str, Any]],
) -> None:
    """An approval of one effect must not silently approve another.

    For an assignment approval, the bound identity/payload keys are
    immutable through the edit-before-approve flow. A changed recipient,
    body/artifact or authorization must go back through preparation and
    request a fresh approval rather than riding this row.
    """
    if action.action_type != "assignment_approval" or not modified_params:
        return
    original = dict(action.params or {})
    for key in _ASSIGNMENT_BINDING_KEYS:
        if key in modified_params and str(modified_params[key]) != str(
                original.get(key)):
            raise HTTPException(
                status_code=422,
                detail=(
                    f"Approval binding '{key}' cannot be changed through "
                    f"this decision; prepare and approve the new effect."),
            )


@router.get("/pending")
async def list_pending_approvals(
    current_user: User = Depends(get_current_user),
):
    """
    Pending HITL actions as a plain array — the shape the Approvals page
    and chat widget have always expected.

    Scoped to the authenticated user's workspace/tenant: a pending action
    from another workspace must not be listable, and a guessed id must not
    be decidable.
    """
    return intervention_service.get_pending_interventions(
        workspace_id=current_user.workspace_id,
        tenant_id=current_user.tenant_id,
    )


@router.post("/{approval_id}")
async def decide_approval(
    approval_id: str,
    body: ApprovalDecision,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """
    Approve or reject a pending HITL action.

    Route gate: supervisor band (team_lead+). Per-action ``required_role``
    (governance config) is enforced again inside the service — this route
    surfaces it as 403 so the UI shows a permission error rather than a
    generic failure.
    """
    user = db.query(User).filter(User.id == current_user.id).first()
    if not user:
        raise HTTPException(status_code=404, detail="User not found")
    if not user_meets_role(user, UserRole.TEAM_LEAD):
        raise HTTPException(
            status_code=403,
            detail="Insufficient permissions. Required role: team_lead or higher",
        )

    decision = body.decision.strip().lower()
    if decision not in ("approved", "rejected"):
        raise HTTPException(status_code=422, detail="decision must be 'approved' or 'rejected'")

    # Surface a per-action required_role denial as 403 (not a generic 400).
    # Scope the lookup to the authenticated workspace/tenant: an id from
    # another workspace must 404 before any role/ownership decision.
    action_query = db.query(HITLAction).filter(HITLAction.id == approval_id)
    if current_user.workspace_id:
        action_query = action_query.filter(
            HITLAction.workspace_id == current_user.workspace_id)
    if current_user.tenant_id:
        action_query = action_query.filter(
            HITLAction.tenant_id == current_user.tenant_id)
    action = action_query.first()
    if action is None:
        raise HTTPException(status_code=404, detail="Approval not found")
    _validate_assignment_approval_payload(action, body.modified_params)
    denial = intervention_service._required_role_denial(db, action, user.id)
    if denial:
        raise HTTPException(status_code=403, detail=denial)

    if decision == "approved":
        result = await intervention_service.approve_intervention(
            approval_id, user.id, modified_params=body.modified_params
        )
    else:
        result = await intervention_service.reject_intervention(
            approval_id, user.id, body.reason or f"Rejected via approvals UI by {user.email}"
        )

    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("message", "Decision failed"))

    # The status write alone leaves paused goal runs/workflows stuck; resume
    # the durable work the human just unblocked (shared with the legacy
    # /api/agents handler in api.agent_routes).
    try:
        from core.hitl_resume import resume_after_hitl_decision

        resume = await resume_after_hitl_decision(
            approval_id,
            approved=decision == "approved",
            reviewer_id=str(user.id),
            guidance=body.reason,
        )
    except Exception as resume_err:  # noqa: BLE001 — decision already committed
        logger.exception("HITL %s decided but resume failed: %s", approval_id, resume_err)
        resume = {"handled": True, "resumed": False, "error": str(resume_err)}

    return {
        # `success` is the GlobalChatWidget's confirmation contract.
        "success": True,
        "approval_id": approval_id,
        "status": decision,
        "decided_by": user.id,
        "message": result.get("message"),
        "resume": resume,
    }
