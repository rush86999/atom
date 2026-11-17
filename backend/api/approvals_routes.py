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

from fastapi import Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import get_current_user, User
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.intervention_service import (
    get_decision_history,
    intervention_service,
    list_recent_decisions,
)
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
    db: Session = Depends(get_db),
):
    """
    Pending HITL actions as a plain array — the shape the Approvals page
    and chat widget have always expected.

    Scoped to the CURRENT durable actor's exact canonical tenant/workspace
    (re-read inside the service). NULL/""/"default" is the one Personal/
    default scope, never a wildcard: a pending action from another named
    tenant/workspace must not be listable, and a guessed id must not be
    decidable. Storage failure is a 503, not an empty success.
    """
    result = intervention_service.get_pending_interventions_for_actor(
        actor_id=current_user.id, db=db)
    if not result.get("success"):
        raise HTTPException(
            status_code=int(result.get("http_status") or 503),
            detail={
                "error": {
                    "code": result.get("error_code")
                    or "PENDING_APPROVALS_UNAVAILABLE",
                    "message": result.get(
                        "message", "Pending approvals unavailable"),
                },
            },
        )
    return result.get("pending", [])


@router.get("/recent")
async def list_recent_approval_decisions(
    limit: int = Query(20, ge=1, le=100),
    current_user: User = Depends(get_current_user),
):
    """Bounded recent decisions the caller may audit (discoverability only).

    Nothing here trusts a client-supplied owner/scope/role: the caller is
    resolved from the database, and the service applies the same scope +
    supervisor/own-subject-or-reviewer policy as the per-decision history.
    No params or snapshots are returned — those are fetched lazily per row.
    """
    result = list_recent_decisions(current_user.id, limit=limit)
    if not result.get("success"):
        raise HTTPException(
            status_code=int(result.get("http_status") or 503),
            detail={
                "error": {
                    "code": result.get("error_code") or "HISTORY_UNAVAILABLE",
                    "message": result.get(
                        "message", "Decision history unavailable"),
                },
            },
        )
    return result.get("decisions", [])


