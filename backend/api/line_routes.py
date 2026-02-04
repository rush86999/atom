"""
LINE API Routes

Provides REST endpoints for LINE messaging integration.
"""

import logging
from typing import Any, Dict, List, Optional
from core.base_routes import BaseAPIRouter
from fastapi import Depends, HTTPException, Query, status, Header
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.requests import Request

from core.database import get_db_session
from integrations.adapters.line_adapter import line_adapter

logger = logging.getLogger(__name__)

router = BaseAPIRouter(prefix="/api/line", tags=["LINE"])


# ============================================================================
# Request/Response Models
# ============================================================================

class SendMessageRequest(BaseModel):
    """Request to send LINE message"""
    to: str = Field(..., description="User ID, group ID, or room ID")
    text: str = Field(..., description="Message text (max 2000 chars)")
    reply_token: Optional[str] = Field(None, description="Reply token if replying to message")


class SendMessagesRequest(BaseModel):
    """Request to send multiple LINE messages"""
    to: str = Field(..., description="User ID, group ID, or room ID")
    messages: List[Dict[str, Any]] = Field(..., description="List of message objects")
    reply_token: Optional[str] = Field(None, description="Reply token if replying")


class SendQuickReplyRequest(BaseModel):
    """Request to send message with quick replies"""
    to: str = Field(..., description="User ID")
    text: str = Field(..., description="Message text")
    quick_reply_items: List[Dict[str, Any]] = Field(..., description="Quick reply buttons")
    reply_token: Optional[str] = Field(None, description="Reply token if replying")


class SendTemplateRequest(BaseModel):
    """Request to send template message"""
    to: str = Field(..., description="User ID")
    alt_text: str = Field(..., description="Alternative text")
    template: Dict[str, Any] = Field(..., description="Template object")
    reply_token: Optional[str] = Field(None, description="Reply token if replying")


# ============================================================================
# LINE Messaging Endpoints
# ============================================================================

@router.post("/webhook")
async def handle_line_webhook(
    request: Request,
    x_line_signature: str = Header(..., alias="X-Line-Signature"),
    db: Session = Depends(get_db_session),
):
    """
    Handle incoming LINE webhook event.

    Processes messages, follows, unfollows, joins, postbacks, and beacons.
    Verifies X-Line-Signature.
    """
    try:
        # Get raw body for signature verification
        body = await request.body()

        # Verify signature
        if not line_adapter.verify_signature(body, x_line_signature):
            logger.warning("Invalid LINE webhook signature")
            raise HTTPException(
                status_code=status.HTTP_403_FORBIDDEN,
                detail="Invalid signature"
            )

        # Parse JSON body
        import json
        event_data = json.loads(body.decode('utf-8'))

        result = await line_adapter.handle_webhook_event(event_data)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling LINE webhook: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/send-message")
async def send_line_message(
    request: SendMessageRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send a text message to LINE recipient.

    Supports user IDs, group IDs, and room IDs.
    """
    try:
        result = await line_adapter.send_message(
            to=request.to,
            text=request.text,
            reply_token=request.reply_token
        )

        if not result.get('ok'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to send message')
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE message: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/send-messages")
async def send_line_messages(
    request: SendMessagesRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send multiple messages to LINE recipient.

    Messages are sent in order as a batch.
    """
    try:
        result = await line_adapter.send_messages(
            to=request.to,
            messages=request.messages,
            reply_token=request.reply_token
        )

        if not result.get('ok'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to send messages')
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE messages: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/send-quick-reply")
async def send_line_quick_reply(
    request: SendQuickReplyRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send message with quick reply buttons.

    Quick replies allow users to respond with button taps.
    """
    try:
        result = await line_adapter.send_quick_reply(
            to=request.to,
            text=request.text,
            quick_reply_items=request.quick_reply_items,
            reply_token=request.reply_token
        )

        if not result.get('ok'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to send quick reply')
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE quick reply: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.post("/send-template")
async def send_line_template(
    request: SendTemplateRequest,
    db: Session = Depends(get_db_session),
):
    """
    Send a template message (buttons, carousel, confirm).

    Templates provide rich interactive UI components.
    """
    try:
        result = await line_adapter.send_template_message(
            to=request.to,
            alt_text=request.alt_text,
            template=request.template,
            reply_token=request.reply_token
        )

        if not result.get('ok'):
            raise HTTPException(
                status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
                detail=result.get('error', 'Failed to send template')
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE template: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/user/{user_id}/profile")
async def get_line_user_profile(
    user_id: str,
    db: Session = Depends(get_db_session),
):
    """Get LINE user profile information."""
    try:
        result = await line_adapter.get_user_profile(user_id)

        if not result.get('ok'):
            raise HTTPException(
                status_code=status.HTTP_404_NOT_FOUND,
                detail=result.get('error', 'User not found')
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LINE user profile: {e}")
        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail=str(e)
        )


@router.get("/health")
async def line_health():
    """LINE health check"""
    try:
        status = await line_adapter.get_service_status()
        if status.get('status') == 'active':
            return {"status": "healthy", "service": "LINE"}
        return {"status": "inactive", "service": "LINE"}
    except Exception as e:
        logger.error(f"LINE health check failed: {e}")
        raise router.internal_error(
            message="Health check failed",
            details={"error": str(e)}
        )


@router.get("/status")
async def line_status():
    """Get detailed LINE status"""
    try:
        return await line_adapter.get_service_status()
    except Exception as e:
        logger.error(f"LINE status check failed: {e}")
        raise router.internal_error(
            message="Status check failed",
            details={"error": str(e)}
        )


@router.get("/capabilities")
async def line_capabilities():
    """Get LINE integration capabilities"""
    return await line_adapter.get_capabilities()
