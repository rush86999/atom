"""
Bitbucket Integration Routes for ATOM Platform
Uses the real bitbucket_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Optional

from fastapi import APIRouter, HTTPException, Query
from pydantic import BaseModel

from .bitbucket_service import BitbucketService

logger = logging.getLogger(__name__)

# Create router
router = APIRouter(prefix="/api/bitbucket", tags=["bitbucket"])

# Initialize service
bitbucket_service = BitbucketService()


class BitbucketSearchRequest(BaseModel):
    query: str
    workspace: Optional[str] = None


class BitbucketAuthRequest(BaseModel):
    code: str


@router.get("/auth/url")
async def get_auth_url():
    """Get Bitbucket OAuth authorization URL"""
    return {
        "url": bitbucket_service.get_authorization_url(),
        "service": "bitbucket",
        "timestamp": datetime.now().isoformat()
    }


@router.post("/auth/callback")
async def auth_callback(request: BitbucketAuthRequest):
    """Exchange authorization code for access token"""
    try:
        token_data = bitbucket_service.exchange_code_for_token(request.code)
        return {
            "ok": True,
            "data": token_data,
            "service": "bitbucket",
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Bitbucket auth callback failed: {e}")
        raise HTTPException(status_code=400, detail=str(e))


@router.get("/status")
async def bitbucket_status(access_token: Optional[str] = None):
    """Get Bitbucket integration status"""
    if not access_token:
        return {
            "ok": True,
            "service": "bitbucket",
            "status": "configured",
            "message": "Bitbucket integration is configured. Provide access_token to check connectivity.",
            "timestamp": datetime.now().isoformat()
        }
    
    result = bitbucket_service.get_health_status(access_token)
    return {
        "ok": result.get("status") == "healthy",
        "service": "bitbucket",
        **result,
        "timestamp": datetime.now().isoformat()
    }


@router.get("/health")
async def bitbucket_health():
    """Health check for Bitbucket integration"""
    return await bitbucket_status()


@router.get("/workspaces")
async def list_workspaces(access_token: str):
    """List Bitbucket workspaces"""
    try:
        workspaces = bitbucket_service.get_workspaces(access_token)
        return {"ok": True, "data": workspaces, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to list workspaces: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/repositories")
async def list_repositories(access_token: str, workspace: Optional[str] = None):
    """List Bitbucket repositories"""
    try:
        repos = bitbucket_service.get_repositories(access_token, workspace)
        return {"ok": True, "data": repos, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        logger.error(f"Failed to list repositories: {e}")
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def bitbucket_search(
    request: BitbucketSearchRequest, 
    access_token: str = Query(..., description="OAuth access token")
):
    """Search Bitbucket code"""
    try:
        results = bitbucket_service.search_code(access_token, request.query, request.workspace)
        return {
            "ok": True,
            "query": request.query,
            "results": results,
            "count": len(results),
            "timestamp": datetime.now().isoformat()
        }
    except Exception as e:
        logger.error(f"Bitbucket search failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))
