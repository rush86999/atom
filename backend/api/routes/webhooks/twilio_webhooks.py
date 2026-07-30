import logging
import os
import hmac
import hashlib
import base64
from urllib.parse import urlencode
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Form
from sqlalchemy.orm import Session
from core.database import get_db
from core.integration_registry import IntegrationRegistry
from api.routes.webhooks.base import get_webhook_registry, verify_hmac_signature
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["Twilio Webhooks"])


def _verify_twilio_signature(request: Request, signature: Optional[str], form_data: dict) -> bool:
    """Verify Twilio's X-Twilio-Signature header.

    Twilio signs: base64(HMAC-SHA1(auth_token, URL + sorted_urlencoded_params)).
    Fails closed when no auth token is configured.
    """
    auth_token = os.getenv("TWILIO_AUTH_TOKEN", "")
    if not auth_token:
        logger.error("Twilio webhook received but TWILIO_AUTH_TOKEN not set — rejecting")
        return False
    if not signature:
        return False

    # Reconstruct the URL Twilio signed (the full callback URL).
    url = str(request.url)
    if url.startswith("http://") and request.headers.get("x-forwarded-proto") == "https":
        url = "https://" + url[len("http://"):]

    # Twilio appends params sorted by key, URL-encoded.
    sorted_params = urlencode(sorted(form_data.items()))
    data = (url + sorted_params).encode()

    computed = base64.b64encode(
        hmac.new(auth_token.encode(), data, hashlib.sha1).digest()
    ).decode()
    return hmac.compare_digest(computed, signature)


@router.post("/sms")
async def twilio_sms_webhook(
    request: Request,
    X_Twilio_Signature: str = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry),
    db: Session = Depends(get_db)
):
    """
    Unified Twilio SMS webhook callback.
    Standardizes messages via the IntegrationRegistry.
    """
    params = await request.form()
    data = dict(params)

    # Verify Twilio signature — previously accepted but never checked (forged
    # SMS callbacks processed). Fails closed: rejects if no auth token.
    if not _verify_twilio_signature(request, X_Twilio_Signature, data):
        raise HTTPException(status_code=401, detail="Invalid Twilio signature")

    to_number = data.get("To")
    tenant_id = to_number or "default"

    result = await webhook_bridge.process_event(
        "twilio",
        tenant_id,
        data,
        registry,
        db
    )

    return result

@router.post("/status")
async def twilio_status_webhook(
    request: Request,
    X_Twilio_Signature: str = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry)
):
    """Twilio Status callback (Message delivered, failed)."""
    params = await request.form()
    data = dict(params)

    if not _verify_twilio_signature(request, X_Twilio_Signature, data):
        raise HTTPException(status_code=401, detail="Invalid Twilio signature")

    tenant_id = data.get("To", "default")
    await registry.execute_operation(
        "twilio",
        tenant_id,
        "track_status_callback",
        {"data": data}
    )

    return {"status": "ok"}
