from datetime import datetime
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import AgentRegistry, HITLAction, HITLActionStatus, User

logger = logging.getLogger(__name__)


def _refusal(
    message: str, error_code: str, http_status: int,
    action_id: Optional[str] = None,
) -> Dict[str, Any]:
    """One refusal shape for every intervention decision surface.

    ``success: False`` keeps the historical service contract; the explicit
    HTTP status/code lets governance/approval routes answer 401/403/404/409
    instead of flattening a scope denial into a generic 400 or a 500.
    """
    result: Dict[str, Any] = {
        "success": False,
        "message": message,
        "error_code": error_code,
        "http_status": int(http_status),
    }
    if action_id:
        result["action_id"] = action_id
    return result


class InterventionService:
    """
    Service for managing Human-in-the-Loop (HITL) interventions.
    Handles creation, retrieval, and resolution of HITL actions.
    """
    
    async def request_intervention(
        self,
        workspace_id: str,
        action_type: str,
        platform: str,
        params: Dict[str, Any],
        reason: str,
        agent_id: Optional[str] = None,
        user_id: Optional[str] = None,
        required_role: Optional[str] = None,
        tenant_id: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Create a new HITL action request in the database.

        ``required_role`` (from governance config ``roles`` map) is persisted
        in ``context_snapshot`` so the approval surface can enforce it; the
        kwarg was already being passed by mcp_service._check_hitl_policy —
        before it existed here every governed intercept raised TypeError and
        failed closed into "policy check unavailable".
        """
        try:
            with get_db_session() as db:
                hitl_action = HITLAction(
                    workspace_id=workspace_id,
                    tenant_id=tenant_id,
                    agent_id=agent_id,
                    user_id=user_id,
                    action_type=action_type,
                    platform=platform,
                    params=params, # SQLAlchemy JSON type handles dict
                    reason=reason,
                    context_snapshot={"required_role": required_role} if required_role else None,
                    status=HITLActionStatus.PENDING.value
                )
                db.add(hitl_action)
                db.commit()
                db.refresh(hitl_action)
                
                logger.info(f"Created HITL action {hitl_action.id} for agent {agent_id}")
                
                return {
                    "status": "PAUSED",
                    "action_id": hitl_action.id,
                    "message": f"Action paused for human review: {reason}",
                    "requires_approval": True
                }
        except Exception as e:
            logger.error(f"Failed to request intervention: {e}")
            return {
                "status": "ERROR",
                "message": f"Failed to persist intervention request: {str(e)}"
            }

    def get_pending_interventions(
        self,
        workspace_id: str = None,
        user_id: str = None,
        tenant_id: str = None,
        include_legacy_unscoped: bool = False,
    ) -> List[Dict[str, Any]]:
        """
        Get pending interventions, optionally filtered by workspace or user
        ownership.

        Resource scoping is applied whenever a workspace/tenant is supplied —
        including the literal ``"default"`` workspace. The previous
        ``workspace_id != "default"`` exception made the default workspace a
        cross-workspace read, which is exactly how a guessed approval id could
        leak or approve another assignment. Legacy rows with no workspace are
        included only when the caller explicitly asks for them.
        """
        with get_db_session() as db:
            query = db.query(HITLAction).filter(
                HITLAction.status == HITLActionStatus.PENDING.value)

            if workspace_id:
                if include_legacy_unscoped:
                    from sqlalchemy import or_
                    query = query.filter(or_(
                        HITLAction.workspace_id == workspace_id,
                        HITLAction.workspace_id.is_(None),
                    ))
                else:
                    query = query.filter(
                        HITLAction.workspace_id == workspace_id)
            if tenant_id:
                query = query.filter(HITLAction.tenant_id == tenant_id)
            if user_id:
                query = query.filter(HITLAction.user_id == user_id)

            actions = query.all()
            
            results = []
            for action in actions:
                agent_name = "Unknown Agent"
                if action.agent_id:
                    agent = db.query(AgentRegistry).filter(AgentRegistry.id == action.agent_id).first()
                    if agent:
                        agent_name = agent.name
                
                results.append({
                    "id": action.id,
                    "agent_id": action.agent_id,
                    "agent_name": agent_name,
                    "user_id": action.user_id,
                    "action_type": action.action_type,
                    "platform": action.platform,
                    "params": action.params,
                    "reason": action.reason,
                    "created_at": action.created_at.isoformat(),
                    "status": action.status
                })
            return results

    async def approve_intervention(
        self,
        action_id: str,
        approver_id: str,
        modified_params: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending intervention.

        Enforces the per-action ``required_role`` persisted by
        ``request_intervention`` (from the governance config ``roles`` map):
        the approver must hold at least that role. Unknown role strings fail
        closed. ``modified_params`` replaces the action's params so the row
        reflects what was actually approved (the UI "Modify before approve"
        flow).
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}

            if action.status != HITLActionStatus.PENDING.value:
                return {
                    "success": False,
                    "message": f"Action is {action.status}, cannot approve.",
                }

            # A never-autonomous TASK admission is a human admission for ONE
            # exact task execution. Its status is not authority: the current
            # reviewer must be verified (exact canonical scope, persisted
            # owner or supervisor, BOTH required_role locations) and the
            # server-owned task/rule binding must be immutable. This runs
            # BEFORE any status write, so governance/bridge callers cannot be
            # the weak surface. The same reviewer fence and the atomic
            # pending-state/binding claim are re-checked in the write below.
            is_task_admission = (
                str(action.action_type or "") == "never_autonomous_task")
            if is_task_admission:
                from core.review_decision_authority import (
                    authorize_task_admission_decision,
                    claim_task_admission_reviewer,
                )

                check = authorize_task_admission_decision(
                    db, action, approver_id,
                    modified_params=modified_params)
                if not check.get("ok"):
                    return _refusal(
                        check["message"], check["error_code"],
                        check["http_status"], action.id)
                if not claim_task_admission_reviewer(
                        db, check["authority"]):
                    db.rollback()
                    return _refusal(
                        "Reviewer authority changed; refresh and retry.",
                        "AUTHORITY_CHANGED", 409, action.id)

            # A goal-run checkpoint is not a status-only intervention: its
            # decision and the run wake are one atomic claim, bound to the
            # run's exact current wait. Governance/messaging callers reach
            # this service with arbitrary HITL ids, so this is the shared
            # guard that keeps them from committing an approved checkpoint
            # row without resuming (the original defect). Reviewer authority
            # (active user, exact scope, owner/supervisor, required_role) is
            # enforced inside the claim, so every checkpoint entry answers
            # the SAME refusal shape/status. Every other action_type keeps
            # the historical path below unchanged.
            if str(action.action_type or "") == "goal_run_checkpoint":
                if modified_params is not None:
                    return _refusal(
                        "A checkpoint's reviewed scope cannot be rewritten "
                        "during approval; refresh the run and decide the "
                        "current checkpoint.",
                        "CHECKPOINT_REVIEW_IMMUTABLE", 409, action.id)
                from core.hitl_resume import resolve_goal_run_checkpoint

                outcome = await resolve_goal_run_checkpoint(
                    action_id,
                    approved=True,
                    reviewer_id=approver_id,
                    db=db,
                )
                if not outcome.get("resumed"):
                    return _refusal(
                        outcome.get("message") or (
                            "This checkpoint is no longer current; refresh "
                            "the run."),
                        str(outcome.get("error_code")
                            or "CHECKPOINT_STALE"),
                        int(outcome.get("http_status") or 409),
                        action.id,
                    )
                return {
                    "success": True,
                    "message": "Checkpoint approved",
                    "action_id": action.id,
                    "resumed": True,
                    "resume": outcome,
                }

            denial = self._required_role_denial(db, action, approver_id)
            if denial:
                return _refusal(
                    denial, "AUTHORITY_REQUIRED", 403, action.id)

            if is_task_admission:
                # Atomic pending-state + immutable binding + fresh-actor
                # claim. A peer that rejected/approved the row (or rewrote
                # its execution/task/rule/profile binding) after our load
                # makes this UPDATE miss; the stale approver never wins.
                from core.review_decision_authority import (
                    claim_task_admission_decision,
                )

                if not claim_task_admission_decision(
                        db, action,
                        status=HITLActionStatus.APPROVED.value,
                        reviewer_id=approver_id):
                    db.rollback()
                    return _refusal(
                        "This task admission was decided or its reviewed "
                        "task binding changed; refresh and retry.",
                        "TASK_ADMISSION_DECISION_CONFLICT", 409, action.id)
            else:
                if modified_params is not None:
                    action.params = modified_params

                # Update status
                action.status = HITLActionStatus.APPROVED.value
                action.reviewed_by = approver_id
                action.reviewed_at = datetime.now()

            db.commit()

            # In a real system, this would resume the suspended workflow/agent.
            # For now, we just mark it approved. The agent/workflow needs to poll or be triggered.

            return {
                "success": True,
                "message": "Action approved",
                "action_id": action.id
            }

    async def reject_intervention(self, action_id: str, approver_id: str, reason: str) -> Dict[str, Any]:
        """
        Reject a pending intervention.

        Enforces the same ``required_role`` gate as approval — rejection is
        also a governance decision.
        """
        with get_db_session() as db:
            action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
            if not action:
                return {"success": False, "message": "Action not found"}

            if action.status != HITLActionStatus.PENDING.value:
                return {
                    "success": False,
                    "message": f"Action is {action.status}, cannot reject.",
                }

            is_task_admission = (
                str(action.action_type or "") == "never_autonomous_task")
            if is_task_admission:
                from core.review_decision_authority import (
                    authorize_task_admission_decision,
                    claim_task_admission_reviewer,
                )

                check = authorize_task_admission_decision(
                    db, action, approver_id)
                if not check.get("ok"):
                    return _refusal(
                        check["message"], check["error_code"],
                        check["http_status"], action.id)
                if not claim_task_admission_reviewer(
                        db, check["authority"]):
                    db.rollback()
                    return _refusal(
                        "Reviewer authority changed; refresh and retry.",
                        "AUTHORITY_CHANGED", 409, action.id)

            if str(action.action_type or "") == "goal_run_checkpoint":
                from core.hitl_resume import resolve_goal_run_checkpoint

                outcome = await resolve_goal_run_checkpoint(
                    action_id,
                    approved=False,
                    reviewer_id=approver_id,
                    guidance=reason,
                    db=db,
                )
                if not outcome.get("resumed"):
                    return _refusal(
                        outcome.get("message") or (
                            "This checkpoint is no longer current; refresh "
                            "the run."),
                        str(outcome.get("error_code")
                            or "CHECKPOINT_STALE"),
                        int(outcome.get("http_status") or 409),
                        action.id,
                    )
                return {
                    "success": True,
                    "message": "Checkpoint rejected",
                    "action_id": action.id,
                    "resumed": True,
                    "resume": outcome,
                }

            denial = self._required_role_denial(db, action, approver_id)
            if denial:
                return _refusal(
                    denial, "AUTHORITY_REQUIRED", 403, action.id)

            if is_task_admission:
                from core.review_decision_authority import (
                    claim_task_admission_decision,
                )

                if not claim_task_admission_decision(
                        db, action,
                        status=HITLActionStatus.REJECTED.value,
                        reviewer_id=approver_id,
                        user_feedback=reason):
                    db.rollback()
                    return _refusal(
                        "This task admission was decided or its reviewed "
                        "task binding changed; refresh and retry.",
                        "TASK_ADMISSION_DECISION_CONFLICT", 409, action.id)
            else:
                action.status = HITLActionStatus.REJECTED.value
                action.reviewed_by = approver_id
                action.reviewed_at = datetime.now()
                action.user_feedback = reason

            db.commit()

            return {
                "success": True,
                "message": "Action rejected",
                "action_id": action.id
            }

    @staticmethod
    def _required_role_denial(db: Session, action: HITLAction, approver_id: str) -> Optional[str]:
        """
        Return a denial reason if ``approver_id`` may not decide ``action``,
        else None. The approver must be a verified (existing, ACTIVE) user;
        they must hold at least EVERY persisted ``required_role`` (HITLAction
        column + governance ``context_snapshot``). Unknown role strings deny
        (fail closed).
        """
        approver = db.query(User).filter(User.id == approver_id).first()
        if (
            not approver
            or not bool(getattr(approver, "is_active", True))
            or getattr(approver, "status", None) not in (None, "active")
        ):
            return "Approver could not be verified; decision denied (fail closed)"

        # ``request_intervention`` persists the governance policy in
        # ``context_snapshot``; the HITLAction column is the durable field
        # other writers set. Both are the same policy, so EVERY persisted
        # requirement is enforced (never only the column when the snapshot is
        # stricter) and an unknown role in either location denies.
        from core.security.rbac import (
            persisted_required_roles,
            required_role_denial,
        )

        return required_role_denial(
            getattr(approver, "role", None),
            persisted_required_roles(action),
        )

# Singleton instance
intervention_service = InterventionService()
