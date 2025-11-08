from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional, List
import logging
import asyncio
from slack_service import SlackService
from auth_handler_slack_new import get_slack_oauth_handler
from db_oauth_slack_new import get_user_slack_tokens, is_slack_token_expired, refresh_slack_tokens

router = APIRouter(prefix="/api/slack", tags=["slack"])
logger = logging.getLogger(__name__)

# Service cache
slack_service_cache = {}

async def get_slack_service(request: Request) -> SlackService:
    """Get Slack service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"slack_{user_id}"
        if cache_key not in slack_service_cache:
            slack_service_cache[cache_key] = SlackService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            
            # Initialize service
            if not await slack_service_cache[cache_key].initialize(db_pool):
                # Try to refresh tokens if expired
                tokens = await get_user_slack_tokens(db_pool, user_id)
                if tokens and await is_slack_token_expired(db_pool, user_id):
                    oauth_handler = get_slack_oauth_handler()
                    refresh_result = await oauth_handler.refresh_access_token(tokens["refresh_token"])
                    
                    if refresh_result["success"]:
                        await refresh_slack_tokens(db_pool, user_id, refresh_result["data"])
                        await slack_service_cache[cache_key].initialize(db_pool)
                    else:
                        raise HTTPException(status_code=401, detail="Slack authentication failed")
        
        return slack_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Slack service: {e}")
        raise HTTPException(status_code=500, detail="Slack service initialization failed")

@router.get("/health")
async def health_check():
    """Health check for Slack integration"""
    try:
        # Check environment variables
        required_vars = ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "ATOM_OAUTH_ENCRYPTION_KEY"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }
        
        services = {
            "real_time": "available",
            "messaging": "available",
            "files": "available",
            "channels": "available",
            "users": "available",
            "search": "available",
            "webhooks": "available",
            "oauth": "available"
        }
        
        return {
            "status": "healthy",
            "service": "slack",
            "services": services,
            "timestamp": "2025-11-07T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Slack health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.get("/auth/url")
async def get_auth_url(request: Request):
    """Get Slack OAuth authorization URL"""
    try:
        oauth_handler = get_slack_oauth_handler()
        state = oauth_handler.generate_state()
        
        # Store state in session (in production, use Redis or database)
        auth_url = await oauth_handler.get_authorization_url(state)
        
        return {
            "success": True,
            "auth_url": auth_url,
            "state": state
        }
        
    except Exception as e:
        logger.error(f"Failed to generate Slack auth URL: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/auth/callback")
async def auth_callback(request: Request):
    """Handle Slack OAuth callback"""
    try:
        body = await request.json()
        code = body.get("code")
        state = body.get("state")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code not provided")
        
        oauth_handler = get_slack_oauth_handler()
        
        # Exchange code for tokens
        token_result = await oauth_handler.exchange_code_for_tokens(code)
        
        if not token_result["success"]:
            raise HTTPException(status_code=400, detail=token_result["error"])
        
        # Get user info
        tokens = token_result["data"]
        user_info_result = await oauth_handler.get_user_info(tokens["access_token"])
        
        if not user_info_result["success"]:
            raise HTTPException(status_code=400, detail="Failed to get Slack user info")
        
        # Store tokens in database
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_slack_token_manager()
        
        user_info = user_info_result["data"]
        
        await token_manager.store_slack_tokens(
            db_pool,
            request.headers.get("x-user-id", "current"),
            user_info.get("team_id", "default"),
            user_info.get("team", "default"),
            tokens
        )
        
        # Log activity
        await token_manager.log_slack_activity(
            db_pool,
            request.headers.get("x-user-id", "current"),
            "oauth_login",
            {
                "team_id": user_info.get("team_id"),
                "team_name": user_info.get("team"),
                "user_id": user_info.get("user_id"),
                "timestamp": datetime.now().isoformat()
            }
        )
        
        return {
            "success": True,
            "message": "Authentication successful",
            "user_info": user_info,
            "tokens": {
                "expires_in": tokens["expires_in"],
                "created_at": tokens["created_at"]
            }
        }
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Slack auth callback failed: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Team endpoints
@router.post("/team/info")
async def get_team_info(
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get Slack team/workspace information"""
    try:
        result = await slack_service.get_team_info()
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack team info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Users endpoints
@router.post("/users")
async def get_users(
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get Slack workspace users"""
    try:
        body = await request.json()
        limit = body.get("limit", 100)
        cursor = body.get("cursor")
        
        result = await slack_service.get_users(limit, cursor)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack users: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/users/{user_id}")
async def get_user_info(
    user_id: str,
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get specific user information"""
    try:
        result = await slack_service.get_user_info(user_id)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack user info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Channels endpoints
@router.post("/channels")
async def get_channels(
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get Slack channels"""
    try:
        body = await request.json()
        types = body.get("types")
        limit = body.get("limit", 100)
        cursor = body.get("cursor")
        
        result = await slack_service.get_channels(types, limit, cursor)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/channels/{channel_id}/messages")
async def get_channel_messages(
    channel_id: str,
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get messages from a channel"""
    try:
        body = await request.json()
        limit = body.get("limit", 100)
        cursor = body.get("cursor")
        oldest = body.get("oldest")
        latest = body.get("latest")
        
        result = await slack_service.get_channel_messages(channel_id, limit, cursor, oldest, latest)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack channel messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/channels/{channel_id}/messages/send")
async def send_message(
    channel_id: str,
    message_data: Dict[str, Any],
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Send a message to a channel"""
    try:
        text = message_data.get("text")
        thread_ts = message_data.get("thread_ts")
        blocks = message_data.get("blocks")
        
        if not text and not blocks:
            raise HTTPException(status_code=400, detail="Message text or blocks are required")
        
        result = await slack_service.send_message(channel_id, text, thread_ts, blocks)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to send Slack message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Files endpoints
@router.post("/files")
async def get_files(
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get Slack files"""
    try:
        body = await request.json()
        types = body.get("types", "all")
        limit = body.get("limit", 100)
        page = body.get("page", 1)
        
        result = await slack_service.get_files(types, limit, page)
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Search endpoints
@router.post("/search/messages")
async def search_messages(
    search_data: Dict[str, Any],
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Search Slack messages"""
    try:
        query = search_data.get("query")
        sort = search_data.get("sort", "timestamp")
        sort_dir = search_data.get("sort_dir", "desc")
        count = search_data.get("count", 50)
        
        if not query:
            raise HTTPException(status_code=400, detail="Search query is required")
        
        result = await slack_service.search_messages(query, sort, sort_dir, count)
        return result
        
    except HTTPException:
        raise
    except Exception as e:
        logger.error(f"Failed to search Slack messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

# Analytics endpoints
@router.post("/analytics/workspace")
async def get_workspace_stats(
    analytics_request: Dict[str, Any],
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get workspace statistics"""
    try:
        result = await slack_service.get_workspace_stats()
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack workspace stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/stats")
async def get_slack_stats(
    request: Request,
    slack_service: SlackService = Depends(get_slack_service)
):
    """Get Slack statistics for user"""
    try:
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_slack_token_manager()
        
        stats = await token_manager.get_slack_stats(db_pool, request.headers.get("x-user-id", "current"))
        
        return {
            "success": True,
            "data": stats
        }
        
    except Exception as e:
        logger.error(f"Failed to get Slack stats: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/logout")
async def logout(request: Request):
    """Logout from Slack"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Delete tokens from database
        from main_api_app import get_db_pool
        db_pool = await get_db_pool()
        token_manager = get_slack_token_manager()
        
        await token_manager.delete_slack_tokens(db_pool, user_id)
        
        # Clear service cache
        cache_key = f"slack_{user_id}"
        if cache_key in slack_service_cache:
            del slack_service_cache[cache_key]
        
        return {
            "success": True,
            "message": "Logged out successfully"
        }
        
    except Exception as e:
        logger.error(f"Failed to logout from Slack: {e}")
        raise HTTPException(status_code=500, detail=str(e))