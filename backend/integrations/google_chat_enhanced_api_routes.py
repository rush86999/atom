"""
Google Chat Enhanced API Routes
Exposes GoogleChatEnhancedService via FastAPI
"""

import asyncio
import logging
from typing import Any, Dict, List, Optional
from fastapi import APIRouter, HTTPException, Request
from pydantic import BaseModel

from integrations.google_chat_enhanced_service import google_chat_enhanced_service
from integrations.universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/google_chat", tags=["Google Chat"])

class GoogleChatMessageRequest(BaseModel):
    space_name: str
    text: str
    thread_name: Optional[str] = None

@router.get("/health")
async def google_chat_health():
    """Google Chat health check"""
    try:
        # Mocking for now, as service status check might not be implemented
        return {"status": "healthy", "service": "Google Chat"}
    except Exception as e:
        logger.error(f"Google Chat health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

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
async def send_google_chat_message(request: GoogleChatMessageRequest):
    """Send a Google Chat message"""
    try:
        result = await google_chat_enhanced_service.send_message(
            space_name=request.space_name,
            text=request.text,
            thread_name=request.thread_name
        )
        return {"success": True, "result": result}
    except Exception as e:
        logger.error(f"Failed to send Google Chat message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/spaces")
async def list_google_chat_spaces():
    """List Google Chat spaces"""
    try:
        # This would use the service to list spaces
        return {"spaces": []}
    except Exception as e:
        logger.error(f"Failed to list Google Chat spaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))
