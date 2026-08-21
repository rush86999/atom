from fastapi import APIRouter, Depends, HTTPException

from integrations.webex_service import webex_service
from core.auth import get_current_user
from core.models import User

router = APIRouter(prefix="/api/webex", tags=["Webex"])

@router.get("/rooms")
async def list_webex_rooms(current_user: User = Depends(get_current_user)):
    """List Webex rooms"""
    return await webex_service.list_rooms()

@router.get("/health")
async def webex_health():
    """Get Webex integration health"""
    return webex_service.health_check()
