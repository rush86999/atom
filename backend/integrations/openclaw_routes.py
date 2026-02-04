
import logging
from typing import Any, Dict, Optional
from fastapi import APIRouter, Depends, Header, HTTPException, Request
from pydantic import BaseModel

from integrations.openclaw_service import openclaw_service

router = APIRouter(prefix="/api/integrations/openclaw", tags=["OpenClaw"])
logger = logging.getLogger(__name__)

class OpenClawConfig(BaseModel):
    webhook_url: str
    api_key: Optional[str] = None

@router.get("/health")
async def health_check():
    """Check connectivity to the configured OpenClaw instance"""
    return await openclaw_service.health_check()

@router.post("/test")
async def test_message(data: Dict[str, str]):
    """Send a test message to OpenClaw"""
    content = data.get("content", "Hello from Atom!")
    recipient = data.get("recipient_id", "test_user")
    
    result = await openclaw_service.send_message(recipient, content)
    return result

@router.post("/webhook")
async def receive_webhook(request: Request, x_openclaw_signature: Optional[str] = Header(None)):
    """
    Dedicated webhook receiver for OpenClaw.
    Allows for separated logic if not using Universal Webhook Bridge.
    Note: Ideally, point OpenClaw to /api/integrations/bridge/webhook/openclaw
    """
    try:
        payload = await request.json()
        
        # Forward to Universal Bridge
        from integrations.universal_webhook_bridge import universal_webhook_bridge
        result = await universal_webhook_bridge.process_incoming_message("openclaw", payload)
        
        return result
    except Exception as e:
        logger.error(f"OpenClaw Webhook Error: {e}")
        raise HTTPException(status_code=500, detail=str(e))
