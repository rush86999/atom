"""
Intercom Integration Routes for ATOM Platform
Uses the real intercom_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .intercom_service import get_intercom_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/intercom", tags=["intercom"])


class IntercomAuthRequest(BaseModel):
    code: str


class IntercomSearchRequest(BaseModel):
    query: str
    limit: int = 50


@router.get("/auth/url")
async def get_auth_url():
    """Get Intercom OAuth URL"""
    service = get_intercom_service()
    client_id = service.client_id or "INSERT_CLIENT_ID"
    return {
        "url": f"https://app.intercom.com/oauth?client_id={client_id}",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/auth/callback")
async def auth_callback(request: IntercomAuthRequest):
    """Exchange authorization code for access token"""
    try:
        service = get_intercom_service()
        token_data = await service.exchange_token(request.code)
        return {
            "ok": True,
            "data": token_data,
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Intercom auth callback failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/contacts")
async def get_contacts(
    access_token: str = Query(..., description="Access token"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get Intercom contacts"""
    try:
        service = get_intercom_service()
        contacts = await service.get_contacts(access_token, limit)
        return {
            "ok": True,
            "contacts": contacts,
            "count": len(contacts),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get contacts: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/conversations")
async def get_conversations(
    access_token: str = Query(..., description="Access token"),
    limit: int = Query(20, ge=1, le=100)
):
    """Get Intercom conversations"""
    try:
        service = get_intercom_service()
        conversations = await service.get_conversations(access_token, limit)
        return {
            "ok": True,
            "conversations": conversations,
            "count": len(conversations),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get conversations: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/admins")
async def get_admins(access_token: str = Query(..., description="Access token")):
    """Get Intercom admins"""
    try:
        service = get_intercom_service()
        admins = await service.get_admins(access_token)
        return {
            "ok": True,
            "admins": admins,
            "count": len(admins),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get admins: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def search_contacts(
    request: IntercomSearchRequest,
    access_token: str = Query(..., description="Access token")
):
    """Search Intercom contacts"""
    try:
        service = get_intercom_service()
        results = await service.search_contacts(access_token, request.query)
        return {
            "ok": True,
            "query": request.query,
            "results": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Intercom search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def intercom_status():
    """Status check for Intercom integration"""
    service = get_intercom_service()
    return {
        "ok": True,
        "service": "intercom",
        "status": "active",
        "configured": bool(service.client_id and service.client_secret),
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def intercom_health():
    """Health check for Intercom integration"""
    try:
        service = get_intercom_service()
        return await service.health_check()
    except Exception as e:
        return {"ok": False, "status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}