@router.get("/{approval_id}/history")
async def get_approval_decision_history(
    approval_id: str,
    revision_limit: int = Query(10, ge=1, le=50),
    current_user: User = Depends(get_current_user),
):
    """Redacted reviewed-vs-approved parameter history for ONE decision.

    A foreign/guessed id is a 404 (never confirmed), an in-scope member who is
    neither the subject nor the reviewer is a 403, unavailable storage is a
    503 — never an empty success. This is an audit projection: it is not
    signed, does not certify the record, and does not claim execution
    happened or was verified.
    """
    result = get_decision_history(
        approval_id, current_user.id, revision_limit=revision_limit)
    if not result.get("success"):
        raise HTTPException(
            status_code=int(result.get("http_status") or 503),
            detail={
                "error": {
                    "code": result.get("error_code") or "HISTORY_UNAVAILABLE",
                    "message": result.get(
                        "message", "Decision history unavailable"),
                },
            },
        )
    return result["history"]


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

    # A never-autonomous task admission cannot be decided by a foreign or
    # unqualified reviewer, and its server-owned task/rule binding is
    # immutable through the edit-before-approve flow. The shared service
    # repeats this check and fences the current actor in its claim.
    if str(action.action_type or "") == "never_autonomous_task":
        from core.review_decision_authority import (
            authorize_task_admission_decision,
        )

        check = authorize_task_admission_decision(
            db, action, str(user.id),
            modified_params=body.modified_params)
        if not check.get("ok"):
            raise HTTPException(
                status_code=int(check["http_status"]),
                detail={
                    "error": {
                        "code": check["error_code"],
                        "message": check["message"],
                    },
                },
            )

    # Same preflight as the legacy approvals surface: validate the exact
    # reviewed goal decision before approve_intervention/reject_intervention
    # mutates the HITL row. Non-goal actions are unaffected.
    from core.hitl_resume import preflight_hitl_decision

    preflight = preflight_hitl_decision(
        approval_id, body.modified_params, action=action, db=db)
    if not preflight.get("valid", True):
        reason = preflight.get("reason") or "stale_decision_review"
        raise HTTPException(
            status_code=409,
            detail={
                "error": (
                    "decision_review_required"
                    if reason == "decision_review_required"
                    else "stale_decision_review"),
                "message": preflight.get("message") or (
                    "The pending decision changed after it was reviewed. "
                    "Refresh the run and review the current decision."),
                "reason": reason,
                "current_decision_id": preflight.get("current_decision_id"),
            },
        )

    # The owner-set absolute deadline is terminal and is enforced BEFORE the
    # status write/resume. A late approval cannot revive an expired wait.
    from core.information_wait import (
        expire_information_wait_if_due,
        is_information_wait_action,
    )

    if is_information_wait_action(action.action_type):
        expiry = expire_information_wait_if_due(action, db_session=db)
        if (
            expiry.get("expired")
            or str(action.status or "") == "expired"
        ):
            raise HTTPException(
                status_code=409,
                detail={
                    "success": False,
                    "error": {
                        "code": "INFORMATION_WAIT_EXPIRED",
                        "message": (
                            "The owner-set deadline for this job passed. No "
                            "decision was applied; review the deadline or "
                            "start a new authorized run."),
                    },
                    "deadline": expiry.get("deadline"),
                    "approval_id": approval_id,
                },
            )

    # A human checkpoint is a decision AND a wake over the run's exact current
    # wait. It must go through the shared atomic claim BEFORE any status
    # write: approve_intervention/reject_intervention commit the HITL row on
    # their own, which is exactly how a cancelled/stale checkpoint used to
    # become approved without resuming. Non-checkpoint actions keep the
    # existing path below unchanged.
    if str(action.action_type or "") == "goal_run_checkpoint":
        if body.modified_params:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": {
                        "code": "CHECKPOINT_REVIEW_IMMUTABLE",
                        "message": (
                            "A checkpoint's reviewed scope cannot be "
                            "rewritten during approval; refresh the run and "
                            "decide the current checkpoint."),
                    },
                },
            )
        from core.hitl_resume import resolve_goal_run_checkpoint

        guidance = (
            body.reason if decision == "approved"
            else (body.reason
                  or f"Rejected via approvals UI by {user.email}"))
        outcome = await resolve_goal_run_checkpoint(
            approval_id,
            approved=decision == "approved",
            reviewer_id=str(user.id),
            guidance=guidance,
            db=db,
        )
        if not outcome.get("resumed"):
            raise HTTPException(
                status_code=int(outcome.get("http_status") or 409),
                detail={
                    "error": {
                        "code": outcome.get("error_code")
                        or "CHECKPOINT_STALE",
                        "message": outcome.get("message") or (
                            "This checkpoint is no longer current; refresh "
                            "the run."),
                    },
                    "approval_id": approval_id,
                },
            )
        return {
            "success": True,
            "approval_id": approval_id,
            "status": decision,
            "decided_by": user.id,
            "message": (
                "Checkpoint approved" if decision == "approved"
                else "Checkpoint rejected"),
            "resume": outcome,
        }

    if decision == "approved":
        result = await intervention_service.approve_intervention(
            approval_id, user.id, modified_params=body.modified_params,
            reason=body.reason,
        )
    else:
        result = await intervention_service.reject_intervention(
            approval_id, user.id, body.reason or f"Rejected via approvals UI by {user.email}"
        )

    if not result.get("success"):
        if result.get("error_code") or result.get("http_status"):
            raise HTTPException(
                status_code=int(result.get("http_status") or 400),
                detail={
                    "error": {
                        "code": result.get("error_code") or "DECISION_FAILED",
                        "message": result.get(
                            "message", "Decision failed"),
                    },
                },
            )
        raise HTTPException(
            status_code=400,
            detail=result.get("message", "Decision failed"))

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
