"""Public boundary for versioned canvas capabilities.

All authorization is server-side: the canvas owner/author and workspace are
resolved from the authenticated request and the Canvas row. No body field can
grant an operation.
"""
from __future__ import annotations

import logging
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
    assess_operation,
    authorize_canvas,
    bind_connected_dataset,
    bind_dataset,
    calculate_operation,
    current_revision,
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
