from fastapi import APIRouter
from .slack_webhooks import router as slack_router
from .whatsapp_webhooks import router as whatsapp_router
from .twilio_webhooks import router as twilio_router
from .discord_webhooks import router as discord_router
from .teams_webhooks import router as teams_router

router = APIRouter(prefix="/api/v1/webhooks/platform", tags=["Platform Webhooks"])

router.include_router(slack_router)
router.include_router(whatsapp_router)
router.include_router(twilio_router)
router.include_router(discord_router)
router.include_router(teams_router)

__all__ = ["router"]
