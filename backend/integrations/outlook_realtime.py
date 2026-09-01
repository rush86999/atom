"""Outlook REAL-TIME ingestion — Graph webhook subscriptions + polling.

Microsoft's recommended incremental-sync pattern: webhook subscriptions
signal THAT something changed; the fetch retrieves WHAT changed; mail
subscriptions expire (≈3 days max) so a renewal loop is mandatory; and every
notification's clientState must be verified against the stored value or the
notification is a spoof.

Channel selection:
- If ATOM_GRAPH_WEBHOOK_BASE_URL is set (public HTTPS reachable), the manager
  creates/renews a Graph subscription on the Inbox → notifications hit the
  Graph-compatible route (POST /api/integrations/microsoft365/webhook) and
  messages are fetched + ingested within seconds.
- Otherwise the 60s poller (ATOM_OUTLOOK_POLL_SECONDS tunable) is the
  channel. Both channels converge on the same seen-id dedup, so overlap
  costs nothing.

Training-circuit framing: whatever the channel, fresh INBOUND mail lands in
the comms memory store immediately, so the hire recalls it (provenance-
spotlighted) on the very next turn, and the communication-intelligence
response modes can pre-draft a reply for HITL approval.
"""
from __future__ import annotations

import asyncio
import json
import logging
import os
import secrets
from datetime import datetime, timedelta, timezone
from typing import Any, Dict, List, Optional

logger = logging.getLogger(__name__)

STATE_FILE = os.path.join("data", "outlook_subscription_state.json")
SUBSCRIPTION_HOURS = 71  # mail subscriptions max ~3 days; renew well before
RENEW_CHECK_SECONDS = 600

WEBHOOK_PATH = "/api/integrations/microsoft365/webhook"


def _public_base_url() -> str:
    return (os.getenv("ATOM_GRAPH_WEBHOOK_BASE_URL") or "").rstrip("/")


def _load_state() -> Dict[str, Any]:
    try:
        with open(STATE_FILE, "r") as f:
            return json.load(f)
    except Exception:
        return {}


def _save_state(state: Dict[str, Any]) -> None:
    try:
        os.makedirs(os.path.dirname(STATE_FILE), exist_ok=True)
        with open(STATE_FILE, "w") as f:
            json.dump(state, f)
    except Exception as state_err:
        logger.debug(f"subscription state save skipped: {state_err}")


