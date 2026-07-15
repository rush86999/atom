"""Thin integration router for token_refresh.

Auto-generated to expose the existing TokenRefresher service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
token_refresh_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.token_refresher import TokenRefresher

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/token_refresh", tags=["token-refresh"])


def _get_service() -> TokenRefresher:
    """Build a TokenRefresher instance from environment configuration."""
    return TokenRefresher()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the token_refresh integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "token_refresh service available (no health_check method)"}
    except Exception as exc:
        logger.warning("token_refresh health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this token_refresh service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


