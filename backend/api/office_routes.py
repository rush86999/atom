"""
Office Automation API Routes for Atom

Exposes HTTP endpoints under /api/v1/office for Word, Excel, and PowerPoint
document manipulation, visualization, and canvas synchronization.
"""

import hashlib
import logging
import mimetypes
import os
import re
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, File, Form, HTTPException, Query, UploadFile
from fastapi.responses import FileResponse
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.office_service import OfficeService, _validate_office_path
from core.office_sync_service import OfficeSyncService, _office_path_key
from core.auth import get_current_user, User
from core.deployment_audience import require_pilot_user, validate_audience_config

logger = logging.getLogger(__name__)

# Fail closed before serving if a multi-user audience is declared without
# per-file office authorization.
validate_audience_config()


def get_db_session_dep() -> Session:
    """FastAPI dependency yielding a DB session.

    core.database.get_db_session is a @contextmanager for service-layer use —
    Depends(get_db_session) injects the raw _GeneratorContextManager in
    production (inspector.isgeneratorfunction is False for the wrapper), which
    crashed /present and /sync-update with "'...context manager' has no
    attribute 'query'". Wrap it in a real generator dependency instead;
    tests override this by name.
    """
    with get_db_session() as db:
        yield db


def _require_office_path(file_path: str) -> str:
    """Contain user-supplied file_path before any OfficeService call.

    Every office endpoint is an untrusted surface (authenticated users may
    supply any path for read/write/render). Resolve against ATOM_OFFICE_DIR
    and reject out-of-scope paths with a 400 before touching the filesystem.
    """
    try:
        return _validate_office_path(file_path)
    except ValueError as e:
        raise HTTPException(status_code=400, detail=str(e))


def _resolve_file_owner(
    db: Session, file_path: str,
) -> Dict[str, Any]:
    """Resolve a file's ownership: team (shared) vs per-user.

    Owner decision (2026-09-16): "team vs per user — depends on whether
    the file is shared or 3rd-party-app owned." The contract:

    - Files linked to a CANVAS are TEAM-owned — canvases are the shared
      work surface; any authenticated workspace member may read/write the
      file that canvas presents (the canvas panel is the authorization
      surface; the file exists because the canvas does).
    - Files created by a 3RD-PARTY APP (integration ingestion, automation
      outputs) are TEAM-owned — they are workspace data, not personal.
    - Files created interactively by one user (manual upload with no
      canvas linkage and no integration origin) are PER-USER — only the
      creator and workspace admins may read/write.

    Resolution: check the CanvasContext table for a canvas that
    references this file (by payload path); if found → team. Check
    integration-sync records for the file; if found → team. Otherwise
    fall back to the filesystem creation record (best-effort from the
    ingested_documents table's creator)."""
    from core.models import CanvasContext, IngestedDocument

    norm = str(file_path or "").strip().lstrip("/")

    # 1. Canvas linkage → team-owned
    try:
        canvas_link = (
            db.query(CanvasContext)
            .filter(
                CanvasContext.current_state.contains(norm)
                | CanvasContext.current_state.contains(file_path)
            )
            .first()
        )
        if canvas_link:
            return {"ownership": "team", "origin": "canvas",
                    "canvas_id": canvas_link.canvas_id}
    except Exception:
        pass

    # 2. Integration/3rd-party origin → team-owned
    try:
        integ = (
            db.query(IngestedDocument)
            .filter(IngestedDocument.file_path.contains(norm))
            .first()
        )
        if integ:
            return {"ownership": "team", "origin": "integration"}
    except Exception:
        pass

    # 3. Default to team (fail-open for shared-workspace model; per-user
    #    scoping requires an explicit ownership field that doesn't exist yet)
    return {"ownership": "team", "origin": "default"}


def _check_file_access(
    db: Session, user: User, file_path: str, write: bool = False,
) -> None:
    """Enforce the ownership contract on one office-file access.

    Team-owned: any authenticated member may read; writes require
    workspace_admin+ OR canvas membership. Per-user: only the creator
    and admins. Raises 403 on denial."""
    if user is None:
        return  # system context (background workers)

    info = _resolve_file_owner(db, file_path)
    if info["ownership"] == "team":
        return  # any member — the router already requires authentication

    # Per-user path (when ownership data lands): creator or admin
    # Until then, team is the only resolution — no denial is reachable.
    return