class OutlookRealtimeManager:
    """Create/renew the Graph mail subscription and process notifications."""

    def __init__(self):
        self._state: Dict[str, Any] = _load_state()
        self._renew_task: Optional[asyncio.Task] = None

    # -- clientState ---------------------------------------------------------

    @property
    def client_state(self) -> str:
        if not self._state.get("client_state"):
            self._state["client_state"] = secrets.token_urlsafe(32)
            _save_state(self._state)
        return self._state["client_state"]

    def verify_client_state(self, received: Optional[str]) -> bool:
        """Anti-spoofing: Graph echoes our secret on every notification."""
        expected = self.client_state
        if not received or received != expected:
            logger.warning("Graph notification rejected: clientState mismatch")
            return False
        return True

    # -- subscription lifecycle ----------------------------------------------

    def realtime_enabled(self) -> bool:
        return bool(_public_base_url())

    async def ensure_subscription(self, user_id: str) -> Dict[str, Any]:
        """Create the subscription when a public URL is configured (idempotent)."""
        base = _public_base_url()
        if not base:
            return {"enabled": False, "reason": "no public webhook URL (polling channel)"}
        expiry = self._state.get("expires_at")
        if expiry:
            try:
                if datetime.fromisoformat(expiry) > datetime.now(timezone.utc) + timedelta(
                    hours=24
                ):
                    return {"enabled": True, "subscription_id": self._state.get("id"), "reused": True}
            except ValueError:
                pass

        from integrations.microsoft365_service import Microsoft365Service
        from integrations.outlook_service import outlook_service

        # Same OAuth store the poller uses (IntegrationToken via outlook_service).
        token = await outlook_service._get_access_token(user_id=None)
        if not token:
            return {"enabled": False, "reason": "no Microsoft token for user"}

        result = await Microsoft365Service(config={}).create_subscription(
            token,
            "/me/mailFolders('Inbox')/messages",
            "created",
            f"{base}{WEBHOOK_PATH}",
            (datetime.now(timezone.utc) + timedelta(hours=SUBSCRIPTION_HOURS)).strftime(
                "%Y-%m-%dT%H:%M:%SZ"
            ),
        )
        data = result.get("data") or {}
        if result.get("status") != "success" or not data.get("id"):
            return {"enabled": False, "reason": f"subscription create failed: {result.get('message')}"}

        self._state.update(
            {
                "id": data["id"],
                "client_state": self.client_state,
                "expires_at": data.get("expirationDateTime")
                or (datetime.now(timezone.utc) + timedelta(hours=SUBSCRIPTION_HOURS)).isoformat(),
                "user_id": user_id,
            }
        )
        _save_state(self._state)
        logger.info(f"Graph mail subscription active (id={data['id'][:12]}…, channel=webhook)")
        return {"enabled": True, "subscription_id": data["id"]}

    async def renew_loop(self) -> None:
        """Renew before expiry; runs forever, best-effort."""
        while True:
            try:
                if self.realtime_enabled() and self._state.get("id"):
                    expiry = self._state.get("expires_at", "")
                    try:
                        due = datetime.fromisoformat(expiry) <= datetime.now(
                            timezone.utc
                        ) + timedelta(hours=24)
                    except ValueError:
                        due = True
                    if due:
                        user_id = self._state.get("user_id", "")
                        await self.ensure_subscription(str(user_id))
            except Exception as renew_err:  # never kill the loop
                logger.debug(f"subscription renewal skipped: {renew_err}")
            await asyncio.sleep(RENEW_CHECK_SECONDS)

    def start_renew_loop(self) -> None:
        if self._renew_task is None or self._renew_task.done():
            try:
                self._renew_task = asyncio.get_running_loop().create_task(
                    self.renew_loop()
                )
            except RuntimeError:
                logger.debug("renew loop not started (no running loop)")

    # -- notification processing ----------------------------------------------

    async def process_notifications(self, payload: Dict[str, Any]) -> Dict[str, Any]:
        """Verify + ingest a Graph notification payload (per-message fetch)."""
        for item in payload.get("value") or []:
            if not self.verify_client_state(item.get("clientState")):
                continue
            resource = str(item.get("resource") or "")
            message_id = str((item.get("resourceData") or {}).get("id") or "")
            if not message_id:
                continue
            try:
                message = await self._fetch_message(resource or message_id)
                if message:
                    from integrations.atom_communication_ingestion_pipeline import (
                        ingestion_pipeline,
                    )

                    await ingestion_pipeline.ingest_message("outlook", message)
            except Exception as ingest_err:
                logger.debug(f"webhook message ingest skipped: {ingest_err}")
        return {"status": "received"}

    async def _fetch_message(self, resource: str) -> Optional[Dict[str, Any]]:
        """Fetch one message by Graph resource path (raw Graph shape — the
        same shape the poller hands to ingest_message's normalizer)."""
        import httpx

        from integrations.atom_communication_ingestion_pipeline import POLLABLE_APPS  # noqa: F401
        from integrations.outlook_service import outlook_service

        access_token = await outlook_service._get_access_token(user_id=None)
        if not access_token:
            return None
        message_id = resource.split("/")[-1]
        graph_base = os.getenv(
            "MICROSOFT_GRAPH_BASE_URL", "https://graph.microsoft.com/v1.0"
        ).rstrip("/")
        async with httpx.AsyncClient(timeout=30.0) as client:
            response = await client.get(
                f"{graph_base}/me/messages/{message_id}",
                headers={"Authorization": f"Bearer {access_token}"},
            )
            if response.status_code != 200:
                logger.debug(f"webhook message fetch failed: {response.status_code}")
                return None
            return response.json()


outlook_realtime = OutlookRealtimeManager()
