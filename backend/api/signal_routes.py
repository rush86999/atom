"""
Signal API Routes

Provides REST endpoints for Signal messaging integration.
"""

import logging
from typing import Any, Dict, List, Optional
from core.base_routes import BaseAPIRouter
from fastapi import Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from core.database import get_db_session
from integrations.adapters.signal_adapter import signal_adapter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/signal", tags=["Signal"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request to send Signal message"""
    recipient_number: str = Field(..., description="Phone number with country code (e.g., +15551234567)")
    message: str = Field(..., description="Message text")
    attachments: Optional[List[Dict[str, Any]]] = Field(None, description="Optional attachments")


class SendMessageResponse(BaseModel):
    """Response for message sending"""
    ok: bool
    message_id: Optional[str] = None
    recipient: Optional[str] = None
    error: Optional[str] = None


class SendReceiptRequest(BaseModel):
    """Request to send receipt"""
    recipient_number: str = Field(..., description="Phone number")
    message_timestamp: str = Field(..., description="Timestamp of message")
    receipt_type: str = Field("read", description="read or delivery")


# ============================================================================
# Signal Messaging Endpoints
# ============================================================================

@router.post("/send-message", response_model=SendMessageResponse)
async def send_signal_message(
    request: SendMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send a message to Signal recipient.

    Signal is a secure messaging platform with end-to-end encryption.
    Requires phone number with country code (e.g., +15551234567).
    """
    try:
        result = await signal_adapter.send_message(
            recipient_number=request.recipient_number,
            message=request.message,
            attachments=request.attachments
        )

        if not result.get('ok'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to send message')
            )

        return result

    except Exception as e:
        logger.error(f"Error sending Signal message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/send-receipt")
async def send_signal_receipt(
    request: SendReceiptRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send read or delivery receipt for a message.

    Acknowledges that a message was read or delivered.
    """
    try:
        result = await signal_adapter.send_receipt(
            recipient_number=request.recipient_number,
            message_timestamp=request.message_timestamp,
            receipt_type=request.receipt_type
        )

        return result

    except Exception as e:
        logger.error(f"Error sending Signal receipt: {e}")
        return {'ok': False, 'error': str(e)}


@router.get("/account/info")
async def get_signal_account_info(
    db: Session = Depends(get_db_session),
):
    """Get information about the Signal account."""
    try:
        result = await signal_adapter.get_account_info()
        return result
    except Exception as e:
        logger.error(f"Error getting Signal account info: {e}")
        return {'ok': False, 'error': str(e)}


@router.post("/webhook/verify")
async def verify_signal_webhook(
    challenge: str = Query(..., description="Webhook challenge string"),
    db: Session = Depends(get_db_session),
):
    """
    Verify Signal webhook challenge.

    Signal REST API sends a challenge to verify the webhook endpoint.
    """
    try:
        result = await signal_adapter.verify_webhook(challenge)
        return result
    except Exception as e:
        logger.error(f"Error verifying Signal webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/webhook/event")
async def handle_signal_webhook_event(
    event_data: Dict[str, Any],
    db: Session = Depends(get_db_session),
):
    """
    Handle incoming Signal webhook event.

    Processes incoming messages and receipts from Signal.
    """
    try:
        result = await signal_adapter.handle_webhook_event(event_data)
        return result
    except Exception as e:
        logger.error(f"Error handling Signal webhook: {e}")
        return {'ok': False, 'error': str(e)}


@router.get("/health")
async def signal_health():
    """Signal health check"""
    try:
        status = await signal_adapter.get_service_status()
        if status.get('status') == 'active':
            return {"status": "healthy", "service": "Signal"}
        return {"status": "inactive", "service": "Signal"}
    except Exception as e:
        logger.error(f"Signal health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}


@router.get("/status")
async def signal_status():
    """Get detailed Signal status"""
    try:
        return await signal_adapter.get_service_status()
    except Exception as e:
        logger.error(f"Signal status check failed: {e}")
        return {"status": "error", "error": str(e)}


@router.get("/capabilities")
async def signal_capabilities():
    """Get Signal integration capabilities"""
    return await signal_adapter.get_capabilities()
