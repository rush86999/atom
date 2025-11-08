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

# Azure OAuth configuration
AZURE_CLIENT_ID = os.getenv("AZURE_CLIENT_ID")
AZURE_CLIENT_SECRET = os.getenv("AZURE_CLIENT_SECRET")
AZURE_TENANT_ID = os.getenv("AZURE_TENANT_ID")
AZURE_REDIRECT_URI = os.getenv("AZURE_REDIRECT_URI", "http://localhost:5058/api/auth/azure/callback")
AZURE_SCOPE = "https://management.azure.com/.default offline_access"

# Azure OAuth endpoints
AZURE_AUTH_URL = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/authorize"
AZURE_TOKEN_URL = f"https://login.microsoftonline.com/{AZURE_TENANT_ID}/oauth2/v2.0/token"
AZURE_GRAPH_URL = "https://graph.microsoft.com/v1.0"

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
    """Generate Azure OAuth authorization URL"""
    try:
        state = await generate_oauth_state(user_id)
        
        params = {
            "response_type": "code",
            "client_id": AZURE_CLIENT_ID,
            "redirect_uri": AZURE_REDIRECT_URI,
            "scope": AZURE_SCOPE,
            "state": state,
            "prompt": "consent"
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{AZURE_AUTH_URL}?{query_string}"
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Azure authorization URL: {e}")
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
            "client_id": AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "code": code,
            "redirect_uri": AZURE_REDIRECT_URI,
            "scope": AZURE_SCOPE
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(AZURE_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Get user profile from Azure Graph API
            profile_data = await get_user_profile(token_data.get("access_token"))
            
            # Store tokens in database
            await store_azure_tokens(user_id, token_data, profile_data)
            
            return {
                "success": True,
                "user_id": user_id,
                "tokens": token_data,
                "profile": profile_data
            }
            
    except Exception as e:
        logger.error(f"Failed to exchange Azure code for tokens: {e}")
        raise Exception(f"Token exchange failed: {str(e)}")

async def refresh_access_token(user_id: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh expired access token"""
    try:
        data = {
            "grant_type": "refresh_token",
            "client_id": AZURE_CLIENT_ID,
            "client_secret": AZURE_CLIENT_SECRET,
            "refresh_token": refresh_token,
            "scope": AZURE_SCOPE
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(AZURE_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            # Update tokens in database
            await update_azure_tokens(user_id, token_data)
            
            return token_data
            
    except Exception as e:
        logger.error(f"Failed to refresh Azure tokens: {e}")
        raise Exception(f"Token refresh failed: {str(e)}")

async def get_user_profile(access_token: str) -> Dict[str, Any]:
    """Get user profile from Azure Graph API"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Get basic profile
            response = await client.get(f"{AZURE_GRAPH_URL}/me", headers=headers)
            response.raise_for_status()
            profile_data = response.json()
            
            # Get additional profile info
            response2 = await client.get(f"{AZURE_GRAPH_URL}/me/photo/$value", headers=headers)
            profile_data["has_photo"] = response2.status_code == 200
            
            return profile_data
            
    except Exception as e:
        logger.error(f"Failed to get Azure user profile: {e}")
        return {}

async def store_azure_tokens(user_id: str, token_data: Dict[str, Any], profile_data: Dict[str, Any]) -> bool:
    """Store OAuth tokens in database"""
    try:
        from db_oauth_azure import store_user_azure_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Calculate expires_at
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type"),
            "profile": profile_data
        }
        
        result = await store_user_azure_tokens(db_pool, user_id, tokens)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to store Azure tokens: {e}")
        return False

async def update_azure_tokens(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Update OAuth tokens in database"""
    try:
        from db_oauth_azure import update_user_azure_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Calculate expires_at
        expires_in = token_data.get("expires_in", 3600)
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type")
        }
        
        result = await update_user_azure_tokens(db_pool, user_id, tokens)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to update Azure tokens: {e}")
        return False

async def revoke_tokens(user_id: str) -> bool:
    """Revoke Azure OAuth tokens"""
    try:
        from db_oauth_azure import delete_user_azure_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        result = await delete_user_azure_tokens(db_pool, user_id)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to revoke Azure tokens: {e}")
        return False

async def get_oauth_client_config() -> Dict[str, Any]:
    """Get OAuth client configuration for frontend"""
    return {
        "client_id": AZURE_CLIENT_ID,
        "tenant_id": AZURE_TENANT_ID,
        "auth_url": AZURE_AUTH_URL,
        "scope": AZURE_SCOPE,
        "redirect_uri": AZURE_REDIRECT_URI
    }