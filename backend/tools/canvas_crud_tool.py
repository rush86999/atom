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
            audit_canvas_type = audit.canvas_type
            # Preserve falsy-but-valid content ("" / [] / 0): the old `or`
            # chain replaced empty content with the whole details dict, so an
            # empty doc/email body came back as {"title": ..., "content": ...}
            # instead of the empty string.
            raw_content = details.get("content")
            if raw_content is None:
                raw_content = details.get("data")
            if raw_content is None and not (
                "content" in details or "data" in details
            ):
                # The latest row carries no body key — but that row may be an
                # EVENT stamp, not the content history: email_send /
                # email_send_attempt rows (canvas_email_service.record_send)
                # append after every send without content. Falling back
                # straight to the Canvas.content column here served the
                # creation-era snapshot and made the real draft vanish after
                # any send attempt (observed 2026-08-31). The audit trail is
                # the content history: scan back to the latest row that
                # actually carries a body.
                content_rows = (
                    db.query(CanvasAudit)
                    .filter(
                        CanvasAudit.canvas_id == canvas_id,
                        CanvasAudit.created_at < audit.created_at,
                    )
                    .order_by(desc(CanvasAudit.created_at))
                    .limit(10)
                    .all()
                )
                for row in content_rows:
                    row_details = row.details_json or {}
                    if "content" in row_details:
                        raw_content = row_details.get("content")
                    elif "data" in row_details:
                        raw_content = row_details.get("data")
                    else:
                        continue
                    # The event row carries no title/type of its own — the
                    # content row is the provenance for both. A type pin on
                    # the NEWEST row still outranks the older row's choice.
                    details = {
                        **row_details,
                        **({"type_pinned": details["type_pinned"]} if details.get("type_pinned") else {}),
                    }
                    audit_canvas_type = row.canvas_type
                    break
            if raw_content is None and "content" not in details and "data" not in details:
                # No content-bearing row in the recent history either —
                # legacy canvas whose body lives only on the Canvas row.
                # Fall back to the Canvas.content column so the page renders
                # the document instead of showing the details
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
                canvas_type, content = coerce_email_canvas(audit_canvas_type, content)

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
                details["content"] = content
            elif details.get("type_pinned"):
                # Pinned: the canvas type is settled (no coercion/retype),
                # but the caller's CONTENT must still land — skipping the
                # merge silently turned every co-editor PUT on a pinned
                # canvas (chat-created email drafts pin) into a no-op row
                # that even shadowed newer content on recency (observed
                # Sept 6: styled-table fix never reached the composer).
                canvas_type = latest.canvas_type
                details["content"] = content
            else:
                if requested_type in ("", "generic") and latest.canvas_type:
                    canvas_type = latest.canvas_type

                from core.chat_draft_classifier import coerce_email_canvas

                canvas_type, content = coerce_email_canvas(canvas_type, content)
                details["content"] = content

            # Append a new audit row (append-only trail). Carry the tenant_id
            # from the latest audit row (CanvasAudit.tenant_id is NOT NULL).
            # STRICT RECENCY: legacy audit rows carry SECOND-precision
            # timestamps, so an update fired in the same second as the row it
            # supersedes tied on created_at and ordering could serve the OLD
            # content (same incident class as the delete tombstone — pinned
            # at least 1µs past the row it supersedes).
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts.tzinfo is None:
                _prev_ts = _prev_ts.replace(tzinfo=_tz.utc)
            new_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=latest.tenant_id,
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="update",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts + _td(microseconds=1)),
                details_json=details,
            )
            db.add(new_audit)
            db.commit()
            db.refresh(new_audit)

        # Broadcast the update via WebSocket.
        await _broadcast_canvas_update(user_id, canvas_id, canvas_type, content, title or details.get("title"))

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


async def _broadcast_canvas_update(
    user_id: str,
    canvas_id: str,
    canvas_type: str,
    content: Any,
    title: Optional[str],
) -> None:
    """WS broadcast shared by every write path (update, restore). Mirrors the
    present-flow contract: the email composer reads To/Cc/Subject from
    `metadata`. Best-effort — a broadcast failure never fails the write."""
    try:
        from core.websockets import manager as ws_manager

        broadcast_data = {
            "action": "update",
            "canvas_id": canvas_id,
            "component": canvas_type,
            "data": content,
            "title": title,
        }
        if canvas_type == "email" and isinstance(content, dict):
            broadcast_data["metadata"] = {
                "to": content.get("to", ""),
                "cc": content.get("cc", ""),
                "subject": content.get("subject", ""),
            }
        await ws_manager.broadcast(f"user:{user_id}", {
            "type": "canvas:update",
            "data": broadcast_data,
        })
    except Exception as ws_err:
        logger.debug(f"Canvas update WS broadcast skipped: {ws_err}")


