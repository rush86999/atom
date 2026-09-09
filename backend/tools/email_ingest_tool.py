"""Agent tool for on-demand email ingestion ("ingest this email").

Where the email_attachment_* tools operate on email-canvas drafts, this
tool addresses a MAILBOX message directly: fetch the full email (body +
attachments) from the owner's connected account and push it through the
same ingestion path the background poller uses, so it becomes recallable
memory even if the poller hasn't reached it yet. Idempotent by contract —
seen-id short-circuit plus the store-level dedup guard make a repeated
ask a truthful no-op.

Governed by the email_attachment autonomy topic (same knob as
email_attachment_ingest — both index mailbox content into memory), at
INTERN maturity: a memory write, not a send, and fully reversible by the
dedup design.
"""

from __future__ import annotations

import logging
from typing import Any, Dict, Optional

from tools.email_attachment_tool import _acting_agent_id, _gate

logger = logging.getLogger(__name__)

# Tool-level provider aliases → pipeline app_type. Anything else is
# rejected before touching the pipeline.
_PROVIDER_ALIASES = {
    "outlook": "outlook",
    "microsoft": "outlook",
    "graph": "outlook",
    "gmail": "gmail",
    "google": "gmail",
    "googlemail": "gmail",
}


async def email_ingest_message(
    user_id: str,
    provider: str,
    message_id: str,
    agent_id: Optional[str] = None,
) -> Dict[str, Any]:
    """Actively ingest one mailbox email (body + attachments) into memory
    so its content is recallable across chats — even if the background
    poller has not indexed it yet. Already-ingested mail is a no-op.

    Args:
        user_id: Mailbox-owning user id (fetch uses ONLY this user's token)
        provider: "outlook" or "gmail" (common aliases accepted)
        message_id: Provider message id (e.g. from outlook_search_emails /
            outlook_read_email)
        agent_id: Calling agent id (for audit attribution)

    Returns:
        {"success", "status": "ingested"|"already_ingested", ...} or
        {"success": False, "error"} / {"success": False, "needs_approval"}
    """
    agent_id = _acting_agent_id(agent_id)
    app = _PROVIDER_ALIASES.get((provider or "").strip().lower())
    if not app:
        return {
            "success": False,
            "error": (
                f"Unsupported provider {provider!r} — use 'outlook' or 'gmail'"
            ),
        }
    message_id = (message_id or "").strip()
    if not message_id:
        return {"success": False, "error": "message_id is required"}

    try:
        from core.database import get_db_session

        with get_db_session() as db:
            gated = _gate(db, user_id, agent_id)
            if gated:
                return gated

        from integrations.atom_communication_ingestion_pipeline import (
            ingestion_pipeline,
        )

        result = await ingestion_pipeline.ingest_email_on_demand(
            app, user_id, message_id
        )
        status = result.get("status")
        if status == "ingested":
            return {
                "success": True,
                "status": "ingested",
                "provider": app,
                "message_id": message_id,
                "subject": result.get("subject") or "",
                "attachments": result.get("attachments") or 0,
                "message": "Email ingested into memory (body + attachments)",
            }
        if status == "already_ingested":
            return {
                "success": True,
                "status": "already_ingested",
                "provider": app,
                "message_id": message_id,
                "message": "Email was already ingested — nothing to do",
            }
        return {
            "success": False,
            "error": result.get("reason") or "ingest_failed",
            "provider": app,
            "message_id": message_id,
        }
    except Exception as e:
        logger.error(f"email_ingest_message failed: {e}")
        return {"success": False, "error": str(e)}
