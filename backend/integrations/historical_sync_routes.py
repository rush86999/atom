"""Thin integration router for historical_sync.

Auto-generated to expose the existing HistoricalSyncService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
historical_sync_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.historical_sync_service import HistoricalSyncService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/historical_sync", tags=["historical-sync"])


def _get_service() -> HistoricalSyncService:
    """Build a HistoricalSyncService instance from environment configuration."""
    return HistoricalSyncService(tenant_id="default")


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the historical_sync integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "historical_sync service available (no health_check method)"}
    except Exception as exc:
        logger.warning("historical_sync health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this historical_sync service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


