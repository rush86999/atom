"""
Signal Routes for ATOM Platform
Exposes Signal webhook functionality for signal-cli-rest-api
"""

import logging
from typing import Any, Dict, List
from fastapi import APIRouter, HTTPException, Request
from .signal_service import signal_service
from .universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/signal", tags=["signal"])

@router.post("/webhook")
async def signal_webhook(request: Request):
    """
    Handle incoming Signal events from signal-cli-rest-api
    The API usually sends a list of envelopes
    """
    try:
        payload = await request.json()
        logger.info(f"Received Signal webhook payload")
        
        # signal-cli-rest-api sends a list of message objects or a single one depending on config
        envelopes = payload if isinstance(payload, list) else [payload]
        
        for envelope in envelopes:
            # Standard signal-cli-rest-api envelope structure
            data = envelope.get("envelope", {})
            sync_message = data.get("syncMessage", {})
            data_message = data.get("dataMessage", {}) or sync_message.get("sentMessage", {})
            
            if data_message and data_message.get("message"):
                import asyncio
                # Extract relevant fields for standardization
                # sender: data.get("source")
                # text: data_message.get("message")
                asyncio.create_task(universal_webhook_bridge.process_incoming_message("signal", envelope))
                
        return {"status": "OK"}
    except Exception as e:
        logger.error(f"Error in Signal webhook: {e}")
        return {"status": "error", "detail": str(e)}

@router.get("/health")
async def signal_health():
    return await signal_service.health_check()
