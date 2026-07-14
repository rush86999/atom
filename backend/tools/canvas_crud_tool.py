"""
Canvas CRUD tools — read, update, delete for ALL canvas types.

Previously only Create (present_*) worked for all types. Read was missing,
Update existed only for docs, and Delete was broken (closed by user_id, not
canvas_id). This module provides generic CRUD that works across all 7 canvas
types using the CanvasAudit append-only trail as the source of truth (same
pattern as canvas_docs_tool.update_docs_canvas).

Every canvas interaction (present/read/update/delete) writes a CanvasAudit
row, so the full lifecycle is auditable and episodes can capture it.
"""

from __future__ import annotations

import logging
import uuid
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)


async def read_canvas(
    user_id: str,
    canvas_id: str,
) -> Dict[str, Any]:
    """Read the current content/state of a canvas by ID.

    Reads the latest CanvasAudit row for the canvas (the audit trail IS the
    source of truth). Returns the content, canvas_type, and metadata.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID (from a previous present_* call)
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            # Skip if the latest action was a delete.
            if audit.action_type == "delete":
                return {"success": False, "error": "Canvas has been deleted", "deleted": True}

            details = audit.details_json or {}
            return {
                "success": True,
                "canvas_id": canvas_id,
                "canvas_type": audit.canvas_type,
                "content": details.get("content") or details.get("data") or details,
                "title": details.get("title"),
                "action_type": audit.action_type,
                "created_at": audit.created_at.isoformat() if audit.created_at else None,
            }
    except Exception as e:
        logger.error(f"Canvas read failed: {e}")
        return {"success": False, "error": str(e)}


async def update_canvas_content(
    user_id: str,
    canvas_id: str,
    content: Any,
    canvas_type: str = "generic",
    title: Optional[str] = None,
) -> Dict[str, Any]:
    """Update the content of an existing canvas.

    Reads the latest CanvasAudit, merges the new content, and appends a new
    CanvasAudit row with action_type="update". Also broadcasts a WS update
    so the frontend reflects the change immediately.

    Works for ALL canvas types (sheets, email, docs, coding, terminal, etc.)
    — generalizes the docs-only update pattern.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID to update
        content: New content (type depends on canvas_type)
        canvas_type: Canvas type (default "generic")
        title: Optional new title
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from core.websockets import manager as ws_manager
        from sqlalchemy import desc

        with get_db_session() as db:
            # Read the latest audit row for this canvas.
            latest = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not latest:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            if latest.action_type == "delete":
                return {"success": False, "error": "Cannot update a deleted canvas"}

            # Merge new content into the existing details.
            details = dict(latest.details_json or {})
            details["content"] = content
            if title:
                details["title"] = title

            # Append a new audit row (append-only trail).
            new_audit = CanvasAudit(
                canvas_id=canvas_id,
                canvas_type=canvas_type,
                action_type="update",
                user_id=user_id,
                details_json=details,
            )
            db.add(new_audit)
            db.commit()
            db.refresh(new_audit)

        # Broadcast the update via WebSocket.
        try:
            user_channel = f"user:{user_id}"
            await ws_manager.broadcast(user_channel, {
                "type": "canvas:update",
                "data": {
                    "action": "update",
                    "canvas_id": canvas_id,
                    "component": canvas_type,
                    "data": content,
                    "title": title or details.get("title"),
                },
            })
        except Exception as ws_err:
            logger.debug(f"Canvas update WS broadcast skipped: {ws_err}")

        logger.info(f"Updated canvas {canvas_id} ({canvas_type})")
        return {
            "success": True,
            "canvas_id": canvas_id,
            "canvas_type": canvas_type,
            "message": f"Canvas updated successfully",
        }
    except Exception as e:
        logger.error(f"Canvas update failed: {e}")
        return {"success": False, "error": str(e)}


async def delete_canvas(
    user_id: str,
    canvas_id: str,
) -> Dict[str, Any]:
    """Delete (close) a specific canvas by ID.

    Writes a CanvasAudit with action_type="delete" and broadcasts a WS close.
    The audit trail is preserved (append-only), so the history is recoverable.

    Unlike the old close_canvas (which closed ALL canvases for a user), this
    targets a specific canvas_id.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID to delete
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from core.websockets import manager as ws_manager
        from sqlalchemy import desc

        with get_db_session() as db:
            # Verify the canvas exists.
            latest = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not latest:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            if latest.action_type == "delete":
                return {"success": False, "error": "Canvas already deleted"}

            canvas_type = latest.canvas_type

            # Write the delete audit.
            delete_audit = CanvasAudit(
                canvas_id=canvas_id,
                canvas_type=canvas_type,
                action_type="delete",
                user_id=user_id,
                details_json={"deleted": True, "previous_action": latest.action_type},
            )
            db.add(delete_audit)
            db.commit()

        # Broadcast close via WebSocket.
        try:
            user_channel = f"user:{user_id}"
            await ws_manager.broadcast(user_channel, {
                "type": "canvas:update",
                "data": {
                    "action": "close",
                    "canvas_id": canvas_id,
                },
            })
        except Exception as ws_err:
            logger.debug(f"Canvas delete WS broadcast skipped: {ws_err}")

        logger.info(f"Deleted canvas {canvas_id}")
        return {
            "success": True,
            "canvas_id": canvas_id,
            "message": "Canvas deleted successfully",
        }
    except Exception as e:
        logger.error(f"Canvas delete failed: {e}")
        return {"success": False, "error": str(e)}


async def list_canvases(
    user_id: str,
    canvas_type: Optional[str] = None,
    include_deleted: bool = False,
) -> Dict[str, Any]:
    """List all canvases for a user, optionally filtered by type.

    Returns the latest state of each unique canvas_id from the audit trail.

    Args:
        user_id: User requesting the action
        canvas_type: Optional filter (e.g. "sheets", "email")
        include_deleted: Include deleted canvases (default False)
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from sqlalchemy import desc, func

        with get_db_session() as db:
            query = db.query(CanvasAudit).filter(CanvasAudit.user_id == user_id)

            if canvas_type:
                query = query.filter(CanvasAudit.canvas_type == canvas_type)

            # Get all audits, group by canvas_id, take the latest per ID.
            all_audits = query.order_by(desc(CanvasAudit.created_at)).all()

            seen = set()
            canvases = []
            for audit in all_audits:
                if audit.canvas_id in seen:
                    continue
                seen.add(audit.canvas_id)

                if audit.action_type == "delete" and not include_deleted:
                    continue

                details = audit.details_json or {}
                canvases.append({
                    "canvas_id": audit.canvas_id,
                    "canvas_type": audit.canvas_type,
                    "action_type": audit.action_type,
                    "title": details.get("title"),
                    "deleted": audit.action_type == "delete",
                    "last_updated": audit.created_at.isoformat() if audit.created_at else None,
                })

            return {
                "success": True,
                "canvases": canvases,
                "count": len(canvases),
            }
    except Exception as e:
        logger.error(f"Canvas list failed: {e}")
        return {"success": False, "error": str(e)}
