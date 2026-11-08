"""Durable assignment status, resume, approval and cancellation.

The UI reads this durable projection; it never reconstructs progress from
chat transcript wording. Scope is the authenticated workspace/tenant and the
run's own workspace binding.
"""
from __future__ import annotations

from core.local_paths import resolve_local_path

import copy
import json
import mimetypes
import os
import time
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

from fastapi import Depends, HTTPException
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.assignment_planner import (
    AssignmentPlanError,
    _registered_action_effect,
    plan_assignment,
    validate_proposed_plan,
)
from core.employee_adaptation import adopt_adaptation, propose_adaptation
from core.employee_patch import PlanPatchError, PlanPatchProposal, apply_plan_patch
from core.employee_proposal import (
    build_employee_context,
    compile_employee_proposal,
    context_from_record,
    employee_job_view,
    objective_identity_hints,
    propose_employee_work,
    validate_employee_proposal,
)
from core.assignment_plan import (
    StepInputError,
    new_teaching_snapshot,
    normalize_standing_authority,
)
from core.task_lifecycle import TaskLifecycleError
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
    build_conversation_calculation,
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


class AssignmentReconciliation(BaseModel):
    verdict: str
    evidence: str
    evidence_ref: Optional[str] = None
    provider_ref: Optional[str] = None


class AssignmentGapResolution(BaseModel):
    resolution: str
    evidence: str = ""


class AssignmentRetry(BaseModel):
    reason: str = "retry a failed step after the cause was repaired"


class AssignmentBudgetExtension(BaseModel):
    max_wall_seconds: Optional[float] = None
    max_steps: Optional[int] = None
    reason: str = "owner extended the assignment budget"


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


class AssignmentReassessment(BaseModel):
    reason: str = ""
    task_context: Dict[str, Any] = {}


class AssignmentInvalidation(BaseModel):
    reason: str = "authorized evidence changed"


class AssignmentExternalResponse(BaseModel):
    response: str
    source: str = ""
    evidence: str = ""
    value: Optional[Any] = None
    # Opaque caller identity for this reply. It is deliberately not stripped,
    # case-folded or otherwise normalized; ``None`` means the legacy omitted-ID
    # path. It is identity, never authentication or authority.
    reply_id: Optional[str] = None


class EmployeeObjectiveStart(BaseModel):
    objective: str
    conversation_id: Optional[str] = None
    agent_id: Optional[str] = None
    employee_id: Optional[str] = None
    sources: List[Dict[str, Any]] = []
    source_scope: Optional[Dict[str, Any]] = None
    task_context: Dict[str, Any] = {}
    authorized_actions: List[str] = ["retrieve"]
    budget: Optional[Dict[str, Any]] = None
    teaching_terms: Dict[str, Any] = {}
    requested_output: Optional[str] = None
    use_model: bool = True


class EmployeeAdvance(BaseModel):
    use_model: bool = True
    max_adaptations: int = 1
    deadline_seconds: float = 240.0


class EmployeeSourceAdd(BaseModel):
    source: Dict[str, Any]
    reason: str = "authorized source added to answer the employee question"


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
    actions: List[Dict[str, Any]] = []
    wait: Optional[Dict[str, Any]] = None
    task_context: Dict[str, Any] = {}
    transport: Optional[str] = None
    proposed_steps: Optional[List[Dict[str, Any]]] = None
    authorized_actions: List[str] = []
    standing_authority: Optional[Dict[str, Any]] = None
    budget: Optional[Dict[str, Any]] = None


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


def _resolve_objective_sources(
    body: "EmployeeObjectiveStart",
    current_user: User,
    db: Session,
) -> List[Dict[str, Any]]:
    """Resolve an objective-only request's authorized source scope."""
    references = [dict(item) for item in (body.sources or [])
                  if isinstance(item, dict)]
    if not references and body.source_scope:
        from core.sheet_dataset_service import find_entries_sync

        scope = dict(body.source_scope or {})
        scope_workspace = str(scope.get("workspace_id") or "").strip()
        workspace_id = current_user.workspace_id or "default"
        if scope_workspace and scope_workspace != workspace_id:
            raise HTTPException(
                status_code=403,
                detail={
                    "error": "resource_workspace_mismatch",
                    "message": "The permitted source scope names a "
                               "different workspace.",
                },
            )
        entries = find_entries_sync(
            query=str(scope.get("query") or ""),
            workspace_id=workspace_id,
            limit=max(1, min(int(scope.get("limit") or 20), 50)),
        )
        try:
            chosen = select_resource_candidates(
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
        if not chosen:
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "resource_discovery_empty",
                    "message": (
                        "No authorized active resource matched the requested "
                        "scope. Name a permitted source or refresh the "
                        "connected catalog."),
                },
            )
        references = [{
            "dataset_name": item.get("dataset_name"),
            "sheet": item.get("entity_name"),
            "source_version": item.get("content_hash"),
            "kind": "workbook" if str(
                item.get("file_name") or "").lower().endswith(
                    (".xlsx", ".xls", ".csv")) else "document",
        } for item in chosen]
    if not references:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "source_scope_required",
                "message": (
                    "An objective-only employee request needs authorized "
                    "source access or a permitted discovery scope."),
            },
        )
    allow_internal = os.getenv("ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS") == "1"
    resolved = []
    for reference in references:
        try:
            resolved.append(resolve_assignment_source(
                db, current_user, reference,
                allow_internal=allow_internal))
        except AssignmentResourceError as exc:
            raise HTTPException(
                status_code=exc.status,
                detail={"error": exc.code, "message": str(exc)})
    return resolved


def _employee_action_views(
    authorized_actions: List[str],
) -> List[Dict[str, Any]]:
    from core.action_registry import action_registry

    views: List[Dict[str, Any]] = []
    for name in authorized_actions:
        name = str(name or "").strip()
        if not name or name in (
                "retrieve", "calculate", "present", "outbound", "send",
                "edit", "delete"):
            continue
        action = action_registry.get_action(name)
        if action is None:
            raise HTTPException(
                status_code=422,
                detail=f"registered action '{name}' is not available")
        views.append({
            "action": name,
            "effect": _registered_action_effect(action),
            "description": getattr(action, "description", "") or "",
        })
    return views


def _employee_llm_for_scope(db: Session, workspace_id: str, tenant_id: str):
    """Build the employee consumer for an already-authorized scope.

    The interactive route has a ``User``; restart recovery only has the run's
    durable workspace/tenant binding. Both paths must use the SAME consumer,
    so the scope-based builder is the single implementation and the route is a
    thin adapter over it.
    """
    try:
        from core.llm_service import LLMService
        return LLMService(
            db=db,
            workspace_id=workspace_id or "default",
            tenant_id=tenant_id or "default",
        )
    except Exception:  # noqa: BLE001 — deterministic fallback remains
        return None


def _employee_llm(current_user: User, db: Session):
    return _employee_llm_for_scope(
        db,
        current_user.workspace_id or "default",
        current_user.tenant_id or "default",
    )


