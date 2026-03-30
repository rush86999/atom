import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Form
from sqlalchemy.orm import Session
from core.database import get_db
from core.integration_registry import IntegrationRegistry
from api.routes.webhooks.base import get_webhook_registry, verify_hmac_signature
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/twilio", tags=["Twilio Webhooks"])

@router.post("/sms")
async def twilio_sms_webhook(
    request: Request,
    X_Twilio_Signature: str = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry),
    db: Session = Depends(get_db)
):
    """
    Unified Twilio SMS webhook callback.
    Standardizes messages via the IntegrationRegistry.
    """
    params = await request.form()
    data = dict(params)
    
    # 1. Workspace Resolution
    # We resolve tenant from the 'To' (our number) or a custom Header
    to_number = data.get("To")
    # For now, default to to_number (in production, use mapping table)
    tenant_id = to_number or "default"
    
    # 2. Dispatch via Webhook Bridge
    result = await webhook_bridge.process_event(
        "twilio",
        tenant_id,
        data,
        registry,
        db
    )
    
    return result

@router.post("/status")
async def twilio_status_webhook(
    request: Request,
    X_Twilio_Signature: str = Header(None),
    registry: IntegrationRegistry = Depends(get_webhook_registry)
):
    """Twilio Status callback (Message delivered, failed)."""
    params = await request.form()
    data = dict(params)
    
    # Delegate tracking to 서비스
    tenant_id = data.get("To", "default")
    await registry.execute_operation(
        "twilio",
        tenant_id,
        "track_status_callback",
        {"data": data}
    )
    
    return {"status": "ok"}
