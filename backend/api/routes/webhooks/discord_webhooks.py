import logging
from typing import Dict, Any, Optional
from fastapi import APIRouter, Depends, HTTPException, Header, Request, Body
from sqlalchemy.orm import Session

from core.database import get_db
from core.integration_registry import IntegrationRegistry
from core.tenant_discovery import TenantDiscoveryService
from core.communication.adapters.discord import DiscordAdapter
from api.routes.webhooks.base import get_webhook_registry
from api.routes.webhooks.webhook_bridge import webhook_bridge

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/discord", tags=["Discord Webhooks"])

@router.post("")
async def discord_webhook(
    request: Request,
    db: Session = Depends(get_db),
    registry: IntegrationRegistry = Depends(get_webhook_registry)
):
    """
    Unified Discord webhook callback.
    Handles verification (Interactions API) and dispatches via UCB.
    """
    body = await request.body()
    try:
        data = await request.json()
    except Exception:
        raise HTTPException(status_code=400, detail="Invalid JSON")

    # 1. Challenge Response (System requirement for Interactions)
    if data.get("type") == 1:
        return {"type": 1}

    # 2. Tenant Resolution
    # Discord interactions don't easily provide a tenant context without looking at guild_id or application_id
    guild_id = data.get("guild_id")
    if not guild_id:
        logger.warning("Discord webhook missing guild_id (likely DM or unhandled type)")
        # In Atoms, DMs might be handled by resolving user_id to tenant or requiring guild context
        raise HTTPException(status_code=400, detail="Missing guild_id")

    discoverer = TenantDiscoveryService(db)
    tenant_id = await discoverer.get_tenant_id_by_external_id("discord", guild_id)
    
    if not tenant_id:
        logger.warning(f"No tenant found for Discord guild_id: {guild_id}")
        return {"status": "ignored", "reason": "tenant_not_found"}

    # 3. Security Verification
    adapter = DiscordAdapter()
    if not await adapter.verify_request(request, body):
        logger.error(f"Unauthorized Discord webhook for tenant {tenant_id}")
        raise HTTPException(status_code=401, detail="Invalid signature")

    # 4. Dispatch via Webhook Bridge
    result = await webhook_bridge.process_event(
        "discord",
        tenant_id,
        data,
        registry,
        db
    )
    
    return result