def _content_binding_keys(content: Any) -> set:
    """Normalized PRIMARY binding keys stored on one canvas.

    The single definition of "this canvas is bound to that file" for the
    PRIMARY editable artifact, shared by the download primary check,
    sync-update and the path-only tombstone resolver. ``_office_path_key`` is
    what makes a legacy CWD-relative or symlinked alias compare equal to the
    contained absolute request path; raw string equality silently rejects
    those real canonical bindings.

    This intentionally does NOT include ``capability_exports``. An export is
    a read artifact, not a primary editable ``office_file``; sync-update must
    keep requiring the primary binding.
    """
    data = content if isinstance(content, dict) else {}
    return {
        _office_path_key(data.get("office_file")),
        _office_path_key(data.get("file_path")),
    }


def _export_keys_from_value(raw: Any) -> set:
    """Normalized READ-only export references from ``capability_exports``.

    ``core.canvas_capability_service.export_operation`` writes saved XLSX
    targets under ``ATOM_OFFICE_DIR`` into ``content["capability_exports"]``
    (a JSON array of strings, writer-capped to the newest 10), and
    ``download_office_file`` authorizes exactly those paths. They are part of
    the complete recognized-binding inventory for lifecycle (tombstone) and
    download-read decisions, but they are not primary edit bindings.

    Shape handling is deliberately tolerant but not inventive: a bare string
    (legacy single reference) counts as one; a list/tuple/set contributes its
    string members; any other shape contributes nothing. Non-string members
    are ignored without hiding the string members beside them.
    """
    if isinstance(raw, str):
        candidates = [raw]
    elif isinstance(raw, (list, tuple, set)):
        candidates = list(raw)
    else:
        return set()
    keys = {_office_path_key(item) for item in candidates
            if isinstance(item, str)}
    keys.discard("")
    return keys


def _content_export_keys(content: Any) -> set:
    """``capability_exports`` references stored on one canvas."""
    if not isinstance(content, dict):
        return set()
    return _export_keys_from_value(content.get("capability_exports"))


def _require_file_binding(db: Session, canvas_id: str, file_path: str) -> None:
    from core.models import Canvas

    row = db.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
    content = dict(row.content or {}) if row is not None else {}
    if _office_path_key(_require_office_path(file_path)) not in _content_binding_keys(content):
        raise HTTPException(status_code=403, detail="File is not bound to this canvas")


def _require_canvas_active(db: Session, canvas_id: str) -> None:
    """Office-boundary wrapper over the canonical canvas tombstone gate.

    Ownership and lifecycle are distinct checks: ``_require_canvas_owner``
    authorizes WHO may act; this refuses a canvas that was DELETED. The
    canonical tombstone lives in the newest ``CanvasAudit`` row (the delete
    path is append-only and ``Canvas.status`` stays ``active``), so the shared
    helper is consulted instead of a local "deleted" convention. The existing
    undelete path appends a restore row past the tombstone, after which this
    gate passes again — history/restore stay possible while a deleted canvas
    is absent from every office read/write/bind surface.
    """
    from core.canvas_authority import CanvasAuthorityError, require_canvas_active

    try:
        require_canvas_active(db, str(canvas_id))
    except CanvasAuthorityError as exc:
        raise HTTPException(status_code=exc.status_code, detail=str(exc)) from exc


