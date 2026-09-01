"""Agent tools for email-canvas attachment CRUD.

Thin governance wrappers over EmailCanvasService: the service owns state,
staging, and provider I/O; these functions add the agent surface — ownership
verify, the per-user autonomy gate (topic ``email_attachment``), and
provenance-wrapped text extraction for the LLM.

Sending WITH attachments is deliberately NOT a tool: sends ride the existing
email-send circuit (email_policy + HITL proposals) where attachment policy
scans already run (canvas_email_service.send_email).

Attachment text returned to the model is UNTRUSTED retrieved data — wrapped
in the same spotlight delimiters the memory assembler uses (delimiter-escape
sanitized), so a hostile attachment can't inject instructions.
"""

from __future__ import annotations

import logging
from datetime import datetime
from typing import Any, Dict, Optional

from core.autonomy_policy import OUTCOME_PROPOSE, gate_for_topic
from core.chat_session_context import audit_agent_id

logger = logging.getLogger(__name__)

# Generated-file cap for agent staged uploads: tool calls carry base64 in
# the LLM context, so keep this far below the human upload cap.
AGENT_STAGE_FILE_MAX_BYTES = 256 * 1024

_MAX_EXTRACT_CHARS = 20_000


def _gate(db, user_id: str, agent_id: Optional[str]) -> Optional[Dict[str, Any]]:
    """Propose-signal when the owner pinned this topic to human approval."""
    gate = gate_for_topic(db, user_id, "email_attachment", agent_id)
    if gate.get("outcome") == OUTCOME_PROPOSE:
        return {
            "success": False,
            "needs_approval": True,
            "topic": "email_attachment",
            "reason": gate.get("reason") or "Owner requires approval for email attachment changes",
        }
    return None


def _acting_agent_id(agent_id: Optional[str]) -> Optional[str]:
    return agent_id or audit_agent_id(None)


async def email_attachment_list(user_id: str, canvas_id: str) -> Dict[str, Any]:
    """List attachments on an email canvas draft (metadata only, no content).

    Args:
        user_id: Owning user id
        canvas_id: Email canvas id

    Returns:
        {"success", "attachments": [{attachment_id, filename, size,
        content_type, origin, ingestion, sent_at}]}
    """
    try:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session

        with get_db_session() as db:
            return EmailCanvasService(db).list_attachments(canvas_id, user_id)
    except Exception as e:
        logger.error(f"email_attachment_list failed: {e}")
        return {"success": False, "error": str(e)}


async def email_attachment_get_text(
    user_id: str,
    canvas_id: str,
    attachment_id: str,
    max_chars: int = 8000,
) -> Dict[str, Any]:
    """Extract the TEXT of an email attachment for reading (PDF/DOCX/XLSX/
    text). Read-only; never returns raw file bytes.

    Args:
        user_id: Owning user id
        canvas_id: Email canvas id
        attachment_id: Attachment record id on the canvas
        max_chars: Cap on returned text (default 8000)

    Returns:
        {"success", "filename", "text" (provenance-wrapped), "truncated"}
    """
    try:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session
        from core.email_policy import spotlight_email_content

        with get_db_session() as db:
            svc = EmailCanvasService(db)
            resolved = await svc.get_attachment_bytes(canvas_id, user_id, attachment_id)
            if not resolved or resolved.get("bytes") is None:
                return {"success": False, "error": "Attachment content unavailable"}
            record = resolved["record"]
            data = resolved["bytes"]

        filename = record.get("filename") or "attachment"
        ext = filename.rsplit(".", 1)[-1].lower() if "." in filename else ""
        text = ""
        try:
            from core.auto_document_ingestion import DocumentParser

            text = await DocumentParser().parse_document(data, ext, filename) or ""
        except Exception as parse_err:
            logger.debug(f"Attachment text extraction failed for {filename}: {parse_err}")

        if not text:
            # Binary format without a text layer: offer ingest instead of
            # pretending we read it.
            return {
                "success": False,
                "filename": filename,
                "error": "No text layer available; run email_attachment_ingest to index it",
            }

        truncated = len(text) > max(1, min(max_chars, _MAX_EXTRACT_CHARS))
        return {
            "success": True,
            "attachment_id": attachment_id,
            "filename": filename,
            "size": record.get("size") or len(data),
            "text": spotlight_email_content(text[: max(1, min(max_chars, _MAX_EXTRACT_CHARS))]),
            "truncated": truncated,
        }
    except Exception as e:
        logger.error(f"email_attachment_get_text failed: {e}")
        return {"success": False, "error": str(e)}


