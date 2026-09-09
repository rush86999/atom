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


@router.get("/pending")
async def list_pending_approvals(
    current_user: User = Depends(get_current_user),
):
    """
    Pending HITL actions as a plain array — the shape the Approvals page
    and chat widget have always expected.
    """
    return intervention_service.get_pending_interventions()


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
    action = db.query(HITLAction).filter(HITLAction.id == approval_id).first()
    if action:
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

    return {
        # `success` is the GlobalChatWidget's confirmation contract.
        "success": True,
        "approval_id": approval_id,
        "status": decision,
        "decided_by": user.id,
        "message": result.get("message"),
    }
