"""
Facebook Messenger API Routes

Provides REST endpoints for Facebook Messenger integration.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.requests import Request

from core.base_routes import BaseAPIRouter
from core.database import get_db_session
from integrations.adapters.messenger_adapter import messenger_adapter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/messenger", tags=["Facebook Messenger"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request to send Messenger message"""
    recipient_id: str = Field(..., description="PSID (Page-Scoped ID) of recipient")
    message: str = Field(..., description="Message text")
    messaging_type: str = Field("RESPONSE", description="RESPONSE, UPDATE, or MESSAGE_TAG")
    quick_replies: Optional[List[Dict[str, Any]]] = Field(None, description="Quick reply buttons")


class SendAttachmentRequest(BaseModel):
    """Request to send attachment"""
    recipient_id: str = Field(..., description="PSID of recipient")
    attachment_type: str = Field(..., description="image, audio, video, or file")
    attachment_url: str = Field(..., description="URL of the attachment")
    messaging_type: str = Field("RESPONSE", description="Message type")


# ============================================================================
# Facebook Messenger Endpoints
# ============================================================================

@router.get("/webhook")
async def verify_messenger_webhook(
    mode: str = Query(..., alias="hub.mode", description="Hub mode"),
    token: str = Query(..., alias="hub.verify_token", description="Verify token"),
    challenge: str = Query(..., alias="hub.challenge", description="Challenge string"),
    db: Session = Depends(get_db_session),
):
    """
    Verify Facebook webhook subscription.

    Facebook sends a GET request with mode, verify_token, and challenge
    to verify the webhook endpoint during subscription setup.
    """
    try:
        result = messenger_adapter.verify_webhook(mode, token, challenge)

        if not result.get('ok'):
            raise router.permission_denied_error(message="Verification failed", details={"error": result.get('error', 'Unknown error')})

        # Return challenge to verify webhook
        return {"hub.challenge": result['challenge']}

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error verifying Messenger webhook: {e}")
        raise router.internal_error(message="Error verifying Messenger webhook", details={"error": str(e)})


@router.post("/webhook")
async def handle_messenger_webhook(
    request: Request,
    x_hub_signature: Optional[str] = Header(None, alias="X-Hub-Signature"),
    db: Session = Depends(get_db_session),
):
    """
    Handle incoming Facebook webhook event.

    Processes incoming messages, deliveries, reads, and postbacks.
    Verifies X-Hub-Signature if app_secret is configured.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature if provided
        if x_hub_signature and messenger_adapter.app_secret:
            if not messenger_adapter.verify_signature(body, x_hub_signature):
                logger.warning("Invalid webhook signature")
                raise router.permission_denied_error(message="Invalid signature")

        # Parse JSON body
        import json
        event_data = json.loads(body.decode('utf-8'))

        result = await messenger_adapter.handle_webhook_event(event_data)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling Messenger webhook: {e}")
        raise router.internal_error(message="Error handling Messenger webhook", details={"error": str(e)})


@router.post("/send-message")
async def send_messenger_message(
    request: SendMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send a message to Facebook Messenger recipient.

    Requires PSID (Page-Scoped ID) of the recipient.
    """
    try:
        result = await messenger_adapter.send_message(
            recipient_id=request.recipient_id,
            message=request.message,
            messaging_type=request.messaging_type,
            quick_replies=request.quick_replies
        )

        if not result.get('ok'):
            raise router.internal_error(
                message="Failed to send message",
                details={"error": result.get('error', 'Unknown error')}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Messenger message: {e}")
        raise router.internal_error(message="Error sending Messenger message", details={"error": str(e)})


@router.post("/send-attachment")
async def send_messenger_attachment(
    request: SendAttachmentRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send an attachment to Messenger recipient.

    Supports image, audio, video, and file attachments.
    """
    try:
        result = await messenger_adapter.send_attachment(
            recipient_id=request.recipient_id,
            attachment_type=request.attachment_type,
            attachment_url=request.attachment_url,
            messaging_type=request.messaging_type
        )

        if not result.get('ok'):
            raise router.internal_error(
                message="Failed to send attachment",
                details={"error": result.get('error', 'Unknown error')}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending Messenger attachment: {e}")
        raise router.internal_error(message="Error sending Messenger attachment", details={"error": str(e)})


@router.get("/user/{user_id}")
async def get_messenger_user_info(
    user_id: str,
    db: Session = Depends(get_db_session),
):
    """Get information about a Messenger user."""
    try:
        result = await messenger_adapter.get_user_info(user_id)

        if not result.get('ok'):
            raise router.not_found_error(message="User not found", details={"error": result.get('error', 'Unknown error')})

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Messenger user info: {e}")
        raise router.internal_error(message="Error getting Messenger user info", details={"error": str(e)})


@router.get("/health")
async def messenger_health():
    """Messenger health check"""
    try:
        status = await messenger_adapter.get_service_status()
        if status.get('status') == 'active':
            return {"status": "healthy", "service": "Facebook Messenger"}
        return {"status": "inactive", "service": "Facebook Messenger"}
    except Exception as e:
        logger.error(f"Messenger health check failed: {e}")
        raise router.internal_error(
            message="Health check failed",
            details={"error": str(e)}
        )


@router.get("/status")
async def messenger_status():
    """Get detailed Messenger status"""
    try:
        return await messenger_adapter.get_service_status()
    except Exception as e:
        logger.error(f"Messenger status check failed: {e}")
        raise router.internal_error(
            message="Status check failed",
            details={"error": str(e)}
        )


@router.get("/capabilities")
async def messenger_capabilities():
    """Get Messenger integration capabilities"""
    return await messenger_adapter.get_capabilities()
