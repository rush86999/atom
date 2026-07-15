"""Thin integration router for zoho_projects.

Auto-generated to expose the existing ZohoProjectsService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
zoho_projects_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from integrations.zoho_projects_service import ZohoProjectsService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/zoho_projects", tags=["zoho-projects"])


def _get_service() -> ZohoProjectsService:
    """Build a ZohoProjectsService instance from environment configuration."""
    return ZohoProjectsService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the zoho_projects integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "zoho_projects service available (no health_check method)"}
    except Exception as exc:
        logger.warning("zoho_projects health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this zoho_projects service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))



@router.get("/portals")
async def get_portals(token: str = Query(None)) -> Dict[str, Any]:
    """List Zoho Projects portals."""
    service = _get_service()
    try:
        result = await service.get_portals(token)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.warning("zoho_projects /portals failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
