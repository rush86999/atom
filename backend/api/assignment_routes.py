"""Durable assignment status, resume, approval and cancellation.

The UI reads this durable projection; it never reconstructs progress from
chat transcript wording. Scope is the authenticated workspace/tenant and the
run's own workspace binding.
"""
from __future__ import annotations

import os
import uuid
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.assignment_planner import (
    AssignmentPlanError,
    plan_assignment,
    validate_proposed_plan,
)
from core.assignment_plan import new_teaching_snapshot
from core.assignment_resources import (
    AssignmentResourceError,
    allocate_output_path,
    derive_aggregate_spec,
    resolve_assignment_source,
    select_resource_candidates,
    source_fingerprint,
)
from core.base_routes import BaseAPIRouter
from core.database import get_db
from core.goals.goal_run_service import GoalRunService
from core.goals.goal_service import GoalService
from core.intervention_service import intervention_service
from core.models import AgentRegistry, HITLAction, HITLActionStatus, UserRole
from core.security.rbac import user_meets_role
from core.task_lifecycle import TaskLifecycle

router = BaseAPIRouter(prefix="/api/assignments", tags=["Assignments"])


class AssignmentCancel(BaseModel):
    reason: str = ""


class AssignmentApproval(BaseModel):
    note: str = ""


class AssignmentGapResolution(BaseModel):
    resolution: str
    evidence: str = ""


class AssignmentExternalResponse(BaseModel):
    response: str
    source: str = ""
    evidence: str = ""


class AssignmentStart(BaseModel):
    objective: str
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None
    employee_id: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    source_scope: Optional[Dict[str, Any]] = None
    discover: bool = False
    deliverables: List[Dict[str, Any]] = []
    calculation: Optional[Dict[str, Any]] = None
    outbound: Optional[Dict[str, Any]] = None
    wait: Optional[Dict[str, Any]] = None
    task_context: Dict[str, Any] = {}
    transport: Optional[str] = None
    proposed_steps: Optional[List[Dict[str, Any]]] = None


def _scoped_run(run_id: str, current_user: User) -> Dict[str, Any]:
    run = GoalRunService(
        workspace_id=current_user.workspace_id or "default",
        tenant_id=current_user.tenant_id or "default",
    ).get_run(run_id)
    if not run:
        raise HTTPException(status_code=404, detail="Assignment not found")
    return run


def _executor(run: Dict[str, Any]):
    from core.assignment_executor import AssignmentExecutor

    svc = GoalRunService(
        workspace_id=run.get("workspace_id") or "default",
        tenant_id=run.get("tenant_id") or "default",
    )
    goals = GoalService(
        workspace_id=run.get("workspace_id") or "default",
        tenant_id=run.get("tenant_id") or "default",
    )
    return AssignmentExecutor(TaskLifecycle(svc, goals))


def _teaching_snapshot_for_start(
    db,
    *,
    agent_id: Optional[str],
    workspace_id: str,
    output_types: List[str],
    task_context: Dict[str, Any],
) -> Dict[str, Any]:
    from core.artifact_teaching import resolve_artifact_teaching

    merged: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    revisions: List[str] = []
    unresolved: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    for output_type in sorted(set(output_types)):
        resolution = resolve_artifact_teaching(
            db, agent_id, output_type,
            task_context=task_context or {},
            workspace_id=workspace_id or "default",
        )
        status = str(resolution.get("status") or "")
        if status in ("needs_context", "conflict"):
            unresolved.extend(resolution.get("clarifications") or [])
            conflicts.extend(resolution.get("conflicts") or [])
            continue
        merged.update(resolution.get("spec") or {})
        sources.extend(resolution.get("sources") or [])
        if resolution.get("revision"):
            revisions.append(str(resolution["revision"]))
    if unresolved or conflicts:
        raise HTTPException(
            status_code=409,
            detail={
                "error": "teaching_context_unresolved",
                "message": (
                    "Teaching cannot govern this assignment until the "
                    "missing context is confirmed."),
                "clarifications": unresolved[:20],
                "conflicts": conflicts[:20],
            },
        )
    return new_teaching_snapshot(
        revision="+".join(sorted(set(revisions))) or "untrained",
        effective_lesson_ids=[
            {"id": item.get("id"), "revision": item.get("revision")}
            for item in sources if item.get("id")
        ][:40],
        matched_context=dict(task_context or {}),
        output_requirements=merged,
        source_versions={
            str(item.get("id")): item.get("revision")
            for item in sources if item.get("id")
        },
    )


