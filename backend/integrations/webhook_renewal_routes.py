"""Thin integration router for webhook_renewal.

Auto-generated to expose the existing ScheduledWebhookRenewalService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
webhook_renewal_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.webhook_renewal_service import ScheduledWebhookRenewalService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/webhook_renewal", tags=["webhook-renewal"])


def _get_service() -> ScheduledWebhookRenewalService:
    """Build a ScheduledWebhookRenewalService instance from environment configuration."""
    return ScheduledWebhookRenewalService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the webhook_renewal integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "webhook_renewal service available (no health_check method)"}
    except Exception as exc:
        logger.warning("webhook_renewal health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this webhook_renewal service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


