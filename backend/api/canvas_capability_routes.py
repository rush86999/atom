"""Public boundary for versioned canvas capabilities.

All authorization is server-side: the canvas owner/author and workspace are
resolved from the authenticated request and the Canvas row. No body field can
grant an operation.
"""
from __future__ import annotations

import logging
import os
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional

from fastapi import Depends, File, HTTPException, UploadFile
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict
from sqlalchemy.orm import Session

from core.auth import User, get_current_user
from core.deployment_audience import require_pilot_user
from core.base_routes import BaseAPIRouter
from core.canvas_capability_service import (
    CapabilityError,
    approve_assessment,
    assess_operation,
    answer_assessment_clarification,
    assessment_authorization,
    assessment_clarification,
    assessment_review_policy,
    clarification_resume_readiness,
    authorize_canvas,
    bind_connected_dataset,
    bind_dataset,
    answer_derive_clarification,
    begin_derive_clarification,
    calculate_operation,
    promote_canvas_teaching,
    propose_canvas_teaching,
    authorize_canvas_employee,
    current_revision,
    decisions_operation,
    derive_operation,
    edit_operation,
    effective_operations,
    export_operation,
    get_dataset,
    get_manifest,
    parse_tabular_upload,
    policy_revision,
    select_operation,
    set_manifest,
)
from core.database import get_db

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/canvas", tags=["canvas_capabilities"], dependencies=[Depends(require_pilot_user)])


class ManifestRequest(BaseModel):
    manifest: Dict[str, Any]


class BindJsonRequest(BaseModel):
    columns: List[str]
    rows: List[List[Any]]
    source: Optional[Dict[str, Any]] = None
    title: Optional[str] = None


class BindConnectedRequest(BaseModel):
    """Catalog reference only.

    Rows, Parquet paths, hashes and permissions are deliberately absent. The
    server resolves all of them from the authenticated workspace catalog.
    """

    model_config = ConfigDict(extra="forbid")

    dataset_name: Optional[str] = None
    source: Optional[str] = None
    external_id: Optional[str] = None
    sheet_name: Optional[str] = None
    source_version: Optional[str] = None
    subject_field: Optional[str] = None
    measure_field: Optional[str] = None
    title: Optional[str] = None


class AskRequest(BaseModel):
    ask: str = ""
    max_subjects: Optional[int] = None


class DeriveRequest(BaseModel):
    """No values and no total: derive reads the authoritative canvas snapshot.

    ``extra='forbid'`` means a browser-supplied total, hidden field or
    read-only widget value is rejected before the service is called.
    """

    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    manifest_revision: str
    source_version: str


class DeriveAnswer(BaseModel):
    model_config = ConfigDict(extra="forbid")

    row: int
    field_id: str
    value: Any


class DeriveAnswerRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    expected_revision: int
    answers: List[DeriveAnswer]


class CanvasAssignRequest(BaseModel):
    """Start an assignment from the current server-issued receipt.

    The body carries revisions and optional declared-action IDs only. Rows,
    totals and action payloads are rebuilt from the authoritative canvas.
    """

    model_config = ConfigDict(extra="forbid")

    objective: str = ""
    agent_id: Optional[str] = None
    expected_revision: int
    manifest_revision: str
    source_version: str
    action_ids: List[str] = []
    conversation_id: Optional[str] = None
    deliverable_kind: Optional[str] = None
    deliverable_title: str = ""


class TeachingProposalRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    lesson: str
    topic: str = "canvas"
    applies_to: List[str] = []
    format_spec: Dict[str, Any] = {}
    conditions: Dict[str, Any] = {}
    context: Dict[str, Any] = {}
    agent_id: Optional[str] = None
    receipt_digest: str = ""
    expected_revision: int
    manifest_revision: str
    source_version: str


class TeachingPromoteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")

    approved: bool
    reason: str = ""
    expected_revision: int
    manifest_revision: str
    source_version: str


class EditRequest(BaseModel):
    edits: List[Dict[str, Any]]
    expected_revision: Optional[int] = None


def _canvas(db: Session, canvas_id: str, user: User):
    from sqlalchemy import desc
    from core.models import Canvas, CanvasAudit

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is None:
        raise CapabilityError("not_found", "Canvas not found.", 404)
    latest = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas_id)
        .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
        .first()
    )
    if latest is not None and latest.action_type == "delete":
        raise CapabilityError("not_found", "Canvas is deleted.", 404)
    authorize_canvas(db, canvas, user)
    return canvas


