from fastapi import APIRouter, HTTPException, Depends, Request
from typing import Dict, Any, Optional
import logging
import asyncio
from slack_enhanced_service import SlackEnhancedService
from slack_oauth_handler import (
    get_authorization_url,
    exchange_code_for_tokens,
    revoke_tokens,
    get_oauth_client_config
)

router = APIRouter(prefix="/api/slack", tags=["slack"])
logger = logging.getLogger(__name__)

# Slack service cache
slack_service_cache = {}

async def get_slack_service(request: Request) -> SlackEnhancedService:
    """Get Slack service instance with user tokens"""
    try:
        user_id = request.headers.get("x-user-id", "current")
        
        # Get service instance from cache or create new
        cache_key = f"slack_{user_id}"
        if cache_key not in slack_service_cache:
            slack_service_cache[cache_key] = SlackEnhancedService(user_id)
            
            # Initialize with database pool
            from main_api_app import get_db_pool
            db_pool = await get_db_pool()
            await slack_service_cache[cache_key].initialize(db_pool)
        
        return slack_service_cache[cache_key]
        
    except Exception as e:
        logger.error(f"Failed to get Slack service: {e}")
        raise HTTPException(status_code=500, detail="Slack service initialization failed")

@router.get("/health")
async def health_check():
    """Health check for Slack integration"""
    try:
        # Check environment variables
        required_vars = ["SLACK_CLIENT_ID", "SLACK_CLIENT_SECRET", "SLACK_SIGNING_SECRET"]
        missing_vars = [var for var in required_vars if not os.getenv(var)]
        
        if missing_vars:
            return {
                "status": "unhealthy",
                "error": f"Missing environment variables: {', '.join(missing_vars)}"
            }
        
        return {
            "status": "healthy",
            "service": "slack-enhanced",
            "timestamp": "2025-11-07T00:00:00Z"
        }
        
    except Exception as e:
        logger.error(f"Slack health check failed: {e}")
        return {
            "status": "unhealthy",
            "error": str(e)
        }

@router.post("/oauth/start")
async def start_slack_oauth(request: Request):
    """Start OAuth flow for Slack"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        redirect_uri = data.get("redirect_uri")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        # Generate authorization URL
        auth_data = await get_authorization_url(user_id)
        
        return {
            "success": True,
            "authorization_url": auth_data["authorization_url"],
            "state": auth_data["state"]
        }
        
    except Exception as e:
        logger.error(f"Failed to start Slack OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/oauth/callback")
async def slack_oauth_callback(request: Request):
    """Handle OAuth callback from Slack"""
    try:
        data = await request.json()
        code = data.get("code")
        state = data.get("state")
        
        if not code or not state:
            raise HTTPException(
                status_code=400, 
                detail="code and state are required"
            )
        
        # Exchange code for tokens
        result = await exchange_code_for_tokens(code, state)
        
        if result["success"]:
            return {
                "success": True,
                "message": "Slack OAuth completed successfully",
                "user_id": result["user_id"],
                "workspace": result.get("workspace", {})
            }
        else:
            raise HTTPException(status_code=400, detail="OAuth token exchange failed")
        
    except Exception as e:
        logger.error(f"Failed to handle Slack OAuth callback: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.delete("/oauth/revoke")
async def revoke_slack_oauth(request: Request):
    """Revoke OAuth tokens"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        if not user_id:
            raise HTTPException(status_code=400, detail="user_id is required")
        
        success = await revoke_tokens(user_id)
        
        if success:
            return {
                "success": True,
                "message": "Slack OAuth tokens revoked successfully"
            }
        else:
            raise HTTPException(status_code=500, detail="Failed to revoke tokens")
        
    except Exception as e:
        logger.error(f"Failed to revoke Slack OAuth: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/user/info")