_VERSION_PREVIEW_CHARS = 600
# Upper bound when a caller asks for FULL version content (agents reading a
# version before reverting). Generous enough for real drafts, tight enough
# that one version can't blow the agent's context window.
_VERSION_FULL_CONTENT_CHARS = 20000


def _serialize_version_text(content: Any, cap: Optional[int] = None) -> str:
    """Version content as bounded text for agent-facing listings."""
    if isinstance(content, str):
        text = content
    else:
        try:
            import json as _json

            text = _json.dumps(content, indent=2, default=str)
        except Exception:
            text = str(content)
    if cap is not None and len(text) > cap:
        return text[:cap] + "…(truncated)"
    return text


async def list_canvas_versions(
    user_id: str,
    canvas_id: str,
    limit: int = 20,
    include_content: bool = False,
) -> Dict[str, Any]:
    """List the version history of a canvas (newest first).

    Every write to a canvas appends a CanvasAudit row, so the audit trail IS
    the version history. Contentless event rows (email_send stamps, delete
    markers) are not versions and are skipped. The newest content-bearing
    row is flagged ``is_current`` — restoring to it would be a no-op.

    Companion to ``restore_canvas_version``: the agent lists versions
    (bounded previews identify each one), picks the right ``audit_id``, and
    restores. Owner-scoped like every other CRUD entry point.

    Args:
        user_id: User requesting the action
        canvas_id: The canvas ID
        limit: Max versions to return (default 20, capped at 50)
        include_content: Include each version's full content (bounded)
            instead of a short preview
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            rows = (
                db.query(CanvasAudit)
                .filter(
                    CanvasAudit.canvas_id == canvas_id,
                    CanvasAudit.action_type != "delete",
                )
                .order_by(desc(CanvasAudit.created_at), desc(CanvasAudit.id))
                .limit(max(1, min(int(limit or 20), 50)))
                .all()
            )

            versions: list = []
            for r in rows:
                details = r.details_json or {}
                content = details.get("content", details.get("data"))
                if content is None:
                    continue  # an event stamp, not a version
                cap = _VERSION_FULL_CONTENT_CHARS if include_content else _VERSION_PREVIEW_CHARS
                entry = {
                    "audit_id": r.id,
                    "created_at": r.created_at.isoformat() if r.created_at else None,
                    "actor": "agent" if r.agent_id else "supervisor",
                    "action_type": r.action_type,
                    "title": details.get("title"),
                    "restored_from": (details.get("restored_from") or {}).get("audit_id")
                    if isinstance(details.get("restored_from"), dict)
                    else None,
                    "content": _serialize_version_text(content, cap),
                    "content_truncated": len(_serialize_version_text(content)) > cap,
                    "is_current": False,
                }
                versions.append(entry)

            if versions:
                versions[0]["is_current"] = True

            return {
                "success": True,
                "canvas_id": canvas_id,
                "versions": versions,
                "count": len(versions),
            }
    except Exception as e:
        logger.error(f"Canvas version list failed: {e}")
        return {"success": False, "error": str(e)}


async def restore_canvas_version(
    user_id: str,
    canvas_id: str,
    audit_id: str,
) -> Dict[str, Any]:
    """Restore an earlier version from the append-only audit trail.

    A restore is itself APPENDED as a new "update" row (nothing is rewritten
    or deleted — the pre-restore state stays in history as its own version),
    carrying `restored_from` provenance. Broadcasts the same WS update as a
    normal edit so every open canvas converges.

    No-op guard: restoring a version whose content equals the current
    content appends nothing and reports ``no_change`` — byte-identical
    "restores" were audit-trail noise that read to the user as an undo that
    did something (same rationale as the editor's no_change guard).

    Type resolution: the restored version's own canvas_type is authoritative
    for its content, EXCEPT when the canvas carries a human type pin
    (`type_pinned`) — the supervisor's manual choice outranks history.
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            # IDOR guard: only the owner may restore this canvas.
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            target = (
                db.query(CanvasAudit)
                .filter(CanvasAudit.id == str(audit_id), CanvasAudit.canvas_id == canvas_id)
                .first()
            )
            if not target:
                return {"success": False, "error": "Version not found"}
            if target.action_type == "delete":
                return {"success": False, "error": "Cannot restore a deletion marker"}

            target_details = target.details_json or {}
            content = target_details.get("content", target_details.get("data"))
            if content is None:
                return {"success": False, "error": "Version carries no restorable content"}

            latest = (
                db.query(CanvasAudit)
                .filter(CanvasAudit.canvas_id == canvas_id)
                .order_by(desc(CanvasAudit.created_at))
                .first()
            )
            if not latest:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}
            if latest.action_type == "delete":
                return {"success": False, "error": "Cannot update a deleted canvas"}

            latest_details = dict(latest.details_json or {})

            # No-op guard: the requested version IS the current content.
            latest_body = latest_details.get("content", latest_details.get("data"))
            if latest_body is not None and content == latest_body:
                return {
                    "success": True,
                    "canvas_id": canvas_id,
                    "no_change": True,
                    "restored_from": audit_id,
                    "message": "Canvas is already at that version — nothing restored",
                }

            if latest_details.get("type_pinned"):
                canvas_type = latest.canvas_type
            else:
                canvas_type = target.canvas_type or latest.canvas_type or "generic"
                from core.chat_draft_classifier import coerce_email_canvas
                canvas_type, content = coerce_email_canvas(canvas_type, content)

            # Base the new row on the LATEST details (preserves send metadata,
            # pins, learning-loop state), then override content/title and mark
            # the provenance.
            new_details = latest_details
            new_details["content"] = content
            if target_details.get("title"):
                new_details["title"] = target_details["title"]
            new_details["restored_from"] = {
                "audit_id": target.id,
                "created_at": target.created_at.isoformat() if target.created_at else None,
                "actor": "agent" if target.agent_id else "supervisor",
            }

            # STRICT RECENCY (same second-precision tie as the delete
            # tombstone): a restore landing in the same second as the edit it
            # reverts must still order AFTER that row, or read_canvas serves
            # the pre-restore content the moment the page refreshes.
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts.tzinfo is None:
                _prev_ts = _prev_ts.replace(tzinfo=_tz.utc)
            new_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=latest.tenant_id,
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="update",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts + _td(microseconds=1)),
                details_json=new_details,
            )
            db.add(new_audit)
            db.commit()
            db.refresh(new_audit)

        await _broadcast_canvas_update(
            user_id, canvas_id, canvas_type, content,
            new_details.get("title"),
        )
        logger.info(
            f"Restored canvas {canvas_id} to version {audit_id} "
            f"({canvas_type}) — appended as a new version"
        )
        return {
            "success": True,
            "canvas_id": canvas_id,
            "canvas_type": canvas_type,
            "restored_from": audit_id,
            "message": "Version restored (appended as the newest version)",
        }
    except Exception as e:
        logger.error(f"Canvas restore failed: {e}")
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
                # IDEMPOTENT: deleting an already-deleted canvas succeeds.
                # The gallery's delete button raced the refetch window once
                # and the non-idempotent 400 surfaced as an AxiosError
                # overlay (observed live 2026-09-01). REST DELETE is
                # idempotent by contract; the outcome is identical.
                return {
                    "success": True,
                    "canvas_id": canvas_id,
                    "already_deleted": True,
                }

            canvas_type = latest.canvas_type

            # Write the delete audit. Carry tenant_id (NOT NULL).
            # STRICT RECENCY: legacy audit rows carry SECOND-precision
            # timestamps (func.now() server default), so a delete fired in the
            # same second as the action it supersedes tied on created_at and
            # the uuid tiebreak let the OLD state win — deletes "came back"
            # (observed live 2026-09-01: delete → restore same second, and a
            # later delete silently no-opped). The new row is pinned at least
            # 1µs past the row it supersedes.
            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts.tzinfo is None:
                _prev_ts = _prev_ts.replace(tzinfo=_tz.utc)
            delete_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=latest.tenant_id,
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=canvas_type,
                action_type="delete",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts + _td(microseconds=1)),
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



