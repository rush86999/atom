"""Spreadsheet Canvas API Routes"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from typing import Dict, Any, Optional, List
from sqlalchemy.orm import Session
import logging

from core.database import get_db
from core.canvas_sheets_service import SpreadsheetCanvasService

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/api/canvas/sheets", tags=["canvas_sheets"])


class CreateSpreadsheetRequest(BaseModel):
    user_id: str
    title: str
    data: Dict[str, Any]
    canvas_id: Optional[str] = None
    agent_id: Optional[str] = None
    layout: str = "sheet"
    formulas: Optional[List[str]] = None


class UpdateCellRequest(BaseModel):
    user_id: str
    cell_ref: str
    value: Any
    cell_type: str = "text"
    formula: Optional[str] = None


class AddChartRequest(BaseModel):
    user_id: str
    chart_type: str
    data_range: str
    title: str = ""


@router.post("/create")
async def create_spreadsheet(request: CreateSpreadsheetRequest, db: Session = Depends(get_db)):
    """Create a new spreadsheet canvas."""
    service = SpreadsheetCanvasService(db)
    result = service.create_spreadsheet_canvas(
        user_id=request.user_id,
        title=request.title,
        data=request.data,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout,
        formulas=request.formulas
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.put("/{canvas_id}/cell")
async def update_cell(canvas_id: str, request: UpdateCellRequest, db: Session = Depends(get_db)):
    """Update a cell value."""
    service = SpreadsheetCanvasService(db)
    result = service.update_cell(
        canvas_id=canvas_id,
        user_id=request.user_id,
        cell_ref=request.cell_ref,
        value=request.value,
        cell_type=request.cell_type,
        formula=request.formula
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.post("/{canvas_id}/chart")
async def add_chart(canvas_id: str, request: AddChartRequest, db: Session = Depends(get_db)):
    """Add a chart to the spreadsheet."""
    service = SpreadsheetCanvasService(db)
    result = service.add_chart(
        canvas_id=canvas_id,
        user_id=request.user_id,
        chart_type=request.chart_type,
        data_range=request.data_range,
        title=request.title
    )
    if not result.get("success"):
        raise HTTPException(status_code=400, detail=result.get("error"))
    return result


@router.get("/{canvas_id}")
async def get_spreadsheet(canvas_id: str, db: Session = Depends(get_db)):
    """Get a spreadsheet canvas."""
    from core.models import CanvasAudit
    from sqlalchemy import desc

    audit = db.query(CanvasAudit).filter(
        CanvasAudit.canvas_id == canvas_id,
        CanvasAudit.canvas_type == "sheets"
    ).order_by(desc(CanvasAudit.created_at)).first()

    if not audit:
        raise HTTPException(status_code=404, detail="Spreadsheet not found")

    return audit.audit_metadata
