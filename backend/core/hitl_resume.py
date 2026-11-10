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
from contextlib import contextmanager
from typing import Any, Dict, Optional

from core.models import HITLAction

logger = logging.getLogger(__name__)

_GOAL_RUN_ACTIONS = {"goal_run_decision", "goal_run_checkpoint"}
_ASSIGNMENT_ACTIONS = {"assignment_approval"}
_CHAT_OBLIGATION_ACTIONS = {"chat_request_obligation"}
_GUIDED_CREATE_ACTIONS = {"create_agent"}
_AGENT_INFORMATION_ACTIONS = {
    "agent_information_request", "agent_missing_information"}


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
            "bind": db.get_bind(),
        }


def _action_field(action: Any, name: str, default: Any = None) -> Any:
    if isinstance(action, dict):
        return action.get(name, default)
    return getattr(action, name, default)


def preflight_hitl_decision(
    action_id: str,
    modified_params: Optional[Dict[str, Any]] = None,
    *,
    action: Any = None,
    db: Any = None,
) -> Dict[str, Any]:
    """Validate a goal-decision approval BEFORE any HITL state changes.

    The approvals queue marks the row approved/rejected before the resume
    bridge runs. For a held goal decision that would be a state change under
    an unvalidated binding. This preflight checks the exact reviewed decision
    generation/material against the authoritative run; non-goal/checkpoint
    actions need no extra check here. Routes pass the action row they already
    loaded so this check uses the same session/transaction boundary.
    """
    if action is None:
        action = _load_action(action_id)
    if action is None:
        return {"valid": False, "reason": "action_not_found"}
    if _action_field(action, "action_type") == "create_agent":
        from core.guided_automation_service import (
            GUIDED_CREATE_REVIEW_SCHEMA,
            guided_create_review_digest,
        )

        if modified_params:
            return {
                "valid": False,
                "reason": "review_material_immutable",
                "message": (
                    "A guided-create review cannot be rewritten during "
                    "approval; reject and request a fresh review."),
            }
        params = _action_field(action, "params") or {}
        if params.get("schema") != GUIDED_CREATE_REVIEW_SCHEMA:
            return {
                "valid": False,
                "reason": "review_schema_invalid",
                "message": (
                    "The guided-create review schema is missing or unknown."),
            }
        if params.get("review_digest") != guided_create_review_digest(params):
            return {
                "valid": False,
                "reason": "review_material_mismatch",
                "message": (
                    "The reviewed guided-create material changed; request a "
                    "fresh review."),
            }
        return {"valid": True}
    if _action_field(action, "action_type") != "goal_run_decision":
        return {"valid": True}

    modified = modified_params or {}
    if any(key in modified for key in (
            "decision", "decision_id", "decision_binding",
            "decision_generation")):
        # A modified decision is not the material the human reviewed.
        return {
            "valid": False,
            "reason": "decision_review_required",
            "message": "A goal decision's reviewed payload cannot be "
                       "rewritten during approval; reject and re-plan instead.",
        }

    params = _action_field(action, "params") or {}
    run_id = str(params.get("run_id") or "")
    decision = params.get("decision")
    if not isinstance(decision, dict):
        decision = {}
    expected_decision_id = str(decision.get("decision_id") or "")
    expected_decision_binding = str(decision.get("decision_binding") or "")
    if not expected_decision_id or not expected_decision_binding:
        return {"valid": False, "reason": "decision_review_required"}
    if not run_id:
        return {"valid": False, "reason": "run_not_found"}

    from core.goals.goal_run_binding import validate_pending_decision
    from core.goals.goal_run_service import GoalRunService

    session_factory = None
    if db is not None:
        @contextmanager
        def _session():
            yield db

        session_factory = _session
    svc = GoalRunService(
        workspace_id=_action_field(action, "workspace_id") or "default",
        tenant_id=_action_field(action, "tenant_id") or "default",
        session_factory=session_factory,
    )
    run = svc.get_run(run_id)
    if not run:
        return {"valid": False, "reason": "run_not_found"}
    pending = run.get("pending_decision")
    if not pending:
        return {"valid": False, "reason": "no_pending_decision"}
    valid, reason = validate_pending_decision(
        run, pending,
        expected_decision_id=expected_decision_id,
        expected_decision_binding=expected_decision_binding)
    return {
        "valid": valid,
        "reason": reason,
        "current_decision_id": pending.get("decision_id"),
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

    decision = params.get("decision")
    if not isinstance(decision, dict):
        decision = {}
    expected_decision_id = str(decision.get("decision_id") or "")
    expected_decision_binding = str(decision.get("decision_binding") or "")
    if not expected_decision_id or not expected_decision_binding:
        return {
            "handled": True,
            "kind": "decision",
            "resumed": False,
            "stale_review": True,
            "reason": "decision_review_required",
        }
    result = await svc.resume(
        run_id,
        approved=approved,
        reviewer=reviewer_id,
        guidance=guidance or action.get("reason"),
        expected_decision_id=expected_decision_id,
        expected_decision_binding=expected_decision_binding,
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


async def _resume_advanced_workflow(
    action: Dict[str, Any], approved: bool, guidance: Optional[str],
    execution_id: str,
) -> Dict[str, Any]:
    """Resume an ORCH-01 execution through its authoritative checkpoint.

    The advanced orchestrator persists executions in ``WorkflowExecution``
    rather than the workflow-engine state store. Its resume method re-reads
    the durable HITLAction and refuses pending/rejected/missing/mismatched
    reviews, so the HITL queue cannot bypass the checkpoint.
    """
    params = action.get("params") or {}
    step_id = str(params.get("step_id") or "")
    if not step_id:
        return {
            "handled": False,
            "reason": "advanced workflow action has no step_id",
        }
    try:
        from advanced_workflow_orchestrator import get_orchestrator

        context = await get_orchestrator().resume_workflow(
            execution_id, step_id)
    except Exception as exc:  # noqa: BLE001 — decision already committed
        return {
            "handled": True,
            "resumed": False,
            "kind": "workflow",
            "error": str(exc)[:500],
        }
    status = getattr(context, "status", None)
    status_value = getattr(status, "value", str(status or ""))
    result = {
        "handled": True,
        "resumed": status_value == "completed",
        "kind": "workflow",
        "status": status_value.upper(),
    }
    if status_value == "waiting_approval":
        result["reason"] = "workflow is still waiting for approval"
    elif status_value in ("failed", "cancelled"):
        result["reason"] = (
            "approval binding did not match the authoritative execution; "
            "a fresh matching review is required")
    return result


async def _resume_workflow(action: Dict[str, Any], approved: bool,
                            guidance: Optional[str]) -> Dict[str, Any]:
    params = action.get("params") or {}
    execution_id = params.get("execution_id") or params.get("workflow_id")
    if not execution_id:
        return {"handled": False, "reason": "workflow action has no execution_id"}

    from core.execution_state_manager import get_state_manager

    state_manager = get_state_manager()
    state = await state_manager.get_execution_state(execution_id)
    if not state:
        return await _resume_advanced_workflow(
            action, approved, guidance, str(execution_id))

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


async def _resume_guided_create(
    action: Dict[str, Any],
    approved: bool,
    reviewer_id: Optional[str],
    guidance: Optional[str],
) -> Dict[str, Any]:
    """Create the exact reviewed guided agent after an existing HITL approval.

    This is not a second review engine: the approvals route already made and
    persisted the human decision. Here we reauthorize the current reviewer and
    acting parent, verify the reviewed intent digest, and use the shared
    create decision writer for one durable agent + receipt.
    """
    from core.agent_decision_write_service import create_agent
    from core.database import get_db_session
    from core.guided_automation_service import (
        GUIDED_CREATE_REVIEW_SCHEMA,
        guided_create_review_digest,
    )
    from core.models import AgentRegistry, User, UserRole
    from core.personal_scope import resolve_tenant_id, resolve_workspace_id

    params = dict(action.get("params") or {})
    if not approved:
        return {"handled": True, "resumed": False, "kind": "guided_create",
                "status": "rejected"}
    if str(action.get("status") or "") != "approved":
        return {"handled": True, "resumed": False, "kind": "guided_create",
                "reason": "action_not_approved",
                "status": action.get("status")}
    if str(params.get("schema") or "") != GUIDED_CREATE_REVIEW_SCHEMA:
        return {"handled": True, "resumed": False, "kind": "guided_create",
                "reason": "review_schema_invalid"}
    if params.get("review_digest") != guided_create_review_digest(params):
        return {"handled": True, "resumed": False, "kind": "guided_create",
                "reason": "review_material_mismatch"}
    if not reviewer_id:
        return {"handled": True, "resumed": False, "kind": "guided_create",
                "reason": "current_reviewer_required"}

    action_tenant = str(params.get("tenant_id") or "")
    action_workspace = str(params.get("workspace_id") or "")
    with get_db_session() as db:
        reviewer = (
            db.query(User).filter(User.id == str(reviewer_id)).first()
        )
        if reviewer is None:
            return {"handled": True, "resumed": False,
                    "kind": "guided_create",
                    "reason": "current_reviewer_required"}
        if (
            resolve_tenant_id(reviewer) != action_tenant
            or resolve_workspace_id(reviewer) != action_workspace
        ):
            return {"handled": True, "resumed": False,
                    "kind": "guided_create",
                    "reason": "review_scope_changed"}

        parent_agent_id = params.get("acting_agent_id")
        parent_authority = None
        if parent_agent_id:
            parent = (
                db.query(AgentRegistry)
                .filter(AgentRegistry.id == str(parent_agent_id))
                .populate_existing()
                .first()
            )
            if parent is None:
                return {"handled": True, "resumed": False,
                        "kind": "guided_create",
                        "reason": "acting_agent_missing"}
            if (
                resolve_tenant_id(parent) != action_tenant
                or resolve_workspace_id(parent) != action_workspace
            ):
                return {"handled": True, "resumed": False,
                        "kind": "guided_create",
                        "reason": "acting_agent_scope_changed"}
            parent_authority = {
                "id": str(parent.id),
                "tenant_id": parent.tenant_id,
                "workspace_id": parent.workspace_id,
                "status": parent.status,
                "confidence_score": parent.confidence_score,
                "enabled": parent.enabled,
                "last_exam_id": parent.last_exam_id,
                "configuration": parent.configuration,
                "capabilities": parent.capabilities,
            }

        result = create_agent(
            db,
            actor=reviewer,
            name=str(params.get("name") or ""),
            category=str(params.get("category") or ""),
            description=params.get("description"),
            configuration=params.get("configuration"),
            schedule_config=params.get("schedule_config"),
            confidence_score=0.1,
            user_id=str(params.get("created_by_user") or ""),
            parent_agent_id=parent_agent_id,
            parent_authority=parent_authority,
            capabilities=params.get("capabilities"),
            minimum_role=UserRole.GUEST,
            authority_label="GUIDED_CREATE_APPROVAL",
            operation_id=f"guided-hitl:{action['id']}",
        )
        status = result.get("status")
        if status in ("verified", "already_applied"):
            data = result.get("data") or {}
            if status == "verified":
                schedule_config = params.get("schedule_config")
                if (
                    isinstance(schedule_config, dict)
                    and schedule_config.get("active")
                ):
                    try:
                        from core.scheduler import AgentScheduler
                        AgentScheduler.get_instance().schedule_agent(
                            data.get("agent_id"), schedule_config)
                    except Exception as exc:  # noqa: BLE001
                        logger.warning(
                            "Guided HITL schedule failed for %s: %s",
                            data.get("agent_id"), exc)
            return {
                "handled": True,
                "resumed": True,
                "kind": "guided_create",
                "agent_id": data.get("agent_id"),
                "operation_id": result.get("operation_id"),
                "audit_id": result.get("audit_id"),
                "verification": data.get("verification"),
            }
        return {
            "handled": True,
            "resumed": False,
            "kind": "guided_create",
            "reason": result.get("error_code") or status,
            "error": result.get("error"),
            "verification": result.get("verification"),
        }


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
        elif action["action_type"] in _AGENT_INFORMATION_ACTIONS:
            from api.agent_routes import resume_information_wait_action

            result = await resume_information_wait_action(
                action_id,
                approved=approved,
                answer=guidance,
                reviewer_id=reviewer_id,
                bind=action.get("bind"),
            )
        elif action["action_type"] in _ASSIGNMENT_ACTIONS:
            result = await _resume_assignment(
                action, approved, reviewer_id, guidance)
        elif action["action_type"] in _CHAT_OBLIGATION_ACTIONS:
            result = await _resume_chat_obligation(
                action, approved, reviewer_id, guidance)
        elif action["action_type"] in _GUIDED_CREATE_ACTIONS:
            result = await _resume_guided_create(
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
