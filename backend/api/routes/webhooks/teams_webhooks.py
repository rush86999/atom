import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from sqlalchemy.orm import Session

from core.database import get_db
from core.integration_registry import IntegrationRegistry
from core.tenant_discovery import TenantDiscoveryService
from core.communication.adapters.teams import TeamsAdapter
from api.routes.webhooks.base import get_webhook_registry
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/teams", tags=["Microsoft Teams Webhooks"])

@router.post("")
async def teams_webhook(
    request: Request,
    db: Session = Depends(get_db),
    registry: IntegrationRegistry = Depends(get_webhook_registry)
):
    """
    Unified Microsoft Teams webhook callback.
    Handles JWT verification and dispatches via UCB.
    """
    body = await request.body()
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 1. Tenant Resolution
    # Teams usually provides tenantId in the activity object
    ms_tenant_id = data.get("conversation", {}).get("tenantId")
    if not ms_tenant_id:
        ms_tenant_id = data.get("channelData", {}).get("tenant", {}).get("id")

    if not ms_tenant_id:
        logger.warning("Teams webhook missing tenantId")
        raise HTTPException(status_code=400, detail="Missing tenantId")

    discoverer = TenantDiscoveryService(db)
    tenant_id = await discoverer.get_tenant_id_by_external_id("teams", ms_tenant_id)
    
    if not tenant_id:
        logger.warning(f"No tenant found for Microsoft Teams tenantId: {ms_tenant_id}")
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 2. Security Verification
    adapter = TeamsAdapter()
    if not await adapter.verify_request(request, body):
        logger.error(f"Unauthorized Teams webhook for tenant {tenant_id}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 3. Dispatch via Webhook Bridge
    result = await webhook_bridge.process_event(
        "teams",
        tenant_id,
        data,
        registry,
        db
    )
    
    return result