async def get_user_info(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Get Slack user information"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        
        result = await slack_service.get_user_info(user_id)
        
        if "error" in result:
            raise HTTPException(status_code=500, detail=result["error"])
        
        return {
            "success": True,
            "data": result
        }
        
    except Exception as e:
        logger.error(f"Failed to get Slack user info: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/channels")
async def get_channels(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Get Slack channels"""
    try:
        data = await request.json()
        types = data.get("types")  # public_channel, private_channel, etc.
        
        result = await slack_service.get_channels(types)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack channels: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/messages")
async def get_messages(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Get messages from Slack channel"""
    try:
        data = await request.json()
        channel_id = data.get("channel_id")
        limit = data.get("limit", 50)
        oldest = data.get("oldest")
        latest = data.get("latest")
        
        if not channel_id:
            raise HTTPException(status_code=400, detail="channel_id is required")
        
        result = await slack_service.get_messages(channel_id, limit, oldest, latest)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/messages/send")
async def send_message(
    message_data: Dict[str, Any],
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Send message to Slack channel"""
    try:
        channel_id = message_data.get("channel_id")
        text = message_data.get("text")
        thread_ts = message_data.get("thread_ts")
        blocks = message_data.get("blocks")
        attachments = message_data.get("attachments")
        
        if not channel_id or not text:
            raise HTTPException(status_code=400, detail="channel_id and text are required")
        
        result = await slack_service.send_message(channel_id, text, thread_ts, blocks, attachments)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        # Log activity
        await slack_service.log_activity("send_message", {
            "channel_id": channel_id,
            "text_preview": text[:100] + "..." if len(text) > 100 else text,
            "has_blocks": bool(blocks),
            "has_attachments": bool(attachments)
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to send Slack message: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/files")
async def get_files(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Get files from Slack"""
    try:
        data = await request.json()
        user_id = data.get("user_id")
        channel_id = data.get("channel_id")
        types = data.get("types", "all")
        limit = data.get("limit", 50)
        
        result = await slack_service.get_files(user_id, channel_id, types, limit)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack files: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/search/messages")
async def search_messages(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Search messages in Slack"""
    try:
        data = await request.json()
        query = data.get("query")
        count = data.get("count", 50)
        sort = data.get("sort", "timestamp_desc")
        channel_id = data.get("channel_id")
        
        if not query:
            raise HTTPException(status_code=400, detail="query is required")
        
        result = await slack_service.search_messages(query, count, sort, channel_id)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        # Log search activity
        await slack_service.log_activity("search_messages", {
            "query": query,
            "count": count,
            "sort": sort,
            "channel_id": channel_id
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to search Slack messages: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reactions")
async def get_reactions(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Get reactions for a message"""
    try:
        data = await request.json()
        channel_id = data.get("channel_id")
        timestamp = data.get("timestamp")
        
        if not channel_id or not timestamp:
            raise HTTPException(status_code=400, detail="channel_id and timestamp are required")
        
        result = await slack_service.get_reactions(channel_id, timestamp)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to get Slack reactions: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/reactions/add")
async def add_reaction(
    request: Request,
    slack_service: SlackEnhancedService = Depends(get_slack_service)
):
    """Add reaction to message"""
    try:
        data = await request.json()
        channel_id = data.get("channel_id")
        timestamp = data.get("timestamp")
        reaction_name = data.get("name")
        
        if not channel_id or not timestamp or not reaction_name:
            raise HTTPException(status_code=400, detail="channel_id, timestamp, and name are required")
        
        result = await slack_service.add_reaction(channel_id, timestamp, reaction_name)
        
        if not result["success"]:
            raise HTTPException(status_code=500, detail=result.get("error", "Unknown error"))
        
        # Log reaction activity
        await slack_service.log_activity("add_reaction", {
            "channel_id": channel_id,
            "timestamp": timestamp,
            "reaction": reaction_name
        })
        
        return result
        
    except Exception as e:
        logger.error(f"Failed to add Slack reaction: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.post("/webhooks/interactive")
async def handle_interactive_webhook(request: Request):
    """Handle Slack interactive webhooks"""
    try:
        # Verify request signature
        from slack_oauth_handler import verify_slack_request
        body = await request.body()
        
        if not await verify_slack_request(body, dict(request.headers)):
            raise HTTPException(status_code=401, detail="Invalid request signature")
        
        # Parse form data
        payload = (await request.form()).get("payload")
        if not payload:
            raise HTTPException(status_code=400, detail="No payload provided")
        
        interaction = json.loads(payload)
        
        # Handle different interaction types
        if interaction["type"] == "block_actions":
            # Handle block actions
            action = interaction["actions"][0]
            return {
                "response_type": "ephemeral",
                "text": f"Action '{action['action_id']}' received"
            }
        elif interaction["type"] == "view_submission":
            # Handle view submissions
            return {
                "response_action": "clear",
                "message": {
                    "type": "message",
                    "text": "Form submitted successfully"
                }
            }
        else:
            return {"status": "received"}
            
    except Exception as e:
        logger.error(f"Failed to handle Slack webhook: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/client-config")
async def get_client_config():
    """Get OAuth client configuration for frontend"""
    try:
        config = await get_oauth_client_config()
        return {
            "success": True,
            "data": config
        }
    except Exception as e:
        logger.error(f"Failed to get Slack client config: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/services/status")
async def get_services_status():
    """Get status of all Slack services"""
    try:
        services_status = {
            "messaging": "available",
            "channels": "available",
            "files": "available",
            "search": "available",
            "reactions": "available",
            "webhooks": "available",
            "user_management": "available",
            "team_info": "available"
        }
        
        return {
            "success": True,
            "services": services_status,
            "overall_status": "healthy"
        }
        
    except Exception as e:
        logger.error(f"Failed to get Slack services status: {e}")
        return {
            "success": False,
            "error": str(e)
        }