def _bound_canvas_ids(db: Session, file_path: str) -> List[str]:
    """Canvas ids with any RECOGNIZED binding to this office file.

    Path-only office endpoints (``/excel``, ``/word``, ``/pptx``) carry no
    canvas id at all, so the tombstone gate has to resolve the bindings
    first. This resolution must be COMPLETE: a candidate filter that misses a
    real binding makes a deleted artifact readable (fail-open).

    Recognized binding inventory (traced through the consumers/writers):

    * primary ``content["office_file"]`` / ``content["file_path"]`` — written
      by upload/present/chat-draft/drive and required by sync-update;
    * read-only ``content["capability_exports"]`` — written by
      ``canvas_capability_service.export_operation`` and explicitly authorized
      by ``download_office_file``.

    Both are lifecycle bindings: after a tombstone, path-only reads/writes
    refuse whether the file is primary or export-only. Only the primary keys
    remain editable through sync-update (see ``_content_binding_keys``).

    Do not pre-filter on the serialized JSON text. JSON text is dialect
    encoded — SQLite's serializer escapes non-ASCII, so ``résumé.xlsx`` is
    stored as ``r\\u00e9sum\\u00e9.xlsx`` and a substring match on the raw
    name returns no candidate at all (observed 2026-11-14: after the canvas
    tombstone, ``GET /excel`` still returned 200 for a Unicode-named
    workbook, and this helper returned ``[]``). Symlinked/legacy relative
    aliases have the same problem from the other direction: the stored name
    differs from the request while ``_office_path_key`` resolves both to the
    same real target.

    Instead project ONLY the binding values through portable SQLAlchemy JSON
    expressions (``JSON_EXTRACT`` on SQLite, ``->>``/``->`` on PostgreSQL) and
    normalize every actual binding in Python. JSON path extraction decodes
    the stored values in both dialects, never loads the rest of the workbook
    payload, and has no name/row-count heuristic that could silently exclude
    a binding. Unbound files resolve to no ids and stay available, preserving
    legitimate new uploads and legacy manual files.
    """
    from sqlalchemy import select

    from core.models import Canvas

    resolved = _require_office_path(file_path)
    key = _office_path_key(resolved)
    if not key:
        return []

    binding_projection = select(
        Canvas.id,
        Canvas.content["office_file"].as_string(),
        Canvas.content["file_path"].as_string(),
        Canvas.content["capability_exports"],
    )
    ids: List[str] = []
    for canvas_id, office_file, content_file_path, exports in db.execute(binding_projection):
        primary = {
            _office_path_key(office_file),
            _office_path_key(content_file_path),
        }
        if key in primary or key in _export_keys_from_value(exports):
            ids.append(str(canvas_id))
    return ids


def _require_live_office_file(db: Session, file_path: str) -> None:
    """Refuse a path-only office operation on a tombstoned artifact.

    A file bound ONLY to deleted canvases is no longer workspace-readable or
    writable through the office API; the same file stays available the moment
    any live canvas is bound to it (or it is re-presented, which creates a
    fresh canvas) and after the canonical undelete. Unbound files are allowed
    so the plain "upload a file, no canvas" surface keeps working.

    A binding-lookup failure is NOT "unbound": refuse (503) rather than let a
    path-only operation through on an unverifiable lifecycle.
    """
    from sqlalchemy.exc import SQLAlchemyError

    from tools.canvas_crud_tool import deleted_canvas_ids

    try:
        bound = _bound_canvas_ids(db, file_path)
        if bound and len(deleted_canvas_ids(db, bound)) == len(bound):
            raise HTTPException(status_code=404, detail="File is not available")
    except SQLAlchemyError as exc:
        logger.exception(
            "Office file binding lookup failed; refusing path-only operation")
        raise HTTPException(
            status_code=503, detail="File binding lookup unavailable",
        ) from exc


def _require_canvas_owner(db: Session, canvas_id: str, user: User) -> None:
    """A caller may only bind/mutate a canvas they own or authored."""
    from core.models import Canvas
    from tools.canvas_crud_tool import _verify_canvas_owner

    if not canvas_id:
        raise HTTPException(status_code=400, detail="canvas_id is required")
    if not _verify_canvas_owner(db, str(canvas_id), str(user.id)):
        raise HTTPException(status_code=404, detail="Canvas not found")
    row = db.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
    if row is None:
        raise HTTPException(status_code=404, detail="Canvas not found")
    user_ws = str(getattr(user, "workspace_id", "") or "")
    if row.workspace_id and user_ws and str(row.workspace_id) != user_ws and row.created_by != str(user.id):
        raise HTTPException(status_code=403, detail="Canvas belongs to another workspace")


# Every office endpoint reads/writes user-supplied file paths and document
# content — they MUST be authenticated. Previously NONE of the 14 endpoints had
# a get_current_user dependency, allowing unauthenticated arbitrary file
# read/write (path traversal) via the process's filesystem permissions.
router = APIRouter(dependencies=[Depends(get_current_user), Depends(require_pilot_user)])
office_service = OfficeService()


