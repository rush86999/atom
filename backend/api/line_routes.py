"""
LINE API Routes

Provides REST endpoints for LINE messaging integration.
"""

import logging
from typing import Any, Dict, List, Optional
from fastapi import Depends, Header, Query, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session
from starlette.requests import Request

from core.base_routes import BaseAPIRouter
from core.database import get_db_session
from core.models import User
from core.security_dependencies import get_current_user
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
            raise router.permission_denied_error(message="Invalid signature")

        # Parse JSON body
        import json
        event_data = json.loads(body.decode('utf-8'))

        result = await line_adapter.handle_webhook_event(event_data)

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error handling LINE webhook: {e}")
        raise router.internal_error(message="Error handling LINE webhook", details={"error": str(e)})


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
            raise router.internal_error(
                message="Failed to send message",
                details={"error": result.get('error', 'Unknown error')}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE message: {e}")
        raise router.internal_error(message="Error sending LINE message", details={"error": str(e)})


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
            raise router.internal_error(
                message="Failed to send messages",
                details={"error": result.get('error', 'Unknown error')}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE messages: {e}")
        raise router.internal_error(message="Error sending LINE messages", details={"error": str(e)})


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
            raise router.internal_error(
                message="Failed to send quick reply",
                details={"error": result.get('error', 'Unknown error')}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE quick reply: {e}")
        raise router.internal_error(message="Error sending LINE quick reply", details={"error": str(e)})


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
            raise router.internal_error(
                message="Failed to send template",
                details={"error": result.get('error', 'Unknown error')}
            )

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error sending LINE template: {e}")
        raise router.internal_error(message="Error sending LINE template", details={"error": str(e)})


@router.get("/user/{user_id}/profile")
async def get_line_user_profile(
    user_id: str,
    current_user: User = Depends(get_current_user),
    db: Session = Depends(get_db_session),
):
    """
    Get LINE user profile information.

    ACCESS CONTROL FIX: Requires authentication and checks user access.
    Users can only access their own profile unless they have admin privileges.
    """
    try:
        # ACCESS CONTROL FIX: Verify user has permission to access this profile
        # Users can only access their own profile (user_id must match current_user.id)
        # Admin users can access any profile (add admin check if needed)

        # For now, enforce strict ownership: user_id must match current_user.id
        # This prevents IDOR attacks where users could access other users' profiles

        # Check if user is accessing their own profile
        # For LINE integration, we might need to map current_user.id to LINE user_id
        # This requires additional logic to verify the mapping

        # For now, add a warning if accessing different user's profile
        if user_id != current_user.id and not current_user.is_superuser:
            logger.warning(f"User {current_user.id} attempting to access LINE profile for user_id {user_id}")
            raise router.permission_denied_error(
                action="get_line_user_profile",
                resource="LINEUserProfile",
                details={"requested_user_id": user_id, "current_user_id": current_user.id}
            )

        result = await line_adapter.get_user_profile(user_id)

        if not result.get('ok'):
            raise router.not_found_error(message="User not found", details={"error": result.get('error', 'Unknown error')})

        return result

    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting LINE user profile: {e}")
        raise router.internal_error(message="Error getting LINE user profile", details={"error": str(e)})


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
