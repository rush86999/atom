"""Thin integration router for stripe.

Auto-generated to expose the existing StripeAdapter service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
stripe_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.integrations.adapters.stripe import StripeAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/stripe", tags=["stripe"])


def _get_service() -> StripeAdapter:
    """Build a StripeAdapter instance from environment configuration."""
    return StripeAdapter()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the stripe integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "stripe service available (no health_check method)"}
    except Exception as exc:
        logger.warning("stripe health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this stripe service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