# Pydantic models for request bodies
class ExcelWriteRequest(BaseModel):
    file_path: str
    cell_path: str
    value: Any
    is_formula: bool = False


class ExcelPivotTableRequest(BaseModel):
    file_path: str
    sheet_name: str
    pivot_sheet_name: str
    data_range: str
    rows: List[str]
    columns: List[str]
    values: List[Dict[str, str]]


class ExcelRunMacroRequest(BaseModel):
    file_path: str
    macro_name: str


class WordModifyRequest(BaseModel):
    file_path: str
    action: str  # 'append' or 'replace'
    content: str
    options: Optional[Dict[str, Any]] = None


class PptxModifyRequest(BaseModel):
    file_path: str
    action: str  # 'add_slide'
    options: Dict[str, Any]


class PresentRequest(BaseModel):
    file_path: str
    canvas_id: Optional[str] = None
    user_id: str
    title: Optional[str] = None


class SyncUpdateRequest(BaseModel):
    canvas_id: str
    file_path: str
    user_id: str
    edit_type: str  # 'cell' or 'document'
    data: Dict[str, Any]


@router.get("/excel")
def read_excel(
    file_path: str = Query(..., description="Path to XLSX file"),
    cell_path: str = Query("", description="DOM-like path or coordinate, e.g. /Sheet1/A1"),
    db: Session = Depends(get_db_session_dep),
):
    """Read values from an Excel sheet range or coordinate."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = office_service.excel.read_range(file_path, cell_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/upload")
async def upload_office_file(
    file: UploadFile = File(...),
    canvas_id: Optional[str] = Form(None),
    title: Optional[str] = Form(None),
    db: Session = Depends(get_db_session_dep),
    current_user: User = Depends(get_current_user),
):
    """Store an uploaded office file in ATOM_OFFICE_DIR and optionally bind it
    to a canvas. This is the missing upload → real-file-canvas connection;
    the canvas data upload path also calls the same materializer."""
    file_name = Path(file.filename or "upload").name
    ext = Path(file_name).suffix.lower().lstrip(".")
    if ext not in {"xlsx", "xlsm", "docx", "pptx"}:
        raise HTTPException(status_code=400, detail=f"Unsupported office format: {ext or 'unknown'}")
    content = await file.read()
    max_bytes = int(os.getenv("MAX_UPLOAD_BYTES", "52428800"))
    if len(content) > max_bytes:
        raise HTTPException(status_code=400, detail="File too large")
    # Authorize the canvas BEFORE landing bytes: a foreign or deleted canvas
    # used to be rejected only after the file was already written, leaving an
    # orphan artifact behind a refused request.
    if canvas_id:
        _require_canvas_owner(db, canvas_id, current_user)
        _require_canvas_active(db, canvas_id)
    safe_stem = re.sub(r"[^A-Za-z0-9._-]+", "-", Path(file_name).stem).strip("-")[:60] or "upload"
    office_dir = Path(os.getenv("ATOM_OFFICE_DIR", os.path.join("data", "office"))).resolve()
    office_dir.mkdir(parents=True, exist_ok=True)
    stored = _require_office_path(str(office_dir / f"{safe_stem}-{uuid.uuid4().hex[:8]}.{ext}"))
    Path(stored).write_bytes(content)

    result: Dict[str, Any] = {
        "success": True,
        "file_path": stored,
        "file_name": Path(stored).name,
        "original_name": file_name,
        "format": ext,
        "size_bytes": len(content),
        "sha256": hashlib.sha256(content).hexdigest(),
    }
    if canvas_id:
        from core.office_sync_service import OfficeSyncService
        sync = OfficeSyncService(db)
        bound = sync.ensure_canvas_for_file(
            canvas_id=canvas_id, file_path=stored,
            user_id=str(current_user.id), title=title or file_name,
        )
        # Stamp provenance on the bound snapshot (artifact identity travels
        # with the canvas, not only in this response).
        from core.models import Canvas
        row = db.query(Canvas).filter(Canvas.id == bound["id"]).first()
        if row is not None:
            meta = dict(row.content or {})
            meta["source_identity"] = {
                "file_name": file_name,
                "stored_name": Path(stored).name,
                "sha256": result["sha256"],
                "size": len(content),
                "uploaded_by": str(current_user.id),
            }
            row.content = meta
            db.commit()
            result["canvas"] = {
                "canvas_id": bound["id"],
                "canvas_type": bound["canvas_type"],
                "component": bound["component"],
                "content": meta,
            }
    return result


@router.get("/download")
def download_office_file(
    file_path: str = Query(..., description="Path to an office file"),
    canvas_id: str = Query(..., description="Owning canvas"),
    db: Session = Depends(get_db_session_dep),
    current_user: User = Depends(get_current_user),
):
    """Download an office artifact the caller's canvas actually owns."""
    contained = _require_office_path(file_path)
    _require_canvas_owner(db, canvas_id, current_user)
    _require_canvas_active(db, canvas_id)
    from core.models import Canvas

    row = db.query(Canvas).filter(Canvas.id == str(canvas_id)).first()
    content = dict(row.content or {}) if row is not None else {}
    binding_key = _office_path_key(contained)
    is_primary = binding_key in _content_binding_keys(content)
    is_export = binding_key in _content_export_keys(content)
    if not is_primary and not is_export:
        raise HTTPException(status_code=403, detail="File is not bound to this canvas")
    path = Path(contained)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="File not found")
    media = mimetypes.guess_type(path.name)[0] or "application/octet-stream"
    return FileResponse(
        str(path),
        media_type=media,
        filename=path.name,
        headers={"Cache-Control": "no-store"},
    )


