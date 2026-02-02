"""Spreadsheet Canvas Tool"""
import logging
from typing import Dict, Any, Optional, List

logger = logging.getLogger(__name__)


async def present_sheets_canvas(
    user_id: str,
    title: str,
    data: Dict[str, Any],
    agent_id: Optional[str] = None,
    layout: str = "sheet",
    formulas: List[str] = None
) -> Dict[str, Any]:
    """
    Present a spreadsheet canvas.

    Creates a grid-based spreadsheet with cells, formulas, and charts.
    """
    from core.database import SessionLocal
    from core.canvas_sheets_service import SpreadsheetCanvasService
    from tools.canvas_tool import present_specialized_canvas

    try:
        with SessionLocal() as db:
            service = SpreadsheetCanvasService(db)

            result = service.create_spreadsheet_canvas(
                user_id=user_id,
                title=title,
                data=data,
                agent_id=agent_id,
                layout=layout,
                formulas=formulas
            )

            if not result.get("success"):
                return result

            canvas_id = result["canvas_id"]

            present_result = await present_specialized_canvas(
                user_id=user_id,
                canvas_type="sheets",
                component_type="data_grid",
                data={
                    "title": title,
                    "cells": result["cells"],
                    "formulas": formulas or []
                },
                title=title,
                agent_id=agent_id,
                layout=layout
            )

            if not present_result.get("success"):
                return present_result

            return {
                "success": True,
                "canvas_id": canvas_id,
                "title": title,
                "message": f"Presented spreadsheet canvas: {title}"
            }

    except Exception as e:
        logger.error(f"Failed to present sheets canvas: {e}")
        return {"success": False, "error": str(e)}
