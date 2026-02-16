"""
WhatsApp Routes for ATOM Platform
Exposes WhatsApp webhook endpoints with IMGovernanceService integration
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, Request, HTTPException, Query, BackgroundTasks, Depends
from pydantic import BaseModel
from sqlalchemy.orm import Session

from core.im_governance_service import IMGovernanceService
from integrations.universal_webhook_bridge import universal_webhook_bridge
from core.communication.adapters.whatsapp import WhatsAppAdapter
from core.database import get_db

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/whatsapp", tags=["WhatsApp"])

# Global adapter instance
whatsapp_adapter = WhatsAppAdapter()


@router.get("/webhook")
async def whatsapp_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    WhatsApp webhook verification endpoint (GET).

    Meta sends a GET request to verify the webhook URL:
    - hub.mode: "subscribe"
    - hub.challenge: Random string to echo back
    - hub.verify_token: Token you set in Meta dashboard

    Environment Variables:
    - WHATSAPP_VERIFY_TOKEN: Random string set in Meta dashboard
      Generate with: openssl rand -hex 16

    Returns the hub.challenge to verify the webhook.
    """
    expected_token = os.getenv("WHATSAPP_VERIFY_TOKEN", "default_random_token_change_in_prod")

    if hub_mode == "subscribe" and hub_verify_token == expected_token:
        logger.info("WhatsApp webhook verified successfully")
        return int(hub_challenge)

    logger.warning("WhatsApp webhook verification failed")
    raise HTTPException(status_code=403, detail="Verification failed")


@router.post("/webhook")
async def whatsapp_webhook(
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    """
    WhatsApp webhook endpoint for incoming messages (POST).

    Flow:
    1. IMGovernanceService verifies signature + rate limits
    2. IMGovernanceService checks permissions
    3. UniversalWebhookBridge processes message
    4. IMGovernanceService logs to audit trail (background)
    """
    import hashlib
    import hmac

    # Initialize IMGovernanceService with database session
    im_governance_service = IMGovernanceService(db)

    # Get raw body bytes for signature verification
    body_bytes = await request.body()

    # Stage 1: Verify signature and rate limit
    try:
        verification_result = await im_governance_service.verify_and_rate_limit(
            request, body_bytes, platform="whatsapp"
        )
    except HTTPException as e:
        # Rate limited or signature invalid
        logger.warning(f"WhatsApp webhook rejected: {e.detail}")
        raise

    # Stage 2: Check permissions
    await im_governance_service.check_permissions(
        sender_id=verification_result["sender_id"],
        platform="whatsapp"
    )

    # Parse JSON payload
    try:
        payload = await request.json()
    except Exception as e:
        logger.error(f"Failed to parse WhatsApp webhook: {e}")
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # Stage 3: Route to Universal Webhook Bridge
    try:
        result = await universal_webhook_bridge.process_incoming_message("whatsapp", payload)

        # Log to audit trail (async, non-blocking)
        background_tasks.add_task(
            im_governance_service.log_to_audit_trail,
            platform="whatsapp",
            sender_id=verification_result["sender_id"],
            payload=payload,
            action="webhook_received",
            success=True
        )

        return result

    except Exception as e:
        logger.error(f"WhatsApp webhook processing failed: {e}")

        # Log failure to audit trail
        background_tasks.add_task(
            im_governance_service.log_to_audit_trail,
            platform="whatsapp",
            sender_id=verification_result["sender_id"],
            payload=payload,
            action="webhook_received",
            success=False,
            error_message=str(e)
        )

        raise HTTPException(status_code=500, detail="Processing failed")


@router.get("/health")
async def whatsapp_health():
    """WhatsApp health check"""
    return {"status": "healthy", "service": "WhatsApp"}


@router.get("/status")
async def whatsapp_status():
    """Get WhatsApp integration status"""
    return {
        "platform": "whatsapp",
        "adapter": "WhatsAppAdapter",
        "features": {
            "messaging": True,
            "media": True,  # Audio, images
            "governance": True
        }
    }