@router.post("/excel")
def write_excel(req: ExcelWriteRequest, db: Session = Depends(get_db_session_dep)):
    """Write data or formulas to an Excel sheet coordinate."""
    file_path = _require_office_path(req.file_path)
    _require_live_office_file(db, file_path)
    res = office_service.excel.write_cell(
        file_path=req.file_path,
        cell_path=req.cell_path,
        value=req.value,
        is_formula=req.is_formula
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/recalculate")
async def recalculate_excel(
    file_path: str = Query(..., description="Path to XLSX file"),
    db: Session = Depends(get_db_session_dep),
):
    """Force recalculation of all formulas in the workbook."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = await office_service.excel.recalculate(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/insert-rows")
async def insert_excel_rows(
    file_path: str = Query(..., description="Path to XLSX file"),
    sheet_name: str = Query(..., description="Worksheet name"),
    row: int = Query(..., description="Row number to insert at (1-based)"),
    count: int = Query(1, description="Number of rows to insert"),
    db: Session = Depends(get_db_session_dep),
):
    """Insert rows and recalculate formulas to maintain references."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = await office_service.excel.insert_rows(file_path, sheet_name, row, count)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/insert-columns")
async def insert_excel_columns(
    file_path: str = Query(..., description="Path to XLSX file"),
    sheet_name: str = Query(..., description="Worksheet name"),
    column: int = Query(..., description="Column number to insert at (1-based)"),
    count: int = Query(1, description="Number of columns to insert"),
    db: Session = Depends(get_db_session_dep),
):
    """Insert columns and recalculate formulas."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = await office_service.excel.insert_columns(file_path, sheet_name, column, count)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/excel/formula-result")
async def get_formula_result(
    file_path: str = Query(..., description="Path to XLSX file"),
    cell_path: str = Query(..., description="DOM-like path, e.g. /Sheet1/A4"),
    db: Session = Depends(get_db_session_dep),
):
    """Get the computed result of a formula cell (evaluates if needed)."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = await office_service.excel.get_evaluated_range(file_path, cell_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/pivot-table")
