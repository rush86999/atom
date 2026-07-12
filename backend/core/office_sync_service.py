"""
Office Synchronization Service for Atom

Bridges the local filesystem documents (.docx, .xlsx, .pptx) and the active Canvas state.
Ensures edits made by the user on the Canvas are saved to disk, and edits made by the agent
on disk are pushed to the Canvas.

In addition to file/Canvas sync, every meaningful document change is ingested into Atom's
memory (knowledge graph + LanceDB) so the agent "remembers" the content of quotes, POs,
price lists, and invoices it generates or edits.
"""

import os
import logging
from pathlib import Path
from typing import Any, Dict, Optional
import uuid
from sqlalchemy.orm import Session

import docx  # python-docx — used for Word-doc canvas→file sync (line ~71)

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

            # Ingest the updated document content into Atom memory so the agent
            # remembers quotes/POs/price-lists/invoices it just generated or edited.
            # Fire-and-forget (async) to avoid blocking the Canvas update.
            import asyncio
            try:
                asyncio.create_task(self._ingest_document_to_memory(file_path, user_id))
            except RuntimeError:
                # No running loop (rare sync caller) — fall back to running it directly.
                self._ingest_document_to_memory_sync(file_path, user_id)

            # Push live update via WebSocket manager
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

    async def _ingest_document_to_memory(self, file_path: str, user_id: str) -> bool:
        """Read a document's content and ingest it into Atom memory (async).

        Reuses AutoDocumentIngestionService.process_file_bytes so the same
        parse → redact → LanceDB + knowledge-graph path used for cloud-drive
        files applies to locally-edited Office documents. Failures are
        non-fatal (best-effort) and only logged.
        """
        try:
            content = self._read_file_bytes(file_path)
            if not content:
                return False
            from core.auto_document_ingestion import AutoDocumentIngestionService

            ingestor = AutoDocumentIngestionService()
            result = await ingestor.process_file_bytes(
                content=content,
                file_name=Path(file_path).name,
                source="office_canvas",
                user_id=user_id,
            )
            status = result.get("status")
            if status == "ingested":
                logger.info(
                    f"Office document ingested to memory: {Path(file_path).name} "
                    f"({result.get('chars_ingested', 0)} chars)"
                )
            return status in ("ingested", "skipped")
        except Exception as e:
            logger.debug(f"Office→memory ingestion skipped for {file_path}: {e}")
            return False

    def _ingest_document_to_memory_sync(self, file_path: str, user_id: str) -> bool:
        """Synchronous fallback for Office→memory ingestion (no running event loop)."""
        try:
            import asyncio
            content = self._read_file_bytes(file_path)
            if not content:
                return False
            from core.auto_document_ingestion import AutoDocumentIngestionService

            ingestor = AutoDocumentIngestionService()
            result = asyncio.new_event_loop().run_until_complete(
                ingestor.process_file_bytes(
                    content=content,
                    file_name=Path(file_path).name,
                    source="office_canvas",
                    user_id=user_id,
                )
            )
            return result.get("status") in ("ingested", "skipped")
        except Exception as e:
            logger.debug(f"Office→memory sync ingestion skipped for {file_path}: {e}")
            return False

    @staticmethod
    def _read_file_bytes(file_path: str) -> Optional[bytes]:
        """Read file bytes if the file exists and is non-empty."""
        try:
            if not os.path.exists(file_path):
                return None
            with open(file_path, "rb") as f:
                content = f.read()
            return content or None
        except Exception:
            return None