async def restore_deleted_canvas(
    user_id: str,
    canvas_id: str,
) -> Dict[str, Any]:
    """Un-delete a tombstoned canvas.

    The delete path is append-only (a CanvasAudit tombstone), so restoring is
    appending an action_type="restore" row carrying the PRE-delete content
    forward — nothing is rewritten, the delete stays in history. After this,
    the latest row is no longer a tombstone: listings include the canvas
    again, read_canvas serves the restored content, and update_canvas_content
    accepts writes. Owner-only, like delete. Best-effort WS broadcast re-
    presents the canvas to open clients.
    """
    try:
        from core.database import get_db_session
        from core.models import CanvasAudit
        from sqlalchemy import desc

        with get_db_session() as db:
            if not _verify_canvas_owner(db, canvas_id, user_id):
                return {"success": False, "error": f"Canvas {canvas_id} not found"}

            latest = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
            ).order_by(desc(CanvasAudit.created_at)).first()

            if not latest:
                return {"success": False, "error": f"Canvas {canvas_id} not found"}
            if latest.action_type != "delete":
                return {"success": False, "error": "Canvas is not deleted"}

            # The pre-delete content: the most recent row that is not the
            # tombstone (the tombstone itself carries no content).
            content_row = db.query(CanvasAudit).filter(
                CanvasAudit.canvas_id == canvas_id,
                CanvasAudit.action_type != "delete",
            ).order_by(desc(CanvasAudit.created_at)).first()
            if not content_row:
                return {"success": False, "error": "No content to restore"}

            details = dict(content_row.details_json or {})
            details["restored_from_delete"] = True

            from datetime import datetime as _dt, timezone as _tz, timedelta as _td

            _prev_ts2 = latest.created_at or _dt.min.replace(tzinfo=_tz.utc)
            if _prev_ts2.tzinfo is None:
                _prev_ts2 = _prev_ts2.replace(tzinfo=_tz.utc)
            restore_audit = CanvasAudit(
                canvas_id=canvas_id,
                tenant_id=latest.tenant_id,
                session_id=audit_session_id(None),
                agent_id=audit_agent_id(None),
                canvas_type=latest.canvas_type,
                action_type="restore",
                user_id=user_id,
                created_at=max(_dt.now(_tz.utc), _prev_ts2 + _td(microseconds=1)),
                details_json=details,
            )
            db.add(restore_audit)
            db.commit()

        canvas_type = str(latest.canvas_type or "generic")
        await _broadcast_canvas_update(
            user_id, canvas_id, canvas_type,
            details.get("content"), details.get("title"),
        )

        logger.info(f"Restored deleted canvas {canvas_id}")
        return {
            "success": True,
            "canvas_id": canvas_id,
            "action_type": "restore",
        }
    except Exception as e:
        logger.warning(f"Canvas restore failed for {canvas_id}: {e}")
        return {"success": False, "error": str(e)}


