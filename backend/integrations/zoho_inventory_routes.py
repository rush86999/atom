"""Thin integration router for zoho_inventory.

Auto-generated to expose the existing ZohoInventoryService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
zoho_inventory_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from integrations.zoho_inventory_service import ZohoInventoryService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/zoho_inventory", tags=["zoho-inventory"])


def _get_service() -> ZohoInventoryService:
    """Build a ZohoInventoryService instance from environment configuration."""
    return ZohoInventoryService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the zoho_inventory integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "zoho_inventory service available (no health_check method)"}
    except Exception as exc:
        logger.warning("zoho_inventory health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this zoho_inventory service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))



@router.get("/items")
async def get_items() -> Dict[str, Any]:
    """List Zoho Inventory items."""
    service = _get_service()
    try:
        result = await service.get_items()
        return {"success": True, "data": result}
    except Exception as exc:
        logger.warning("zoho_inventory /items failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
