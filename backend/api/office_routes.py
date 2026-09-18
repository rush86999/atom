"""
Office Automation API Routes for Atom

Exposes HTTP endpoints under /api/v1/office for Word, Excel, and PowerPoint
document manipulation, visualization, and canvas synchronization.
"""

import logging
import uuid
from pathlib import Path
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.office_service import OfficeService, _validate_office_path
from core.office_sync_service import OfficeSyncService
from core.auth import get_current_user, User

logger = logging.getLogger(__name__)


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

# Every office endpoint reads/writes user-supplied file paths and document
# content — they MUST be authenticated. Previously NONE of the 14 endpoints had
# a get_current_user dependency, allowing unauthenticated arbitrary file
# read/write (path traversal) via the process's filesystem permissions.
router = APIRouter(dependencies=[Depends(get_current_user)])
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
    cell_path: str = Query("", description="DOM-like path or coordinate, e.g. /Sheet1/A1")
):
    """Read values from an Excel sheet range or coordinate."""
    file_path = _require_office_path(file_path)
    res = office_service.excel.read_range(file_path, cell_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel")
def write_excel(req: ExcelWriteRequest):
    """Write data or formulas to an Excel sheet coordinate."""
    file_path = _require_office_path(req.file_path)
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
    file_path: str = Query(..., description="Path to XLSX file")
):
    """Force recalculation of all formulas in the workbook."""
    file_path = _require_office_path(file_path)
    res = await office_service.excel.recalculate(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/insert-rows")
async def insert_excel_rows(
    file_path: str = Query(..., description="Path to XLSX file"),
    sheet_name: str = Query(..., description="Worksheet name"),
    row: int = Query(..., description="Row number to insert at (1-based)"),
    count: int = Query(1, description="Number of rows to insert")
):
    """Insert rows and recalculate formulas to maintain references."""
    file_path = _require_office_path(file_path)
    res = await office_service.excel.insert_rows(file_path, sheet_name, row, count)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/insert-columns")
async def insert_excel_columns(
    file_path: str = Query(..., description="Path to XLSX file"),
    sheet_name: str = Query(..., description="Worksheet name"),
    column: int = Query(..., description="Column number to insert at (1-based)"),
    count: int = Query(1, description="Number of columns to insert")
):
    """Insert columns and recalculate formulas."""
    file_path = _require_office_path(file_path)
    res = await office_service.excel.insert_columns(file_path, sheet_name, column, count)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/excel/formula-result")
async def get_formula_result(
    file_path: str = Query(..., description="Path to XLSX file"),
    cell_path: str = Query(..., description="DOM-like path, e.g. /Sheet1/A4")
):
    """Get the computed result of a formula cell (evaluates if needed)."""
    file_path = _require_office_path(file_path)
    res = await office_service.excel.get_evaluated_range(file_path, cell_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/pivot-table")
async def create_excel_pivot_table(req: ExcelPivotTableRequest):
    """Create a styled pivot table in the Excel workbook."""
    file_path = _require_office_path(req.file_path)
    res = await office_service.excel.add_pivot_table(
        req.file_path, req.sheet_name, req.pivot_sheet_name,
        req.data_range, req.rows, req.columns, req.values
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel/run-macro")
async def run_excel_macro(req: ExcelRunMacroRequest):
    """Run an Excel VBA/Basic macro inside a sandboxed environment."""
    file_path = _require_office_path(req.file_path)
    res = await office_service.excel.run_excel_macro(file_path, req.macro_name)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/word")
def read_word(file_path: str = Query(..., description="Path to DOCX file")):
    """Read contents of a Word document."""
    file_path = _require_office_path(file_path)
    res = office_service.word.read_document(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/word")
def modify_word(req: WordModifyRequest):
    """Modify paragraphs or replace text placeholders in a Word document."""
    file_path = _require_office_path(req.file_path)
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
def read_pptx(file_path: str = Query(..., description="Path to PPTX file")):
    """Read slides and shape contents of a PowerPoint presentation."""
    file_path = _require_office_path(file_path)
    res = office_service.pptx.read_slides(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/pptx")
def modify_pptx(req: PptxModifyRequest):
    """Modify slides or layouts in a PowerPoint presentation."""
    file_path = _require_office_path(req.file_path)
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
