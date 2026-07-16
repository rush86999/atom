"""Thin integration router for clickup.

Auto-generated to expose the existing ClickUpAdapter service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
clickup_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.integrations.adapters.clickup import ClickUpAdapter

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/clickup", tags=["clickup"])


def _get_service() -> ClickUpAdapter:
    """Build a ClickUpAdapter instance from environment configuration."""
    return ClickUpAdapter()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the clickup integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "clickup service available (no health_check method)"}
    except Exception as exc:
        logger.warning("clickup health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this clickup service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