def _employee_provider_model() -> Optional[tuple]:
    """Operator-declared employee serving pin, e.g. ollama:llama3.1:8b."""
    raw = os.getenv("ATOM_EMPLOYEE_PROVIDER_MODEL", "").strip()
    if ":" not in raw:
        return None
    provider, model = raw.split(":", 1)
    provider, model = provider.strip(), model.strip()
    return (provider, model) if provider and model else None


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
    has_proposed_external = any(
        str((step or {}).get("effect") or "") == "external"
        for step in (body.proposed_steps or []))
    if not body.deliverables and not body.outbound and not has_proposed_external:
        raise HTTPException(
            status_code=422,
            detail=(
                "at least one deliverable, outbound action or proposed "
                "external step is required"))
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

    _method_lessons: List[Dict[str, Any]] = []
    if body.calculation is None and body.agent_id:
        from core.conversation_learning import applicable_method_lessons
        from core.student_learning_service import lesson_context_requirements

        _workspace = current_user.workspace_id or "default"
        _method_resolution = applicable_method_lessons(
            db, body.agent_id, body.task_context, workspace_id=_workspace)
        if _method_resolution.get("status") == "conflict":
            raise HTTPException(
                status_code=409,
                detail={
                    "error": "teaching_context_conflict",
                    "message": (
                        "Equally specific taught methods conflict for this "
                        "context; confirm which scope governs."),
                    "lessons": [
                        {"lesson_id": item["entry"].get("id"),
                         "topic": item["entry"].get("topic")}
                        for item in _method_resolution.get("lessons") or []
                    ],
                },
            )
        if _method_resolution.get("status") == "applicable":
            _method_lessons = list(_method_resolution.get("lessons") or [])
            try:
                body.calculation = build_conversation_calculation(
                    _method_lessons[0]["entry"], resolved_sources)
            except TaughtCalculationError as exc:
                raise HTTPException(
                    status_code=exc.status,
                    detail={
                        "error": exc.code,
                        "message": str(exc),
                        **dict(exc.detail or {}),
                    },
                )
        else:
            _requirements = lesson_context_requirements(
                db, body.agent_id, body.task_context,
                workspace_id=_workspace, query=body.objective)
            if _requirements.get("mismatch"):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "teaching_context_mismatch",
                        "message": (
                            "The established task context does not match the "
                            "taught guidance for this assignment."),
                        "conflicts": list(
                            _requirements.get("conflicts") or []),
                    },
                )
            if _requirements.get("needs_context"):
                raise HTTPException(
                    status_code=409,
                    detail={
                        "error": "teaching_context_unresolved",
                        "message": (
                            "Taught guidance cannot govern this assignment "
                            "until the missing context is confirmed."),
                        "missing": list(_requirements.get("missing") or []),
                        "lesson_ids": list(
                            _requirements.get("lesson_ids") or []),
                    },
                )

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
    if _method_lessons:
        _effective = list(teaching.get("effective_lesson_ids") or [])
        for _item in _method_lessons:
            _effective.append({
                "id": _item["entry"].get("id"),
                "revision": _item["entry"].get("revision") or 1,
            })
        teaching["effective_lesson_ids"] = _effective
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
    for action_name in body.authorized_actions:
        action_name = str(action_name or "").strip()
        if action_name and action_name not in accepted_actions:
            accepted_actions.append(action_name)
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
    if body.actions:
        from core.action_registry import action_registry

        for spec in body.actions:
            name = str((spec or {}).get("action") or "").strip()
            action = action_registry.get_action(name)
            if action is None:
                raise HTTPException(
                    status_code=422,
                    detail=f"registered action '{name}' is not available")
            required = ("outbound" if _registered_action_effect(action)
                        == "external" else "retrieve")
            if required not in accepted_actions:
                accepted_actions.append(required)
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
        standing_authority = normalize_standing_authority(
            body.standing_authority, granted_by=current_user.id)
    except Exception as exc:  # noqa: BLE001 — a bad grant is a client error
        raise HTTPException(status_code=422, detail=str(exc))
    try:
        plan = plan_assignment(
            objective=body.objective,
            sources=resolved_sources,
            deliverables=deliverables,
            calculation=body.calculation,
            outbound=body.outbound,
            actions=body.actions,
            wait=body.wait,
            standing_authority=standing_authority,
            budget=body.budget,
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
    except (AssignmentPlanError, StepInputError, TaskLifecycleError) as exc:
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


def _consumed_observation_ids(assignment: Dict[str, Any]) -> set:
    consumed = set()
    for item in assignment.get("patch_history") or []:
        for observed in item.get("observations") or []:
            value = (observed.get("observation_id")
                     if isinstance(observed, dict) else observed)
            if value:
                consumed.add(str(value))
    return consumed


def _mark_wait_reviewed(
    executor: Any, run_id: str, step_id: str,
) -> None:
    """Bound independent-work review to one attempt per durable wait."""
    from core.assignment_plan import step_by_id

    def compute(record, assignment):
        new_plan = copy.deepcopy(assignment)
        step = step_by_id(new_plan, step_id)
        if step is not None and isinstance(step.get("waiting"), dict):
            waiting = dict(step["waiting"])
            waiting["reviewed_at"] = datetime.now(timezone.utc).isoformat()
            waiting["reviewed_by"] = "employee"
            step["waiting"] = waiting
        return new_plan, {}

    try:
        executor.lifecycle.mutate_assignment(
            run_id, compute,
            rationale="employee reviewed independent work during a wait")
    except Exception:  # noqa: BLE001 — review marker is advisory
        pass


def _waiting_observations(
    assignment: Dict[str, Any],
    *,
    allow_reviewed: bool = False,
) -> List[Dict[str, Any]]:
    """Fresh reasoning observation for a durable wait with ready work.

    The observation carries the blocked fact and the operations that remain
    ready. Its id is server-derived from the durable wait, so a consumed wait
    observation cannot drive a second identical proposal.
    """
    observations: List[Dict[str, Any]] = []
    consumed = set()
    for history in assignment.get("patch_history") or []:
        for observed in history.get("observations") or []:
            value = (
                observed.get("observation_id") or observed.get("id")
                if isinstance(observed, dict) else observed)
            if value:
                consumed.add(str(value))
    for step in assignment.get("steps") or []:
        if str(step.get("status") or "") != "waiting":
            continue
        if str(step.get("adapter") or "") != "assignment.wait":
            continue
        waiting = step.get("waiting") or {}
        if waiting.get("reviewed_at") and not allow_reviewed:
            # The employee already considered independent work for this
            # durable wait; only fresh evidence or an explicit user advance
            # may ask again.
            continue
        correlation = str(waiting.get("correlation_id") or "").strip()
        if not correlation:
            continue
        observation_id = f"waiting-{correlation}"
        if observation_id in consumed:
            continue
        from core.employee_proposal import operation_capabilities

        ready = [
            str(item.get("label") or item.get("operation"))
            for item in operation_capabilities(assignment)
            if str(item.get("status") or "") == "ready"
        ]
        observations.append({
            "observation_id": observation_id,
            "kind": "waiting_state",
            "step_id": step.get("step_id"),
            "reason": (
                f"waiting for {waiting.get('fact') or 'an external fact'} "
                f"for {waiting.get('subject') or 'the subject'} from "
                f"{waiting.get('party') or 'the authorized source'}; "
                f"blocks {waiting.get('blocks') or 'dependent work'}; "
                f"ready independent work: {', '.join(ready) or 'none'}"),
        })
        break
    return observations


def _routing_history_entry(
    routing: Any, *, stage: str, attempt_id: Optional[str] = None,
) -> Optional[Dict[str, Any]]:
    """Persist route attribution without raw provider text.

    Requested/served identity is internal audit data; the business-facing
    notice is derived separately and never carries model branding or scores.
    """
    if not isinstance(routing, Mapping):
        return None
    error = routing.get("error")
    error_code = (
        str(error.get("code") or "")
        if isinstance(error, Mapping) else "")
    if not error_code and not routing.get("mode"):
        return None
    return {
        "kind": "employee_route",
        "stage": str(stage or "employee")[:80],
        "attempt_id": str(attempt_id or "")[:120] or None,
        "mode": routing.get("mode"),
        "requested_route": routing.get("requested_route"),
        "served_route": routing.get("served_route"),
        "resolved_model": routing.get("resolved_model"),
        "profile": routing.get("profile"),
        "routing_result_id": routing.get("routing_result_id"),
        "error_code": error_code or None,
    }


def _record_employee_routing(
    executor: Any, run_id: str, routing: Any, *,
    stage: str, attempt_id: Optional[str] = None,
) -> None:
    entry = _routing_history_entry(
        routing, stage=stage, attempt_id=attempt_id)
    if entry is None:
        return
    try:
        executor.lifecycle.runs.append_decision(run_id, entry)
    except Exception:  # noqa: BLE001 — attribution cannot break the job
        pass


async def _record_round_business_outcome(
    executor: Any,
    run_id: str,
    result: Any,
    *,
    stage: str,
    assignment: Optional[Mapping[str, Any]] = None,
    extra_features: Optional[Mapping[str, Any]] = None,
    outcome_override: Optional[Mapping[str, Any]] = None,
) -> Optional[Dict[str, Any]]:
    """Annotate the round's model attempt with the task's explicit outcome.

    The outcome is read from durable task state, not from a model label. The
    recorder skips deterministic fallbacks and unknown verdicts; a model-owned
    attempt is credited/debited only when ``objective_met`` is True/False.
    """
    try:
        record = executor.lifecycle.get_task(run_id) or {}
        current = record.get("assignment") or {}
        outcome = (
            dict(outcome_override)
            if outcome_override is not None
            else (current.get("outcome") or {}))
        scope = assignment or current
        from core.employee_routing_feedback import record_business_outcome

        return await record_business_outcome(
            result,
            stage=stage,
            outcome=outcome,
            workspace_id=scope.get("workspace_id"),
            tenant_id=scope.get("tenant_id"),
            extra_features=extra_features,
        )
    except Exception:  # noqa: BLE001 — evidence must not break the job
        return None


def _latest_employee_routing(executor: Any, run_id: str) -> Optional[Dict[str, Any]]:
    try:
        decisions = executor.lifecycle.runs.get_decisions(run_id)
    except Exception:  # noqa: BLE001 — a read view must not crash
        return None
    for decision in reversed(decisions or []):
        if not isinstance(decision, Mapping):
            continue
        if decision.get("kind") != "employee_route":
            continue
        return {
            "mode": decision.get("mode"),
            "requested_route": decision.get("requested_route"),
            "served_route": decision.get("served_route"),
            "resolved_model": decision.get("resolved_model"),
            "profile": decision.get("profile"),
            "error": (
                {"code": decision.get("error_code")}
                if decision.get("error_code") else None),
        }
    return None


async def _record_information_wait(
    executor: Any, run_id: str, entries: List[Dict[str, Any]],
) -> List[Dict[str, Any]]:
    """Persist a targeted obligation and settle its durable idle interval.

    Recording the question IS the wait. Re-entering the existing executor
    opens the assignment-level idle interval when no branch can progress, so a
    prolonged information wait does not consume active wall budget. This is
    the same executor boundary used by ordinary work; it makes no model call
    and adds no task, engine or authority.
    """
    from core.task_lifecycle import add_unresolved_questions

    added = add_unresolved_questions(executor.lifecycle, run_id, entries)
    await executor.execute(run_id, max_steps=12)
    return added


async def _advance_employee_work(
    executor: Any, run_id: str, llm: Any, *, max_rounds: int = 3,
    deadline_seconds: float = 240.0,
    provider_model: Optional[tuple] = None,
    allow_completed_evidence: bool = False,
    force_wait_review: bool = False,
) -> List[Dict[str, Any]]:
    """Run the ordinary objective's typed follow-up through the product.

    The initial proposal chooses read-only evidence. This loop hands the
    durable evidence result back to the same adaptation contract used by the
    served smokes, adopts the compiled work request, and lets the existing
    executor own execution. It never invents evidence or a plan patch.

    ``allow_completed_evidence`` is set only when new authorized evidence
    arrived after a completed job: the employee may reassess that evidence
    and choose supported next work again. Consumed observations are excluded,
    so a completed job with no fresh evidence still stops immediately.
    """
    from core.employee_job_runner import (
        action_views, compile_evidence_read_patch,
        deterministic_unread_evidence_proposal, evidence_observations,
        missing_prerequisite_question, scoped_missing_roles,
        unread_authorized_sources,
    )
    from core.employee_proposal import operation_capabilities
    from core.task_lifecycle import open_unresolved_questions

    deadline = time.monotonic() + max(0.0, float(deadline_seconds))
    rounds: List[Dict[str, Any]] = []
    for _ in range(max_rounds):
        record = executor.lifecycle.get_task(run_id) or {}
        assignment = record.get("assignment") or {}
        status = str(assignment.get("status") or "")
        if status in ("failed", "cancelled"):
            break
        # An open obligation blocks its dependent scope, not the whole job.
        # Independent work may proceed while another capability waits for a
        # material fact; the compiled request and readiness predicates still
        # decide what is executable.
        ready_operations = [
            item for item in operation_capabilities(assignment)
            if str(item.get("status") or "") == "ready"
        ]
        if open_unresolved_questions(record) and not ready_operations:
            break
        observations = evidence_observations(record)
        if not observations and status == "waiting" and ready_operations:
            observations = _waiting_observations(
                assignment, allow_reviewed=force_wait_review)
        if status == "completed" and not (
                allow_completed_evidence and observations):
            break
        # Only new evidence reads can drive a proposal; a business calculation
        # result is not fresh evidence and must not cause the model to repeat
        # the same work.
        context = context_from_record(
            record, action_views=action_views(assignment))
        unread = unread_authorized_sources(assignment)
        # The discovery prompt already tells the model to use
        # context.unread_sources when it is non-empty. Populate that contract
        # from the same bounded source views the model can already see; this
        # does not add authority or raw content.
        unread_views = [
            dict(source) for source in context.get("sources") or []
            if isinstance(source, Mapping) and not source.get("read")
        ]
        if unread_views:
            context["unread_sources"] = unread_views
            context["unread_source_count"] = len(unread_views)
        waiting_open = any(
            str(step.get("status") or "") == "waiting"
            and str(step.get("adapter") or "") == "assignment.wait"
            for step in assignment.get("steps") or [])
        # Discovery continuation: let the model choose an additional read from
        # the retained handles when no supported operation is ready yet, or
        # when a declared prerequisite is a business record that the remaining
        # authorized scope can still supply. The compiler validates the handle;
        # no upload or new authority.
        needs_more_evidence = any(
            str(item.get("status") or "") in (
                "unavailable", "missing", "ambiguous")
            for item in context.get("available_business_operations") or []
            if isinstance(item, dict))
        if unread and (
                not context.get("work_request_schemas")
                or (needs_more_evidence and not waiting_open)):
            remaining = max(0.0, deadline - time.monotonic())
            discovery = await propose_employee_work(
                context, llm_service=llm,
                deadline_seconds=remaining,
                provider_model=provider_model)
            proposal = discovery.get("proposal") or {}
            round_record = {
                "source": discovery.get("source"),
                "technical_fallback": discovery.get(
                    "technical_fallback", False),
                "decision": "evidence_read",
                "errors": discovery.get("errors") or [],
                "failure_stage": discovery.get("failure_stage"),
                "attempt_id": discovery.get("attempt_id"),
                "routing": discovery.get("routing"),
                "unread_source_count": len(unread),
                "proposal_kind": proposal.get("proposal_kind"),
                "proposal_reason": proposal.get("reason"),
                "proposal_sources": [
                    read.get("source_id")
                    for read in proposal.get("evidence_reads") or []
                ],
                "proposal_clarification": (
                    proposal.get("clarification") or {}),
                "observation_ids": [
                    item["observation_id"] for item in observations],
            }
            rounds.append(round_record)
            _record_employee_routing(
                executor, run_id, discovery.get("routing"),
                stage="employee_evidence_selection",
                attempt_id=discovery.get("attempt_id"))
            reads = list(proposal.get("evidence_reads") or [])

            def _compile_reads(candidate):
                try:
                    compiled = compile_evidence_read_patch(
                        assignment, candidate, context)
                except Exception as exc:  # noqa: BLE001 - typed refusal
                    round_record.setdefault(
                        "adoption_errors", []).append(
                            f"{type(exc).__name__}: {exc}")
                    return None
                round_record.setdefault("selected_sources", []).extend(
                    compiled.get("selected") or [])
                return compiled

            compiled = _compile_reads(proposal) if reads else None
            if compiled is None or not compiled.get("patch"):
                # One bounded repair sees only the unread handles, so the
                # model cannot repeat a source it already read. It still
                # selects through the same proposal/compiler contract.
                repair_sources = [
                    dict(source) for source in context.get("sources") or []
                    if isinstance(source, Mapping) and not source.get("read")
                ]
                remaining = max(0.0, deadline - time.monotonic())
                if repair_sources and remaining > 0:
                    repair_context = dict(context)
                    repair_context["sources"] = repair_sources
                    repair_context["unread_sources"] = repair_sources
                    repair_context["unread_source_count"] = len(
                        repair_sources)
                    repair_context["repair"] = (
                        "Select only from the unread authorized sources.")
                    repaired = await propose_employee_work(
                        repair_context, llm_service=llm,
                        deadline_seconds=remaining,
                        provider_model=provider_model)
                    repair_proposal = repaired.get("proposal") or {}
                    round_record["repair_source"] = repaired.get("source")
                    round_record["repair_sources"] = [
                        read.get("source_id")
                        for read in repair_proposal.get("evidence_reads") or []
                    ]
                    if repair_proposal.get("evidence_reads"):
                        repaired_compiled = _compile_reads(repair_proposal)
                        if (repaired_compiled
                                and repaired_compiled.get("patch")):
                            compiled = repaired_compiled
                            round_record["repair"] = "unread_scope"
                if compiled is None or not compiled.get("patch"):
                    # The authorized scope still has unread handles. A model
                    # proposal that only re-reads known sources (or asks
                    # without reading) must not become a user question while
                    # the scope can satisfy the need. This fallback is labeled
                    # and uses the same handle/compiler path; it grants no new
                    # permission.
                    fallback_proposal = deterministic_unread_evidence_proposal(
                        unread)
                    if fallback_proposal:
                        round_record["fallback"] = (
                            "deterministic_unread_scope")
                        fallback_compiled = _compile_reads(fallback_proposal)
                        if (fallback_compiled
                                and fallback_compiled.get("patch")):
                            compiled = fallback_compiled
            if compiled is not None and compiled.get("patch"):
                try:
                    adopted = apply_plan_patch(
                        executor.lifecycle, run_id, compiled["patch"],
                        rationale=(
                            "employee selected additional authorized evidence"))
                except Exception as exc:  # noqa: BLE001
                    round_record["adoption_error"] = (
                        f"{type(exc).__name__}: {exc}")
                    break
                round_record["adoption_status"] = adopted.get("status")
                execution = await executor.execute(run_id, max_steps=12)
                round_record["execution_status"] = (
                    (execution.get("assignment") or {}).get("status"))
                round_record["evaluation"] = (
                    await _record_round_business_outcome(
                        executor, run_id, discovery,
                        stage="employee_evidence_selection",
                        assignment=assignment,
                        extra_features={
                            "adoption_status": adopted.get("status"),
                            "selected_sources": list(
                                round_record.get("selected_sources") or []),
                            "attempt_id": round_record.get("attempt_id"),
                            "repair_source": round_record.get(
                                "repair_source"),
                            "repair_sources": list(
                                round_record.get("repair_sources") or []),
                        }))
                if round_record["execution_status"] in (
                        "completed", "failed", "cancelled"):
                    break
                continue
            round_record["progress"] = "no_progress"
            fallback = missing_prerequisite_question(context)
            if fallback:
                await _record_information_wait(
                    executor, run_id, [fallback])
                round_record["obligation"] = fallback
                round_record["obligation_source"] = (
                    "deterministic_missing_prerequisite")
            break
        if not observations:
            break
        proposal_result = await propose_adaptation(
            context, observations, assignment=assignment, llm_service=llm,
            provider_model=provider_model,
            deadline=deadline)
        for observed in observations:
            if observed.get("kind") == "waiting_state" and observed.get(
                    "step_id"):
                _mark_wait_reviewed(
                    executor, run_id, str(observed["step_id"]))
        proposal = proposal_result.get("proposal") or {}
        round_record = {
            "source": proposal_result.get("source"),
            "technical_fallback": proposal_result.get(
                "technical_fallback", False),
            "decision": proposal.get("decision"),
            "errors": proposal_result.get("errors") or [],
            "failure_stage": proposal_result.get("failure_stage"),
            "attempt_id": proposal_result.get("attempt_id"),
            "routing": proposal_result.get("routing"),
            "observation_ids": [item["observation_id"]
                                for item in observations],
        }
        rounds.append(round_record)
        _record_employee_routing(
            executor, run_id, proposal_result.get("routing"),
            stage="employee_adaptation",
            attempt_id=proposal_result.get("attempt_id"))
        if proposal_result.get("source") == "model_wait_choice":
            # A parsed wait/clarify/retain is not a business success. Record
            # the decision's policy state before any adoption branch; a later
            # explicit task outcome may annotate the same generation.
            round_record["evaluation"] = await _record_round_business_outcome(
                executor, run_id, proposal_result,
                stage="employee_wait_choice", assignment=assignment,
                outcome_override={"objective_met": None},
                extra_features={
                    "attempt_id": round_record.get("attempt_id"),
                    "business_decision": (
                        proposal_result.get("business_decision")
                        or proposal.get("decision") or "wait"),
                })
        if not proposal or proposal.get("decision") in ("retain",):
            question = missing_prerequisite_question(assignment)
            if question and not open_unresolved_questions(
                    executor.lifecycle.get_task(run_id) or {}):
                await _record_information_wait(
                    executor, run_id, [question])
                round_record["obligation"] = question
                round_record["obligation_source"] = (
                    "deterministic_missing_prerequisite")
                round_record["progress"] = "no_progress"
            break
        if proposal_result.get("source") not in (
                "model", "model_repaired", "model_compact",
                "model_wait_choice"):
            # A semantic wait rejection returns a deterministic, targeted
            # clarification. It is not model work, but the question must
            # still be persisted so the rejected wait cannot silently
            # abandon the missing prerequisite. Other deterministic
            # fallbacks remain inert here.
            if not (
                    proposal.get("decision") == "clarify"
                    and proposal_result.get("failure_stage")
                    == "wait_choice_policy"):
                break
        if proposal.get("decision") == "clarify":
            clarification = proposal.get("clarification") or {}
            question = str(clarification.get("question") or "").strip()
            if not question:
                # A bare "clarify" is not actionable. Fall back to the
                # capability's declared missing prerequisite instead of
                # silently abandoning the objective.
                fallback = missing_prerequisite_question(assignment)
                if fallback and not open_unresolved_questions(
                        executor.lifecycle.get_task(run_id) or {}):
                    await _record_information_wait(
                        executor, run_id, [fallback])
                    round_record["obligation"] = fallback
                    round_record["obligation_source"] = (
                        "deterministic_empty_clarification")
                    round_record["progress"] = "no_progress"
                break
            if question:
                missing = [
                    dict(item) for item in (
                        context.get("missing_prerequisites") or [])
                    if isinstance(item, Mapping)
                ]
                chosen = next((
                    item for item in missing
                    if str(item.get("question_hint") or "").strip()
                    == question), None)
                if chosen is None and missing:
                    chosen = next((
                        item for item in missing
                        if str(item.get("operation") or "").replace(
                            "_", " ") in question.lower()), missing[0])
                entry = {
                    "kind": "business_decision",
                    "question": question,
                    "concept": clarification.get("concept") or None,
                    "reason": clarification.get("unblocks") or None,
                    "next_action": "Confirm the missing business fact.",
                    "next_retrieval": clarification.get("unblocks") or None,
                }
                if chosen:
                    # Scope the durable obligation to the fact this question
                    # explicitly requests. A capability missing two roles keeps
                    # the unrequested role blocking (it is still absent from
                    # the compiler's role binding); it must not become part of
                    # this question's settlement identity.
                    requested_roles = scoped_missing_roles(
                        chosen, clarification)
                    entry["kind"] = "missing_evidence"
                    entry["concept"] = (
                        entry["concept"] or chosen.get("operation"))
                    entry["item"] = chosen.get("label")
                    entry["missing_roles"] = list(requested_roles)
                    entry["inputs"] = {
                        "operation": chosen.get("operation"),
                        "missing": list(requested_roles),
                        "known_identities": dict(
                            chosen.get("known_identities") or {}),
                    }
                    entry["reason"] = (
                        entry["reason"] or (
                            "missing prerequisite: "
                            + ", ".join(requested_roles)))
                    entry["next_retrieval"] = (
                        chosen.get("question_hint")
                        or entry["next_retrieval"])
                await _record_information_wait(
                    executor, run_id, [entry])
            round_record["clarification"] = clarification
            break
        if proposal.get("decision") not in ("replan", "work_request"):
            break
        if not proposal.get("work_request"):
            break
        try:
            adopted = adopt_adaptation(
                executor.lifecycle, run_id, proposal,
                rationale="ordinary objective adaptive follow-up")
        except Exception as exc:  # noqa: BLE001 - typed refusal
            round_record["adoption_error"] = f"{type(exc).__name__}: {exc}"
            break
        round_record["adoption_status"] = adopted.get("status")
        round_record["work_request_operation"] = (
            (proposal.get("work_request") or {}).get("operation"))
        if adopted.get("status") != "applied":
            break
        execution = await executor.execute(run_id, max_steps=12)
        round_record["execution_status"] = (
            (execution.get("assignment") or {}).get("status"))
        round_record["evaluation"] = await _record_round_business_outcome(
            executor, run_id, proposal_result,
            stage="employee_adaptation", assignment=assignment,
            extra_features={
                "adoption_status": adopted.get("status"),
                "work_request_operation": (
                    (proposal.get("work_request") or {}).get("operation")),
                "repair": proposal_result.get("repair"),
                "attempt_id": round_record.get("attempt_id"),
            })
        if round_record["execution_status"] in (
                "completed", "failed", "cancelled"):
            break
    return rounds


@router.post("/from-objective")
async def start_employee_objective(
    body: EmployeeObjectiveStart,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Start useful employee work from an objective, without a supplied plan.

    The reasoning consumer may choose authorized read-only evidence work or
    one targeted business clarification. The existing assignment planner
    compiles the proposal and AssignmentExecutor remains the sole driver.
    """
    if not str(body.objective or "").strip():
        raise HTTPException(status_code=422, detail="objective is required")
    workspace_id = current_user.workspace_id or "default"
    tenant_id = current_user.tenant_id or "default"
    employee = current_user
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

    resolved_sources = _resolve_objective_sources(body, current_user, db)
    action_views = _employee_action_views(body.authorized_actions)
    teaching = _teaching_snapshot_for_start(
        db,
        agent_id=body.agent_id,
        workspace_id=workspace_id,
        output_types=[],
        task_context=body.task_context,
        now=datetime.now(timezone.utc).isoformat(),
    )
    if body.teaching_terms:
        teaching = dict(teaching)
        teaching["terms"] = {
            **dict(teaching.get("terms") or {}),
            **{str(key): value for key, value in body.teaching_terms.items()},
        }
    context = build_employee_context(
        objective=body.objective,
        employee_id=employee.id,
        agent_id=body.agent_id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        teaching=teaching,
        sources=resolved_sources,
        task_context=body.task_context,
        criteria=[],
        facts=[],
        open_obligations=[],
        authorized_actions=body.authorized_actions,
        action_views=action_views,
        budget=body.budget or {},
    )
    llm = _employee_llm(current_user, db) if body.use_model else None
    provider_model = _employee_provider_model()
    proposal_result = await propose_employee_work(
        context, llm_service=llm, provider_model=provider_model,
        deadline_seconds=float(os.getenv(
            "ATOM_EMPLOYEE_ADVANCE_DEADLINE_SECONDS", "240")))
    checked = validate_employee_proposal(
        proposal_result.get("proposal"), context)
    if not checked["valid"]:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "employee_proposal_invalid",
                "message": "The employee proposal was not executable.",
                "errors": checked["errors"],
            },
        )
    proposal = checked["proposal"]
    compiled = compile_employee_proposal(
        proposal, context, sources=resolved_sources, facts=[])
    if not compiled["valid"]:
        raise HTTPException(
            status_code=422,
            detail={
                "error": "employee_proposal_compile_failed",
                "message": "The employee proposal could not be compiled.",
                "errors": compiled["errors"],
            },
        )
    clarification = (compiled["plan_kwargs"] or {}).get("clarification")
    if (not proposal.get("evidence_reads") and clarification):
        raise HTTPException(
            status_code=409,
            detail={
                "error": "employee_clarification_required",
                "message": clarification.get("question"),
                "clarification": clarification,
                "proposal_source": proposal_result.get("source"),
                "technical_fallback": proposal_result.get(
                    "technical_fallback", False),
            },
        )
    accepted_actions = list(dict.fromkeys(
        ["retrieve", *list(body.authorized_actions or [])]))
    if body.requested_output:
        accepted_actions = list(dict.fromkeys(
            [*accepted_actions, "present"]))
    plan = plan_assignment(
        objective=body.objective,
        sources=list(compiled["plan_kwargs"].get("sources") or []),
        authorized_sources=list(resolved_sources),
        deliverables=[],
        calculation=None,
        outbound=None,
        actions=list(compiled["plan_kwargs"].get("actions") or []),
        wait=None,
        teaching_snapshot=teaching,
        authorized_actions=accepted_actions,
        employee_id=employee.id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        agent_id=body.agent_id,
        budget=body.budget,
        facts=list(compiled["plan_kwargs"].get("facts") or []),
        provenance={
            "conversation_id": body.conversation_id,
            "started_from": "employee_objective",
            "requester_id": current_user.id,
            "proposal_source": proposal_result.get("source"),
            "proposal_reason": proposal.get("reason"),
            "technical_fallback": proposal_result.get(
                "technical_fallback", False),
            "use_model": bool(body.use_model),
            "source_fingerprint": source_fingerprint(resolved_sources),
            "objective_identities": objective_identity_hints(
                body.objective),
        },
    )
    requested_output = str(body.requested_output or "").strip().lower()
    if requested_output:
        from core.assignment_plan import new_deliverable

        if requested_output not in ("document", "presentation"):
            raise HTTPException(
                status_code=422,
                detail=(
                    "requested_output must be document or presentation for "
                    "employee-decided artifact work"))
        artifact_path = allocate_output_path(
            employee, kind=requested_output, title=body.objective,
            assignment_id=f"draft-{uuid.uuid4().hex[:12]}")
        deliverable_id = "del-requested-output"
        plan["deliverables"].append(new_deliverable(
            deliverable_id=deliverable_id,
            kind=requested_output,
            description=body.objective,
            required=True,
            step_id="requested-artifact",
        ))
        plan["provenance"].update({
            "requested_output": requested_output,
            "requested_output_path": artifact_path,
            "requested_output_deliverable_id": deliverable_id,
        })
        plan["completion_criteria"].insert(0, {
            "criterion_id": f"artifact_verified:{deliverable_id}",
            "kind": "artifact_verified",
            "required": True,
            "verifier": "artifact_verified",
            "scope": {"workspace_id": workspace_id},
            "deliverable_id": deliverable_id,
        })
    plan["completion_criteria"].append({
        "criterion_id": "employee_result:objective",
        "kind": "employee_result",
        "required": True,
        "verifier": "employee_result",
        "scope": {"workspace_id": workspace_id},
    })
    executor = _executor({
        "workspace_id": workspace_id,
        "tenant_id": tenant_id,
    })
    record = executor.create_assignment(
        body.conversation_id or f"chat-assignment-{uuid.uuid4().hex[:12]}",
        body.objective,
        assignment=plan,
        employee_id=employee.id,
        workspace_id=workspace_id,
        tenant_id=tenant_id,
        entities=[],
        requested_fields=[],
    )
    run_id = record["run_id"]
    _record_employee_routing(
        executor, run_id, proposal_result.get("routing"),
        stage="employee_proposal",
        attempt_id=proposal_result.get("attempt_id"))
    if clarification:
        await _record_information_wait(
            executor, run_id,
            [{
                "kind": "business_decision",
                "question": clarification.get("question"),
                "concept": clarification.get("concept") or None,
                "reason": clarification.get("unblocks") or None,
                "next_action": "Confirm the missing business fact.",
                "next_retrieval": clarification.get("unblocks") or None,
            }],
        )
    status = await executor.execute(run_id, max_steps=12)
    adaptive_rounds = []
    if llm is not None:
        deadline_seconds = float(os.getenv(
            "ATOM_EMPLOYEE_ADVANCE_DEADLINE_SECONDS", "240"))
        adaptive_rounds = await _advance_employee_work(
            executor, run_id, llm, provider_model=provider_model,
            deadline_seconds=deadline_seconds, max_rounds=4)
        # The follow-up calls the executor again; the response must reflect
        # the resulting steps/status, not the pre-adaptation snapshot.
        status = executor.status(run_id)
        # If no round already evaluated an explicit business outcome, the
        # initial model proposal owns this job's result. A deterministic
        # fallback is skipped by the recorder, never credited as model work.
        if not any(
                isinstance(item, Mapping)
                and isinstance(item.get("evaluation"), Mapping)
                and item["evaluation"].get("recorded")
                for item in adaptive_rounds):
            await _record_round_business_outcome(
                executor, run_id, proposal_result,
                stage="employee_proposal", assignment=plan,
                extra_features={
                    "attempt_id": proposal_result.get("attempt_id"),
                })
    current = executor.lifecycle.get_task(run_id) or {}
    from core.task_lifecycle import open_unresolved_questions
    employee_routing = _latest_employee_routing(executor, run_id)
    job = employee_job_view(
        current.get("assignment") or {},
        record=current,
        open_obligations=open_unresolved_questions(current),
        routing=employee_routing,
    )
    return {
        "run_id": run_id,
        "assignment": status,
        "employee_job": job,
        "proposal": proposal,
        "proposal_source": proposal_result.get("source"),
        "technical_fallback": proposal_result.get(
            "technical_fallback", False),
        "proposal_errors": proposal_result.get("errors") or [],
        "employee_routing": employee_routing,
        "adaptive_rounds": adaptive_rounds,
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
        steps = record["assignment"].get("steps") or []
        required = [step for step in steps if step.get("required", True)]
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
                    for step in steps
                    if step.get("status") in (
                        "running", "waiting", "awaiting_approval")), None),
                "progress": {
                    "completed_steps": sum(
                        1 for step in required
                        if step.get("status") in ("applied", "skipped")),
                    "required_steps": len(required),
                    "waiting_steps": sum(
                        1 for step in steps
                        if step.get("status") in (
                            "waiting", "awaiting_approval")),
                },
            },
        })
    return results


@router.get("/sources")
async def list_assignment_sources(
    query: str = "",
    limit: int = 50,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
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
    existing_files = {
        str(entry.get("file_name") or "").lower()
        for entry in entries if entry.get("file_name")
    }
    seen_source_versions = {
        (str(entry.get("file_name") or "").lower(),
         str(entry.get("content_hash") or ""))
        for entry in entries if entry.get("file_name")
    }
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
    # Ordinary uploaded documents are authorized sources too. They are
    # selected by durable document_id, never by a caller-supplied path.
    from core.models import IngestedDocument

    documents = db.query(IngestedDocument).filter(
        IngestedDocument.workspace_id == workspace_id,
    ).order_by(IngestedDocument.ingested_at.desc()).limit(
        max(1, min(int(limit or 50), 100))).all()
    for row in documents:
        freshness = str(row.freshness_status or "fresh").lower()
        if freshness in ("removed", "superseded", "outdated", "stale"):
            continue
        if query and query.lower() not in str(row.file_name or "").lower():
            continue
        if str(row.file_name or "").lower() in existing_files:
            # A workbook upload also materializes a sheet dataset; expose the
            # tabular source once, not the same file as a text document too.
            continue
        source_key = (
            str(row.file_name or "").lower(),
            str(row.source_content_hash or row.external_id or ""))
        if source_key in seen_source_versions:
            # Repeated uploads of the same authorized file/version must not
            # create duplicate source steps or ambiguous evidence roles.
            continue
        seen_source_versions.add(source_key)
        rows.append({
            "document_id": row.id,
            "dataset_name": None,
            "sheet": None,
            "file_name": row.file_name,
            "source": row.integration_id or "upload",
            "external_id": row.external_id,
            "source_version": row.source_content_hash or row.external_id,
            "kind": "document",
            "columns": [],
            "numeric_columns": [],
            "row_count": 0,
            "coverage": {"known": True, "freshness": freshness},
            "ingested_at": row.ingested_at.isoformat()
            if row.ingested_at else None,
        })
    return rows


@router.get("/{run_id}")
async def assignment_status(
    run_id: str,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    status = executor.status(run_id)
    record = executor.lifecycle.get_task(run_id) or {}
    employee_routing = _latest_employee_routing(executor, run_id)
    status["employee_routing"] = employee_routing
    status["employee_job"] = employee_job_view(
        record.get("assignment") or {},
        record=record,
        open_obligations=status.get("open_gaps") or [],
        routing=employee_routing,
    )
    return status


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
    root = resolve_local_path(os.getenv("ATOM_ASSIGNMENT_OUTPUT_DIR")
                or os.getenv("ATOM_OFFICE_DIR")
                or "data/office/assignments")
    path = resolve_local_path(raw_path)
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


@router.post("/{run_id}/budget")
async def extend_assignment_budget(
    run_id: str,
    body: AssignmentBudgetExtension,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Increase a live assignment's bounded step/wall budget.

    The executor's own failure message tells the owner to increase the budget
    or resolve the work explicitly. This route is that owner action: it never
    restarts the job, grants authority or changes the objective. Existing
    limits can only be raised, never lowered, and the audit fields identify
    the owner and reason on the durable assignment.
    """
    if body.max_wall_seconds is None and body.max_steps is None:
        raise HTTPException(
            status_code=422,
            detail="max_wall_seconds or max_steps is required")
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)

    def compute(record, assignment):
        budget = dict(assignment.get("budget") or {})
        if body.max_wall_seconds is not None:
            budget["max_wall_seconds"] = max(
                float(budget.get("max_wall_seconds") or 0.0),
                min(float(body.max_wall_seconds), 86400.0),
            )
        if body.max_steps is not None:
            budget["max_steps"] = max(
                int(budget.get("max_steps") or 0),
                min(int(body.max_steps), 200),
            )
        budget["budget_extended_by"] = current_user.id
        budget["budget_extended_at"] = datetime.now(
            timezone.utc).isoformat()
        budget["budget_extension_reason"] = str(
            body.reason or "owner extended the assignment budget")[:300]
        assignment["budget"] = budget
        return assignment, {"budget": budget}

    try:
        result = executor.lifecycle.mutate_assignment(
            run_id, compute,
            rationale="owner extended the assignment budget")
    except Exception as exc:  # noqa: BLE001 — durable state remains
        raise HTTPException(status_code=409, detail=str(exc))
    return {
        "assignment": executor.status(run_id),
        "budget": result["budget"],
    }


@router.post("/{run_id}/retry/{step_id}")
async def retry_assignment_step(
    run_id: str,
    step_id: str,
    body: AssignmentRetry,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Retry one failed step as a new attempt, then resume the same run.

    Used when a failure cause (for example an exhausted wall budget during a
    legitimate durable wait) has been repaired. The step's attempt counter and
    the operation history keep the failed attempt visible.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    try:
        executor.retry_step(run_id, step_id, reason=body.reason)
    except Exception as exc:  # noqa: BLE001 — durable state remains
        raise HTTPException(status_code=409, detail=str(exc))
    return await executor.resume(run_id)


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


@router.post("/{run_id}/advance")
async def advance_assignment(
    run_id: str,
    body: EmployeeAdvance,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Continue from applied evidence to model-chosen supported work.

    The initial objective call owns evidence discovery. This endpoint hands
    the accepted observations to the same adaptation consumer, adopts one
    typed work request (or persists one targeted clarification), and advances
    the existing executor. No caller-supplied plan, rows or step mechanics are
    accepted here.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    llm = _employee_llm(current_user, db) if body.use_model else None
    try:
        await executor.execute(run_id, max_steps=12)
        rounds = await _advance_employee_work(
            executor, run_id, llm,
            max_rounds=max(0, min(int(body.max_adaptations), 3)),
            deadline_seconds=max(0.0, float(body.deadline_seconds)),
            provider_model=_employee_provider_model(),
            force_wait_review=True)
        return {
            "run_id": run_id,
            "assignment": executor.status(run_id),
            "rounds": rounds,
        }
    except Exception as exc:  # noqa: BLE001 — durable state remains
        raise HTTPException(status_code=409, detail=str(exc)) from exc


@router.post("/{run_id}/sources")
async def add_assignment_source(
    run_id: str,
    body: EmployeeSourceAdd,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Add one authorized source after a targeted evidence question.

    The source is resolved through the same connected/internal binding as the
    objective start, read by the normal adapter, and then the existing
    adaptive consumer decides whether the new evidence supports business work.
    No rows, expected values or step mechanics are supplied by the caller.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    allow_internal = os.getenv(
        "ATOM_ASSIGNMENT_ALLOW_INTERNAL_PATHS") == "1"
    try:
        resolved = resolve_assignment_source(
            db, current_user, dict(body.source or {}),
            allow_internal=allow_internal)
    except AssignmentResourceError as exc:
        raise HTTPException(
            status_code=exc.status,
            detail={"error": exc.code, "message": str(exc)}) from exc
    record = executor.lifecycle.get_task(run_id) or {}
    assignment = record.get("assignment") or {}
    was_completed = str(assignment.get("status") or "") == "completed"
    # A real change is a different version of the business source this job
    # already depended on: either the same resource id, or the same named
    # file uploaded as a new document version. Adding an unrelated authorized
    # source is not a change and must not make the employee repeat accepted
    # business work.
    def _business_name(binding: Dict[str, Any]) -> str:
        return str(
            binding.get("original_file_name") or binding.get("file_name")
            or "").strip().lower()

    resolved_name = str(
        resolved.get("original_file_name") or resolved.get("file_name")
        or "").strip().lower()
    resolved_version = str(resolved.get("source_version") or "")
    same_resource_previous_version = False
    prior_source_step = None
    for existing_step in assignment.get("steps") or []:
        inputs = (existing_step.get("inputs")
                  if isinstance(existing_step.get("inputs"), dict) else {})
        binding = inputs.get("resource_binding")
        if not isinstance(binding, dict):
            continue
        previous_version = str(binding.get("source_version") or "")
        if previous_version and previous_version == resolved_version:
            continue
        same_resource = str(binding.get("resource_id") or "") == str(
            resolved.get("resource_id") or "")
        same_name = bool(resolved_name) and _business_name(
            binding) == resolved_name
        if same_resource or same_name:
            same_resource_previous_version = True
            if previous_version and previous_version != resolved_version:
                prior_source_step = existing_step
            break
    # A duplicate source addition must not add another read step or cause
    # duplicate arithmetic/effects later. Same resource identity/version is
    # already present: skip the write, but keep the continuation path below
    # available so a delivery that was accepted before an interruption can
    # still finish the same task instead of stranding it.
    existing = None
    for step in assignment.get("steps") or []:
        binding = ((step.get("inputs") or {}).get("resource_binding")
                   if isinstance(step.get("inputs"), dict) else None)
        if not isinstance(binding, dict):
            continue
        if str(binding.get("resource_id") or "") == str(
                resolved.get("resource_id") or "") and str(
                binding.get("source_version") or "") == str(
                resolved.get("source_version") or ""):
            existing = step
            break
    from core.assignment_planner import _source_step
    from core.employee_patch import apply_plan_patch
    import hashlib as _hashlib

    reassessment_rounds: List[Dict[str, Any]] = []
    if existing is not None:
        step = dict(existing)
        status = executor.status(run_id)
        if str((record.get("assignment") or {}).get("status") or "") not in (
                "completed", "failed", "cancelled"):
            # Replaying an accepted source is not a new effect. Run the same
            # executor so any already-compiled work can finish; operation
            # receipts/CAS make this idempotent.
            try:
                status = await executor.execute(run_id, max_steps=12)
            except Exception as exc:  # noqa: BLE001 — durable state remains
                raise HTTPException(
                    status_code=409, detail=str(exc)) from exc
        adopted: Dict[str, Any] = {
            "status": "already_present",
            "reason": "the authorized source version is already present",
            "step_id": step.get("step_id"),
        }
    else:
        # The caller explicitly supplied a newer version of the same
        # authorized source. Reuse the existing source step and its
        # descendants; do not add a second source identity or silently keep
        # the stale cached result. Existing invalidation/CAS preserves the
        # prior result for audit and reopens only the affected branch.
        prior_path = ""
        if prior_source_step is not None:
            prior_inputs = prior_source_step.get("inputs")
            prior_path = str(
                (prior_inputs or {}).get("path") or "") if isinstance(
                    prior_inputs, dict) else ""
        resolved_path = str(resolved.get("path") or "")
        if (prior_source_step is not None and not was_completed
                and prior_path and resolved_path
                and os.path.realpath(prior_path) == os.path.realpath(
                    resolved_path)):
            try:
                executor.invalidate_step(
                    run_id, prior_source_step["step_id"],
                    reason=(
                        "explicitly authorized newer source version; "
                        "re-reading the current accepted source"))
                status = await executor.execute(run_id, max_steps=12)
            except Exception as exc:  # noqa: BLE001 — durable state remains
                raise HTTPException(status_code=409, detail=str(exc)) from exc
            step = prior_source_step
            adopted = {
                "status": "source_replaced",
                "reason": "explicitly authorized newer source version",
                "step_id": step.get("step_id"),
            }
        else:
            indexes = []
            for step in assignment.get("steps") or []:
                step_id = str(step.get("step_id") or "")
                if step_id.startswith("source-"):
                    try:
                        indexes.append(int(step_id.split("-", 1)[1]))
                    except ValueError:
                        pass
            raw_step = _source_step(
                resolved, (max(indexes) if indexes else 0) + 1)
            step = {
                key: raw_step.get(key) for key in (
                    "step_id", "title", "operation_type", "adapter", "depends_on",
                    "inputs", "effect", "requires", "required")
                if raw_step.get(key) is not None
            }
            identity = _hashlib.sha256(json.dumps(
                {"resource_id": resolved.get("resource_id"),
                 "source_version": resolved.get("source_version")},
                sort_keys=True, default=str).encode()).hexdigest()[:16]
            patch = {
                "patch_id": f"source-add-{identity}",
                "base_task_version": int(record.get("task_version") or 0),
                "base_plan_revision": int(assignment.get("plan_revision") or 1),
                "reason": body.reason,
                "observations": [{
                    "kind": "authorized_source_added",
                    "resource_id": resolved.get("resource_id"),
                    "source_version": resolved.get("source_version"),
                }],
                "invalidate_steps": [],
                "remove_steps": [],
                "add_steps": [step],
                "update_steps": [],
                "add_facts": [],
                "set_requires": {},
            }
            try:
                adopted = apply_plan_patch(
                    executor.lifecycle, run_id, patch, rationale=body.reason)
                status = await executor.execute(run_id, max_steps=12)
            except Exception as exc:  # noqa: BLE001 — durable state remains
                raise HTTPException(status_code=409, detail=str(exc)) from exc
    # A genuinely new authorized version on a completed job is fresh
    # evidence: let the same employee adaptation contract decide whether the
    # changed evidence supports more work or a material clarification. The
    # loop only runs for model-driven jobs and only while an unconsumed
    # evidence observation exists, so duplicate adds and calculation-only
    # results stay inert.
    provenance = assignment.get("provenance") or {}
    added_now = next((
        item for item in (
            executor.lifecycle.get_assignment(run_id) or {}).get("steps") or []
        if item.get("step_id") == step.get("step_id")), {})
    if (was_completed and existing is None and same_resource_previous_version
            and str(provenance.get("proposal_source") or "") in (
                "model", "model_repaired")
            and added_now.get("status") == "applied"):
        try:
            llm = _employee_llm(current_user, db)
            reassessment_rounds = await _advance_employee_work(
                executor, run_id, llm, max_rounds=1,
                deadline_seconds=180.0,
                provider_model=_employee_provider_model(),
                allow_completed_evidence=True)
            status = executor.status(run_id)
        except Exception as exc:  # noqa: BLE001 — source add already durable
            reassessment_rounds = [{
                "source": "error",
                "decision": "reassessment_failed",
                "error": f"{type(exc).__name__}: {exc}",
            }]
    # Settle only obligations that this accepted source actually made ready.
    current = executor.lifecycle.get_task(run_id) or {}
    current_assignment = current.get("assignment") or {}
    from core.employee_job_runner import capability_roles_satisfied
    from core.employee_proposal import operation_capabilities
    from core.task_lifecycle import (
        open_unresolved_questions, resolve_unresolved_questions,
    )
    capabilities = {
        str(item.get("operation") or ""): item
        for item in operation_capabilities(current_assignment)
    }
    added_step = next((
        item for item in current_assignment.get("steps") or []
        if item.get("step_id") == step.get("step_id")), {})
    added_data = ((added_step.get("result") or {}).get("data")
                  if isinstance(added_step.get("result"), dict) else {})
    observed_po = str(
        (added_data or {}).get("po_id") or "").strip()
    settled = []
    mismatched = []
    question_ids = []
    for question in open_unresolved_questions(current):
        if question.get("kind") not in (
                "missing_prerequisite", "missing_evidence"):
            continue
        operation = str(
            question.get("operation") or question.get("concept") or "")
        capability = capabilities.get(operation)
        if capability is None:
            continue
        inputs = question.get("inputs") if isinstance(
            question.get("inputs"), dict) else {}
        known = inputs.get("known_identities") if isinstance(
            inputs.get("known_identities"), dict) else {}
        expected_po = str(known.get("purchase_order.po_id") or "").strip()
        if expected_po and observed_po and expected_po != observed_po:
            mismatched.append(question.get("question_id"))
            continue
        requested_roles = [
            str(role) for role in (
                inputs.get("missing")
                or question.get("missing_roles")
                or [])
            if str(role).strip()
        ]
        # Role-scoped settlement: an answer settles the question whose named
        # role(s) it actually supplied. A capability still missing another
        # declared role stays non-ready, so dependent execution remains
        # blocked and the same consumer asks for the next fact. Legacy broad
        # questions (no role scope) keep whole-capability readiness.
        if not capability_roles_satisfied(capability, requested_roles):
            continue
        question_ids.append(str(question.get("question_id")))
    if question_ids:
        settled = resolve_unresolved_questions(
            executor.lifecycle, run_id, question_ids=question_ids,
            resolution=(
                "authorized source "
                f"{resolved.get('resource_id')} version "
                f"{resolved.get('source_version')} supplied the requested "
                "evidence role(s)"))
        status = executor.status(run_id)
    # Source-triggered continuation. A source answer that settled a targeted
    # obligation is itself the wake-up: hand the fresh accepted evidence to
    # the SAME adaptation consumer and executor that /advance uses. A replay
    # whose source was durably accepted before an interruption may have no
    # open question left, so it recovers when the applied source still has an
    # unconsumed evidence observation. Arrival/question settlement alone never
    # marks the business objective complete; only an executed, verified
    # result can.
    continuation_rounds: List[Dict[str, Any]] = []
    current = executor.lifecycle.get_task(run_id) or {}
    current_assignment = current.get("assignment") or {}
    current_status = str(current_assignment.get("status") or "")
    open_after = open_unresolved_questions(current)
    source_step_id = str(step.get("step_id") or "")
    from core.employee_job_runner import evidence_observations
    fresh_source_observation = any(
        str(item.get("step_id") or "") == source_step_id
        for item in evidence_observations(current))
    use_model = provenance.get("use_model", True) is not False
    recovered_replay = (
        existing is not None
        and not open_after
        and fresh_source_observation
        and current_status not in ("completed", "failed", "cancelled"))
    should_continue = (
        use_model
        and not was_completed
        and not reassessment_rounds
        and current_status not in ("completed", "failed", "cancelled")
        and (bool(question_ids) or recovered_replay))
    if should_continue:
        try:
            llm = _employee_llm(current_user, db)
            continuation_rounds = await _advance_employee_work(
                executor, run_id, llm, max_rounds=1,
                deadline_seconds=180.0,
                provider_model=_employee_provider_model())
            status = executor.status(run_id)
        except Exception as exc:  # noqa: BLE001 — source add already durable
            continuation_rounds = [{
                "source": "error",
                "decision": "source_continuation_failed",
                "error": f"{type(exc).__name__}: {exc}",
            }]
    return {**adopted, "assignment": status,
            "resolved_question_ids": [
                item.get("question_id") for item in settled],
            "mismatched_question_ids": [
                item for item in mismatched if item],
            "observed_purchase_order": observed_po or None,
            "reassessment_rounds": reassessment_rounds,
            "continuation_rounds": continuation_rounds}


@router.post("/{run_id}/reassess")
async def reassess_assignment(
    run_id: str,
    body: AssignmentReassessment,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Explicitly adopt corrected teaching for active work.

    Historical results/artifacts stay in the assignment's prior_results.
    Only teaching-dependent steps and their descendants are reopened under a
    new plan revision; current access/authority is rechecked on execution.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    assignment = executor.lifecycle.get_assignment(run_id) or {}
    provenance = assignment.get("provenance") or {}
    agent_id = str(provenance.get("agent_id") or "") or None
    task_context = dict(
        (assignment.get("teaching_snapshot") or {}).get(
            "matched_context") or {})
    task_context.update(dict(body.task_context or {}))
    output_types: List[str] = []
    for item in assignment.get("deliverables") or []:
        mapped = {
            "document": "document", "spreadsheet": "spreadsheet",
            "presentation": "presentation", "email_draft": "email",
            "email": "email",
        }.get(str(item.get("kind") or ""))
        if mapped and mapped not in output_types:
            output_types.append(mapped)
    if not output_types:
        output_types = ["document"]
    recipients = [
        str(item) for item in (
            (assignment.get("provenance") or {}).get("email_to") or [])
        if str(item).strip()]
    try:
        teaching = _teaching_snapshot_for_start(
            db,
            agent_id=agent_id,
            workspace_id=current_user.workspace_id or "default",
            output_types=output_types,
            task_context=task_context,
            recipient=recipients[0] if recipients else None,
            task_scope=str(task_context.get("task_scope") or "") or None,
            now=datetime.now(timezone.utc).isoformat(),
        )
        result = executor.reassess_teaching(
            run_id, teaching,
            reason=body.reason or "explicit reassessment")
        status = await executor.execute(run_id, max_steps=12)
    except (AssignmentPlanError, TaskLifecycleError) as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {**result, "assignment": status}


@router.post("/{run_id}/invalidate/{step_id}")
async def invalidate_assignment_step(
    run_id: str,
    step_id: str,
    body: AssignmentInvalidation,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Explicitly reopen one branch after its evidence changed.

    Prior results/artifacts remain in the audit history. The step and every
    descendant run under a new plan revision, so old approvals/payloads do
    not ride the changed evidence.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    try:
        result = executor.invalidate_step(
            run_id, step_id, reason=body.reason or "evidence changed")
        status = await executor.execute(run_id, max_steps=12)
    except TaskLifecycleError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {**result, "assignment": status}


@router.post("/{run_id}/patch")
async def patch_assignment_plan(
    run_id: str,
    body: PlanPatchProposal,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Adopt one validated plan patch atomically, then advance ready work."""
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    try:
        result = apply_plan_patch(
            executor.lifecycle, run_id, body.model_dump(),
            rationale=body.reason or "explicit employee plan patch")
        status = await executor.execute(run_id, max_steps=12)
    except PlanPatchError as exc:
        raise HTTPException(status_code=409, detail=str(exc))
    return {**result, "assignment": status}


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
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    result = executor.record_external_response(
        run_id, correlation_id,
        response=body.response,
        source=body.source or str(current_user.id),
        evidence=body.evidence,
        value=body.value,
        reply_id=body.reply_id,
    )
    if result.get("status") == "terminal":
        # The run exists and is terminal; the reply is refused rather than
        # matched to a historical wait and woken.
        raise HTTPException(status_code=409, detail=result.get("message"))
    if result.get("status") == "unmatched":
        raise HTTPException(status_code=404, detail=result.get("message"))
    if result.get("status") in (
            "reply_conflict", "reply_identity_conflict",
            "reply_scope_conflict"):
        # One opaque reply identity cannot change material or move to another
        # wait. Refuse before any state transition, wake or execute.
        raise HTTPException(status_code=409, detail=result)
    if result.get("status") in (
            "conflict", "partial", "unavailable", "incomplete"):
        # The reply was retained as a durable conflict or record-specific
        # partial answer and the wait remains open. Do not resume and do not
        # turn it into a generic assignment projection the UI cannot explain.
        return result
    if result.get("status") == "already_applied" or result.get("replayed"):
        # Exact replay (explicit or legacy) is idempotent: it must not execute
        # or advance the same job a second time.
        return result
    resumed = await executor.resume(run_id)
    # An authorized reply can make a previously blocked capability ready.
    # Hand the fresh evidence to the same adaptation contract so the model,
    # not the route, chooses the supported next work.
    if result.get("status") == "resumed":
        assignment = executor.lifecycle.get_assignment(run_id) or {}
        provenance = assignment.get("provenance") or {}
        # A deterministic initial discovery does not make the job
        # non-model-driven: later adaptation rounds may be model-selected.
        # Only an explicit objective start with use_model=false stays offline.
        if provenance.get("use_model", True) is not False:
            llm = _employee_llm(current_user, db)
            rounds = await _advance_employee_work(
                executor, run_id, llm, max_rounds=1,
                deadline_seconds=180.0,
                provider_model=_employee_provider_model(),
                allow_completed_evidence=True)
            if rounds:
                return {**resumed, "adaptive_rounds": rounds}
    return resumed


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


@router.post("/{run_id}/reconcile/{step_id}")
async def reconcile_assignment_step(
    run_id: str,
    step_id: str,
    body: AssignmentReconciliation,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
) -> Dict[str, Any]:
    """Settle one uncertain external effect against durable evidence.

    ``applied`` records completion and advances; ``not_applied`` permits a
    NEW operation on the next resume; ``insufficient`` leaves the uncertain
    state intact and never resends. Evidence is required for every verdict.
    """
    run = _scoped_run(run_id, current_user)
    executor = _executor(run)
    record = executor.lifecycle.get_task(run_id) or {}
    if str((record.get("task_revision") or {}).get("authorization")
           or "").lower() == "cancelled":
        raise HTTPException(
            status_code=409,
            detail="The assignment is cancelled; reconciliation cannot revive it")
    user = db.query(User).filter(User.id == current_user.id).first()
    if user is None or not user_meets_role(user, UserRole.TEAM_LEAD):
        raise HTTPException(
            status_code=403,
            detail="Insufficient reconciliation authority for this assignment")
    try:
        result = executor.reconcile_step(
            run_id, step_id, body.verdict,
            evidence=body.evidence,
            evidence_ref=body.evidence_ref,
            provider_ref=body.provider_ref,
        )
    except Exception as exc:  # noqa: BLE001 — keep the uncertain state
        raise HTTPException(status_code=409, detail=str(exc))
    if body.verdict == "insufficient":
        return result
    result["assignment"] = await executor.resume(run_id)
    return result
