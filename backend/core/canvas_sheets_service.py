"""
Spreadsheet Canvas Service

Backend service for spreadsheet canvas with grid editing,
formulas, charts, and pivot tables.
"""
import logging
from typing import Dict, Any, List, Optional
from datetime import datetime
from sqlalchemy.orm import Session
import uuid

from core.models import CanvasAudit

logger = logging.getLogger(__name__)


class SpreadsheetCell:
    """Represents a spreadsheet cell."""
    def __init__(self, cell_ref: str, value: Any, cell_type: str = "text",
                 formula: Optional[str] = None, formatting: Optional[Dict] = None):
        self.cell_ref = cell_ref  # A1, B2, etc.
        self.value = value
        self.cell_type = cell_type  # text, number, date, formula
        self.formula = formula
        self.formatting = formatting or {}


class SpreadsheetChart:
    """Represents an embedded chart."""
    def __init__(self, chart_id: str, chart_type: str, data_range: str,
                 title: str = "", position: Optional[Dict] = None):
        self.chart_id = chart_id
        self.chart_type = chart_type  # line, bar, pie
        self.data_range = data_range  # A1:B10
        self.title = title
        self.position = position or {"row": 0, "col": 0}


class SpreadsheetCanvasService:
    """Service for managing spreadsheet canvases."""

    def __init__(self, db: Session):
        self.db = db

    def create_spreadsheet_canvas(
        self,
        user_id: str,
        title: str,
        data: Dict[str, Any],
        canvas_id: Optional[str] = None,
        agent_id: Optional[str] = None,
        layout: str = "sheet",
        formulas: List[str] = None
    ) -> Dict[str, Any]:
        """Create a new spreadsheet canvas."""
        try:
            canvas_id = canvas_id or str(uuid.uuid4())

            # Initialize cells
            cells = {}
            for cell_ref, value in data.items():
                cells[cell_ref] = {
                    "cell_ref": cell_ref,
                    "value": value,
                    "cell_type": "formula" if cell_ref in (formulas or []) else "text"
                }

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                agent_id=agent_id,
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="sheets",
                component_type="data_grid",
                action="create",
                audit_metadata={
                    "title": title,
                    "layout": layout,
                    "cells": cells,
                    "formulas": formulas or [],
                    "charts": [],
                    "pivot_tables": []
                }
            )

            self.db.add(audit)
            self.db.commit()

            logger.info(f"Created spreadsheet canvas {canvas_id}: {title}")

            return {
                "success": True,
                "canvas_id": canvas_id,
                "title": title,
                "cells": cells
            }

        except Exception as e:
            logger.error(f"Failed to create spreadsheet: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def update_cell(
        self,
        canvas_id: str,
        user_id: str,
        cell_ref: str,
        value: Any,
        cell_type: str = "text",
        formula: Optional[str] = None
    ) -> Dict[str, Any]:
        """Update a cell value."""
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "sheets"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Spreadsheet not found"}

            metadata = audit.audit_metadata
            cells = metadata.get("cells", {})

            cells[cell_ref] = {
                "cell_ref": cell_ref,
                "value": value,
                "cell_type": cell_type,
                "formula": formula
            }

            metadata["cells"] = cells
            metadata["updated_at"] = datetime.now().isoformat()

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="sheets",
                component_type="data_grid",
                action="update_cell",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "cell_ref": cell_ref, "value": value}

        except Exception as e:
            logger.error(f"Failed to update cell: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_chart(
        self,
        canvas_id: str,
        user_id: str,
        chart_type: str,
        data_range: str,
        title: str = ""
    ) -> Dict[str, Any]:
        """Add a chart to the spreadsheet."""
        try:
            from sqlalchemy import desc

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "sheets"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Spreadsheet not found"}

            metadata = audit.audit_metadata
            charts = metadata.get("charts", [])

            chart = {
                "chart_id": str(uuid.uuid4()),
                "chart_type": chart_type,
                "data_range": data_range,
                "title": title,
                "created_at": datetime.now().isoformat()
            }

            charts.append(chart)
            metadata["charts"] = charts

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                workspace_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                canvas_type="sheets",
                component_type="chart_embed",
                action="add_chart",
                audit_metadata=metadata
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "chart_id": chart["chart_id"]}

        except Exception as e:
            logger.error(f"Failed to add chart: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
