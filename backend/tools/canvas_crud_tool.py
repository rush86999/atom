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

from core.chat_session_context import audit_agent_id, audit_session_id

logger = logging.getLogger(__name__)


def _verify_canvas_owner(db, canvas_id: str, user_id: str) -> bool:
    """Return True if ``canvas_id`` exists and is owned by ``user_id``.

    Guards against IDOR: the canvas CRUD functions previously queried by
    canvas_id only, so any authenticated user could read/modify/delete another
    user's canvas by guessing the id. The Canvas.created_by column is the
    authoritative owner (NOT NULL).

    Agent-created canvases (present_markdown & friends) historically write
    ONLY a CanvasAudit row — no Canvas row exists for them, which made every
    agent-created canvas 404 on read/update/delete. Fall back to the audit
    trail's user_id (the acting owner) for those; IDOR protection is
    preserved because CanvasAudit.user_id is set by the creating user.
    """
    from core.models import Canvas, CanvasAudit

    canvas = db.query(Canvas).filter(Canvas.id == canvas_id).first()
    if canvas is not None:
        return canvas.created_by == user_id

    audit = (
        db.query(CanvasAudit)
        .filter(CanvasAudit.canvas_id == canvas_id)
        .order_by(CanvasAudit.created_at.desc())
        .first()
    )
    return audit is not None and audit.user_id == user_id


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
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            # IDOR guard: only the owner may read this canvas.
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            audit = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not audit:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            # Skip if the latest action was a delete.
            if audit.action_type == "delete":
                return {"success": False, "error": "Canvas has been deleted", "deleted": True}

            details = audit.details_json or {}
            # Preserve falsy-but-valid content ("" / [] / 0): the old `or`
            # chain replaced empty content with the whole details dict, so an
            # empty doc/email body came back as {"title": ..., "content": ...}
            # instead of the empty string.
            raw_content = details.get("content")
            if raw_content is None:
                raw_content = details.get("data")
            if raw_content is None and "content" not in details and "data" not in details:
                # Audit row carries no body key at all (writer divergence —
                # e.g. chat_draft_to_canvas stored the document only on the
                # Canvas row). Fall back to the Canvas.content column so the
                # page renders the document instead of showing the details
                # metadata ({source, title}) as if it were the body.
                canvas_row = db.query(Canvas).filter(Canvas.id == canvas_id).first()
                if canvas_row is not None and canvas_row.content is not None:
                    raw_content = canvas_row.content
            content = raw_content if raw_content is not None else details

            # Email-draft normalization: canvases created before the
            # classifier existed (and EmailCanvasService's draft-details
            # shape) render on /canvas/{id} as documents/raw JSON with no
            # To/Subject fields or Send button. The audit trail stays
            # append-only — the read normalizes the shape, it never
            # rewrites history. A user-pinned type (manual retype in the
            # UI) is exempt: their choice outranks the classifier, forever.
            from core.chat_draft_classifier import coerce_email_canvas

            if details.get("type_pinned"):
                canvas_type = audit.canvas_type
            else:
                canvas_type, content = coerce_email_canvas(audit.canvas_type, content)

            return {
                "success": True,
                "canvas_id": canvas_id,
                "canvas_type": canvas_type,
                "content": content,
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
    manual_retype: bool = False,
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
        manual_retype: True when a HUMAN switched the canvas type in the UI
            (the escape hatch for a wrong classifier guess). Pins the choice
            on the audit row (``details.type_pinned``) and skips email
            coercion so the manual type survives every later read/save.
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from core.websockets import manager as ws_manager
        from sqlalchemy import desc

        with get_db_session() as db:
            # IDOR guard: only the owner may update this canvas.
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

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

            # Type resolution — three tiers:
            # 1. manual_retype: the human switched the type in the UI. Their
            #    choice wins permanently: pin it and skip the email coercion
            #    (an email-shaped body must not flip a manually-typed
            #    document back into the composer on the next read).
            # 2. already pinned: the pin survives agent/default passes —
            #    only another explicit human retype can change the type.
            # 3. otherwise: a content update never retypes the canvas to the
            #    endpoint's "generic" default — preserve the canvas's own
            #    type when the caller didn't name one — then run the same
            #    email-draft normalization as read_canvas (a co-editor
            #    rewrite that turns a doc into a pure email draft retypes
            #    the canvas so the composer renders).
            requested_type = (canvas_type or "").strip().lower()
            if manual_retype:
                canvas_type = requested_type or "generic"
                details["type_pinned"] = True
            elif details.get("type_pinned"):
                canvas_type = latest.canvas_type
            else:
                if requested_type in ("", "generic") and latest.canvas_type:
                    canvas_type = latest.canvas_type

                from core.chat_draft_classifier import coerce_email_canvas

                canvas_type, content = coerce_email_canvas(canvas_type, content)
                details["content"] = content

            # Append a new audit row (append-only trail). Carry the tenant_id
            # from the latest audit row (CanvasAudit.tenant_id is NOT NULL).
            new_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=latest.tenant_id,
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
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
            broadcast_data = {
                "action": "update",
                "canvas_id": canvas_id,
                "component": canvas_type,
                "data": content,
                "title": title or details.get("title"),
            }
            # The email composer reads to/cc/subject from `metadata` (present
            # flow contract) — include it so live panels seed the fields.
            if canvas_type == "email" and isinstance(content, dict):
                broadcast_data["metadata"] = {
                    "to": content.get("to", ""),
                    "cc": content.get("cc", ""),
                    "subject": content.get("subject", ""),
                }
            await ws_manager.broadcast(user_channel, {
                "type": "canvas:update",
                "data": broadcast_data,
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
            # IDOR guard: only the owner may delete this canvas.
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            # Verify the canvas exists.
            latest = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not latest:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            if latest.action_type == "delete":
                return {"success": False, "error": "Canvas already deleted"}

            canvas_type = latest.canvas_type

            # Write the delete audit. Carry tenant_id (NOT NULL).
            delete_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=latest.tenant_id,
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
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


# ----------------------------------------------------------------------------
# Discovery helpers — search / display titles / snippets.
#
# The audit trail's details_json carries the body under different keys
# depending on the writer (present_* tools use "content", some flows "data",
# chat_draft_to_canvas stores the document only on the Canvas row). read_canvas
# already resolves that ladder; list/search must walk the SAME ladder or those
# canvases become unfindable (no title, no snippet, no content match).
# ----------------------------------------------------------------------------

_BODY_KEYS = ("content", "data")


def _audit_body(details: Dict[str, Any]) -> Any:
    """Resolve the body from audit details, preserving empty-but-valid values."""
    for key in _BODY_KEYS:
        if key in details and details[key] is not None:
            return details[key]
    return None


def _text_of(content: Any) -> str:
    """Flatten canvas content (str | dict | list) to searchable/preview text."""
    if content is None:
        return ""
    if isinstance(content, str):
        return content
    if isinstance(content, dict):
        parts: list = []
        for key in ("subject", "to", "title", "content", "text", "instruction", "body"):
            if isinstance(content.get(key), str) and content[key].strip():
                parts.append(content[key].strip())
        if parts:
            return " ".join(parts)
        import json as _json

        try:
            return _json.dumps(content, default=str)
        except Exception:
            return str(content)
    if isinstance(content, (list, tuple)):
        return " ".join(_text_of(item) for item in content)
    return str(content)


def _first_meaningful_line(text: str, cap: int = 80) -> Optional[str]:
    """First non-empty line with markdown noise stripped — the Notion-style
    derived title for untitled canvases, so a card never shows a raw UUID."""
    for line in text.splitlines():
        cleaned = line.lstrip("#*>- ` \t").strip()
        if cleaned:
            return cleaned[:cap] + ("…" if len(cleaned) > cap else "")
    return None


def _derive_display_title(
    canvas_type: Optional[str],
    details: Dict[str, Any],
    body: Any,
    canvas_name: Optional[str] = None,
) -> str:
    """Best-effort human title. Priority: explicit audit title → Canvas.name →
    type-aware content inference → typed fallback."""
    explicit = (details.get("title") or "").strip() if isinstance(details.get("title"), str) else details.get("title")
    if explicit:
        return str(explicit)[:120]
    if canvas_name:
        return str(canvas_name)[:120]

    ctype = (canvas_type or "").lower()
    if isinstance(body, dict):
        subject = str(body.get("subject") or "").strip()
        if subject:
            return subject[:120]
        to = str(body.get("to") or "").strip()
        if to:
            recipient = to.split(",")[0].strip()
            return f"Email to {recipient}"[:120]
        if ctype == "email":
            return "Email draft"
    line = _first_meaningful_line(_text_of(body))
    if line:
        return line
    if ctype:
        return f"Untitled {ctype} canvas"
    return "Untitled canvas"


def _content_snippet(body: Any, q: Optional[str], cap: int = 140) -> Optional[str]:
    """Short text excerpt for list cards. When searching, window the excerpt
    around the first match so the user sees WHY the canvas matched."""
    text = " ".join(_text_of(body).split())
    if not text:
        return None
    needle = (q or "").strip().lower()
    if needle:
        idx = text.lower().find(needle)
        if idx >= 0:
            start = max(0, idx - 40)
            end = min(len(text), idx + len(needle) + (cap - 40))
            prefix = "…" if start > 0 else ""
            suffix = "…" if end < len(text) else ""
            return prefix + text[start:end] + suffix
    return text[:cap] + ("…" if len(text) > cap else "")


async def list_canvases(
    user_id: str,
    canvas_type: Optional[str] = None,
    include_deleted: bool = False,
    q: Optional[str] = None,
    limit: Optional[int] = 60,
    offset: int = 0,
) -> Dict[str, Any]:
    """List a user's canvases from the audit trail — searchable and paginated.

    Returns the latest state of each unique canvas_id (the audit trail IS the
    source of truth; agent-created canvases have no Canvas row). As canvas
    counts grow this stays fast: the DB collapses to one row per canvas via a
    ROW_NUMBER() window (instead of materializing every historical audit row)
    and only the requested page is serialized.

    Discovery features (the "find the right canvas" journey):
    - ``q``: case-insensitive substring match over derived title, canvas_type,
      canvas_id, and the canvas body text — finds untitled canvases by content.
    - ``display_title``: title derived from content when no explicit title
      exists (email subject/recipient, first line of a doc) — never a raw UUID.
    - ``snippet``: content excerpt, windowed around the search match.

    Args:
        user_id: User requesting the action
        canvas_type: Optional filter (e.g. "sheets", "email")
        include_deleted: Include deleted canvases (default False)
        q: Optional search string (title / content / type / id)
        limit: Page size (default 60; capped at 200; None = no cap for
            internal callers that want the full set)
        offset: Page offset
    """
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import desc, func
        from sqlalchemy.orm import aliased

        with get_db_session() as db:
            # Latest audit row per canvas_id (deterministic: newest created_at,
            # then id as tiebreak for same-commit timestamps).
            rn = (
                func.row_number()
                .over(
                    partition_by=CanvasAudit.canvas_id,
                    order_by=(CanvasAudit.created_at.desc(), CanvasAudit.id.desc()),
                )
                .label("rn")
            )
            base = db.query(CanvasAudit, rn).filter(CanvasAudit.user_id == user_id)
            if canvas_type:
                base = base.filter(CanvasAudit.canvas_type == canvas_type)

            subq = base.subquery()
            latest = (
                db.query(aliased(CanvasAudit, subq))
                .filter(subq.c.rn == 1)
                .order_by(subq.c.created_at.desc(), subq.c.id.desc())
                .all()
            )

            # Canvas-row enrichment, two batched queries:
            # 1. names for every listed canvas (Canvas.name outranks
            #    content-derived titles — office /present canvases carry a
            #    real filename there);
            # 2. content ONLY for canvases whose audit details carry no body
            #    key at all (chat_draft_to_canvas writes the document only on
            #    the Canvas row — same fallback ladder as read_canvas).
            all_ids = [row.canvas_id for row in latest]
            canvas_names: Dict[str, str] = {}
            if all_ids:
                for cid, name in (
                    db.query(Canvas.id, Canvas.name)
                    .filter(Canvas.id.in_(all_ids))
                    .all()
                ):
                    canvas_names[cid] = name
            fallback_ids = []
            for row in latest:
                details = row.details_json or {}
                if _audit_body(details) is None and "content" not in details and "data" not in details:
                    fallback_ids.append(row.canvas_id)
            canvas_content: Dict[str, Any] = {}
            if fallback_ids:
                for row in db.query(Canvas).filter(Canvas.id.in_(fallback_ids)).all():
                    canvas_content[row.id] = row.content

            needle = (q or "").strip().lower()
            matches: list = []
            for row in latest:
                if row.action_type == "delete" and not include_deleted:
                    continue

                details = row.details_json or {}
                body = _audit_body(details)
                if body is None:
                    body = canvas_content.get(row.canvas_id)

                display_title = _derive_display_title(
                    row.canvas_type, details, body,
                    canvas_name=canvas_names.get(row.canvas_id),
                )

                if needle:
                    haystack = " ".join(
                        part.lower()
                        for part in (
                            display_title,
                            str(details.get("title") or ""),
                            row.canvas_type or "",
                            row.canvas_id,
                            _text_of(body),
                        )
                        if part
                    )
                    if needle not in haystack:
                        continue

                matches.append({
                    "canvas_id": row.canvas_id,
                    "canvas_type": row.canvas_type,
                    "action_type": row.action_type,
                    "title": details.get("title"),
                    "display_title": display_title,
                    "snippet": _content_snippet(body, q),
                    "deleted": row.action_type == "delete",
                    "last_updated": row.created_at.isoformat() if row.created_at else None,
                })

            total = len(matches)
            if limit is None:
                # Internal full-set callers: no cap, no paging.
                page = matches[int(offset):]
            else:
                page_limit = max(1, min(int(limit), 200))
                page = matches[int(offset): int(offset) + page_limit]

            return {
                "success": True,
                "canvases": page,
                "count": len(page),
                "total": total,
            }
    except Exception as e:
        logger.error(f"Canvas list failed: {e}")
        return {"success": False, "error": str(e)}
