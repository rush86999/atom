"""Thin integration router for zoho_crm.

Auto-generated to expose the existing ZohoCRMService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
zoho_crm_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from integrations.zoho_crm_service import ZohoCRMService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/zoho_crm", tags=["zoho-crm"])


def _get_service() -> ZohoCRMService:
    """Build a ZohoCRMService instance from environment configuration."""
    return ZohoCRMService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the zoho_crm integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "zoho_crm service available (no health_check method)"}
    except Exception as exc:
        logger.warning("zoho_crm health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this zoho_crm service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))



@router.get("/leads")
async def get_leads(limit: str = Query(None)) -> Dict[str, Any]:
    """Get recent leads from Zoho CRM."""
    service = _get_service()
    try:
        result = await service.get_leads(limit=limit)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.warning("zoho_crm /leads failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
