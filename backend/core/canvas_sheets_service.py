"""
Spreadsheet Canvas Service

Backend service for spreadsheet canvas with grid editing,
formulas, charts, and pivot tables.
"""
from datetime import datetime
import logging
from typing import Any, Dict, List, Optional
import uuid
from sqlalchemy.orm import Session

from core.canvas_authority import (
    CanvasAuthorityError,
    claim_active_actor,
    require_active_actor,
    require_canvas_read,
    require_canvas_write,
    reserve_canvas_id,
)
from core.models import CanvasAudit

logger = logging.getLogger(__name__)


def _authority_refusal(exc: CanvasAuthorityError) -> Dict[str, Any]:
    return {
        "success": False,
        "error": str(exc),
        "http_status": exc.status_code,
        "error_code": exc.code,
    }


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

    def _actor(self, user_id: str) -> Dict[str, Any]:
        return require_active_actor(self.db, user_id)

    def get_spreadsheet(self, canvas_id: str, user_id: str) -> Dict[str, Any]:
        """Return the latest spreadsheet state for an authorized reader."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_read(self.db, canvas_id, actor)
            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "sheets",
            ).order_by(desc(CanvasAudit.created_at)).first()
            if not audit:
                return {
                    "success": False,
                    "error": "Spreadsheet not found",
                    "http_status": 404,
                    "error_code": "CANVAS_NOT_FOUND",
                }
            return audit.details_json or {}
        except CanvasAuthorityError as exc:
            return _authority_refusal(exc)
        except Exception as exc:  # noqa: BLE001 - unreadable is not a pass
            logger.error("Failed to read spreadsheet: %s", type(exc).__name__)
            return {
                "success": False,
                "error": "Spreadsheet could not be read",
                "http_status": 503,
                "error_code": "SPREADSHEET_READ_FAILED",
            }

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
        """Create a new spreadsheet canvas for the current active actor."""
        try:
            actor = self._actor(user_id)
            requested_id = str(canvas_id).strip() if canvas_id is not None else ""
            canvas_id = requested_id or str(uuid.uuid4())

            # Initialize cells
            cells = {}
            for cell_ref, value in data.items():
                cells[cell_ref] = {
                    "cell_ref": cell_ref,
                    "value": value,
                    "cell_type": "formula" if cell_ref in (formulas or []) else "text"
                }

            # The existing Canvas primary key is the atomic id reservation.
            # Any existing id (same owner, another owner or another family)
            # is refused; creation is not an implicit upsert.
            reserve_canvas_id(
                self.db,
                canvas_id=canvas_id,
                actor=actor,
                title=title,
                canvas_type="sheets",
            )
            claim_active_actor(self.db, actor)

            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                agent_id=agent_id,
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="create",
                canvas_type="sheets",
                details_json={
                    "canvas_type": "sheets",
                    "component_type": "data_grid",
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

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
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
        """Update a cell value for the current authorized actor."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_write(self.db, canvas_id, actor)

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "sheets"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Spreadsheet not found"}

            metadata = audit.details_json or {}
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
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="update_cell",
                canvas_type="sheets",
                details_json={
                    "canvas_type": "sheets",
                    "component_type": "data_grid",
                    **metadata,
                }
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "cell_ref": cell_ref, "value": value}

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
        except Exception as e:
            logger.error(f"Failed to update cell: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def update_cell_transactional(
        self,
        canvas_id: str,
        user_id: str,
        cell_ref: str,
        value: Any,
        cell_type: str = "text",
        formula: Optional[str] = None,
        should_fail: bool = False
    ) -> Dict[str, Any]:
        """Update cell value with transactional safety/rollback."""
        from core.sandbox_transaction import SandboxTransaction
        import tempfile
        import json
        from pathlib import Path
        
        with tempfile.TemporaryDirectory() as temp_dir:
            tx_path = Path(temp_dir) / "canvas_tx"
            tx_path.mkdir()
            (tx_path / "state.json").write_text(json.dumps({"cell": cell_ref, "val": "prev_val"}))
            
            try:
                with SandboxTransaction(tx_path):
                    (tx_path / "state.json").write_text(json.dumps({"cell": cell_ref, "val": value}))
                    if should_fail:
                        raise ValueError("Transactional failure: formula validation breached limits")
                    
                    return self.update_cell(canvas_id, user_id, cell_ref, value, cell_type, formula)
            except Exception as e:
                logger.warning(f"Canvas transaction rolled back: {e}")
                raise

    def add_chart(
        self,
        canvas_id: str,
        user_id: str,
        chart_type: str,
        data_range: str,
        title: str = ""
    ) -> Dict[str, Any]:
        """Add a chart to the spreadsheet for the current authorized actor."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_write(self.db, canvas_id, actor)

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "sheets"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Spreadsheet not found"}

            metadata = audit.details_json or {}
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
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="add_chart",
                canvas_type="sheets",
                details_json={
                    "canvas_type": "sheets",
                    "component_type": "chart_embed",
                    **metadata,
                }
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "chart_id": chart["chart_id"]}

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
        except Exception as e:
            logger.error(f"Failed to add chart: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}

    def add_pivot_table(
        self,
        canvas_id: str,
        user_id: str,
        sheet_name: str,
        pivot_sheet_name: str,
        data_range: str,
        rows: List[str],
        columns: List[str],
        values: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Add a pivot table for the current authorized actor."""
        try:
            from sqlalchemy import desc

            actor = self._actor(user_id)
            require_canvas_write(self.db, canvas_id, actor)

            audit = self.db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.canvas_type == "sheets"
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": "Spreadsheet not found"}

            metadata = audit.details_json or {}
            pivot_tables = metadata.get("pivot_tables", [])

            pivot = {
                "pivot_id": str(uuid.uuid4()),
                "sheet_name": sheet_name,
                "pivot_sheet_name": pivot_sheet_name,
                "data_range": data_range,
                "rows": rows,
                "columns": columns,
                "values": values,
                "created_at": datetime.now().isoformat()
            }

            pivot_tables.append(pivot)
            metadata["pivot_tables"] = pivot_tables

            update_audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id=str(actor.get("effective_tenant_id") or actor.get("tenant_id") or "default"),
                user_id=str(actor["id"]),
                canvas_id=canvas_id,
                action_type="add_pivot_table",
                canvas_type="sheets",
                details_json={
                    "canvas_type": "sheets",
                    "component_type": "pivot_table",
                    **metadata,
                }
            )

            self.db.add(update_audit)
            self.db.commit()

            return {"success": True, "pivot_id": pivot["pivot_id"]}

        except CanvasAuthorityError as exc:
            self.db.rollback()
            return _authority_refusal(exc)
        except Exception as e:
            logger.error(f"Failed to add pivot table to canvas: {e}")
            self.db.rollback()
            return {"success": False, "error": str(e)}
