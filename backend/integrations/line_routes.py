"""
Line Routes for ATOM Platform
Exposes Line webhook functionality
"""

import asyncio
import base64
import hashlib
import hmac
import logging
import os
from typing import Any, Dict
from fastapi import APIRouter, Header, HTTPException, Request

from .line_service import LineService
from .universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

_bg_tasks: set = set()

# The module previously imported ``line_service`` as an instance, but
# line_service.py only defines the ``LineService`` class — the import failed
# with ImportError, so this router (and the webhook below) was dead.
line_service = LineService()

router = APIRouter(prefix="/api/line", tags=["line"])

@router.post("/webhook")
async def line_webhook(request: Request, x_line_signature: str = Header(None)):
    """
    Handle incoming Line events
    """
    body = await request.body()

    # Verify signature — FAIL CLOSED (R45 pattern). Previously an invalid or
    # missing signature only logged a warning and the event was still
    # processed, and an unset LINE_CHANNEL_SECRET defaulted to the empty
    # string (anyone could compute the matching HMAC).
    channel_secret = os.getenv("LINE_CHANNEL_SECRET", "")
    if not channel_secret:
        logger.warning("LINE_CHANNEL_SECRET not configured; refusing Line webhook")
        raise HTTPException(status_code=503, detail="Webhook not configured")
    if not x_line_signature:
        raise HTTPException(status_code=401, detail="Missing signature")
    digest = hmac.new(channel_secret.encode(), body, hashlib.sha256).digest()
    signature = base64.b64encode(digest).decode()

    if not hmac.compare_digest(signature, x_line_signature):
        logger.warning("Invalid Line signature")
        raise HTTPException(status_code=401, detail="Invalid signature")

    data = await request.json()
    logger.info(f"Received Line webhook event count: {len(data.get('events', []))}")
    
    for event in data.get("events", []):
        if event.get("type") == "message" and event.get("message", {}).get("type") == "text":
            _t = asyncio.create_task(universal_webhook_bridge.process_incoming_message("line", event)); _bg_tasks.add(_t); _t.add_done_callback(_bg_tasks.discard)
            
    return {"status": "OK"}

@router.get("/health")
async def line_health():
    return line_service.health_check()
