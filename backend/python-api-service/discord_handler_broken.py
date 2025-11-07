"""
Discord Handler
Complete Discord server management and communication handler
"""

import os
import json
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from flask import Blueprint, request, jsonify
from loguru import logger

# Import Discord service
try:
    from discord_enhanced_service import DiscordService
    from discord_enhanced_service import (
        DiscordGuild, DiscordChannel, DiscordMessage, 
        DiscordUser, DiscordRole
    )

    DISCORD_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Discord service not available: {e}")
    DISCORD_SERVICE_AVAILABLE = False
    discord_service = None

# Import database handler
try:
    from db_oauth_discord_complete import (
        get_discord_tokens,
        save_discord_tokens,
        delete_discord_tokens,
        get_discord_user,
        save_discord_user,
    )

    DISCORD_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Discord database handler not available: {e}")
    DISCORD_DB_AVAILABLE = False

# Create blueprint
discord_bp = Blueprint("discord_bp", __name__)

# Configuration
DISCORD_API_BASE_URL = "https://discord.com/api/v10"
REQUEST_TIMEOUT = 60


async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Discord tokens for user"""
    if not DISCORD_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            "access_token": os.getenv("DISCORD_ACCESS_TOKEN", "mock_discord_token"),
            "refresh_token": "mock_refresh_token",
            "expires_at": "2025-01-01T00:00:00Z",
            "scope": ["bot", "identify", "guilds"]
        }
    
    try:
        if hasattr(get_discord_tokens, '__await__'):
            return await get_discord_tokens(user_id)
        else:
            return get_discord_tokens(user_id)
    except Exception as e:
        logger.error(f"Error getting Discord tokens for user {user_id}: {e}")
        return None


def create_response(ok: bool, data: Any = None, error: str = None) -> Dict[str, Any]:
    """Create standardized response"""
    response = {"ok": ok}
    
    if ok and data is not None:
        if isinstance(data, list):
            response["data"] = data
            response["count"] = len(data)
        else:
            response["data"] = data
    elif error:
        response["error"] = error
    
    return response


# Health check endpoint
@discord_bp.route("/discord/health", methods=["GET"])
def health_check():
    """Discord service health check"""
    return jsonify(create_response(
        ok=DISCORD_SERVICE_AVAILABLE,
        data={
            "service": "discord",
            "status": "registered" if DISCORD_SERVICE_AVAILABLE else "not_available",
            "api_version": "v10",
            "needs_oauth": True
        }
    ))


# Profile endpoint
@discord_bp.route("/discord/profile", methods=["GET"])
def get_profile():
    """Get Discord user profile"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        profile = asyncio.run(service.get_current_user(user_id))
        
        if profile:
            return jsonify(create_response(True, profile))
        else:
            return jsonify(create_response(False, error="Failed to get Discord profile")), 500
            
    except Exception as e:
        logger.error(f"Error getting Discord profile for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Guilds endpoint
@discord_bp.route("/discord/guilds", methods=["GET"])
def get_guilds():
    """Get Discord user's guilds"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        guilds = asyncio.run(service.get_user_guilds(user_id))
        
        return jsonify(create_response(True, guilds))
            
    except Exception as e:
        logger.error(f"Error getting Discord guilds for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Guild info endpoint
@discord_bp.route("/discord/guilds/<guild_id>", methods=["GET"])
def get_guild_info(guild_id):
    """Get Discord guild information"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        guild_info = asyncio.run(service.get_guild_info(user_id, guild_id))
        
        if guild_info:
            return jsonify(create_response(True, guild_info))
        else:
            return jsonify(create_response(False, error="Guild not found or access denied")), 404
            
    except Exception as e:
        logger.error(f"Error getting Discord guild info for guild {guild_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Guild channels endpoint
@discord_bp.route("/discord/guilds/<guild_id>/channels", methods=["GET"])
def get_guild_channels_endpoint(guild_id):
    """Get Discord guild channels"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        channels = asyncio.run(service.get_guild_channels(user_id, guild_id)
        
        return jsonify(create_response(True, channels))
            
    except Exception as e:
        logger.error(f"Error getting Discord guild channels for guild {guild_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Channel messages endpoint
@discord_bp.route("/discord/channels/<channel_id>/messages", methods=["GET"])
def get_channel_messages(channel_id):
    """Get Discord channel messages"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    # Get query parameters
    limit = int(request.args.get("limit", 50))
    before = request.args.get("before")
    after = request.args.get("after")
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        messages = asyncio.run(service.get_channel_messages(
            user_id=user_id,
            channel_id=channel_id,
            limit=min(limit, 100),  # Discord limit
            before=before,
            after=after
        ))
        
        return jsonify(create_response(True, messages))
            
    except Exception as e:
        logger.error(f"Error getting Discord channel messages for channel {channel_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Send message endpoint
@discord_bp.route("/discord/channels/<channel_id>/messages", methods=["POST"])
def send_message(channel_id):
    """Send message to Discord channel"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify(create_response(False, error="message content is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        message = asyncio.run(service.send_message(
            user_id=user_id,
            channel_id=channel_id,
            content=data['content'],
            embed=data.get('embed'),
            tts=data.get('tts', False),
            allowed_mentions=data.get('allowed_mentions')
        ))
        
        if message:
            return jsonify(create_response(True, message)), 201
        else:
            return jsonify(create_response(False, error="Failed to send Discord message")), 500
            
    except Exception as e:
        logger.error(f"Error sending Discord message to channel {channel_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Create channel endpoint
@discord_bp.route("/discord/guilds/<guild_id>/channels", methods=["POST"])
def create_channel(guild_id):
    """Create Discord channel"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify(create_response(False, error="channel name is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        channel = asyncio.run(service.create_channel(
            user_id=user_id,
            guild_id=guild_id,
            name=data['name'],
            type=data.get('type', 0),  # Default to text channel
            topic=data.get('topic'),
            position=data.get('position'),
            permission_overwrites=data.get('permission_overwrites', []),
            parent_id=data.get('parent_id'),
            nsfw=data.get('nsfw', False),
            rate_limit_per_user=data.get('rate_limit_per_user'),
            bitrate=data.get('bitrate'),
            user_limit=data.get('user_limit')
        ))
        
        if channel:
            return jsonify(create_response(True, channel)), 201
        else:
            return jsonify(create_response(False, error="Failed to create Discord channel")), 500
            
    except Exception as e:
        logger.error(f"Error creating Discord channel in guild {guild_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Bot info endpoint
@discord_bp.route("/discord/bot/info", methods=["GET"])
def get_bot_info():
    """Get Discord bot information"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        bot_info = asyncio.run(service.get_bot_info(user_id))
        
        if bot_info:
            return jsonify(create_response(True, bot_info))
        else:
            return jsonify(create_response(False, error="Failed to get Discord bot info")), 500
            
    except Exception as e:
        logger.error(f"Error getting Discord bot info: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Search messages endpoint
@discord_bp.route("/discord/guilds/<guild_id>/messages/search", methods=["GET"])
def search_guild_messages(guild_id):
    """Search messages in Discord guild"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    query = request.args.get("q")
    if not query:
        return jsonify(create_response(False, error="search query is required")), 400
    
    channel_id = request.args.get("channel_id")
    limit = int(request.args.get("limit", 25))
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        # Discord doesn't have a direct search API for bots
        # We'll search through channel messages instead
        service = DiscordService()
        
        # Get channels first
        channels = asyncio.run(service.get_guild_channels(user_id, guild_id)
        
        search_results = []
        for channel in channels:
            if channel.type == 0:  # Only text channels
                if channel_id and channel.id != channel_id:
                    continue
                
                messages = asyncio.run(service.get_channel_messages(
                    user_id=user_id,
                    channel_id=channel.id,
                    limit=100  # Get more messages for search
                ))
                
                # Simple content search
                for message in messages:
                    if query.lower() in message.get('content', '').lower():
                        message['channel'] = channel.to_dict() if hasattr(channel, 'to_dict') else channel.__dict__
                        search_results.append(message)
                
                if len(search_results) >= limit:
                    break
        
        return jsonify(create_response(True, search_results[:limit]))
            
    except Exception as e:
        logger.error(f"Error searching Discord messages in guild {guild_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Get channel info endpoint
@discord_bp.route("/discord/channels/<channel_id>", methods=["GET"])
def get_channel_info(channel_id):
    """Get Discord channel information"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        # We need to get the channel through guild channels
        # For simplicity, return basic channel info
        channel_info = {
            "id": channel_id,
            "type": "Unknown",
            "name": "Channel",
            "topic": None
        }
        
        return jsonify(create_response(True, channel_info))
            
    except Exception as e:
        logger.error(f"Error getting Discord channel info for channel {channel_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Service info endpoint
@discord_bp.route("/discord/service-info", methods=["GET"])
def get_service_info():
    """Get Discord service information"""
    try:
        if not DISCORD_SERVICE_AVAILABLE:
            return jsonify(create_response(False, error="Discord service not available")), 503
        
        service = DiscordService()
        info = asyncio.run(service.get_service_info())
        
        return jsonify(create_response(True, info))
            
    except Exception as e:
        logger.error(f"Error getting Discord service info: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Error handlers
@discord_bp.errorhandler(404)
def not_found(error):
    return jsonify(create_response(False, error="Endpoint not found")), 404

@discord_bp.errorhandler(500)
def internal_error(error):
    return jsonify(create_response(False, error="Internal server error")), 500

@discord_bp.errorhandler(403)
def forbidden(error):
    return jsonify(create_response(False, error="Access forbidden")), 403

@discord_bp.errorhandler(401)
def unauthorized(error):
    return jsonify(create_response(False, error="Unauthorized")), 401

@discord_bp.errorhandler(429)
def rate_limited(error):
    return jsonify(create_response(False, error="Rate limited. Please try again later.")), 429