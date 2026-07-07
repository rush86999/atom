"""
Office Synchronization Service for Atom

Bridges the local filesystem documents (.docx, .xlsx, .pptx) and the active Canvas state.
Ensures edits made by the user on the Canvas are saved to disk, and edits made by the agent
on disk are pushed to the Canvas.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import uuid
from sqlalchemy.orm import Session

from core.office_service import OfficeService
from core.models import CanvasAudit
from core.websockets import manager as ws_manager

logger = logging.getLogger(__name__)


class OfficeSyncService:
    """Service coordinates bi-directional sync between files and canvas UI."""

    def __init__(self, db: Session):
        self.db = db
        self.office = OfficeService()

    def sync_canvas_to_file(
        self,
        canvas_id: str,
        file_path: str,
        user_id: str,
        edit_type: str,  # 'cell' or 'document'
        data: Dict[str, Any]
    ) -> Dict[str, Any]:
        """Apply Canvas user edit back to filesystem document."""
        if not os.path.exists(file_path):
            return {"success": False, "error": f"File not found: {file_path}"}

        ext = Path(file_path).suffix.lower()
        try:
            if ext == ".xlsx" and edit_type == "cell":
                cell_path = data.get("cell_path")
                value = data.get("value")
                is_formula = data.get("is_formula", False)

                if not cell_path:
                    return {"success": False, "error": "cell_path required for Excel cell update"}

                res = self.office.excel.write_cell(
                    file_path=file_path,
                    cell_path=cell_path,
                    value=value,
                    is_formula=is_formula
                )
                if not res.get("success"):
                    return res

            elif ext == ".docx" and edit_type == "document":
                # For document, we might write the whole content (markdown/html) or replace paragraphs
                content = data.get("content", "")
                
                # Turn content into Docx (for simple edit, we can clear and re-write, or append)
                # For simplicity in co-editing, we write/overwrite paragraphs
                doc = docx.Document()
                for line in content.split('\n'):
                    doc.add_paragraph(line)
                doc.save(file_path)

            else:
                return {"success": False, "error": f"Unsupported sync edit type: {edit_type} for extension {ext}"}

            # After saving the file, push updated preview back to all subscribers
            self.broadcast_file_update(canvas_id, file_path, user_id)

            return {
                "success": True,
                "message": f"Successfully synchronized canvas {canvas_id} changes to {file_path}"
            }

        except Exception as e:
            logger.error(f"Failed to sync canvas to file: {e}")
            return {"success": False, "error": str(e)}

    def broadcast_file_update(self, canvas_id: str, file_path: str, user_id: str):
        """Broadcast updated document HTML render to the Canvas WebSocket subscribers."""
        try:
            render_res = self.office.renderer.render_to_html(file_path)
            if not render_res.get("success"):
                return

            ext = Path(file_path).suffix.lower()
            canvas_type = "sheets" if ext == ".xlsx" else "docs"
            component_type = "data_grid" if ext == ".xlsx" else "rich_editor"

            # Create updated audit record to update state history
            audit = CanvasAudit(
                id=str(uuid.uuid4()),
                tenant_id="default",
                user_id=user_id,
                canvas_id=canvas_id,
                action_type="update",
                canvas_type=canvas_type,
                details_json={
                    "canvas_type": canvas_type,
                    "component_type": component_type,
                    "file_path": file_path,
                    "html": render_res["html"],
                    "title": Path(file_path).name
                }
            )
            self.db.add(audit)
            self.db.commit()

            # Push live update via WebSocket manager
            import asyncio
            asyncio.create_task(ws_manager.broadcast({
                "type": "canvas:update",
                "data": {
                    "action": "update",
                    "canvas_id": canvas_id,
                    "canvas_type": canvas_type,
                    "component": "office_preview",
                    "data": {
                        "html": render_res["html"],
                        "file_path": file_path
                    }
                }
            }))

        except Exception as e:
            logger.error(f"Failed to broadcast file update: {e}")
