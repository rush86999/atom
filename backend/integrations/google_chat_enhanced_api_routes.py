"""
Google Chat Enhanced API Routes
Exposes GoogleChatEnhancedService via FastAPI
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel

from core.auth import get_current_user
from core.models import User
from integrations.google_chat_enhanced_service import GoogleChatEnhancedService
from integrations.universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/google_chat", tags=["Google Chat"])

# Initialize service (singleton instantiation mirrors the xero/mailchimp
# route pattern; the service module itself does not export an instance)
google_chat_service = GoogleChatEnhancedService()

class GoogleChatMessageRequest(BaseModel):
    space_name: str
    text: str
    thread_name: Optional[str] = None

@router.get("/health")
async def google_chat_health():
    """Google Chat health check"""
    return {"status": "healthy", "service": "Google Chat"}

@router.post("/webhook")
async def google_chat_webhook(request: Request):
    """Google Chat webhook endpoint for incoming events"""
    event = await request.json()
    logger.info(f"Received Google Chat event: {event.get('type')}")
    
    # Route to Universal Webhook Bridge if it's a message
    if event.get("type") == "MESSAGE":
        message = event.get("message", {})
        asyncio.create_task(universal_webhook_bridge.process_incoming_message("google_chat", message))
        
    return {"status": "ok"}

@router.post("/send")
async def send_google_chat_message(request: GoogleChatMessageRequest,
                                   current_user: User = Depends(get_current_user)):
    """Send a Google Chat message"""
    try:
        result = await google_chat_service.send_message(
            space_id=request.space_name,
            text=request.text,
            thread_id=request.thread_name
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Failed to send Google Chat message: {e}")
        raise HTTPException(status_code=500, detail="Internal error")

@router.get("/spaces")
async def list_google_chat_spaces(current_user: User = Depends(get_current_user)):
    """List Google Chat spaces"""
    # This would use the service to list spaces
    return {"spaces": []}
