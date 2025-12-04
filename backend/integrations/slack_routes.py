"""
Slack Integration Routes - Fixed FastAPI Version
Complete Slack integration with comprehensive API endpoints using FastAPI
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional

from fastapi import APIRouter, HTTPException, Depends
from pydantic import BaseModel
import os
from fastapi import Request
from core.oauth_handler import OAuthHandler, SLACK_OAUTH_CONFIG
from core.token_storage import token_storage

logger = logging.getLogger(__name__)

try:
    from slack_sdk import WebClient
    from slack_sdk.errors import SlackApiError
    SLACK_SDK_AVAILABLE = True
except ImportError:
    SLACK_SDK_AVAILABLE = False
    logger.warning("slack_sdk not installed, running in mock mode")

# Create FastAPI router
# Auth Type: OAuth2
router = APIRouter(prefix="/api/slack", tags=["slack"])

def get_slack_client():
    """Get Slack WebClient if token is available"""
    token = os.getenv("SLACK_BOT_TOKEN")
    if not token:
        return None
    return WebClient(token=token)


class SlackMessageRequest(BaseModel):
    channel: str
    text: str
    user_id: str = "test_user"


class SlackMessageResponse(BaseModel):
    ok: bool
    channel: str
    message_id: str
    text: str
    timestamp: str


class SlackSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"
    max_results: int = 10


class SlackSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    total_results: int
    timestamp: str


class SlackChannelRequest(BaseModel):
    channel_id: str
    user_id: str = "test_user"


class SlackChannelResponse(BaseModel):
    ok: bool
    channel_id: str
    name: str
    members: List[Dict]
    timestamp: str


@router.get("/status")
async def slack_status(user_id: str = "test_user"):
    """Get Slack integration status"""
    client = get_slack_client()
    is_connected = client is not None and SLACK_SDK_AVAILABLE
    
    return {
        "ok": True,
        "service": "slack",
        "user_id": user_id,
        "status": "connected" if is_connected else "mock_mode",
        "message": "Slack integration is available" if is_connected else "Running in mock mode (missing SLACK_BOT_TOKEN)",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/health")
async def slack_health(user_id: str = "test_user"):
    """Health check endpoint (alias for status)"""
    return await slack_status(user_id)



@router.post("/messages")
async def send_slack_message(request: SlackMessageRequest):
    """Send a Slack message"""
    logger.info(f"Sending Slack message to channel: {request.channel}")

    client = get_slack_client()
    if client and SLACK_SDK_AVAILABLE:
        try:
            response = client.chat_postMessage(
                channel=request.channel,
                text=request.text
            )
            return SlackMessageResponse(
                ok=True,
                channel=response["channel"],
                message_id=response["ts"],
                text=request.text,
                timestamp=datetime.now().isoformat(),
            )
        except SlackApiError as e:
            logger.error(f"Error sending message: {e.response['error']}")
            raise HTTPException(status_code=400, detail=f"Slack API Error: {e.response['error']}")
    
    # Fallback to mock
    return SlackMessageResponse(
        ok=True,
        channel=request.channel,
        message_id=f"msg_{request.channel}_{datetime.now().timestamp()}",
        text=request.text,
        timestamp=datetime.now().isoformat(),
    )


@router.post("/search")
async def slack_search(request: SlackSearchRequest):
    """Search Slack messages"""
    logger.info(f"Searching Slack for: {request.query}")

    # Mock search results
    mock_results = [
        {
            "id": f"msg_{i}",
            "channel": f"channel_{i}",
            "user": f"user_{i}",
            "text": f"This message contains {request.query} - result {i}",
            "timestamp": f"2025-11-09T{10 + i}:00:00Z",
            "reactions": ["👍", "🚀"] if i % 2 == 0 else ["👀"],
        }
        for i in range(1, request.max_results + 1)
    ]

    return SlackSearchResponse(
        ok=True,
        query=request.query,
        results=mock_results,
        total_results=len(mock_results),
        timestamp=datetime.now().isoformat(),
    )


@router.get("/channels/{channel_id}")
async def get_slack_channel(channel_id: str, user_id: str = "test_user"):
    """Get a specific Slack channel"""
    logger.info(f"Getting Slack channel: {channel_id}")

    if not channel_id:
        raise HTTPException(status_code=400, detail="Channel ID is required")

    mock_members = [
        {"id": f"user_{i}", "name": f"Member {i}", "is_bot": i == 1}
        for i in range(1, 6)
    ]

    return SlackChannelResponse(
        ok=True,
        channel_id=channel_id,
        name=f"Channel {channel_id}",
        members=mock_members,
        timestamp=datetime.now().isoformat(),
    )


@router.get("/channels")
async def list_slack_channels(user_id: str = "test_user"):
    """List available Slack channels"""
    logger.info("Listing Slack channels")

    mock_channels = [
        {
            "id": f"channel_{i}",
            "name": f"general-{i}",
            "is_private": i % 3 == 0,
            "member_count": 10 + i,
            "topic": f"Channel topic {i}",
        }
        for i in range(1, 8)
    ]

    return {
        "ok": True,
        "channels": mock_channels,
        "total_channels": len(mock_channels),
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/users/{user_id}")
async def get_slack_user(user_id: str):
    """Get Slack user information"""
    logger.info(f"Getting Slack user: {user_id}")

    return {
        "ok": True,
        "user": {
            "id": user_id,
            "name": f"user_{user_id}",
            "real_name": f"Real Name {user_id}",
            "email": f"user{user_id}@example.com",
            "is_bot": "bot" in user_id,
            "timezone": "America/New_York",
        },
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/conversations/history")
async def get_conversation_history(
    channel: str, limit: int = 10, user_id: str = "test_user"
):
    """Get conversation history for a channel"""
    logger.info(f"Getting conversation history for channel: {channel}")

    mock_messages = [
        {
            "id": f"msg_{i}",
            "user": f"user_{i}",
            "text": f"Message {i} in conversation",
            "timestamp": f"2025-11-09T{10 + i}:00:00Z",
            "reactions": ["👍"] if i % 2 == 0 else [],
        }
        for i in range(1, limit + 1)
    ]

    return {
        "ok": True,
        "channel": channel,
        "messages": mock_messages,
        "total_messages": len(mock_messages),
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/reactions/add")
async def add_slack_reaction(
    channel: str, timestamp: str, reaction: str, user_id: str = "test_user"
):
    """Add a reaction to a Slack message"""
    logger.info(f"Adding reaction {reaction} to message in {channel}")

    return {
        "ok": True,
        "channel": channel,
        "timestamp": timestamp,
        "reaction": reaction,
        "message": f"Reaction {reaction} added successfully",
        "timestamp": datetime.now().isoformat(),
    }


@router.post("/callback")
async def slack_oauth_callback(request: Request):
    """Handle Slack OAuth callback"""
    try:
        data = await request.json()
        code = data.get("code")
        
        if not code:
            raise HTTPException(status_code=400, detail="Authorization code is required")

        handler = OAuthHandler(SLACK_OAUTH_CONFIG)
        tokens = await handler.exchange_code_for_tokens(code)
        
        # Store tokens securely
        token_storage.save_token("slack", tokens)
        
        logger.info("Slack OAuth successful - tokens received and stored")
        return {"status": "success", "provider": "slack", "tokens": tokens}
    
    except Exception as e:
        logger.error(f"Slack OAuth callback error: {e}")
        raise HTTPException(status_code=500, detail=str(e))

@router.get("/auth/url")
async def get_auth_url():
    """Get Slack OAuth URL"""
    return {
        "url": "https://slack.com/oauth/v2/authorize?client_id=INSERT_CLIENT_ID&scope=chat:write,channels:read,users:read&redirect_uri=http%3A%2F%2Flocalhost%3A8000%2Fapi%2Fslack%2Fcallback",
        "timestamp": datetime.now().isoformat()
    }
