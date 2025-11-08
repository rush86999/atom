from fastapi import APIRouter, HTTPException, Request, Response
from fastapi.responses import RedirectResponse, JSONResponse
from typing import Dict, Any
import logging
import os
from auth_handler_azure import (
    get_authorization_url,
    exchange_code_for_tokens,
    revoke_tokens,
    get_oauth_client_config
)

router = APIRouter(prefix="/api/auth/azure", tags=["azure-oauth"])
logger = logging.getLogger(__name__)

@router.get("/client-config")
async def get_azure_client_config():
    """Get OAuth client configuration"""
    try:
        config = await get_oauth_client_config()
        return JSONResponse({
            "success": True,
            "data": config
        })
    except Exception as e:
        logger.error(f"Failed to get Azure client config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/start")
async def start_azure_oauth(request: Request):
    """Start OAuth flow for Azure"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        redirect_uri = data.get("redirect_uri")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        # Generate authorization URL
        auth_data = await get_authorization_url(user_id)
        
        # Update redirect URI if provided
        if redirect_uri:
            from auth_handler_azure import AZURE_REDIRECT_URI
            global AZURE_REDIRECT_URI
            AZURE_REDIRECT_URI = redirect_uri
        
        return JSONResponse({
            "success": True,
            "authorization_url": auth_data["authorization_url"],
            "state": auth_data["state"]
        })
        
    except Exception as e:
        logger.error(f"Failed to start Azure OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/callback")
async def azure_oauth_callback(request: Request):
    """Handle OAuth callback from Azure"""
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
                "message": "Azure OAuth completed successfully",
                "user_id": result["user_id"],
                "profile": result.get("profile", {})
            })
        else:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")
        
    except Exception as e:
        logger.error(f"Failed to handle Azure OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/revoke")
async def revoke_azure_oauth(request: Request):
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
                "message": "Azure OAuth tokens revoked successfully"
            })
        else:
            raise HTTPException(status_code=500, detail="Failed to revoke tokens")
        
    except Exception as e:
        logger.error(f"Failed to revoke Azure OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/authorize")
async def azure_authorize_endpoint(request: Request):
    """Redirect to Azure authorization URL (for direct access)"""
    try:
        user_id = request.query_params.get("user_id")
        
        if not user_id:
            raise HTTPException(
                status_code=400, 
                detail="user_id parameter is required"
            )
        
        # Generate authorization URL
        auth_data = await get_authorization_url(user_id)
        
        # Redirect to Azure
        return RedirectResponse(url=auth_data["authorization_url"])
        
    except Exception as e:
        logger.error(f"Failed to authorize Azure: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/health")
async def azure_oauth_health():
    """Health check for Azure OAuth service"""
    try:
        # Check if required environment variables are set
        from auth_handler_azure import AZURE_CLIENT_ID, AZURE_CLIENT_SECRET, AZURE_TENANT_ID
        
        required_vars = {
            "AZURE_CLIENT_ID": AZURE_CLIENT_ID,
            "AZURE_CLIENT_SECRET": AZURE_CLIENT_SECRET,
            "AZURE_TENANT_ID": AZURE_TENANT_ID,
            "AZURE_SUBSCRIPTION_ID": os.getenv("AZURE_SUBSCRIPTION_ID")
        }
        
        missing_vars = [var for var, value in required_vars.items() if not value]
        
        if missing_vars:
            return JSONResponse({
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }, status_code=503)
        
        return JSONResponse({
            "status": "healthy",
            "service": "azure-oauth",
            "timestamp": "2025-11-07T00:00:00Z"
        })
        
    except Exception as e:
        logger.error(f"Azure OAuth health check failed: {e}")
        return JSONResponse({
            "status": "unhealthy",
            "error": str(e)
        }, status_code=503)