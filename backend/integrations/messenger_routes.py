"""
Messenger Routes for ATOM Platform
Exposes Messenger webhook functionality
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request, Query
from .messenger_service import messenger_service
from .universal_webhook_bridge import universal_webhook_bridge
import os

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/messenger", tags=["messenger"])

@router.get("/webhook")
async def messenger_webhook_verify(
    hub_mode: str = Query(None, alias="hub.mode"),
    hub_challenge: str = Query(None, alias="hub.challenge"),
    hub_verify_token: str = Query(None, alias="hub.verify_token")
):
    """
    Handle Messenger webhook verification
    """
    verify_token = os.getenv("MESSENGER_VERIFY_TOKEN")
    
    if hub_mode == "subscribe" and hub_verify_token == verify_token:
        logger.info("Messenger webhook verified")
        from fastapi.responses import Response
        return Response(content=hub_challenge)
    
    raise HTTPException(status_code=403, detail="Verification failed")

@router.post("/webhook")
async def messenger_webhook(request: Request):
    """
    Handle incoming Messenger events
    """
    data = await request.json()
    logger.info(f"Received Messenger webhook: {data.get('object')}")
    
    if data.get("object") == "page":
        for entry in data.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                if messaging_event.get("message"):
                    import asyncio
                    asyncio.create_task(universal_webhook_bridge.process_incoming_message("messenger", messaging_event))
                    
    return {"status": "EVENT_RECEIVED"}

@router.get("/health")
async def messenger_health():
    return await messenger_service.health_check()
