"""Resume the work behind a decided HITL action.

Approval used to be a status write: the row flipped to APPROVED and the
paused goal run / workflow stayed paused forever ("For now, we just mark it
approved"). This module is the single bridge from a decision to the durable
work it unblocked, shared by both approval surfaces that exist today
(``/api/agents/approvals`` on api.agent_routes and the alias in
api.approvals_routes).

Failures here never roll back the human decision. They are logged and
returned so the caller can surface a warning; a retry is safe because the
goal-run service resolves by the wake spec / pending decision, not by the
HITL row's status.
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from core.models import HITLAction

logger = logging.getLogger(__name__)

_GOAL_RUN_ACTIONS = {"goal_run_decision", "goal_run_checkpoint"}
_ASSIGNMENT_ACTIONS = {"assignment_approval"}
_CHAT_OBLIGATION_ACTIONS = {"chat_request_obligation"}


def _load_action(action_id: str) -> Optional[Dict[str, Any]]:
    from core.database import get_db_session

    with get_db_session() as db:
        action = db.query(HITLAction).filter(HITLAction.id == action_id).first()
        if action is None:
            return None
        # Copy the small set of fields we need; the session closes below.
        return {
            "id": action.id,
            "workspace_id": action.workspace_id,
            "tenant_id": action.tenant_id,
            "action_type": action.action_type,
            "params": dict(action.params or {}),
            "reason": action.reason,
            "status": action.status,
        }


async def _resume_goal_run(action: Dict[str, Any], approved: bool,
                           reviewer_id: Optional[str],
                           guidance: Optional[str]) -> Dict[str, Any]:
    from core.goals.goal_run_service import GoalRunService

    params = action.get("params") or {}
    run_id = params.get("run_id")
    if not run_id:
        return {"handled": False, "reason": "goal-run action has no run_id"}

    svc = GoalRunService(
        workspace_id=action.get("workspace_id") or "default",
        tenant_id=action.get("tenant_id") or "default",
    )
    if action["action_type"] == "goal_run_checkpoint":
        step_id = params.get("step_id")
        wake = svc.consume_wake(run_id, {
            "event": "human_checkpoint",
            "hitl_id": action["id"],
            "approved": approved,
        })
        if not wake.get("consumed"):
            return {"handled": True, "resumed": False,
                    "reason": wake.get("reason", "run not waiting")}
        if approved:
            svc.complete_checkpoint(run_id, step_id=step_id)
        else:
            svc.rewind_to_work_before(run_id, step_id=step_id)
        loop = await svc.advance(
            run_id,
            event={
                "event": "human_checkpoint",
                "approved": approved,
                "guidance": guidance,
                "summary": guidance or (
                    "checkpoint approved" if approved else "checkpoint rejected"),
            },
        )
        return {"handled": True, "resumed": True, "kind": "checkpoint",
                "loop": loop}

    result = await svc.resume(
        run_id,
        approved=approved,
        reviewer=reviewer_id,
        guidance=guidance or action.get("reason"),
    )
    return {"handled": True, "kind": "decision", **result}


async def _resume_assignment(
    action: Dict[str, Any], approved: bool,
    reviewer_id: Optional[str], guidance: Optional[str],
) -> Dict[str, Any]:
    """Resume the assignment whose concrete effect was approved/rejected.

    The HITL row is only the authorization event. The operation payload,
    artifact revision and assignment plan are re-checked through the same
    durable run identity; a changed payload cannot ride an old approval.
    """
    from core.assignment_executor import AssignmentExecutor
    from core.goals.goal_run_service import GoalRunService
    from core.task_lifecycle import TaskLifecycle

    params = action.get("params") or {}
    run_id = str(params.get("run_id") or "")
    step_id = str(params.get("step_id") or "")
    if not run_id or not step_id:
        return {"handled": False, "reason": "assignment action has no run/step"}
    svc = GoalRunService(
        workspace_id=action.get("workspace_id") or "default",
        tenant_id=action.get("tenant_id") or "default",
    )
    lifecycle = TaskLifecycle(svc)
    executor = AssignmentExecutor(lifecycle)
    if not approved:
        try:
            svc.consume_wake(run_id, {
                "event": "human_checkpoint",
                "hitl_id": action["id"],
                "approved": False,
            })
        except Exception:
            pass
        result = executor.reject_step(
            run_id, step_id,
            rejected_by=reviewer_id or "approver",
            reason=guidance or action.get("reason") or "rejected by approver",
        )
        return {"handled": True, "resumed": False, "kind": "assignment",
                **result}
    approval = executor.approve_step(
        run_id, step_id,
        approved_by=reviewer_id or "approver",
        note=guidance or "",
    )
    if approval.get("status") != "approved":
        return {
            "handled": True, "resumed": False, "kind": "assignment",
            "reason": (
                "the prepared effect changed; a fresh approval is required"),
            "approval": approval,
        }
    loop = await executor.resume(run_id)
    return {"handled": True, "resumed": True, "kind": "assignment",
            "assignment": loop}


async def _resume_chat_obligation(
    action: Dict[str, Any], approved: bool,
    reviewer_id: Optional[str], guidance: Optional[str],
) -> Dict[str, Any]:
    """Resume a prepared chat obligation through the existing proposal path.

    The HITL row is the approval event; the concrete email payload lives on
    the AgentProposal. Approval executes that proposal through the existing
    deterministic email policy (controlled transport in tests), never a
    second send path.
    """
    params = action.get("params") or {}
    proposal_id = str(params.get("proposal_id") or "")
    if not proposal_id:
        return {
            "handled": False,
            "reason": "chat obligation has no prepared proposal",
        }
    from core.proposal_service import (
        ProposalApprovalInvalidated,
        ProposalService,
    )

    expected_payload_sha256 = str(params.get("payload_sha256") or "")
    expected_artifact_revision = str(
        params.get("artifact_revision") or "")
    from core.database import get_db_session

    with get_db_session() as db:
        service = ProposalService(db)
        current = service._proposal_query(
            proposal_id, action.get("tenant_id")).first()
        if current is None:
            return {
                "handled": False,
                "reason": "prepared proposal not found",
            }
        if not approved:
            try:
                await service.reject_proposal(
                    proposal_id,
                    user_id=reviewer_id or "approver",
                    reason=guidance or action.get("reason") or "rejected",
                    tenant_id=action.get("tenant_id"),
                )
            except Exception as exc:  # noqa: BLE001 — decision stands
                return {
                    "handled": True, "resumed": False,
                    "kind": "chat_obligation",
                    "proposal_id": proposal_id,
                    "error": str(exc)[:500],
                }
            return {
                "handled": True, "resumed": False,
                "kind": "chat_obligation",
                "proposal_id": proposal_id,
                "status": "rejected",
            }
        if current.status == "executed":
            return {
                "handled": True, "resumed": True, "replayed": True,
                "kind": "chat_obligation",
                "proposal_id": proposal_id,
                "status": "already_executed",
            }
        if current.status in ("rejected", "cancelled", "execution_failed"):
            return {
                "handled": True, "resumed": False,
                "kind": "chat_obligation",
                "proposal_id": proposal_id,
                "status": current.status,
            }
        if not expected_payload_sha256:
            return {
                "handled": True, "resumed": False,
                "kind": "chat_obligation",
                "proposal_id": proposal_id,
                "status": "missing_payload_binding",
                "reason": (
                    "this approval has no reviewed payload binding; fresh "
                    "review is required"),
            }
        try:
            result = await service.approve_proposal(
                proposal_id,
                user_id=reviewer_id or "approver",
                tenant_id=action.get("tenant_id"),
                expected_payload_sha256=expected_payload_sha256,
                expected_artifact_revision=(
                    expected_artifact_revision or None),
            )
        except ProposalApprovalInvalidated as exc:
            return {
                "handled": True, "resumed": False,
                "kind": "chat_obligation",
                "proposal_id": proposal_id,
                "status": "payload_changed",
                "reason": str(exc)[:500],
                "fresh_review_required": True,
            }
        return {
            "handled": True,
            "resumed": bool((result or {}).get("success")),
            "kind": "chat_obligation",
            "proposal_id": proposal_id,
            "result": result,
        }


async def _resume_workflow(action: Dict[str, Any], approved: bool,
                            guidance: Optional[str]) -> Dict[str, Any]:
    params = action.get("params") or {}
    execution_id = params.get("execution_id")
    if not execution_id:
        return {"handled": False, "reason": "workflow action has no execution_id"}

    from core.execution_state_manager import get_state_manager

    state_manager = get_state_manager()
    state = await state_manager.get_execution_state(execution_id)
    if not state:
        return {"handled": True, "resumed": False, "reason": "execution not found"}

    if not approved:
        await state_manager.update_execution_status(
            execution_id, "FAILED",
            error=(guidance or "Rejected by human reviewer")[:500],
        )
        return {"handled": True, "resumed": False, "kind": "workflow",
                "status": "FAILED"}

    workflow_id = params.get("workflow_id") or state.get("workflow_id")
    from core.workflow_endpoints import _load_template_definition, load_workflows

    workflow = next(
        (w for w in load_workflows()
         if w.get("id") == workflow_id or w.get("workflow_id") == workflow_id),
        None,
    )
    if workflow is None and workflow_id:
        workflow = _load_template_definition(workflow_id)
    if not workflow:
        return {"handled": True, "resumed": False,
                "reason": f"workflow {workflow_id!r} not found"}

    from core.workflow_engine import get_workflow_engine

    ok = await get_workflow_engine().resume_workflow(
        execution_id, workflow,
        {"approved": True, "hitl_action_id": action["id"],
         "guidance": guidance or ""},
    )
    return {"handled": True, "resumed": bool(ok), "kind": "workflow",
            "status": "RUNNING" if ok else "PAUSED"}


async def resume_after_hitl_decision(
    action_id: str,
    approved: bool,
    reviewer_id: Optional[str] = None,
    guidance: Optional[str] = None,
) -> Dict[str, Any]:
    """Resume whatever the decided action was blocking.

    Returns ``{"handled": False}`` for ordinary governed actions that have no
    durable waiter (they already executed through their own path).
    """
    action = _load_action(action_id)
    if action is None:
        return {"handled": False, "reason": "action not found"}

    try:
        if action["action_type"] in _GOAL_RUN_ACTIONS:
            result = await _resume_goal_run(action, approved, reviewer_id, guidance)
        elif action["action_type"] in _ASSIGNMENT_ACTIONS:
            result = await _resume_assignment(
                action, approved, reviewer_id, guidance)
        elif action["action_type"] in _CHAT_OBLIGATION_ACTIONS:
            result = await _resume_chat_obligation(
                action, approved, reviewer_id, guidance)
        elif (action.get("params") or {}).get("execution_id"):
            result = await _resume_workflow(action, approved, guidance)
        else:
            return {"handled": False, "reason": "no durable waiter for this action"}
    except Exception as exc:  # noqa: BLE001 — never undo a human decision
        logger.exception("HITL %s decided but resume failed: %s", action_id, exc)
        return {"handled": True, "resumed": False, "error": str(exc)[:500]}

    if result.get("handled") and not result.get("resumed"):
        logger.warning(
            "HITL %s decided (%s) but work did not resume: %s",
            action_id, "approved" if approved else "rejected", result,
        )
    return result
