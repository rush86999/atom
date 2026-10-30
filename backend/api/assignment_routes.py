"""Durable assignment status, resume, approval and cancellation.

The UI reads this durable projection; it never reconstructs progress from
chat transcript wording. Scope is the authenticated workspace/tenant and the
run's own workspace binding.
"""
from __future__ import annotations

import json
import mimetypes
import os
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
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
import core.assignment_teaching  # noqa: F401,E402  (installs taught-calc schema)
from core.assignment_teaching import (  # noqa: E402
    TaughtCalculationError,
    build_taught_calculation,
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


class AssignmentMappingCorrection(BaseModel):
    concept: str
    expected_revision: int
    column: str
    unit: str = ""
    evidence: str = ""
    # Optional identity when the same concept is confirmed on more than one
    # sheet or source version. Never used to widen the lookup.
    sheet: str = ""
    source_version: str = ""


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
    recipient: Optional[str] = None,
    task_scope: Optional[str] = None,
    now: Optional[str] = None,
) -> Dict[str, Any]:
    from core.artifact_teaching import resolve_artifact_teaching

    merged: Dict[str, Any] = {}
    sources: List[Dict[str, Any]] = []
    revisions: List[str] = []
    field_mappings: List[Dict[str, Any]] = []
    unresolved: List[Dict[str, Any]] = []
    conflicts: List[Dict[str, Any]] = []
    for output_type in sorted(set(output_types)):
        resolution = resolve_artifact_teaching(
            db, agent_id, output_type,
            recipient=recipient,
            task_scope=task_scope,
            task_context=task_context or {},
            workspace_id=workspace_id or "default",
            now=now,
        )
        status = str(resolution.get("status") or "")
        if status in ("needs_context", "conflict"):
            unresolved.extend(resolution.get("clarifications") or [])
            conflicts.extend(resolution.get("conflicts") or [])
            continue
        merged.update(resolution.get("spec") or {})
        field_mappings.extend(resolution.get("field_mappings") or [])
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
        field_mappings=field_mappings,
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
    # Bootstrap admin rows can carry NULL workspace/tenant columns while the
    # rest of the app resolves them to "default". Compare against the same
    # effective scope so the default employee is selectable on a fresh install.
    workspace_id = current_user.workspace_id or "default"
    tenant_id = current_user.tenant_id or "default"
    if body.employee_id and body.employee_id != current_user.id:
        employee = db.query(User).filter(
            User.id == body.employee_id,
            User.workspace_id == workspace_id,
            User.tenant_id == tenant_id,
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
            AgentRegistry.workspace_id == workspace_id,
            AgentRegistry.tenant_id == tenant_id,
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

    output_types = [
        {
            "document": "document",
            "spreadsheet": "spreadsheet",
            "presentation": "presentation",
            "email_draft": "email",
        }.get(str(item.get("kind") or "").lower(), "")
        for item in body.deliverables
    ]
    if body.outbound:
        output_types.append("email")
    outbound_recipients = list((body.outbound or {}).get("to") or [])
    teaching_recipient = str(
        (outbound_recipients[0] if outbound_recipients else "")
        or (body.task_context or {}).get("recipient") or "") or None
    teaching_scope = str(
        (body.task_context or {}).get("task_scope") or "") or None
    teaching = _teaching_snapshot_for_start(
        db,
        agent_id=body.agent_id,
        workspace_id=current_user.workspace_id or "default",
        output_types=[item for item in output_types if item],
        task_context=body.task_context,
        recipient=teaching_recipient,
        task_scope=teaching_scope,
        now=datetime.now(timezone.utc).isoformat(),
    )
    if body.calculation is None:
        try:
            body.calculation = build_taught_calculation(
                teaching, resolved_sources, body.wait)
        except TaughtCalculationError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={
                    "error": exc.code,
                    "message": str(exc),
                    **dict(exc.detail or {}),
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


@router.get("/sources")
async def list_assignment_sources(
    query: str = "",
    limit: int = 50,
    current_user: User = Depends(get_current_user),
) -> List[Dict[str, Any]]:
    """Authorized catalog sources the ordinary assignment form can name.

    The assignment proposal never accepts a filesystem path. This projection
    is deliberately smaller than the catalog row: no parquet path, no source
    metadata, and only the workspace's active entries.
    """
    from core.assignment_resources import _parquet_schema
    from core.sheet_dataset_service import find_entries_sync

    workspace_id = current_user.workspace_id or "default"
    entries = find_entries_sync(
        query=query,
        workspace_id=workspace_id,
        limit=max(1, min(int(limit or 50), 100)),
    )
    rows: List[Dict[str, Any]] = []
    for entry in entries:
        if str(entry.get("workspace_id") or "") not in ("", workspace_id):
            continue
        parquet_path = str(entry.get("parquet_path") or "")
        numeric_columns: List[str] = []
        if parquet_path and Path(parquet_path).is_file():
            _columns, numeric_columns = _parquet_schema(Path(parquet_path))
        file_name = str(entry.get("file_name") or "")
        kind = "workbook" if file_name.lower().endswith(
            (".xlsx", ".xls", ".xlsm", ".csv")) else "document"
        rows.append({
            "dataset_name": entry.get("dataset_name"),
            "sheet": entry.get("entity_name"),
            "file_name": file_name,
            "source": entry.get("source"),
            "external_id": entry.get("external_id"),
            "source_version": entry.get("content_hash"),
            "kind": kind,
            "columns": list(entry.get("columns") or []),
            "numeric_columns": numeric_columns,
            "row_count": int(entry.get("row_count") or 0),
            "coverage": entry.get("coverage") or {},
            "ingested_at": entry.get("ingested_at"),
        })
    return rows


@router.get("/{run_id}")
async def assignment_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    return _executor(run).status(run_id)


@router.get("/{run_id}/deliverables/{deliverable_id}/download")
async def download_assignment_deliverable(
    run_id: str,
    deliverable_id: str,
    current_user: User = Depends(get_current_user),
):
    """Download an artifact this run owns, without exposing a local path."""
    run = _scoped_run(run_id, current_user)
    detail = _executor(run).status(run_id)
    assignment = detail.get("assignment") or {}
    deliverable = next((
        item for item in assignment.get("deliverables") or []
        if str(item.get("deliverable_id") or "") == deliverable_id), None)
    if deliverable is None:
        raise HTTPException(status_code=404, detail="Deliverable not found")
    raw_path = str(deliverable.get("artifact_path") or "").strip()
    if not raw_path:
        raise HTTPException(status_code=404, detail="Deliverable has no artifact")
    root = Path(os.getenv("ATOM_ASSIGNMENT_OUTPUT_DIR")
                or "data/office/assignments").resolve()
    path = Path(raw_path).resolve()
    if path != root and root not in path.parents:
        raise HTTPException(
            status_code=403,
            detail="Artifact is outside the assignment output store",
        )
    if not path.is_file():
        raise HTTPException(status_code=404, detail="Artifact file is missing")
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        str(path),
        media_type=media,
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


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
    if result.get("status") in ("conflict", "partial"):
        # The reply was retained as a durable conflict or record-specific
        # partial answer and the wait remains open. Do not resume and do not
        # turn it into a generic assignment projection the UI cannot explain.
        return result
    return await executor.resume(run_id)


@router.post("/{run_id}/gaps/{question_id}/resolve")
async def resolve_assignment_gap(
    run_id: str,
    question_id: str,
    body: AssignmentGapResolution,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    record = executor.lifecycle.get_task(run_id) or {}
    question = next((
        item for item in (record.get("task_revision") or {}).get(
            "unresolved") or []
        if item.get("question_id") == question_id), None)
    if question is None:
        raise HTTPException(status_code=404, detail="Gap not found")
    from core.assignment_executor import AssignmentError, resolution_matches

    if question.get("status") != "open":
        if resolution_matches(question.get("resolution"), body.resolution):
            current = executor.status(run_id)
            return {"status": "already_resolved",
                    "assignment": current.get("assignment"),
                    "open_gaps": current.get("open_gaps") or []}
        raise HTTPException(
            status_code=409,
            detail="The gap was already resolved with a different answer")
    if str((record.get("task_revision") or {}).get("authorization")
           or "").lower() == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="The assignment is cancelled; a gap cannot revive it")

    mapping = dict((question.get("inputs") or {}).get("mapping") or {})
    parsed: Dict[str, Any] = {}
    if mapping:
        try:
            loaded = json.loads(str(body.resolution))
            parsed = loaded if isinstance(loaded, dict) else {}
        except (TypeError, ValueError):
            parsed = {}
    current_source = None
    if mapping and parsed.get("rejected") is not True:
        source_binding = {}
        for raw_source in (record.get("assignment") or {}).get(
                "sources") or []:
            binding = dict(raw_source.get("binding") or {})
            if str(binding.get("sheet") or "") != str(
                    mapping.get("sheet") or ""):
                continue
            mapped_version = str(mapping.get("source_version") or "")
            if mapped_version and str(
                    binding.get("source_version") or "") != mapped_version:
                continue
            source_binding = binding
            break
        if source_binding:
            try:
                current_source = resolve_assignment_source(
                    db, current_user,
                    {
                        "dataset_name": source_binding.get("dataset_name"),
                        "source": source_binding.get("source"),
                        "external_id": source_binding.get("external_id"),
                        "sheet": source_binding.get("sheet"),
                        "source_version": mapping.get("source_version"),
                    })
            except AssignmentResourceError as exc:
                raise HTTPException(
                    status_code=exc.status,
                    detail={"error": exc.code, "message": str(exc)})

    try:
        result = executor.resolve_gap(
            run_id, question_id,
            resolution=body.resolution,
            resolved_by=str(current_user.id),
            evidence=body.evidence,
            current_source=current_source,
        )
    except AssignmentError as exc:
        # A refused confirmation is a conflict with durable state, not a
        # server failure. resolve_gap validates before any lifecycle write.
        raise HTTPException(status_code=409, detail=str(exc))
    if result.get("status") in ("already_resolved", "rejected_candidates"):
        return result
    return await executor.resume(run_id)


@router.post("/{run_id}/mappings/correct")
async def correct_assignment_mapping(
    run_id: str,
    body: AssignmentMappingCorrection,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Correct a confirmed mapping against the current authorized source.

    The expected mapping revision is required and checked under the lifecycle
    CAS. The route re-resolves the source with the authenticated principal so
    a stale/foreign resource cannot be substituted, then the executor applies
    the mapping change, invalidates only dependent work and resumes it.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    record = executor.lifecycle.get_task(run_id) or {}
    assignment = record.get("assignment") or {}
    concept = str(body.concept or "").strip()
    from core.assignment_executor import (
        AssignmentError,
        select_confirmed_mapping,
    )

    mappings = [
        dict(item) for item in (
            assignment.get("teaching_snapshot") or {}
        ).get("field_mappings") or []
        if isinstance(item, dict)
    ]
    selection, selection_problem = select_confirmed_mapping(
        mappings, concept=concept, sheet=body.sheet,
        source_version=body.source_version)
    if selection_problem == "ambiguous":
        raise HTTPException(
            status_code=409,
            detail=(
                f"more than one confirmed mapping exists for concept "
                f"'{concept}'; name the sheet or source version"))
    if selection is None:
        raise HTTPException(status_code=404, detail="Mapping not found")
    _index, mapping = selection
    current_revision = int(mapping.get("revision") or 1)
    if int(body.expected_revision) != current_revision:
        # Refuse before resolving/reading the source: a stale token must not
        # mutate or even re-enter the resource path.
        raise HTTPException(
            status_code=409,
            detail=(
                f"stale mapping revision: expected "
                f"{body.expected_revision}, current {current_revision}"))
    source_binding = {}
    for raw_source in assignment.get("sources") or []:
        binding = dict(raw_source.get("binding") or {})
        if str(binding.get("sheet") or "") != str(
                mapping.get("sheet") or ""):
            continue
        mapped_version = str(mapping.get("source_version") or "")
        if mapped_version and str(
                binding.get("source_version") or "") != mapped_version:
            continue
        source_binding = binding
        break
    if not source_binding:
        raise HTTPException(
            status_code=409,
            detail="The mapping's authorized source is no longer available")
    try:
        current_source = resolve_assignment_source(
            db, current_user,
            {
                "dataset_name": source_binding.get("dataset_name"),
                "source": source_binding.get("source"),
                "external_id": source_binding.get("external_id"),
                "sheet": source_binding.get("sheet"),
                "source_version": mapping.get("source_version"),
            })
    except AssignmentResourceError as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"error": exc.code, "message": str(exc)})

    try:
        executor.correct_mapping(
            run_id,
            concept=concept,
            expected_revision=body.expected_revision,
            column=body.column,
            unit=body.unit,
            corrected_by=str(current_user.id),
            current_source=current_source,
            evidence=body.evidence,
            sheet=body.sheet,
            source_version=body.source_version,
        )
    except AssignmentError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
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