@router.post("")
async def start_assignment(
    body: AssignmentStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Create a validated assignment from an accepted Chat objective."""
    if not str(body.objective or "").strip():
        raise HTTPException(status_code=422, detail="objective is required")
    if body.discover and not body.sources:
        from core.sheet_dataset_service import find_entries_sync

        scope = dict(body.source_scope or {})
        scope_workspace = str(scope.get("workspace_id") or "").strip()
        workspace_id = current_user.workspace_id or "default"
        if scope_workspace and scope_workspace != workspace_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "resource_workspace_mismatch",
                    "message": (
                        "The permitted source scope names a different "
                        "workspace."),
                },
            )
        entries = find_entries_sync(
            query=str(scope.get("query") or ""),
            workspace_id=workspace_id,
            limit=max(1, min(int(scope.get("limit") or 20), 50)),
        )
        try:
            chosen_entries = select_resource_candidates(
                entries,
                objective=body.objective,
                scope_query=str(scope.get("query") or ""),
                explicit_sheet=scope.get("sheet"),
                required_count=max(
                    1, min(int(scope.get("required_count") or 1), 5)),
            )
        except AssignmentResourceError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={
                    "error": exc.code,
                    "message": str(exc),
                    "candidates": [
                        {
                            "dataset_name": item.get("dataset_name"),
                            "sheet": item.get("entity_name"),
                            "file_name": item.get("file_name"),
                            "columns": item.get("columns") or [],
                            "row_count": item.get("row_count"),
                            "coverage": item.get("coverage") or {},
                        }
                        for item in (exc.candidates or [])[:10]
                    ],
                },
            )
        if not chosen_entries:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "resource_discovery_empty",
                    "message": (
                        "No authorized active resource matched the requested "
                        "scope. Name a permitted source or refresh the "
                        "connected catalog."),
                    "next_action": "Refresh the connected source or widen "
                                    "the permitted scope explicitly.",
                },
            )
        body.sources = [{
            "dataset_name": chosen.get("dataset_name"),
            "sheet": chosen.get("entity_name"),
            "source_version": chosen.get("content_hash"),
            "kind": "workbook" if str(
                chosen.get("file_name") or "").lower().endswith(
                    (".xlsx", ".xls", ".csv")) else "document",
        } for chosen in chosen_entries]
    if not body.sources:
        raise HTTPException(
            status_code=422,
            detail="at least one authorized source is required")
    if not body.deliverables and not body.outbound:
        raise HTTPException(
            status_code=422,
            detail="at least one deliverable or outbound action is required")
    employee = current_user
    if body.employee_id and body.employee_id != current_user.id:
        employee = db.query(User).filter(
            User.id == body.employee_id,
            User.workspace_id == current_user.workspace_id,
            User.tenant_id == current_user.tenant_id,
        ).first()
        if employee is None:
            raise HTTPException(status_code=404, detail="Employee not found")
        if not user_meets_role(current_user, UserRole.TEAM_LEAD):
            raise HTTPException(
                status_code=403,
                detail="Only a supervisor may assign work to another employee")
    if body.agent_id:
        agent = db.query(AgentRegistry).filter(
            AgentRegistry.id == body.agent_id,
            AgentRegistry.workspace_id == current_user.workspace_id,
            AgentRegistry.tenant_id == current_user.tenant_id,
        ).first()
        if agent is None:
            raise HTTPException(status_code=404, detail="Employee agent not found")

    allow_internal = os.getenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS") == "1"
    resolved_sources = []
    for reference in body.sources:
        try:
            resolved_sources.append(resolve_assignment_source(
                db, current_user, reference, allow_internal=allow_internal))
        except AssignmentResourceError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={"error": exc.code, "message": str(exc)})
    if not resolved_sources:
        raise HTTPException(
            status_code=422, detail="no authorized source resolved")

    if body.calculation is None:
        try:
            body.calculation = derive_aggregate_spec(
                body.objective, resolved_sources)
        except AssignmentResourceError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={
                    "error": exc.code,
                    "message": str(exc),
                    "candidates": list(exc.candidates or [])[:20],
                },
            )

    deliverables = []
    accepted_actions = ["retrieve"]
    if body.calculation:
        accepted_actions.append("calculate")
    if body.deliverables:
        accepted_actions.append("present")
    for index, raw in enumerate(body.deliverables):
        deliverable = dict(raw)
        deliverable.pop("path", None)
        kind = str(deliverable.get("kind") or "").lower()
        if kind not in ("document", "presentation", "spreadsheet",
                        "email_draft"):
            raise HTTPException(
                status_code=422,
                detail=f"unsupported deliverable kind '{kind}'")
        if kind == "email_draft":
            accepted_actions.append("edit")
            if not str(deliverable.get("body") or "").strip(
                    ) and not body.calculation:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "artifact_content_required",
                        "message": (
                            "The email draft needs a body or a validated "
                            "result to compose from."),
                        "clarifications": [{
                            "concept": "email_content",
                            "question": "What should the email draft say?",
                        }],
                    },
                )
        elif kind in ("document", "presentation"):
            if not str(deliverable.get("content") or "").strip(
                    ) and not body.calculation:
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "artifact_content_required",
                        "message": (
                            "The artifact needs explicit content or a "
                            "validated result to compose from; generic "
                            "prose is not a grounded deliverable."),
                        "clarifications": [{
                            "concept": "artifact_content",
                            "question": (
                                "Which facts or calculation should the "
                                "artifact contain?"),
                        }],
                    },
                )
        elif kind == "spreadsheet":
            rows = deliverable.get("rows")
            if not isinstance(rows, list) or not rows:
                if not resolved_sources:
                    raise HTTPException(
                        status_code=409,
                        detail={
                            "error": "artifact_rows_required",
                            "message": (
                                "The spreadsheet needs rows or a validated "
                                "source read."),
                        },
                    )
        title = str(deliverable.get("description")
                    or body.objective)[:200]
        deliverable["path"] = allocate_output_path(
            current_user, kind=kind, title=title,
            assignment_id=f"draft-{uuid.uuid4().hex[:12]}")
        deliverables.append(deliverable)
    if body.outbound:
        accepted_actions.append("outbound")
        if not str((body.outbound or {}).get("body") or "").strip(
                ) and not body.calculation:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "outbound_content_required",
                    "message": (
                        "The outbound message needs a body or a validated "
                        "result to compose from."),
                },
            )
    if body.proposed_steps is not None and os.getenv(
            "ATOM_ASSIGNMENT_ALLOW_PROPOSED_STEPS") != "1":
        raise HTTPException(
            status_code=422,
            detail=(
                "public proposals cannot submit executable steps directly; "
                "use the capability planner"))

    output_types = []
    for deliverable in deliverables:
        output_types.append({
            "document": "document",
            "spreadsheet": "spreadsheet",
            "presentation": "presentation",
            "email_draft": "email",
        }.get(str(deliverable.get("kind") or "").lower(), ""))
    if body.outbound:
        output_types.append("email")
    teaching = _teaching_snapshot_for_start(
        db,
        agent_id=body.agent_id,
        workspace_id=current_user.workspace_id or "default",
        output_types=[item for item in output_types if item],
        task_context=body.task_context,
    )

    transport_adapter = None
    if body.transport == "controlled":
        from core.assignment_executor import default_adapter_registry

        if default_adapter_registry.get("assignment.controlled_outbox"):
            transport_adapter = "assignment.controlled_outbox"
        else:
            raise HTTPException(
                status_code=409,
                detail="controlled transport is not enabled in this runtime")

    try:
        plan = plan_assignment(
            objective=body.objective,
            sources=resolved_sources,
            deliverables=deliverables,
            calculation=body.calculation,
            outbound=body.outbound,
            wait=body.wait,
            teaching_snapshot=teaching,
            authorized_actions=accepted_actions,
            employee_id=employee.id,
            workspace_id=current_user.workspace_id or "default",
            tenant_id=current_user.tenant_id or "default",
            agent_id=body.agent_id,
            transport_adapter=transport_adapter,
            provenance={
                "conversation_id": body.conversation_id,
                "started_from": "chat",
                "requester_id": current_user.id,
                "source_fingerprint": source_fingerprint(resolved_sources),
            },
            proposed_steps=body.proposed_steps,
        )
        if body.proposed_steps is not None:
            validate_proposed_plan(plan)
    except AssignmentPlanError as exc:
        raise HTTPException(status_code=422, detail=str(exc))

    executor = _executor({
        "workspace_id": current_user.workspace_id or "default",
        "tenant_id": current_user.tenant_id or "default",
    })
    record = executor.create_assignment(
        body.conversation_id or f"chat-assignment-{uuid.uuid4().hex[:12]}",
        body.objective,
        assignment=plan,
        employee_id=employee.id,
        workspace_id=current_user.workspace_id or "default",
        tenant_id=current_user.tenant_id or "default",
        entities=[],
        requested_fields=[],
    )
    status = await executor.execute(record["run_id"], max_steps=12)
    return {
        "run_id": record["run_id"],
        "assignment": status,
        "plan_revision": plan.get("plan_revision"),
        "teaching_revision": (
            plan.get("teaching_snapshot") or {}).get("revision"),
    }


@router.get("")
async def list_assignments(
    include_terminal: bool = False,
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    svc = GoalRunService(
        workspace_id=current_user.workspace_id or "default",
        tenant_id=current_user.tenant_id or "default",
    )
    rows = svc.list_runs(
        include_terminal=include_terminal, limit=100)
    results = []
    for run in rows:
        record = TaskLifecycle(svc).get_task(run.get("id"))
        if record is None or record.get("assignment") is None:
            continue
        results.append({
            "run_id": run.get("id"),
            "status": run.get("status"),
            "assignment": {
                "assignment_id": record["assignment"].get("assignment_id"),
                "objective": record["assignment"].get("objective"),
                "state": record["assignment"].get("status"),
                "plan_revision": record["assignment"].get("plan_revision"),
                "current_action": next((
                    step.get("title")
                    for step in record["assignment"].get("steps") or []
                    if step.get("status") in (
                        "running", "waiting", "awaiting_approval")), None),
            },
        })
    return results


@router.get("/{run_id}")
async def assignment_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    return _executor(run).status(run_id)


@router.post("/{run_id}/resume")
async def resume_assignment(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    try:
        return await executor.resume(run_id)
    except Exception as exc:  # noqa: BLE001 — durable state remains
        raise HTTPException(status_code=409, detail=str(exc))


@router.post("/{run_id}/cancel")
async def cancel_assignment(
    run_id: str,
    body: AssignmentCancel,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    executor.cancel(
        run_id, reason=body.reason or "cancelled by user",
        cancelled_by=str(current_user.id))
    return executor.status(run_id)


@router.post("/{run_id}/responses/{correlation_id}")
async def record_assignment_response(
    run_id: str,
    correlation_id: str,
    body: AssignmentExternalResponse,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    result = executor.record_external_response(
        run_id, correlation_id,
        response=body.response,
        source=body.source or str(current_user.id),
        evidence=body.evidence,
    )
    if result.get("status") == "unmatched":
        raise HTTPException(status_code=404, detail=result.get("message"))
    return await executor.resume(run_id)


@router.post("/{run_id}/gaps/{question_id}/resolve")
async def resolve_assignment_gap(
    run_id: str,
    question_id: str,
    body: AssignmentGapResolution,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    record = executor.lifecycle.get_task(run_id) or {}
    question = next((
        item for item in (record.get("task_revision") or {}).get(
            "unresolved") or []
        if item.get("question_id") == question_id
        and item.get("status") == "open"), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Open gap not found")
    if str((record.get("task_revision") or {}).get("authorization")
           or "").lower() == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="The assignment is cancelled; a gap cannot revive it")
    executor.resolve_gap(
        run_id, question_id,
        resolution=body.resolution,
        resolved_by=str(current_user.id),
        evidence=body.evidence,
    )
    return await executor.resume(run_id)


@router.post("/{run_id}/approve/{step_id}")
async def approve_assignment_step(
    run_id: str,
    step_id: str,
    body: AssignmentApproval,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    record = executor.lifecycle.get_task(run_id) or {}
    assignment = record.get("assignment") or {}
    step = next((
        item for item in assignment.get("steps") or []
        if item.get("step_id") == step_id), None)
    if step is None:
        raise HTTPException(status_code=404, detail="Assignment step not found")
    if str((record.get("task_revision") or {}).get("authorization")
           or "").lower() == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="The assignment is cancelled; approval cannot revive it")
    request = step.get("approval_request") or {}
    if not request.get("hitl_action_id"):
        raise HTTPException(
            status_code=409, detail="No prepared approval request for this step")

    action = db.query(HITLAction).filter(
        HITLAction.id == request["hitl_action_id"],
        HITLAction.workspace_id == run.get("workspace_id"),
        HITLAction.tenant_id == run.get("tenant_id"),
        HITLAction.status == HITLActionStatus.PENDING.value,
    ).first()
    if action is None:
        raise HTTPException(
            status_code=404, detail="Approval request not found")
    params = action.params or {}
    expected = {
        "run_id": run_id,
        "step_id": step_id,
        "operation_id": step.get("operation_id"),
        "payload_sha256": request.get("payload_sha256"),
        "artifact_revision": request.get("artifact_revision"),
        "authorization_revision": request.get("authorization_revision"),
    }
    for key, value in expected.items():
        if str(params.get(key) or "") != str(value or ""):
            raise HTTPException(
                status_code=409,
                detail=(
                    f"Approval binding '{key}' no longer matches the "
                    f"prepared effect"))

    user = db.query(User).filter(User.id == current_user.id).first()
    if user is None:
        raise HTTPException(status_code=403, detail="Approver not found")
    denial = intervention_service._required_role_denial(db, action, user.id)
    if denial:
        raise HTTPException(status_code=403, detail=denial)
    if not user_meets_role(user, UserRole.TEAM_LEAD):
        raise HTTPException(
            status_code=403,
            detail="Insufficient approval authority for this assignment")

    try:
        result = executor.approve_step(
            run_id, step_id, approved_by=str(current_user.id),
            note=body.note)
    except Exception as exc:  # noqa: BLE001 — approval stays pending
        raise HTTPException(status_code=409, detail=str(exc))
    if result.get("status") == "approval_refreshed":
        raise HTTPException(
            status_code=409,
            detail=(
                "The prepared effect changed; review and approve the new "
                "payload explicitly"))
    if result.get("status") == "approved":
        from datetime import datetime, timezone

        action.status = HITLActionStatus.APPROVED.value
        action.reviewed_by = str(current_user.id)
        action.reviewed_at = datetime.now(timezone.utc)
        db.commit()
        result["assignment"] = await executor.resume(run_id)
    return result
