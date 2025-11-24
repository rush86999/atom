import logging
from typing import Dict, List, Optional
from datetime import datetime

from fastapi import APIRouter, HTTPException, Query
from fastapi.responses import RedirectResponse
from pydantic import BaseModel

from integrations.auth_handler_figma import figma_auth_handler

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/figma", tags=["figma"])

class FigmaSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"

class FigmaSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str

# OAuth Endpoints
@router.get("/oauth/url")
async def get_figma_oauth_url(state: Optional[str] = None):
    """Get Figma OAuth authorization URL"""
    try:
        auth_url = figma_auth_handler.get_authorization_url(state)
        return {
            "ok": True,
            "authorization_url": auth_url,
            "message": "Redirect user to this URL to authorize Figma access"
        }
    except Exception as e:
        logger.error(f"Error generating Figma OAuth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/oauth/callback")
async def figma_oauth_callback(code: str = Query(...), state: Optional[str] = None):
    """Handle Figma OAuth callback"""
    try:
        token_data = await figma_auth_handler.exchange_code_for_token(code)
        
        # In production, you would:
        # 1. Validate the state parameter
        # 2. Store tokens in database encrypted with ATOM_ENCRYPTION_KEY
        # 3. Associate tokens with the user
        
        return {
            "ok": True,
            "message": "Successfully connected to Figma",
            "user_id": token_data.get("user_id"),
            "expires_in": token_data.get("expires_in")
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error in Figma OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/oauth/status")
async def get_figma_oauth_status():
    """Get current Figma OAuth connection status"""
    try:
        status = figma_auth_handler.get_connection_status()
        return {
            "ok": True,
            **status
        }
    except Exception as e:
        logger.error(f"Error getting Figma OAuth status: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# API Endpoints (require valid OAuth token)
@router.get("/status")
async def figma_status(user_id: str = "test_user"):
    """Get Figma integration status"""
    connection_status = figma_auth_handler.get_connection_status()
    
    return {
        "ok": True,
        "service": "figma",
        "user_id": user_id,
        "status": "connected" if connection_status["connected"] else "disconnected",
        "message": "Figma integration is available" if connection_status["connected"] else "Please authenticate with Figma",
        **connection_status
    }

@router.get("/user")
async def get_figma_user():
    """Get authenticated Figma user information"""
    try:
        await figma_auth_handler.ensure_valid_token()
        user_info = await figma_auth_handler.get_user_info()
        return {
            "ok": True,
            **user_info
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error getting Figma user: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/files")
async def list_figma_files():
    """List Figma files (requires authentication)"""
    try:
        token = await figma_auth_handler.ensure_valid_token()
        
        # In production, make actual API call to Figma
        # import aiohttp
        # async with aiohttp.ClientSession() as session:
        #     headers = {"Authorization": f"Bearer {token}"}
        #     async with session.get(f"{figma_auth_handler.api_base_url}/teams/{team_id}/projects", headers=headers) as response:
        #         return await response.json()
        
        # Mock response for now
        return {
            "ok": True,
            "files": [
                {"key": "fig-001", "name": "Homepage Design", "type": "design"},
                {"key": "fig-002", "name": "Mobile App UI", "type": "design"},
            ]
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Figma files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search")
async def figma_search(request: FigmaSearchRequest):
    """Search Figma content (requires authentication)"""
    try:
        await figma_auth_handler.ensure_valid_token()
        
        logger.info(f"Searching Figma for: {request.query}")

        # Mock results - in production, search using Figma API
        mock_results = [
            {
                "id": "item_001",
                "title": f"Figma Design - {request.query}",
                "type": "file",
                "snippet": f"Design file matching: {request.query}",
            }
        ]

        return FigmaSearchResponse(
            ok=True,
            query=request.query,
            results=mock_results,
            timestamp=datetime.now().isoformat(),
        )
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error searching Figma: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/items")
async def list_figma_items(user_id: str = "test_user"):
    """List Figma items (requires authentication)"""
    try:
        await figma_auth_handler.ensure_valid_token()
        
        return {
            "ok": True,
            "items": [
                {
                    "id": f"item_{i}",
                    "title": f"Figma Item {i}",
                    "status": "active",
                }
                for i in range(1, 6)
            ],
        }
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Error listing Figma items: {e}")
        raise HTTPException(status_code=500, detail=str(e))

