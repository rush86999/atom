"""
Telegram Routes for ATOM Platform
Exposes AtomTelegramIntegration via FastAPI
"""

import logging
from fastapi import APIRouter, HTTPException, Depends
from typing import Dict, Any, List, Optional
from pydantic import BaseModel
from integrations.atom_telegram_integration import atom_telegram_integration
from integrations.universal_webhook_bridge import universal_webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/telegram", tags=["Telegram"])

@router.post("/webhook")
async def telegram_webhook(update: Dict[str, Any]):
    """Telegram webhook endpoint for incoming updates"""
    logger.info(f"Received Telegram webhook update: {update.get('update_id')}")
    
    # Check if it's a message
    message = update.get("message")
    if message:
        # Route to Universal Webhook Bridge
        # Non-blocking call
        import asyncio
        asyncio.create_task(universal_webhook_bridge.process_incoming_message("telegram", message))
        
    return {"status": "ok"}

class TelegramMessageRequest(BaseModel):
    channel_id: int
    message: str
    metadata: Optional[Dict[str, Any]] = None

@router.get("/health")
async def telegram_health():
    """Telegram health check"""
    try:
        status = await atom_telegram_integration.get_service_status()
        if status.get("status") == "active":
            return {"status": "healthy", "service": "Telegram"}
        return {"status": "inactive", "service": "Telegram"}
    except Exception as e:
        logger.error(f"Telegram health check failed: {e}")
        return {"status": "unhealthy", "error": str(e)}

@router.get("/status")
async def telegram_status():
    """Get detailed Telegram status"""
    return await atom_telegram_integration.get_service_status()

@router.post("/send")
async def send_telegram_message(request: TelegramMessageRequest):
    """Send a telegram message"""
    result = await atom_telegram_integration.send_intelligent_message(
        channel_id=request.channel_id,
        message=request.message,
        metadata=request.metadata
    )
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
    return result

@router.get("/workspaces/{user_id}")
async def get_telegram_workspaces(user_id: int):
    """Get Telegram workspaces for user"""
    return await atom_telegram_integration.get_intelligent_workspaces(user_id)
