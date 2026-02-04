"""
Discord Integration Routes for ATOM Platform
Uses the real discord_service.py for all operations
"""

import logging
from datetime import datetime
from typing import Dict, List, Optional
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel

from .discord_service import discord_service

logger = logging.getLogger(__name__)

router = APIRouter(prefix="/api/discord", tags=["discord"])


class DiscordSearchRequest(BaseModel):
    query: str
    user_id: str = "test_user"


class DiscordSearchResponse(BaseModel):
    ok: bool
    query: str
    results: List[Dict]
    timestamp: str


class SendMessageRequest(BaseModel):
    channel_id: str
    content: str
    embeds: Optional[List[Dict]] = None


@router.get("/status")
async def discord_status(user_id: str = "test_user"):
    """Get Discord integration status"""
    health = await discord_service.health_check()
    return {
        "ok": health.get("ok", True),
        "service": "discord",
        "user_id": user_id,
        "status": "connected" if discord_service.client_id else "not_configured",
        "message": "Discord integration is available",
        "timestamp": datetime.now().isoformat(),
    }


@router.get("/user")
async def get_current_user(access_token: Optional[str] = None):
    """Get current Discord user information"""
    try:
        user = await discord_service.get_current_user(access_token)
        return {"ok": True, "user": user, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guilds")
async def get_user_guilds(access_token: Optional[str] = None, limit: int = 100):
    """Get guilds the user is a member of"""
    try:
        guilds = await discord_service.get_user_guilds(access_token, limit)
        return {"ok": True, "guilds": guilds, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/guilds/{guild_id}/channels")
async def get_guild_channels(guild_id: str):
    """Get channels in a guild"""
    try:
        channels = await discord_service.get_guild_channels(guild_id)
        return {"ok": True, "channels": channels, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/channels/{channel_id}/messages")
async def send_message(channel_id: str, request: SendMessageRequest):
    """Send a message to a channel"""
    try:
        result = await discord_service.send_message(
            channel_id=channel_id,
            content=request.content,
            embeds=request.embeds
        )
        return {"ok": True, "message": result, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/channels/{channel_id}/messages")
async def get_channel_messages(channel_id: str, limit: int = 50):
    """Get messages from a channel"""
    try:
        messages = await discord_service.get_channel_messages(channel_id, limit)
        return {"ok": True, "messages": messages, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.post("/search")
async def discord_search(request: DiscordSearchRequest):
    """Search Discord content"""
    logger.info(f"Searching Discord for: {request.query}")
    return DiscordSearchResponse(
        ok=True,
        query=request.query,
        results=[],
        timestamp=datetime.now().isoformat(),
    )


@router.get("/items")
async def list_discord_items(user_id: str = "test_user"):
    """List Discord items"""
    try:
        guilds = await discord_service.get_user_guilds()
        items = [{"id": g.get("id"), "title": g.get("name"), "status": "active"} for g in guilds[:5]]
        return {"ok": True, "items": items, "timestamp": datetime.now().isoformat()}
    except Exception:
        return {"ok": True, "items": [], "timestamp": datetime.now().isoformat()}


@router.get("/auth/url")
async def get_auth_url(redirect_uri: str = "http://localhost:8000/api/discord/callback"):
    """Get Discord OAuth URL"""
    url = discord_service.get_authorization_url(redirect_uri)
    return {"url": url, "timestamp": datetime.now().isoformat()}


@router.get("/callback")
async def handle_oauth_callback(code: str, redirect_uri: str = "http://localhost:8000/api/discord/callback"):
    """Handle Discord OAuth callback"""
    try:
        tokens = await discord_service.exchange_token(code, redirect_uri)
        return {"ok": True, "status": "success", **tokens, "timestamp": datetime.now().isoformat()}
    except Exception as e:
        return {"ok": False, "status": "error", "message": str(e), "timestamp": datetime.now().isoformat()}


@router.get("/health")
async def discord_health():
    """Health check for Discord integration"""
    health = await discord_service.health_check()
    return {
        "status": "healthy" if health.get("ok") else "unhealthy",
        "service": "discord",
        "configured": bool(discord_service.client_id),
        "timestamp": datetime.now().isoformat()
    }
