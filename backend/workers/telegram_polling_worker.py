"""
Telegram Long-Polling Worker

NAT-friendly alternative to the webhook pipeline: instead of Telegram calling
us, we call Telegram. getUpdates long-polling needs no public URL, no tunnel,
and no domain — the Personal Edition ("single user, Telegram-only IM") works
anywhere out of the box.

Processes updates through the same governance + Universal Webhook Bridge path
as the HTTP webhook route (see integrations/telegram_routes.py), so
maturity gates, audit trail, and agent replies behave identically.

Enable with TELEGRAM_POLLING_ENABLED=true (and TELEGRAM_BOT_TOKEN set).
Telegram forbids webhook and polling at once, so the worker deletes any
registered webhook on startup.
"""

import asyncio
import logging
import os
from typing import Any, Dict, Optional

import httpx

logger = logging.getLogger(__name__)

TELEGRAM_API_BASE = "https://api.telegram.org"
LONG_POLL_TIMEOUT_SECONDS = 25
POLL_RESTART_DELAY_SECONDS = 3
MAX_UPDATES_PER_REQUEST = 50


class TelegramPollingWorker:
    """Background worker that long-polls Telegram getUpdates and dispatches
    messages through the same pipeline as the webhook route."""

    def __init__(self, bot_token: Optional[str] = None):
        self.bot_token = bot_token or os.getenv("TELEGRAM_BOT_TOKEN", "")
        self.running = False
        self._offset = 0  # update_id of the last processed update + 1
        if not self.bot_token:
            logger.warning("TelegramPollingWorker: TELEGRAM_BOT_TOKEN not set — worker will idle")

    # ------------------------------------------------------------------ #
    # Telegram Bot API helpers
    # ------------------------------------------------------------------ #

    def _api_url(self, method: str) -> str:
        return f"{TELEGRAM_API_BASE}/bot{self.bot_token}/{method}"

    async def _delete_webhook(self) -> None:
        """Telegram rejects getUpdates while a webhook is registered (409)."""
        try:
            async with httpx.AsyncClient(timeout=15) as client:
                resp = await client.post(self._api_url("deleteWebhook"))
                data = resp.json()
                if data.get("ok"):
                    logger.info("TelegramPollingWorker: deleted registered webhook (polling mode)")
                else:
                    logger.warning(f"TelegramPollingWorker: deleteWebhook response: {data}")
        except Exception as e:
            logger.warning(f"TelegramPollingWorker: deleteWebhook failed: {e}")

    async def _get_updates(self, client: httpx.AsyncClient) -> list:
        resp = await client.post(
            self._api_url("getUpdates"),
            json={
                "offset": self._offset,
                "timeout": LONG_POLL_TIMEOUT_SECONDS,
                "limit": MAX_UPDATES_PER_REQUEST,
                "allowed_updates": ["message", "callback_query"],
            },
        )
        data = resp.json()
        if not data.get("ok"):
            description = data.get("description", "unknown error")
            if "409" in str(resp.status_code) or "Conflict" in description:
                # A webhook is still registered — remove it and retry next cycle.
                await self._delete_webhook()
            logger.warning(f"TelegramPollingWorker: getUpdates error: {description}")
            return []
        return data.get("result", [])

    # ------------------------------------------------------------------ #
    # Update processing (mirrors integrations/telegram_routes.py webhook)
    # ------------------------------------------------------------------ #

    async def _handle_update(self, update: Dict[str, Any]) -> None:
        from core.database import SessionLocal
        from core.im_governance_service import IMGovernanceService
        from integrations.atom_telegram_integration import atom_telegram_integration
        from integrations.universal_webhook_bridge import universal_webhook_bridge

        callback_query = update.get("callback_query")
        if callback_query:
            asyncio.create_task(atom_telegram_integration.handle_callback_query(callback_query))
            return

        message = update.get("message")
        if not message:
            return

        sender = message.get("from") or {}
        sender_id = str(sender.get("id", "unknown"))

        db = SessionLocal()
        try:
            im_governance_service = IMGovernanceService(db)

            # Polling skips the webhook-signature stage (we fetched the update
            # directly from Telegram over TLS) but keeps the permission gate
            # (blocked users, STUDENT-agent IM trigger block).
            try:
                await im_governance_service.check_permissions(
                    sender_id=sender_id, platform="telegram"
                )
            except Exception as e:
                logger.warning(f"Telegram polling permission check failed: {getattr(e, 'detail', e)}")
                await im_governance_service.log_to_audit_trail(
                    platform="telegram",
                    sender_id=sender_id,
                    payload=update,
                    action="polling_update_received",
                    success=False,
                    error_message=str(getattr(e, "detail", e)),
                )
                return

            try:
                await universal_webhook_bridge.process_incoming_message("telegram", message)
                await im_governance_service.log_to_audit_trail(
                    platform="telegram",
                    sender_id=sender_id,
                    payload=update,
                    action="polling_update_received",
                    success=True,
                )
                # Persist to the communication memory store (vector+FTS) — the
                # tiered webhook path does this for webhook mode; polling must
                # match it or IM conversations never become retrievable memory.
                asyncio.create_task(self._ingest_to_comm_store(message))
            except Exception as e:
                logger.error(f"Telegram polling processing failed: {e}")
                await im_governance_service.log_to_audit_trail(
                    platform="telegram",
                    sender_id=sender_id,
                    payload=update,
                    action="polling_update_received",
                    success=False,
                    error_message=str(e),
                )
        finally:
            db.close()

    async def _ingest_to_comm_store(self, message: Dict[str, Any]) -> None:
        """Fire-and-forget: write the message to the comms memory store."""
        try:
            from integrations.atom_communication_ingestion_pipeline import (
                get_ingestion_pipeline,
            )

            pipeline = get_ingestion_pipeline("default")
            # Stable id: raw Telegram messages carry only `message_id`, and
            # the normalizer's fallback mints a fresh timestamp id per call —
            # every re-delivered update (restart re-poll re-delivers pending
            # updates for up to 24h because the polling offset is in-memory)
            # became a NEW duplicate row. Key on chat + Telegram message id
            # so the poller's seen-id dedup (store-reconciled) applies.
            message = dict(message)
            message["id"] = (
                f"tg_{message.get('chat', {}).get('id', 'unknown')}"
                f"_{message.get('message_id', 'unknown')}"
            )
            if pipeline.is_message_known("telegram", message["id"]):
                return
            success = await pipeline.ingest_message("telegram", message)
            if success:
                pipeline.mark_message_ingested("telegram", message["id"])
        except Exception as e:
            logger.debug(f"TelegramPollingWorker: comm-store ingest skipped: {e}")

    # ------------------------------------------------------------------ #
    # Main loop
    # ------------------------------------------------------------------ #

    async def run(self) -> None:
        self.running = True
        logger.info("TelegramPollingWorker: starting long-poll loop")
        await self._delete_webhook()

        async with httpx.AsyncClient(timeout=LONG_POLL_TIMEOUT_SECONDS + 15) as client:
            while self.running:
                if not self.bot_token:
                    await asyncio.sleep(60)
                    continue
                try:
                    updates = await self._get_updates(client)
                    for update in updates:
                        self._offset = max(self._offset, int(update.get("update_id", 0)) + 1)
                        await self._handle_update(update)
                except asyncio.CancelledError:
                    logger.info("TelegramPollingWorker: cancelled")
                    raise
                except Exception as e:
                    logger.warning(f"TelegramPollingWorker: poll cycle failed: {e}")
                    await asyncio.sleep(POLL_RESTART_DELAY_SECONDS)

    def stop(self) -> None:
        self.running = False
