"""Spreadsheet Canvas API Routes"""
import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.base_routes import BaseAPIRouter
from core.canvas_sheets_service import SpreadsheetCanvasService
from core.database import get_db
from core.auth import get_current_user, User

logger = logging.getLogger(__name__)
# All canvas-sheets endpoints create/read user-attributed spreadsheets — they
# must be authenticated. Previously none had auth.
router = BaseAPIRouter(prefix="/api/canvas/sheets", tags=["canvas_sheets"], dependencies=[Depends(get_current_user)])


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


def _raise_service_error(result: Dict[str, Any], default_code: str, default_message: str) -> None:
    """Map a typed service refusal to its real HTTP status."""
    raise router.error_response(
        error_code=result.get("error_code") or default_code,
        message=result.get("error") or default_message,
        status_code=int(result.get("http_status") or 400),
    )


@router.post("/create")
async def create_spreadsheet(request: CreateSpreadsheetRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Create a new spreadsheet canvas for the authenticated actor."""
    service = SpreadsheetCanvasService(db)
    result = service.create_spreadsheet_canvas(
        user_id=current_user.id,
        title=request.title,
        data=request.data,
        canvas_id=request.canvas_id,
        agent_id=request.agent_id,
        layout=request.layout,
        formulas=request.formulas
    )
    if not result.get("success"):
        _raise_service_error(
            result,
            "SPREADSHEET_CREATE_FAILED",
            "Failed to create spreadsheet canvas",
        )
    return result


@router.put("/{canvas_id}/cell")
async def update_cell(canvas_id: str, request: UpdateCellRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Update a cell value."""
    service = SpreadsheetCanvasService(db)
    result = service.update_cell(
        canvas_id=canvas_id,
        user_id=current_user.id,
        cell_ref=request.cell_ref,
        value=request.value,
        cell_type=request.cell_type,
        formula=request.formula
    )
    if not result.get("success"):
        _raise_service_error(
            result, "CELL_UPDATE_FAILED", "Failed to update cell")
    return result


@router.post("/{canvas_id}/chart")
async def add_chart(canvas_id: str, request: AddChartRequest, current_user: User = Depends(get_current_user), db: Session = Depends(get_db)):
    """Add a chart to the spreadsheet."""
    service = SpreadsheetCanvasService(db)
    result = service.add_chart(
        canvas_id=canvas_id,
        user_id=current_user.id,
        chart_type=request.chart_type,
        data_range=request.data_range,
        title=request.title
    )
    if not result.get("success"):
        _raise_service_error(
            result, "CHART_ADD_FAILED", "Failed to add chart")
    return result


@router.get("/{canvas_id}")
async def get_spreadsheet(
    canvas_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    """Get a spreadsheet canvas for the current authorized actor."""
    service = SpreadsheetCanvasService(db)
    result = service.get_spreadsheet(canvas_id, current_user.id)
    if isinstance(result, dict) and result.get("error_code"):
        _raise_service_error(
            result, "SPREADSHEET_READ_FAILED", "Spreadsheet could not be read")
    return result