async def list_canvases(
    user_id: str,
    canvas_type: Optional[str] = None,
    include_deleted: bool = False,
    q: Optional[str] = None,
    limit: Optional[int] = 60,
    offset: int = 0,
    session_id: Optional[str] = None,
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
    - ``session_id``: scope to canvases touched in one chat session — the
      agent-chat Artifacts panel lists what that conversation produced. The
      session filter applies to the audit rows BEFORE the latest-per-canvas
      window, so a canvas presented in this session still appears even if its
      newest edit happened elsewhere; ``version`` counts this session's rows.

    Args:
        user_id: User requesting the action
        canvas_type: Optional filter (e.g. "sheets", "email")
        include_deleted: Include deleted canvases (default False)
        q: Optional search string (title / content / type / id)
        limit: Page size (default 60; capped at 200; None = no cap for
            internal callers that want the full set)
        offset: Page offset
        session_id: Optional chat-session scope (CanvasAudit.session_id)
    """
    try:
        from core.database import get_db_session
        from core.models import Canvas, CanvasAudit
        from sqlalchemy import desc, func
        from sqlalchemy.orm import aliased

        with get_db_session() as db:
            # Latest audit row per canvas_id (deterministic: newest created_at,
            # then id as tiebreak for same-commit timestamps) + how many rows
            # this scope has per canvas (the sidebar's v{n} badge — one more
            # window over the same partition, no extra query).
            rn = (
                func.row_number()
                .over(
                    partition_by=CanvasAudit.canvas_id,
                    order_by=(CanvasAudit.created_at.desc(), CanvasAudit.id.desc()),
                )
                .label("rn")
            )
            version_count = (
                func.count()
                .over(partition_by=CanvasAudit.canvas_id)
                .label("version_count")
            )
            base = db.query(CanvasAudit, rn, version_count).filter(
                CanvasAudit.user_id == user_id
            )
            if canvas_type:
                base = base.filter(CanvasAudit.canvas_type == canvas_type)
            if session_id:
                base = base.filter(CanvasAudit.session_id == session_id)

            subq = base.subquery()
            latest = (
                db.query(aliased(CanvasAudit, subq), subq.c.version_count)
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
            all_ids = [row.canvas_id for row, _vc in latest]
            canvas_names: Dict[str, str] = {}
            if all_ids:
                for cid, name in (
                    db.query(Canvas.id, Canvas.name)
                    .filter(Canvas.id.in_(all_ids))
                    .all()
                ):
                    canvas_names[cid] = name
            fallback_ids = []
            for row, _version_count in latest:
                details = row.details_json or {}
                if _audit_body(details) is None and "content" not in details and "data" not in details:
                    fallback_ids.append(row.canvas_id)
            canvas_content: Dict[str, Any] = {}
            if fallback_ids:
                for row in db.query(Canvas).filter(Canvas.id.in_(fallback_ids)).all():
                    canvas_content[row.id] = row.content

            needle = (q or "").strip().lower()
            matches: list = []
            for row, version_count in latest:
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
                    "version": int(version_count or 1),
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