def _error(exc: CapabilityError) -> JSONResponse:
    return JSONResponse(
        status_code=exc.status_code,
        content={
            "success": False,
            "error": {
                "code": exc.code,
                "message": exc.message,
                **exc.extra,
            },
        },
    )


@router.get("/{canvas_id}/capability")
async def read_capability(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        manifest = get_manifest(canvas)
        dataset = get_dataset(canvas)
        return {
            "success": True,
            "canvas_id": canvas.id,
            "canvas_type": canvas.canvas_type,
            "manifest": manifest,
            "operations": effective_operations(canvas, manifest),
            "policy_revision": policy_revision(manifest) if manifest else None,
            "revision": current_revision(canvas),
            # Existing read consumers see the review state, so none of them
            # can treat the assessment as authorized by omission.
            "review_policy": assessment_review_policy(),
            "authorization": assessment_authorization(canvas, db=db),
            "dataset": {
                "columns": dataset.get("columns") or [],
                "row_count": len(dataset.get("rows") or []),
                "source": dataset.get("source") or {},
            },
        }
    except CapabilityError as exc:
        return _error(exc)


@router.put("/{canvas_id}/capability/manifest")
async def put_capability_manifest(
    canvas_id: str,
    request: ManifestRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return set_manifest(db, canvas, current_user, request.manifest)
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/bind")
async def bind_capability_file(
    canvas_id: str,
    file: UploadFile = File(...),
    title: Optional[str] = None,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        manifest = get_manifest(canvas)
        if not manifest:
            raise CapabilityError("not_capability_canvas", "Set a capability manifest first.")
        if "bind" not in (manifest.get("operations") or []):
            raise CapabilityError("unsupported_operation", "Bind is not declared.")
        content = await file.read()
        columns, rows = parse_tabular_upload(file.filename or "dataset.csv", content)
        return bind_dataset(
            db, canvas, current_user, columns, rows,
            source={"file_name": file.filename or "dataset"},
            title=title or file.filename,
            verified_file_sha256=__import__("hashlib").sha256(content).hexdigest(),
        )
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/bind-json")
async def bind_capability_json(
    canvas_id: str,
    request: BindJsonRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        manifest = get_manifest(canvas)
        if not manifest:
            raise CapabilityError("not_capability_canvas", "Set a capability manifest first.")
        if "bind" not in (manifest.get("operations") or []):
            raise CapabilityError("unsupported_operation", "Bind is not declared.")
        return bind_dataset(
            db, canvas, current_user, request.columns, request.rows,
            source=request.source, title=request.title,
        )
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/bind-connected")
async def bind_capability_connected(
    canvas_id: str,
    request: BindConnectedRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return bind_connected_dataset(
            db, canvas, current_user,
            dataset_name=request.dataset_name,
            source=request.source,
            external_id=request.external_id,
            sheet_name=request.sheet_name,
            expected_version=request.source_version,
            subject_field=request.subject_field,
            measure_field=request.measure_field,
            title=request.title,
        )
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/select")
async def capability_select(
    canvas_id: str,
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return select_operation(db, canvas, current_user, request.ask)
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/calculate")
async def capability_calculate(
    canvas_id: str,
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return calculate_operation(db, canvas, current_user, request.ask)
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/derive")
async def capability_derive(
    canvas_id: str,
    request: DeriveRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        try:
            return derive_operation(
                db, canvas, current_user,
                expected_revision=request.expected_revision,
                manifest_revision_value=request.manifest_revision,
                source_version=request.source_version,
            )
        except CapabilityError as exc:
            if exc.code != "missing_required_value":
                raise
            clarification = begin_derive_clarification(
                db, canvas, current_user, exc,
                expected_revision=request.expected_revision,
                manifest_revision_value=request.manifest_revision,
                source_version=request.source_version,
            )
            return {
                "success": True,
                "operation": "derive",
                "status": "clarification",
                "clarification": clarification,
                "revision": current_revision(canvas),
            }
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/derive/{clarification_id}/answer")
async def capability_derive_answer(
    canvas_id: str,
    clarification_id: str,
    request: DeriveAnswerRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return answer_derive_clarification(
            db, canvas, current_user, clarification_id,
            [item.model_dump() for item in request.answers],
            expected_revision=request.expected_revision,
            raise_on_refusal=True,
        )
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/assign")
async def capability_assign(
    canvas_id: str,
    request: CanvasAssignRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        manifest = get_manifest(canvas)
        if not manifest:
            raise CapabilityError(
                "not_capability_canvas",
                "This canvas has no capability manifest.")
        try:
            receipt = derive_operation(
                db, canvas, current_user,
                expected_revision=request.expected_revision,
                manifest_revision_value=request.manifest_revision,
                source_version=request.source_version,
            )
        except CapabilityError as exc:
            if exc.code == "missing_required_value":
                return _error(exc)
            raise
        declared = {
            str(item.get("id") or ""): dict(item)
            for item in (manifest.get("actions") or [])
            if isinstance(item, dict)
        }
        action_ids = list(request.action_ids or declared.keys())
        unknown = sorted(set(action_ids) - set(declared))
        if unknown:
            raise CapabilityError(
                "unsupported_action",
                "The requested action(s) are not declared on this canvas: "
                + ", ".join(unknown),
                409,
            )
        objective = str(request.objective or "").strip() or (
            f"Complete the canvas {canvas.name or canvas.id}")
        employee_id = str(
            request.agent_id
            or (manifest.get("teaching_binding") or {}).get("agent_id")
            or "").strip()
        if employee_id:
            authorize_canvas_employee(db, current_user, employee_id)
        from core.canvas_assignment import build_canvas_assignment_plan
        from core.goals.goal_run_service import GoalRunService
        from core.goals.goal_service import GoalService
        from core.task_lifecycle import TaskLifecycle
        from core.assignment_executor import AssignmentExecutor

        workspace_id = str(current_user.workspace_id or "default")
        tenant_id = str(current_user.tenant_id or "default")
        deliverable = None
        teaching_snapshot = None
        if request.deliverable_kind:
            kind = str(request.deliverable_kind).strip().lower()
            if kind not in {"document", "spreadsheet", "presentation"}:
                raise CapabilityError(
                    "unsupported_deliverable",
                    "The canvas artifact kind must be document, spreadsheet "
                    "or presentation.",
                    409,
                )
            from core.artifact_teaching import resolve_artifact_teaching
            from core.assignment_plan import new_teaching_snapshot
            resolved = resolve_artifact_teaching(
                db, employee_id, kind,
                task_context={"canvas_id": canvas.id},
                workspace_id=workspace_id,
            )
            teaching_snapshot = new_teaching_snapshot(
                revision=str(resolved.get("revision") or ""),
                effective_lesson_ids=[
                    {"id": item.get("id"),
                     "revision": item.get("revision") or 1}
                    for item in (resolved.get("sources") or [])
                    if isinstance(item, dict) and item.get("id")
                ],
                matched_context={"canvas_id": canvas.id},
                output_requirements=dict(resolved.get("spec") or {}),
                source_versions={
                    "canvas": request.source_version,
                    "manifest": request.manifest_revision,
                },
            )
            extension = {
                "document": ".docx", "spreadsheet": ".xlsx",
                "presentation": ".pptx",
            }[kind]
            output_root = Path(
                os.getenv("ATOM_ASSIGNMENT_OUTPUT_DIR")
                or os.getenv("ATOM_OFFICE_DIR")
                or os.path.join("data", "office", "assignments"))
            output_root.mkdir(parents=True, exist_ok=True)
            artifact_path = output_root / (
                f"canvas-{canvas.id}-{uuid.uuid4().hex[:8]}{extension}")
            deliverable = {
                "kind": kind,
                "path": str(artifact_path),
                "title": str(
                    request.deliverable_title or objective),
            }
        plan = build_canvas_assignment_plan(
            canvas, manifest, receipt,
            objective=objective, employee_id=employee_id,
            workspace_id=workspace_id, tenant_id=tenant_id,
            action_ids=action_ids,
            requester_id=str(current_user.id or ""),
            deliverable=deliverable,
            teaching_snapshot=teaching_snapshot,
        )
        runs = GoalRunService(
            workspace_id=workspace_id, tenant_id=tenant_id)
        goals = GoalService(
            workspace_id=workspace_id, tenant_id=tenant_id)
        executor = AssignmentExecutor(TaskLifecycle(runs, goals))
        conversation_id = str(
            request.conversation_id or f"canvas-{canvas.id}")
        created = executor.create_assignment(
            conversation_id, objective, assignment=plan)
        started = await executor.execute(created["run_id"])
        return {
            "success": True,
            "run_id": created["run_id"],
            "assignment": started.get("assignment") or {},
            "receipt_digest": receipt["input_receipt"]["digest"],
            "action_ids": action_ids,
        }
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/teaching/propose")
async def capability_teaching_propose(
    canvas_id: str,
    request: TeachingProposalRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return {
            "success": True,
            "proposal": propose_canvas_teaching(
                db, canvas, current_user, request.model_dump(),
                expected_revision=request.expected_revision,
                manifest_revision_value=request.manifest_revision,
                source_version=request.source_version,
            ),
        }
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/teaching/{proposal_id}/promote")
async def capability_teaching_promote(
    canvas_id: str,
    proposal_id: str,
    request: TeachingPromoteRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return promote_canvas_teaching(
            db, canvas, current_user, proposal_id,
            approved=request.approved,
            expected_revision=request.expected_revision,
            manifest_revision_value=request.manifest_revision,
            source_version=request.source_version,
            reason=request.reason,
        )
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/assess")
async def capability_assess(
    canvas_id: str,
    request: AskRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return await assess_operation(
            db, canvas, current_user, request.ask,
            max_subjects=request.max_subjects,
        )
    except CapabilityError as exc:
        return _error(exc)


class ClarifyRequest(BaseModel):
    answers: List[Dict[str, Any]]


@router.post("/{canvas_id}/capability/assess/{execution_id}/clarify")
async def capability_clarify(
    canvas_id: str,
    execution_id: str,
    request: ClarifyRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Answer a durable clarification, then resume the same work.

    The obligation keeps the original objective, request identity, source and
    teaching revisions. Once every requirement is answered the assessment is
    re-dispatched against the same canvas and policy; the new execution
    invalidates the old approval.
    """
    try:
        canvas = _canvas(db, canvas_id, current_user)
        result = answer_assessment_clarification(
            db, canvas, current_user, execution_id, request.answers)
        if not result.get("ready_to_resume"):
            return result
        # Re-read and re-validate immediately before dispatch: a policy/source/
        # manifest change between recording the answer and resuming must not
        # silently reuse the answer under the new rules.
        canvas = _canvas(db, canvas_id, current_user)
        readiness = clarification_resume_readiness(canvas)
        if not readiness.get("ready"):
            return {
                "success": False,
                "canvas_id": canvas.id,
                "state": readiness.get("state"),
                "outcome": "refuse",
                "stale": readiness.get("stale") or [],
                "clarification": assessment_clarification(canvas),
                "ready_to_resume": False,
            }
        original = (result.get("clarification") or {}).get(
            "request", {}).get("ask") or "Assess every selected row."
        resumed = await assess_operation(
            db, canvas, current_user, original,
            clarification_answers=result["clarification"]["requirements"],
            clarification_revisions=readiness.get("accepted_revisions"))
        resumed["clarification_resumed"] = True
        return resumed
    except CapabilityError as exc:
        return _error(exc)


@router.get("/{canvas_id}/capability/decisions")
async def capability_decisions(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Downstream use of an assessment's decisions.

    Refuses with ``review_required`` / ``stale_assessment`` unless the current
    assessment is certified without unresolved requirements or a human
    approved exactly this execution at the same source/policy revisions.
    """
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return decisions_operation(canvas, db=db, user=current_user)
    except CapabilityError as exc:
        return _error(exc)


@router.get("/{canvas_id}/capability/authorization")
async def capability_authorization(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return {
            "success": True,
            "canvas_id": canvas.id,
            "authorization": assessment_authorization(canvas, db=db),
        }
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/assess/{execution_id}/approve")
async def capability_approve_assessment(
    canvas_id: str,
    execution_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Human approval bound to one exact assessment."""
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return approve_assessment(db, canvas, current_user, execution_id)
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/edit")
async def capability_edit(
    canvas_id: str,
    request: EditRequest,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return edit_operation(
            db, canvas, current_user, request.edits, request.expected_revision,
        )
    except CapabilityError as exc:
        return _error(exc)


@router.post("/{canvas_id}/capability/export")
async def capability_export(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    try:
        canvas = _canvas(db, canvas_id, current_user)
        return export_operation(db, canvas, current_user)
    except CapabilityError as exc:
        return _error(exc)
