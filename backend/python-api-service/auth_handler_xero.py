import os
import json
import secrets
import asyncio
import logging
from typing import Dict, Any, Optional
from datetime import datetime, timezone
import httpx
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Xero OAuth configuration
XERO_CLIENT_ID = os.getenv("XERO_CLIENT_ID")
XERO_CLIENT_SECRET = os.getenv("XERO_CLIENT_SECRET")
XERO_REDIRECT_URI = os.getenv("XERO_REDIRECT_URI", "http://localhost:5058/api/auth/xero/callback")
XERO_SCOPE = "accounting.settings accounting.transactions accounting.contacts accounting.reports.read offline_access"

# Xero API endpoints
XERO_AUTH_URL = "https://login.xero.com/identity/connect/authorize"
XERO_TOKEN_URL = "https://identity.xero.com/connect/token"
XERO_API_BASE = "https://api.xero.com/api.xro/2.0"

# Store state tokens (in production, use Redis or database)
oauth_states = {}

async def generate_oauth_state(user_id: str) -> str:
    """Generate secure OAuth state token"""
    state = secrets.token_urlsafe(32)
    oauth_states[state] = {
        "user_id": user_id,
        "timestamp": datetime.now(timezone.utc).isoformat()
    }
    return state

async def validate_oauth_state(state: str) -> Optional[Dict[str, Any]]:
    """Validate OAuth state token"""
    if state not in oauth_states:
        return None
    
    state_data = oauth_states[state]
    
    # Check if state is expired (30 minutes)
    timestamp = datetime.fromisoformat(state_data["timestamp"])
    if (datetime.now(timezone.utc) - timestamp).seconds > 1800:
        del oauth_states[state]
        return None
    
    del oauth_states[state]
    return state_data

async def get_authorization_url(user_id: str) -> Dict[str, Any]:
    """Generate Xero OAuth authorization URL"""
    try:
        state = await generate_oauth_state(user_id)
        
        params = {
            "response_type": "code",
            "client_id": XERO_CLIENT_ID,
            "redirect_uri": XERO_REDIRECT_URI,
            "scope": XERO_SCOPE,
            "state": state
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{XERO_AUTH_URL}?{query_string}"
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Xero authorization URL: {e}")
        raise Exception(f"OAuth URL generation failed: {str(e)}")

async def exchange_code_for_tokens(code: str, state: str) -> Dict[str, Any]:
    """Exchange authorization code for access tokens"""
    try:
        # Validate state
        state_data = await validate_oauth_state(state)
        if not state_data:
            raise Exception("Invalid or expired OAuth state")
        
        user_id = state_data["user_id"]
        
        # Exchange code for tokens
        data = {
            "grant_type": "authorization_code",
            "client_id": XERO_CLIENT_ID,
            "client_secret": XERO_CLIENT_SECRET,
            "code": code,
            "redirect_uri": XERO_REDIRECT_URI
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(XERO_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Store tokens in database
            await store_xero_tokens(user_id, token_data)
            
            return {
                "success": True,
                "user_id": user_id,
                "tokens": token_data
            }
            
    except Exception as e:
        logger.error(f"Failed to exchange Xero code for tokens: {e}")
        raise Exception(f"Token exchange failed: {str(e)}")

async def refresh_access_token(user_id: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh expired access token"""
    try:
        data = {
            "grant_type": "refresh_token",
            "client_id": XERO_CLIENT_ID,
            "client_secret": XERO_CLIENT_SECRET,
            "refresh_token": refresh_token
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(XERO_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Update tokens in database
            await update_xero_tokens(user_id, token_data)
            
            return token_data
            
    except Exception as e:
        logger.error(f"Failed to refresh Xero tokens: {e}")
        raise Exception(f"Token refresh failed: {str(e)}")

async def store_xero_tokens(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Store OAuth tokens in database"""
    try:
        # Import here to avoid circular imports
        from db_oauth_xero import store_user_xero_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Calculate expires_at
        expires_in = token_data.get("expires_in", 1800)
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type")
        }
        
        result = await store_user_xero_tokens(db_pool, user_id, tokens)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to store Xero tokens: {e}")
        return False

async def update_xero_tokens(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Update OAuth tokens in database"""
    try:
        from db_oauth_xero import update_user_xero_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Calculate expires_at
        expires_in = token_data.get("expires_in", 1800)
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type")
        }
        
        result = await update_user_xero_tokens(db_pool, user_id, tokens)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to update Xero tokens: {e}")
        return False

async def revoke_tokens(user_id: str) -> bool:
    """Revoke Xero OAuth tokens"""
    try:
        from db_oauth_xero import delete_user_xero_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        result = await delete_user_xero_tokens(db_pool, user_id)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to revoke Xero tokens: {e}")
        return False

async def get_oauth_client_config() -> Dict[str, Any]:
    """Get OAuth client configuration for frontend"""
    return {
        "client_id": XERO_CLIENT_ID,
        "auth_url": XERO_AUTH_URL,
        "scope": XERO_SCOPE,
        "redirect_uri": XERO_REDIRECT_URI
    }