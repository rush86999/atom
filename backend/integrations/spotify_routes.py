"""Thin integration router for spotify.

Auto-generated to expose the existing SpotifyService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
spotify_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from core.media.spotify_service import SpotifyService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/spotify", tags=["spotify"])


def _get_service() -> SpotifyService:
    """Build a SpotifyService instance from environment configuration."""
    return SpotifyService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the spotify integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "spotify service available (no health_check method)"}
    except Exception as exc:
        logger.warning("spotify health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this spotify service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


