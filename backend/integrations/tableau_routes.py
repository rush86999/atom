"""
Tableau Integration Routes for ATOM Platform
Uses the real tableau_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Any, Dict, List, Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .tableau_service import get_tableau_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/tableau", tags=["tableau"])


class TableauSignInRequest(BaseModel):
    username: str
    password: str
    site_content_url: str = ""


class TableauSearchRequest(BaseModel):
    query: str
    types: List[str] = ["workbook", "view", "datasource"]
    limit: int = 50


@router.get("/auth/url")
async def get_auth_url():
    """Get Tableau auth information"""
    return {
        "url": "https://10ax.online.tableau.com",
        "message": "Tableau uses username/password sign-in, not OAuth",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/auth/signin")
async def sign_in(request: TableauSignInRequest):
    """Sign in to Tableau Server"""
    try:
        service = get_tableau_service()
        result = await service.sign_in(
            request.username, 
            request.password, 
            request.site_content_url
        )
        return {"ok": True, "data": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Tableau sign in failed: {e}")
        raise HTTPException(status_code=401, detail=str(e))


@router.get("/workbooks")
async def get_workbooks(auth_token: Optional[str] = None):
    """Get Tableau workbooks"""
    try:
        service = get_tableau_service()
        workbooks = await service.get_workbooks(auth_token)
        return {
            "ok": True,
            "workbooks": workbooks,
            "count": len(workbooks),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get workbooks: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/views")
async def get_views(auth_token: Optional[str] = None):
    """Get Tableau views"""
    try:
        service = get_tableau_service()
        views = await service.get_views(auth_token)
        return {
            "ok": True,
            "views": views,
            "count": len(views),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get views: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/datasources")
async def get_datasources(auth_token: Optional[str] = None):
    """Get Tableau datasources"""
    try:
        service = get_tableau_service()
        datasources = await service.get_datasources(auth_token)
        return {
            "ok": True,
            "datasources": datasources,
            "count": len(datasources),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Failed to get datasources: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/status")
async def tableau_status():
    """Status check for Tableau integration"""
    return {
        "ok": True,
        "service": "tableau",
        "status": "active",
        "timestamp": datetime.now().isoformat(),
        "capabilities": ["workbooks", "views", "datasources"]
    }


@router.get("/health")
async def tableau_health():
    """Health check for Tableau integration"""
    try:
        service = get_tableau_service()
        health = await service.health_check()
        return health
    except Exception as e:
        return {"ok": False, "status": "unhealthy", "error": str(e), "timestamp": datetime.now().isoformat()}
