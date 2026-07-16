"""Thin integration router for slack_chat.

Auto-generated to expose the existing SlackUnifiedService service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
slack_chat_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from integrations.slack_service_unified import SlackUnifiedService

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/slack_chat", tags=["slack-chat"])


def _get_service() -> SlackUnifiedService:
    """Build a SlackUnifiedService instance from environment configuration."""
    return SlackUnifiedService()


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the slack_chat integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "slack_chat service available (no health_check method)"}
    except Exception as exc:
        logger.warning("slack_chat health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this slack_chat service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


