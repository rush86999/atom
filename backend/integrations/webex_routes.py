from fastapi import APIRouter, HTTPException
from integrations.webex_service import webex_service

router = APIRouter(prefix="/api/webex", tags=["Webex"])

@router.get("/rooms")
async def list_webex_rooms():
    """List Webex rooms"""
    return await webex_service.list_rooms()

@router.get("/health")
async def webex_health():
    """Get Webex integration health"""
    return await webex_service.check_health()
