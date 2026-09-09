"""Communication Hub draft service — real implementation of the agent's
``draft_response`` / ``approve_draft`` / ``analyze_message`` tools.

History: these tools previously imported ``core.collaboration_hub_service``
which did NOT exist (phantom module) — every agent draft call failed with
"Collaboration Hub service not available". This module is the real backend.

Design (training purpose): a drafted reply becomes a THREADED DRAFT in the
actual provider mailbox (Outlook Drafts folder / Gmail Drafts), so a human
supervisor reviews/edits/sends it in the mail client — the natural training
loop. Nothing is sent by ``draft_response``; ``approve_draft`` sends the
threaded reply through the existing universal send path. No new DB store and
no migration: the mailbox is the store.

Provider/token resolution is delegated to UniversalIntegrationService (the
same registry+token path every other mail operation uses).
"""
from __future__ import annotations

import logging
from typing import Any, Dict, Optional

logger = logging.getLogger(__name__)

# Mail providers a draft can target (search order when platform is omitted).
_MAIL_PROVIDERS = ("outlook", "gmail")


class CollaborationHubService:
    """Draft + approve operations for the Communication Hub tool surface."""

    def __init__(self, db: Any = None):
        self._db = db  # kept for factory-signature compatibility

    # -- sync analysis leg (no persistence table exists; log-only today) -----
    def update_ai_analysis(self, message_id: Optional[str], analysis: Any) -> Dict[str, Any]:
        """Persist an agent's message analysis. No hub analysis table exists
        yet, so this is a best-effort log + ok (the agent's thought is what
        matters for training; storing comes with the hub UI work)."""
        logger.info("Hub analysis for message %s: %s", message_id,
                    str(analysis)[:200] if analysis else "")
        return {"status": "ok", "message_id": message_id}

    # -- draft leg ------------------------------------------------------------
    async def save_draft_response(
        self,
        message_id: Optional[str],
        content: str,
        confidence: float = 0.8,
        platform: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """Create a THREADED DRAFT reply to ``message_id`` (never sends)."""
        if not message_id:
            return {"status": "error", "error": "message_id is required"}
        text = str(content or "").strip()
        if not text:
            return {"status": "error", "error": "content is required"}

        from integrations.universal_integration_service import UniversalIntegrationService

        ctx = {"user_id": user_id, "workspace_id": workspace_id,
               "tenant_id": workspace_id}
        svc = UniversalIntegrationService(workspace_id=workspace_id)

        targets = [platform] if platform else list(_MAIL_PROVIDERS)
        errors = {}
        for prov in targets:
            try:
                result = await svc.execute(prov, "create_draft", {
                    "message_id": message_id,
                    "body": text,
                    "confidence": confidence,
                }, context=ctx)
            except Exception as e:  # pragma: no cover - defensive
                errors[prov] = str(e)[:200]
                continue
            data = result.get("data") or {}
            if result.get("status") == "success" and (data.get("draft_id") or data.get("id")):
                return {
                    "status": "success",
                    "platform": prov,
                    "draft_id": data.get("draft_id") or data.get("id"),
                    "message": "Draft saved — review it in the mailbox Drafts folder.",
                }
            errors[prov] = str(result.get("message") or result.get("error") or result)[:200]
        return {
            "status": "error",
            "error": "Draft failed on all providers: " + "; ".join(
                f"{p}: {e}" for p, e in errors.items()
            ),
        }

    # -- approve leg ----------------------------------------------------------
    async def approve_draft(
        self,
        message_id: Optional[str],
        edited_content: Optional[str] = None,
        platform: Optional[str] = None,
        user_id: Optional[str] = None,
        workspace_id: str = "default",
    ) -> Dict[str, Any]:
        """Send the approved reply in the original thread (approval-gated
        upstream by HITL policy before this tool is reachable)."""
        if not message_id:
            return {"status": "error", "error": "message_id is required"}
        text = str(edited_content or "").strip()
        if not text:
            return {"status": "error",
                    "error": "edited_content is required (or approve/send in the mail client)"}

        from integrations.universal_integration_service import UniversalIntegrationService

        ctx = {"user_id": user_id, "workspace_id": workspace_id,
               "tenant_id": workspace_id}
        svc = UniversalIntegrationService(workspace_id=workspace_id)
        targets = [platform] if platform else list(_MAIL_PROVIDERS)
        errors = {}
        for prov in targets:
            try:
                result = await svc.execute(prov, "send_message", {
                    "reply_to_message_id": message_id,
                    "body": text,
                }, context=ctx)
            except Exception as e:  # pragma: no cover - defensive
                errors[prov] = str(e)[:200]
                continue
            if result.get("status") == "success":
                return {"status": "success", "platform": prov,
                        "message": "Reply sent in the original thread."}
            errors[prov] = str(result.get("message") or result.get("error") or result)[:200]
        return {"status": "error", "error": "Send failed on all providers: " + "; ".join(
            f"{p}: {e}" for p, e in errors.items())}


_hub_instance: Optional[CollaborationHubService] = None


def get_collaboration_hub_service(db: Any = None) -> CollaborationHubService:
    """Factory kept signature-compatible with the (formerly phantom) import."""
    global _hub_instance
    if _hub_instance is None:
        _hub_instance = CollaborationHubService(db=db)
    return _hub_instance
