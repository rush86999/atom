"""Thin integration router for zoho_flow (webhook-push app).

Zoho Flow has no public read API (flows/executions are UI-only), so this
surface is: /health + /capabilities for the Integrations hub and /events
for readback of execution events already ingested by the platform's
``POST /webhooks/zoho-flow`` endpoint. The service class is the source of
truth.
"""

import logging
from typing import Any, Dict

from fastapi import APIRouter, Depends, HTTPException

from core.auth import User, get_current_user
from integrations.zoho_flow_service import ZohoFlowService, zoho_flow_service

logger = logging.getLogger(__name__)

# No router-level prefix or auth: /health + /capabilities stay public for
# hub probes (sibling zoho_*_routes style); data endpoints declare their
# own auth. The webhook itself lives at /webhooks/zoho-flow
# (api/webhook_routes.py) — this router only reads back what it ingested.
router = APIRouter(tags=["zoho-flow"])


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the zoho_flow integration."""
    try:
        return zoho_flow_service.health_check()
    except Exception as exc:
        logger.warning("zoho_flow health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this zoho_flow service supports."""
    try:
        return zoho_flow_service.get_capabilities()
    except Exception as exc:
        logger.warning("zoho_flow capabilities failed: %s", exc)
        raise HTTPException(status_code=503, detail="Service temporarily unavailable")


@router.get("/events")
async def list_events(
    limit: int = 20,
    current_user: User = Depends(get_current_user),
) -> Dict[str, Any]:
    """Recent ingested flow execution events (push arrived via /webhooks/zoho-flow)."""
    service = ZohoFlowService(config={"workspace_id": "default"})
    return {
        "success": True,
        "data": await service.list_events(limit=min(limit, 100)),
    }