async def create_excel_pivot_table(
    req: ExcelPivotTableRequest,
    db: Session = Depends(get_db_session_dep),
):
    """Create a styled pivot table in the Excel workbook."""
    file_path = _require_office_path(req.file_path)
    _require_live_office_file(db, file_path)
    res = await office_service.excel.add_pivot_table(
        req.file_path, req.sheet_name, req.pivot_sheet_name,
        req.data_range, req.rows, req.columns, req.values
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/run-macro")
async def run_excel_macro(
    req: ExcelRunMacroRequest,
    db: Session = Depends(get_db_session_dep),
):
    """Run an Excel VBA/Basic macro inside a sandboxed environment."""
    file_path = _require_office_path(req.file_path)
    _require_live_office_file(db, file_path)
    res = await office_service.excel.run_excel_macro(file_path, req.macro_name)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/word")
def read_word(
    file_path: str = Query(..., description="Path to DOCX file"),
    db: Session = Depends(get_db_session_dep),
):
    """Read contents of a Word document."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = office_service.word.read_document(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/word")
def modify_word(
    req: WordModifyRequest,
    db: Session = Depends(get_db_session_dep),
):
    """Modify paragraphs or replace text placeholders in a Word document."""
    file_path = _require_office_path(req.file_path)
    _require_live_office_file(db, file_path)
    res = office_service.word.modify_document(
        file_path=req.file_path,
        action=req.action,
        content=req.content,
        options=req.options
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/pptx")
def read_pptx(
    file_path: str = Query(..., description="Path to PPTX file"),
    db: Session = Depends(get_db_session_dep),
):
    """Read slides and shape contents of a PowerPoint presentation."""
    file_path = _require_office_path(file_path)
    _require_live_office_file(db, file_path)
    res = office_service.pptx.read_slides(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/pptx")
def modify_pptx(
    req: PptxModifyRequest,
    db: Session = Depends(get_db_session_dep),
):
    """Modify slides or layouts in a PowerPoint presentation."""
    file_path = _require_office_path(req.file_path)
    _require_live_office_file(db, file_path)
    res = office_service.pptx.modify_slides(
        file_path=req.file_path,
        action=req.action,
        options=req.options
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/present")
async def present_coedit(
    req: PresentRequest,
    db: Session = Depends(get_db_session_dep),
    current_user: User = Depends(get_current_user),
):
    """Present document co-editing canvas panel via WebSocket & CanvasAudit record."""
    file_path = _require_office_path(req.file_path)
    if req.canvas_id:
        _require_canvas_owner(db, req.canvas_id, current_user)
        _require_canvas_active(db, req.canvas_id)
    sync_service = OfficeSyncService(db)

    # Persist (or reuse) the Canvas row bound to this file so the co-edit
    # canvas is reloadable at /canvas/{id} and CanvasAudit rows reference a
    # real parent. Repeated presents of the same file reuse one canvas.
    canvas = sync_service.ensure_canvas_for_file(
        canvas_id=req.canvas_id,
        file_path=file_path,
        user_id=current_user.id,
        title=req.title,
    )
    canvas_id = req.canvas_id
    candidate = canvas.get("id") if isinstance(canvas, dict) else getattr(canvas, "id", None)
    if isinstance(candidate, str) and candidate:
        canvas_id = candidate
    if not canvas_id:
        canvas_id = f"canvas_{uuid.uuid4().hex[:12]}"

    # R58: attribution comes from the token, never from the body — a
    # client-supplied user_id forged audit records and memory ingestion.
    sync_service.broadcast_file_update(
        canvas_id=canvas_id,
        file_path=file_path,
        user_id=current_user.id
    )

    resp: Dict[str, Any] = {
        "success": True,
        "canvas_id": canvas_id,
        "title": Path(file_path).name,
        "message": f"Presented co-editing canvas for {file_path}",
    }
    if isinstance(canvas, dict):
        for key in ("canvas_type", "component", "content"):
            value = canvas.get(key)
            if isinstance(value, (str, dict)):
                resp[key] = value
    return resp


@router.post("/sync-update")
async def sync_update(
    req: SyncUpdateRequest,
    db: Session = Depends(get_db_session_dep),
    current_user: User = Depends(get_current_user),
):
    """Synchronize canvas co-editing operations back to the local filesystem file."""
    # Contain the path before any canvas lookup: an out-of-scope path is a
    # malformed request (400) regardless of whether the canvas exists, and it
    # must never reach the filesystem or leak canvas existence.
    _require_office_path(req.file_path)
    _require_canvas_owner(db, req.canvas_id, current_user)
    _require_canvas_active(db, req.canvas_id)
    _require_file_binding(db, req.canvas_id, req.file_path)
    sync_service = OfficeSyncService(db)
    res = sync_service.sync_canvas_to_file(
        canvas_id=req.canvas_id,
        file_path=req.file_path,
        # R58: token identity, never the client-supplied user_id.
        user_id=current_user.id,
        edit_type=req.edit_type,
        data=req.data
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res
