from datetime import datetime
import copy
import json
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.models import AgentRegistry, HITLAction, HITLActionStatus, User

logger = logging.getLogger(__name__)

# Durable approval receipt key inside the EXISTING ``HITLAction.context_snapshot``
# JSON column. No second table/registry: one append-only list keeps every
# reviewed proposal and the exact effective parameters the human approved.
HITL_PARAMETER_HISTORY_KEY = "parameter_history"


def _copy_json_value(value: Any) -> Any:
    """Deep-copy a JSON-ish HITL value so history can never alias live params."""
    return copy.deepcopy(value)


def _history_entries(action: Any) -> List[Dict[str, Any]]:
    snapshot = getattr(action, "context_snapshot", None)
    if not isinstance(snapshot, dict):
        return []
    entries = snapshot.get(HITL_PARAMETER_HISTORY_KEY)
    if isinstance(entries, dict):
        return [entries]
    if isinstance(entries, list):
        return [entry for entry in entries if isinstance(entry, dict)]
    return []


def record_approved_parameters(
    action: Any,
    *,
    reviewed_params: Any,
    approved_params: Any,
    actor_id: Optional[str],
    reason: Optional[str] = None,
    decided_at: Any = None,
) -> Optional[Dict[str, Any]]:
    """Append the review/approval parameter receipt to the HITL row.

    The original reviewed payload is copied BEFORE any caller assigns the
    effective payload to ``action.params``. Both values are deep-copied into
    ``context_snapshot[HITL_PARAMETER_HISTORY_KEY]``, which is the existing
    durable JSON history field on the row, and every previous entry is kept
    (append-only). The scan is deliberately narrow: this is the same protected
    authority row the approval itself writes, not a new audit payload.

    Returns the appended entry, or ``None`` when the existing snapshot is not
    a JSON object / cannot be copied. A malformed snapshot is left untouched:
    the approval still commits with the effective params, and the readback
    reports the original as unknown instead of inventing one.
    """
    snapshot = getattr(action, "context_snapshot", None)
    if snapshot is None:
        snapshot = {}
    if not isinstance(snapshot, dict):
        logger.error(
            "HITL %s parameter history not recorded: context_snapshot is %s",
            getattr(action, "id", None), type(snapshot).__name__)
        return None

    try:
        reviewed_copy = _copy_json_value(reviewed_params)
        approved_copy = _copy_json_value(approved_params)
    except Exception:  # noqa: BLE001 - never fake a receipt
        logger.exception(
            "HITL %s parameter history not recorded: params not copyable",
            getattr(action, "id", None))
        return None

    existing = snapshot.get(HITL_PARAMETER_HISTORY_KEY)
    if existing is None:
        entries: List[Dict[str, Any]] = []
    elif isinstance(existing, dict):
        entries = [existing]
    elif isinstance(existing, list):
        entries = [entry for entry in existing if isinstance(entry, dict)]
    else:
        logger.error(
            "HITL %s parameter history not recorded: %s is %s",
            getattr(action, "id", None), HITL_PARAMETER_HISTORY_KEY,
            type(existing).__name__)
        return None

    when = decided_at
    if when is None:
        when = getattr(action, "reviewed_at", None) or datetime.now()
    when_text = when.isoformat() if hasattr(when, "isoformat") else str(when)

    reason_text: Optional[str]
    if reason is None:
        reason_text = None
    else:
        reason_text = str(reason)
        if not reason_text.strip():
            reason_text = None

    entry = {
        "revision": len(entries) + 1,
        "reviewed_params": reviewed_copy,
        "approved_params": approved_copy,
        "modified": reviewed_copy != approved_copy,
        "modified_by": str(actor_id) if actor_id not in (None, "") else None,
        "modified_at": when_text,
        "reason": reason_text,
    }
    entries.append(entry)

    updated = dict(snapshot)
    updated[HITL_PARAMETER_HISTORY_KEY] = entries
    action.context_snapshot = updated
    return entry


