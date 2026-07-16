"""
Office Automation API Routes for Atom

Exposes HTTP endpoints under /api/v1/office for Word, Excel, and PowerPoint
document manipulation, visualization, and canvas synchronization.
"""

import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, HTTPException, Query
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.database import get_db_session
from core.office_service import OfficeService
from core.office_sync_service import OfficeSyncService

logger = logging.getLogger(__name__)

router = APIRouter()
office_service = OfficeService()


# Pydantic models for request bodies
class ExcelWriteRequest(BaseModel):
    file_path: str
    cell_path: str
    value: Any
    is_formula: bool = False


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
    res = office_service.excel.read_range(file_path, cell_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/excel")
def write_excel(req: ExcelWriteRequest):
    """Write data or formulas to an Excel sheet coordinate."""
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
    res = await office_service.ExcelManager.recalculate(file_path)
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
    res = await office_service.ExcelManager.insert_rows(file_path, sheet_name, row, count)
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
    res = await office_service.ExcelManager.insert_columns(file_path, sheet_name, column, count)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/excel/formula-result")
async def get_formula_result(
    file_path: str = Query(..., description="Path to XLSX file"),
    cell_path: str = Query(..., description="DOM-like path, e.g. /Sheet1/A4")
):
    """Get the computed result of a formula cell (evaluates if needed)."""
    res = await office_service.ExcelManager.get_evaluated_range(file_path, cell_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.get("/word")
def read_word(file_path: str = Query(..., description="Path to DOCX file")):
    """Read contents of a Word document."""
    res = office_service.word.read_document(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/word")
def modify_word(req: WordModifyRequest):
    """Modify paragraphs or replace text placeholders in a Word document."""
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
    res = office_service.pptx.read_slides(file_path)
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/pptx")
def modify_pptx(req: PptxModifyRequest):
    """Modify slides or layouts in a PowerPoint presentation."""
    res = office_service.pptx.modify_slides(
        file_path=req.file_path,
        action=req.action,
        options=req.options
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res


@router.post("/present")
def present_coedit(req: PresentRequest, db: Session = Depends(get_db_session)):
    """Present document co-editing canvas panel via WebSocket & CanvasAudit record."""
    sync_service = OfficeSyncService(db)
    canvas_id = req.canvas_id or f"canvas_{uuid.uuid4().hex[:12]}"
    
    # Trigger initial preview generation
    sync_service.broadcast_file_update(
        canvas_id=canvas_id,
        file_path=req.file_path,
        user_id=req.user_id
    )

    return {
        "success": True,
        "canvas_id": canvas_id,
        "message": f"Presented co-editing canvas for {req.file_path}"
    }


@router.post("/sync-update")
def sync_update(req: SyncUpdateRequest, db: Session = Depends(get_db_session)):
    """Synchronize canvas co-editing operations back to the local filesystem file."""
    sync_service = OfficeSyncService(db)
    res = sync_service.sync_canvas_to_file(
        canvas_id=req.canvas_id,
        file_path=req.file_path,
        user_id=req.user_id,
        edit_type=req.edit_type,
        data=req.data
    )
    if not res.get("success"):
        raise HTTPException(status_code=400, detail=res.get("error"))
    return res
