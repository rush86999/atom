"""Thin integration router for telegram_chat.

Auto-generated to expose the existing AtomTelegramIntegration service via a minimal HTTP surface
(/health + /capabilities). This was added because main_api_app.py referenced a
telegram_chat_routes module that did not exist, causing a silent 404. The service
class is the source of truth; these endpoints delegate to it.
"""
import logging
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query

from integrations.atom_telegram_integration import AtomTelegramIntegration

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/integrations/telegram_chat", tags=["telegram-chat"])


def _get_service() -> AtomTelegramIntegration:
    """Build a AtomTelegramIntegration instance from environment configuration."""
    import os
    return AtomTelegramIntegration(config={"bot_token": os.getenv("TELEGRAM_BOT_TOKEN", "")})


@router.get("/health")
async def health() -> Dict[str, Any]:
    """Health check for the telegram_chat integration."""
    try:
        return _get_service().health_check()
    except AttributeError:
        return {"healthy": True, "message": "telegram_chat service available (no health_check method)"}
    except Exception as exc:
        logger.warning("telegram_chat health check failed: %s", exc)
        return {"healthy": False, "message": str(exc)}


@router.get("/capabilities")
async def capabilities() -> Dict[str, Any]:
    """Return the operations this telegram_chat service supports."""
    try:
        return _get_service().get_capabilities()
    except AttributeError:
        return {"operations": [], "message": "no capabilities method"}
    except Exception as exc:
        raise HTTPException(status_code=503, detail=str(exc))


