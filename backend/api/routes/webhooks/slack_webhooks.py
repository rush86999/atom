import logging
import json
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from sqlalchemy.orm import Session

from core.database import get_db
from core.models import TenantIntegration
from core.integration_registry import IntegrationRegistry
from core.tenant_discovery import TenantDiscoveryService
from core.webhook_security import verify_slack_webhook
from api.routes.webhooks.base import get_webhook_registry
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/slack", tags=["Slack Webhooks"])

@router.post("")
async def slack_webhook(
    request: Request,
    x_slack_signature: str = Header(None),
    x_slack_request_timestamp: str = Header(None),
    db: Session = Depends(get_db),
    registry: IntegrationRegistry = Depends(get_webhook_registry)
):
    """
    Unified Slack webhook callback.
    Standardizes events and dispatches via the IntegrationRegistry.
    """
    body = await request.body()
    try:
        data = json.loads(body)
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 1. Challenge Response (System requirement)
    if data.get("type") == "url_verification":
        return {"challenge": data.get("challenge")}

    # 2. Workspace Resolution (Tenant Isolation)
    team_id = data.get("team_id")
    if not team_id:
        # Check inside event if not top-level
        team_id = data.get("event", {}).get("team")
        
    if not team_id:
        logger.warning("Slack webhook missing team_id")
        raise HTTPException(status_code=400, detail="Missing team_id")

    # Resolve tenant using Discovery Service
    discoverer = TenantDiscoveryService(db)
    tenant_id = await discoverer.get_tenant_id_by_external_id("slack", team_id)
    
    if not tenant_id:
        logger.warning(f"No tenant found for Slack team_id: {team_id}")
        # Return 200/202 to avoid Slack retries, but log it
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 3. Security Verification
    integration = db.query(TenantIntegration).filter(
        TenantIntegration.tenant_id == tenant_id,
        TenantIntegration.connector_id == "slack"
    ).first()

    if integration and integration.config:
        signing_secret = integration.config.get("slack_signing_secret")
        if signing_secret:
            if not verify_slack_webhook(body, x_slack_signature, x_slack_request_timestamp, signing_secret):
                logger.error(f"Unauthorized Slack webhook for tenant {tenant_id}")
                raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. Dispatch via Webhook Bridge
    result = await webhook_bridge.process_event(
        "slack",
        tenant_id,
        data.get("event", {}),
        registry,
        db
    )
    
    return result
