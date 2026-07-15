"""Thin integration router for zoho_books.

Auto-generated to expose the existing ZohoBooksService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
zoho_books_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from integrations.zoho_books_service import ZohoBooksService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/zoho_books", tags=["zoho-books"])


def _get_service() -> ZohoBooksService:
    """Build a ZohoBooksService instance from environment configuration."""
    return ZohoBooksService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the zoho_books integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "zoho_books service available (no health_check method)"}
    except Exception as exc:
        logger.warning("zoho_books health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this zoho_books service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))



@router.get("/contacts")
async def get_contacts(token: str = Query(None), organization_id: str = Query(None)) -> Dict[str, Any]:
    """List Zoho Books contacts."""
    service = _get_service()
    try:
        result = await service.get_contacts(token, organization_id)
        return {"success": True, "data": result}
    except Exception as exc:
        logger.warning("zoho_books /contacts failed: %s", exc)
        raise HTTPException(status_code=503, detail=str(exc))