async def email_attachment_stage_file(
    user_id: str,
    canvas_id: str,
    filename: str,
    content_b64: str,
    content_type: str = "",
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Stage a SMALL generated file onto the email draft (≤256KB base64 —
    e.g. a summary CSV). Larger files: ask the user to upload.

    Args:
        user_id: Owning user id
        canvas_id: Email canvas id
        filename: File name (extension must be allowed)
        content_b64: Base64 file content
        content_type: MIME type (optional)
        agent_id: Calling agent id (for audit attribution)

    Returns:
        {"success", "attachment": {...}} — record rides the draft's send list
    """
    import base64

    agent_id = _acting_agent_id(agent_id)
    try:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session

        data = base64.b64decode(content_b64 or "", validate=False)
        if not data:
            return {"success": False, "error": "content_b64 is empty"}
        if len(data) > AGENT_STAGE_FILE_MAX_BYTES:
            return {
                "success": False,
                "error": (
                    f"File exceeds the {AGENT_STAGE_FILE_MAX_BYTES // 1024} KB "
                    "agent staging cap — ask the user to upload it"
                ),
            }

        with get_db_session() as db:
            svc = EmailCanvasService(db)
            gated = _gate(db, user_id, agent_id)
            if gated:
                return gated
            result = svc.stage_attachments(
                canvas_id,
                user_id,
                [
                    {
                        "filename": filename,
                        "content_bytes": data,
                        "content_type": content_type,
                    }
                ],
                agent_id=agent_id,
            )
        if result.get("success"):
            result["message"] = f"Staged {filename} on the email draft"
        return result
    except Exception as e:
        logger.error(f"email_attachment_stage_file failed: {e}")
        return {"success": False, "error": str(e)}


async def email_attachment_attach(
    user_id: str,
    canvas_id: str,
    message_id: str,
    attachment_id: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Attach a file from a received email in the thread onto the outgoing
    draft (e.g. "attach the contract she sent back").

    Args:
        user_id: Owning user id
        canvas_id: Email canvas id
        message_id: Thread message the file arrived on
        attachment_id: Attachment id within that message
        agent_id: Calling agent id (for audit attribution)

    Returns:
        {"success", "attachment": {...}}
    """
    agent_id = _acting_agent_id(agent_id)
    try:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session

        with get_db_session() as db:
            svc = EmailCanvasService(db)
            gated = _gate(db, user_id, agent_id)
            if gated:
                return gated

            metadata = svc._latest_email_metadata(canvas_id)
            if metadata is None:
                return {"success": False, "error": "Email canvas not found"}
            if svc._canvas_owner_id(canvas_id) != user_id:
                return {"success": False, "error": "Not the canvas owner"}

            source = None
            for msg in metadata.get("messages") or []:
                if msg.get("message_id") != message_id:
                    continue
                for att in msg.get("attachments") or []:
                    att_key = str(
                        att.get("attachment_id")
                        or att.get("attachmentId")
                        or att.get("id")
                        or ""
                    )
                    if att_key == attachment_id:
                        source = att
                        break
            if source is None:
                return {
                    "success": False,
                    "error": f"Attachment {attachment_id} not found on message {message_id}",
                }

            draft_ids = {
                a.get("attachment_id") for a in metadata.get("attachments") or []
            }
            if attachment_id in draft_ids:
                return {
                    "success": True,
                    "already_attached": True,
                    "attachment_id": attachment_id,
                }

            record = {
                "attachment_id": attachment_id,
                "message_id": message_id,
                "provider": source.get("provider") or "outlook",
                "filename": source.get("filename")
                or source.get("name")
                or "attachment",
                "content_type": source.get("content_type")
                or source.get("contentType")
                or source.get("mimeType")
                or "application/octet-stream",
                "size": source.get("size") or 0,
                "is_inline": bool(source.get("is_inline") or source.get("isInline")),
                "origin": "received",
                "ingestion": source.get("ingestion"),
                "added_by": {
                    "actor": "agent" if agent_id else "user",
                    "user_id": user_id,
                    "agent_id": agent_id,
                },
                "created_at": datetime.now().isoformat(),
            }
            metadata.setdefault("attachments", []).append(record)
            svc._record_attachment_state(
                canvas_id, user_id, agent_id, metadata, "attach"
            )
            return {"success": True, "attachment": record}
    except Exception as e:
        logger.error(f"email_attachment_attach failed: {e}")
        return {"success": False, "error": str(e)}


async def email_attachment_remove(
    user_id: str,
    canvas_id: str,
    attachment_id: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Remove an attachment from the email draft. Staged files are deleted;
    received ones are detached from the draft (mailbox copy untouched).

    Args:
        user_id: Owning user id
        canvas_id: Email canvas id
        attachment_id: Attachment record id
        agent_id: Calling agent id (for audit attribution)

    Returns:
        {"success", "attachment_id", "staged_deleted"}
    """
    agent_id = _acting_agent_id(agent_id)
    try:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session

        with get_db_session() as db:
            svc = EmailCanvasService(db)
            gated = _gate(db, user_id, agent_id)
            if gated:
                return gated
            return svc.remove_attachment(canvas_id, user_id, attachment_id, agent_id)
    except Exception as e:
        logger.error(f"email_attachment_remove failed: {e}")
        return {"success": False, "error": str(e)}


async def email_attachment_ingest(
    user_id: str,
    canvas_id: str,
    attachment_id: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Index an email attachment's text into memory so its content is
    recallable across chats (PDF/DOCX/XLSX etc.).

    Args:
        user_id: Owning user id
        canvas_id: Email canvas id
        attachment_id: Attachment record id
        agent_id: Calling agent id (for audit attribution)

    Returns:
        {"success", "ingestion": {status, doc_id}}
    """
    agent_id = _acting_agent_id(agent_id)
    try:
        from core.canvas_email_service import EmailCanvasService
        from core.database import get_db_session

        with get_db_session() as db:
            svc = EmailCanvasService(db)
            gated = _gate(db, user_id, agent_id)
            if gated:
                return gated
            return await svc.ingest_attachment(canvas_id, user_id, attachment_id, agent_id)
    except Exception as e:
        logger.error(f"email_attachment_ingest failed: {e}")
        return {"success": False, "error": str(e)}
