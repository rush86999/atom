"""
Matrix Routes for ATOM Platform
Exposes Matrix webhook functionality
"""

import logging
from typing import Any, Dict
from fastapi import APIRouter, HTTPException, Request

from .matrix_service import matrix_service
from .universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/matrix", tags=["matrix"])

@router.post("/webhook")
async def matrix_webhook(event: Dict[str, Any]):
    """
    Handle incoming Matrix events.
    In a real Matrix setup, you'd use a pusher or an AS integration.
    This endpoint assumes Matrix is configured to push events here.
    """
    logger.info(f"Received Matrix event: {event.get('event_id')}")
    
    # Check if it's a message
    if event.get("type") == "m.room.message":
        import asyncio
        asyncio.create_task(universal_webhook_bridge.process_incoming_message("matrix", event))
        
    return {"status": "received"}

@router.get("/health")
async def matrix_health():
    return await matrix_service.health_check()
