from fastapi import APIRouter, Request, Response, HTTPException
from fastapi.responses import JSONResponse, RedirectResponse
from typing import Dict, Any
import logging
from auth_handler_xero import (
    get_authorization_url,
    exchange_code_for_tokens,
    get_oauth_client_config,
    revoke_tokens
)

router = APIRouter(prefix="/auth/xero", tags=["xero-oauth"])
logger = logging.getLogger(__name__)

@router.get("/client-config")
async def get_xero_client_config():
    """Get OAuth client configuration"""
    try:
        config = await get_oauth_client_config()
        return JSONResponse({
            "success": True,
            "data": config
        })
    except Exception as e:
        logger.error(f"Failed to get Xero client config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_oauth(request: Request):
    """Start OAuth flow for Xero"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        redirect_uri = data.get("redirect_uri")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        # Generate authorization URL
        auth_data = await get_authorization_url(user_id)
        
        if redirect_uri:
            # Update redirect URI in auth_data
            from auth_handler_xero import XERO_REDIRECT_URI
            auth_handler_xero.XERO_REDIRECT_URI = redirect_uri
        
        return JSONResponse({
            "success": True,
            "authorization_url": auth_data["authorization_url"],
            "state": auth_data["state"]
        })
        
    except Exception as e:
        logger.error(f"Failed to start Xero OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callback")
async def oauth_callback(request: Request):
    """Handle OAuth callback from Xero"""
    try:
        data = await request.json()
        code = data.get("code")
        state = data.get("state")
        user_id = data.get("user_id")
        
        if not code or not state or not user_id:
            raise HTTPException(
                status_code=400, 
                detail="code, state, and user_id are required"
            )
        
        # Exchange code for tokens
        result = await exchange_code_for_tokens(code, state)
        
        if result["success"]:
            return JSONResponse({
                "success": True,
                "message": "Xero OAuth completed successfully",
                "user_id": result["user_id"]
            })
        else:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")
        
    except Exception as e:
        logger.error(f"Failed to handle Xero OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/revoke")
async def revoke_oauth(request: Request):
    """Revoke OAuth tokens"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        success = await revoke_tokens(user_id)
        
        if success:
            return JSONResponse({
                "success": True,
                "message": "Xero OAuth tokens revoked successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to revoke tokens")
        
    except Exception as e:
        logger.error(f"Failed to revoke Xero OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/authorize")
async def authorize_endpoint(request: Request):
    """Redirect to Xero authorization URL (for direct access)"""
    try:
        user_id = request.query_params.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=400, 
                detail="user_id parameter is required"
            )
        
        # Generate authorization URL
        auth_data = await get_authorization_url(user_id)
        
        # Redirect to Xero
        return RedirectResponse(url=auth_data["authorization_url"])
        
    except Exception as e:
        logger.error(f"Failed to authorize Xero: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def health_check():
    """Health check for Xero OAuth service"""
    try:
        # Check if required environment variables are set
        from auth_handler_xero import XERO_CLIENT_ID, XERO_CLIENT_SECRET
        
        if not XERO_CLIENT_ID or not XERO_CLIENT_SECRET:
            return JSONResponse({
                "status": "unhealthy",
                "error": "Missing OAuth configuration"
            }, status_code=503)
        
        return JSONResponse({
            "status": "healthy",
            "service": "xero-oauth",
            "timestamp": "2025-11-07T00:00:00Z"
        })
        
    except Exception as e:
        logger.error(f"Xero OAuth health check failed: {e}")
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e)
        }, status_code=503)