def describe_parameter_history(
    action: Any, *, redact: bool = True,
) -> Dict[str, Any]:
    """Read back the review/approval parameter lineage for one HITL row.

    New approvals carry an append-only receipt. Historical rows approved
    before this receipt existed have NO recorded original: their
    ``original_params`` is ``None`` and ``original_known`` is ``False`` — the
    current ``params`` are reported as the effective payload, never passed off
    as the reviewed original.

    ``redact=True`` (default) applies the repo's existing
    ``core.blueprint_sanitizer.strip_credentials`` sanitizer to the projection
    so a general audit/export surface cannot dump credential-shaped keys. The
    raw values remain only in the protected HITL authority row; use
    ``redact=False`` only inside trusted server-side code.
    """
    entries = _history_entries(action)
    latest = entries[-1] if entries else None
    status = str(getattr(action, "status", "") or "")
    current_params = _copy_json_value(getattr(action, "params", None))

    if latest is not None:
        original = _copy_json_value(latest.get("reviewed_params"))
        effective = _copy_json_value(latest.get("approved_params"))
        original_known = (
            "reviewed_params" in latest
            and latest.get("reviewed_params") is not None)
        modified = latest.get("modified")
        if modified is None and original_known:
            modified = original != effective
        revision = latest.get("revision")
        modified_by = latest.get("modified_by")
        modified_at = latest.get("modified_at")
        reason = latest.get("reason")
        legacy_unrecorded = False
    elif status == HITLActionStatus.APPROVED.value:
        # The approval may have rewritten params before this receipt existed.
        # Do not reconstruct a reviewed original from the rewritten value.
        original = None
        effective = current_params
        original_known = False
        modified = None
        revision = None
        modified_by = None
        modified_at = None
        reason = None
        legacy_unrecorded = True
    else:
        # Pending/rejected rows never had a params rewrite path, so the
        # current payload is still the reviewed proposal. Effective params
        # exist only after an approval.
        original = current_params
        effective = None
        original_known = isinstance(current_params, dict)
        modified = None
        revision = None
        modified_by = None
        modified_at = None
        reason = None
        legacy_unrecorded = False

    reviewed_at = getattr(action, "reviewed_at", None)
    result: Dict[str, Any] = {
        "status": status,
        "original_known": bool(original_known),
        "original_params": original,
        "effective_params": effective,
        "modified": modified,
        "revision": revision,
        "modified_by": modified_by,
        "modified_at": modified_at,
        "reason": reason,
        "reviewed_by": str(getattr(action, "reviewed_by", None) or "") or None,
        "reviewed_at": (
            reviewed_at.isoformat()
            if hasattr(reviewed_at, "isoformat") else reviewed_at),
        "history_entries": len(entries),
        "legacy_unrecorded": legacy_unrecorded,
        "redacted": bool(redact),
    }
    if redact:
        # Existing repo sanitizer (P5 sharing surfaces); deep-copies and drops
        # credential-shaped KEYS. Never mutates the stored authority values.
        from core.blueprint_sanitizer import strip_credentials

        if result["original_params"] is not None:
            result["original_params"] = strip_credentials(
                result["original_params"])
        if result["effective_params"] is not None:
            result["effective_params"] = strip_credentials(
                result["effective_params"])
        if result["reason"]:
            # Free text: the existing text sanitizer redacts key/password/PII
            # patterns that a JSON key denylist cannot see.
            from core.secrets_redactor import redact_before_storage

            result["reason"] = redact_before_storage(str(result["reason"]))
    return result


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
        reason: Optional[str] = None,
    ) -> Dict[str, Any]:
        """
        Approve a pending intervention.

        Enforces the per-action ``required_role`` persisted by
        ``request_intervention`` (from the governance config ``roles`` map):
        the approver must hold at least that role. Unknown role strings fail
        closed. ``modified_params`` replaces the action's params so the row
        reflects what was actually approved (the UI "Modify before approve"
        flow).

        The exact reviewed (original) and approved (effective) payloads are
        appended to the row's existing ``context_snapshot`` history before the
        ``params`` column is rewritten. Execution therefore keeps consuming
        the effective payload, while an auditor can still read what the human
        was shown. ``reason`` is the approver's optional note; when absent it
        is recorded as unknown rather than invented.
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
                # Capture the reviewed proposal BEFORE the edit-before-approve
                # flow rewrites the live params column. The receipt below
                # stores this exact value (deep-copied) plus the effective
                # payload that execution will consume.
                reviewed_params = copy.deepcopy(action.params or {})
                if modified_params is not None:
                    action.params = modified_params

                # Update status
                action.status = HITLActionStatus.APPROVED.value
                action.reviewed_by = approver_id
                action.reviewed_at = datetime.now()
                record_approved_parameters(
                    action,
                    reviewed_params=reviewed_params,
                    approved_params=action.params,
                    actor_id=approver_id,
                    reason=reason,
                    decided_at=action.reviewed_at,
                )

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
