import logging
import os
import hmac
import hashlib
from typing import Any, Dict, Optional

from fastapi import APIRouter, Depends, Header, HTTPException, Query, Request
from sqlalchemy.orm import Session

from api.routes.webhooks.base import get_webhook_registry
from api.routes.webhooks.webhook_bridge import webhook_bridge
from core.credential_vault import find_tenant_by_platform_id
from core.database import get_db
from core.integration_registry import IntegrationRegistry

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/whatsapp", tags=["WhatsApp Webhooks"])


@router.get("")
async def whatsapp_verification(
    hub_mode: str = Query(..., alias="hub.mode"),
    hub_challenge: str = Query(..., alias="hub.challenge"),
    hub_verify_token: str = Query(..., alias="hub.verify_token"),
):
    """
    WhatsApp Webhook Verification (System Requirement).
    Meta calls this once to confirm our endpoint owns the verify token.
    """
    import os
    verify_token = os.getenv("WHATSAPP_WEBHOOK_VERIFY_TOKEN", "atom_whatsapp_verify_token_2024")
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        return int(hub_challenge)
    raise HTTPException(status_code=403, detail="Webhook verification failed")


@router.post("")
async def whatsapp_webhook(
    request: Request,
    x_hub_signature_256: Optional[str] = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry),
    db: Session = Depends(get_db),
):
    """
    Multi-tenant WhatsApp webhook.

    Resolves the incoming tenant by matching phone_number_id against
    encrypted TenantSetting rows via CredentialVault, then dispatches
    to the webhook bridge.
    """
    raw_body = await request.body()

    # Verify WhatsApp/Meta signature — x-hub-signature-256 is HMAC-SHA256 of
    # the raw body with the app secret (WHATSAPP_APP_SECRET). Previously the
    # header was accepted but never verified (forged events processed).
    app_secret = os.getenv("WHATSAPP_APP_SECRET", "")
    if not app_secret:
        logger.error("WhatsApp webhook received but WHATSAPP_APP_SECRET not set — rejecting")
        raise HTTPException(status_code=401, detail="App secret not configured")
    if not x_hub_signature_256:
        raise HTTPException(status_code=401, detail="Missing signature")
    expected = "sha256=" + hmac.new(app_secret.encode(), raw_body, hashlib.sha256).hexdigest()
    if not hmac.compare_digest(expected, x_hub_signature_256):
        raise HTTPException(status_code=401, detail="Invalid signature")

    # BUG (this wave): `request.json()` is an async coroutine in Starlette —
    # the un-awaited call returned a coroutine, so EVERY signature-valid
    # payload crashed with "'coroutine' object has no attribute 'get'".
    data = await request.json()

    entries = data.get("entry", [])
    if not entries:
        return {"status": "no_entries"}

    # --- Tenant resolution ---
    phone_number_id: Optional[str] = (
        entries[0]
        .get("changes", [{}])[0]
        .get("value", {})
        .get("metadata", {})
        .get("phone_number_id")
    )

    tenant_id: Optional[str] = None
    if phone_number_id:
        tenant_id = find_tenant_by_platform_id(db, "whatsapp", "phone_number_id", phone_number_id)

    if not tenant_id:
        logger.warning(
            f"No tenant found for WhatsApp phone_number_id={phone_number_id!r}. "
            "Dropping webhook."
        )
        # Return 200 to prevent Meta from retrying indefinitely
        return {"status": "tenant_not_found"}

    # --- Dispatch via Webhook Bridge ---
    # The UCB (Universal Communication Bridge) internally iterates over entries 
    # and messages, so we pass the full payload once.
    result = await webhook_bridge.process_event(
        "whatsapp",
        tenant_id,
        data,
        registry,
        db
    )

    return {"result": result, "status": "processed", "tenant_id": tenant_id}

