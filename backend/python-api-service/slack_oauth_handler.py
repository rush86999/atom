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

# Slack OAuth configuration
SLACK_CLIENT_ID = os.getenv("SLACK_CLIENT_ID")
SLACK_CLIENT_SECRET = os.getenv("SLACK_CLIENT_SECRET")
SLACK_REDIRECT_URI = os.getenv("SLACK_REDIRECT_URI", "http://localhost:5058/api/auth/slack/callback")
SLACK_SIGNING_SECRET = os.getenv("SLACK_SIGNING_SECRET")

# Slack API endpoints
SLACK_AUTH_URL = "https://slack.com/oauth/v2/authorize"
SLACK_TOKEN_URL = "https://slack.com/api/oauth.v2.access"
SLACK_API_BASE = "https://slack.com/api"

# Scopes required
SLACK_SCOPES = [
    "channels:read",
    "channels:write",
    "chat:write",
    "users:read",
    "files:read",
    "files:write",
    "reactions:read",
    "reactions:write",
    "team:read",
    "emoji:read",
    "search:read",
    "groups:read",
    "im:read",
    "mpim:read"
]

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
    """Generate Slack authorization URL"""
    try:
        state = await generate_oauth_state(user_id)
        
        params = {
            "response_type": "code",
            "client_id": SLACK_CLIENT_ID,
            "redirect_uri": SLACK_REDIRECT_URI,
            "scope": " ".join(SLACK_SCOPES),
            "state": state,
            "user_scope": ""  # Add user scopes if needed
        }
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        auth_url = f"{SLACK_AUTH_URL}?{query_string}"
        
        return {
            "authorization_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Slack authorization URL: {e}")
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
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "code": code,
            "redirect_uri": SLACK_REDIRECT_URI
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(SLACK_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            if not token_data.get("ok"):
                raise Exception(f"Slack OAuth failed: {token_data.get('error', 'Unknown error')}")
            
            # Get workspace info
            workspace_info = await get_workspace_info(token_data["access_token"])
            
            # Store tokens in database
            await store_slack_tokens(user_id, token_data, workspace_info)
            
            return {
                "success": True,
                "user_id": user_id,
                "tokens": token_data,
                "workspace": workspace_info
            }
            
    except Exception as e:
        logger.error(f"Failed to exchange Slack code for tokens: {e}")
        raise Exception(f"Token exchange failed: {str(e)}")

async def refresh_access_token(user_id: str, refresh_token: str) -> Dict[str, Any]:
    """Refresh expired access token"""
    try:
        data = {
            "client_id": SLACK_CLIENT_ID,
            "client_secret": SLACK_CLIENT_SECRET,
            "grant_type": "refresh_token",
            "refresh_token": refresh_token
        }
        
        headers = {
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        async with httpx.AsyncClient() as client:
            response = await client.post(SLACK_TOKEN_URL, data=data, headers=headers)
            response.raise_for_status()
            
            token_data = response.json()
            
            if not token_data.get("ok"):
                raise Exception(f"Slack token refresh failed: {token_data.get('error', 'Unknown error')}")
            
            # Update tokens in database
            await update_slack_tokens(user_id, token_data)
            
            return token_data
            
    except Exception as e:
        logger.error(f"Failed to refresh Slack tokens: {e}")
        raise Exception(f"Token refresh failed: {str(e)}")

async def get_workspace_info(access_token: str) -> Dict[str, Any]:
    """Get Slack workspace information"""
    try:
        headers = {
            "Authorization": f"Bearer {access_token}",
            "Content-Type": "application/json"
        }
        
        async with httpx.AsyncClient() as client:
            # Get team info
            response = await client.get(f"{SLACK_API_BASE}/team.info", headers=headers)
            response.raise_for_status()
            
            team_data = response.json()
            
            if not team_data.get("ok"):
                return {}
            
            team = team_data.get("team", {})
            
            return {
                "team_id": team.get("id"),
                "team_name": team.get("name"),
                "domain": team.get("domain"),
                "email_domain": team.get("email_domain"),
                "icon": team.get("icon", {}).get("image_132"),
                "created": team.get("created"),
                "enterprise_id": team.get("enterprise_id"),
                "enterprise_name": team.get("enterprise_name")
            }
            
    except Exception as e:
        logger.error(f"Failed to get Slack workspace info: {e}")
        return {}

async def store_slack_tokens(user_id: str, token_data: Dict[str, Any], workspace_info: Dict[str, Any]) -> bool:
    """Store OAuth tokens in database"""
    try:
        from db_oauth_slack import store_user_slack_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Calculate expires_at (Slack tokens typically don't expire, but we'll set a default)
        expires_in = token_data.get("expires_in", 86400 * 30)  # 30 days default
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type", "Bearer"),
            "workspace": workspace_info
        }
        
        result = await store_user_slack_tokens(db_pool, user_id, tokens)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to store Slack tokens: {e}")
        return False

async def update_slack_tokens(user_id: str, token_data: Dict[str, Any]) -> bool:
    """Update OAuth tokens in database"""
    try:
        from db_oauth_slack import update_user_slack_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        # Calculate expires_at
        expires_in = token_data.get("expires_in", 86400 * 30)  # 30 days default
        expires_at = datetime.now(timezone.utc).timestamp() + expires_in
        
        tokens = {
            "access_token": token_data.get("access_token"),
            "refresh_token": token_data.get("refresh_token"),
            "expires_at": expires_at,
            "scope": token_data.get("scope"),
            "token_type": token_data.get("token_type", "Bearer")
        }
        
        result = await update_user_slack_tokens(db_pool, user_id, tokens)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to update Slack tokens: {e}")
        return False

async def revoke_tokens(user_id: str) -> bool:
    """Revoke Slack OAuth tokens"""
    try:
        from db_oauth_slack import delete_user_slack_tokens
        from main_api_app import get_db_pool
        
        db_pool = await get_db_pool()
        
        result = await delete_user_slack_tokens(db_pool, user_id)
        return result["success"]
        
    except Exception as e:
        logger.error(f"Failed to revoke Slack tokens: {e}")
        return False

async def get_oauth_client_config() -> Dict[str, Any]:
    """Get OAuth client configuration for frontend"""
    return {
        "client_id": SLACK_CLIENT_ID,
        "auth_url": SLACK_AUTH_URL,
        "scopes": SLACK_SCOPES,
        "redirect_uri": SLACK_REDIRECT_URI
    }

async def verify_slack_request(request_body: bytes, headers: Dict[str, str]) -> bool:
    """Verify Slack request signature"""
    try:
        if not SLACK_SIGNING_SECRET:
            return True  # Skip verification if signing secret not configured
        
        timestamp = headers.get("x-slack-request-timestamp")
        signature = headers.get("x-slack-signature")
        
        if not timestamp or not signature:
            return False
        
        # Check if request is too old (5 minutes)
        if abs(int(time.time()) - int(timestamp)) > 300:
            return False
        
        # Create expected signature
        sig_basestring = f"v0:{timestamp}:{request_body.decode()}"
        expected_signature = "v0=" + hmac.new(
            SLACK_SIGNING_SECRET.encode(),
            sig_basestring.encode(),
            hashlib.sha256
        ).hexdigest()
        
        return hmac.compare_digest(expected_signature, signature)
        
    except Exception as e:
        logger.error(f"Failed to verify Slack request: {e}")
        return False