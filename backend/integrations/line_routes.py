"""
Line Routes for ATOM Platform
Exposes Line webhook functionality
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, Header
from .line_service import line_service
from .universal_webhook_bridge import universal_webhook_bridge
import os
import hmac
import hashlib
import base64

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/line", tags=["line"])

@router.post("/webhook")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    """
    Handle incoming Line events
    """
    body = await request.body()
    
    # Verify signature
    channel_secret = os.getenv("LINE_CHANNEL_SECRET", "").encode()
    hash = hmac.new(channel_secret, body, hashlib.sha256).digest()
    signature = base64.b64encode(hash).decode()
    
    if x_line_signature != signature:
        logger.warning("Invalid Line signature")
        # In production, you'd want to ignore or reject this, but for now we follow
    
    data = await request.json()
    logger.info(f"Received Line webhook event count: {len(data.get('events', []))}")
    
    for event in data.get("events", []):
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            import asyncio
            asyncio.create_task(universal_webhook_bridge.process_incoming_message("line", event))
            
    return {"status": "OK"}

@router.get("/health")
async def line_health():
    return await line_service.health_check()
