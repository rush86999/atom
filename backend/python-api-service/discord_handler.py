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

# Create blueprint
discord_bp = Blueprint("discord_bp", __name__)

# Mock service for testing
class MockDiscordService:
    def __init__(self):
        self.api_base_url = "https://discord.com/api/v10"
    
    async def get_current_user(self, user_id):
        return {
            "id": "123456789",
            "username": "TestUser",
            "discriminator": "0001",
            "avatar": "test_avatar",
            "bot": False,
            "verified": True,
            "email": "test@example.com"
        }
    
    async def get_user_guilds(self, user_id):
        return [
            {
                "id": "987654321",
                "name": "Test Server",
                "icon": "test_icon",
                "owner": True,
                "permissions": "2147483647",
                "features": ["COMMUNITY"],
                "member_count": 100
            }
        ]
    
    async def get_guild_info(self, user_id, guild_id):
        return {
            "id": guild_id,
            "name": "Test Server",
            "icon": "test_icon",
            "owner_id": user_id,
            "member_count": 100,
            "text_channel_count": 10,
            "voice_channel_count": 5
        }
    
    async def get_guild_channels(self, user_id, guild_id):
        return [
            {
                "id": "111111111",
                "type": 0,
                "guild_id": guild_id,
                "name": "general",
                "topic": "General discussion",
                "position": 0,
                "nsfw": False,
                "message_count": 1000
            }
        ]
    
    async def get_channel_messages(self, user_id, channel_id, limit=50, before=None, after=None):
        return [
            {
                "id": "222222222",
                "channel_id": channel_id,
                "author": {
                    "id": user_id,
                    "username": "TestUser",
                    "discriminator": "0001"
                },
                "content": "Hello, world!",
                "timestamp": "2023-01-01T00:00:00Z",
                "type": 0
            }
        ]
    
    async def send_message(self, user_id, channel_id, content, embed=None, tts=False, allowed_mentions=None):
        return {
            "id": "333333333",
            "channel_id": channel_id,
            "author": {
                "id": "123456789",
                "username": "ATOMBOT",
                "discriminator": "0001"
            },
            "content": content,
            "timestamp": "2023-01-01T00:00:00Z",
            "type": 0
        }
    
    async def create_channel(self, user_id, guild_id, name, type=0, topic=None, position=None, **kwargs):
        return {
            "id": "444444444",
            "type": type,
            "guild_id": guild_id,
            "name": name,
            "topic": topic,
            "position": position or 0,
            "nsfw": False
        }
    
    async def get_bot_info(self, user_id):
        return {
            "id": "555555555",
            "username": "ATOMBOT",
            "discriminator": "0001",
            "avatar": "bot_avatar",
            "bot": True
        }
    
    async def get_service_info(self):
        return {
            "service": "discord",
            "version": "v1.0.0",
            "api_version": "v10",
            "features": [
                "guild_management",
                "channel_management",
                "message_sending",
                "user_authentication",
                "bot_integration"
            ],
            "rate_limits": {
                "requests_per_second": 50,
                "requests_per_minute": 1200
            }
        }


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
        ok=True,
        data={
            "service": "discord",
            "status": "registered",
            "needs_oauth": True,
            "api_version": "v10"
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
        service = MockDiscordService()
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
        service = MockDiscordService()
        guilds = asyncio.run(service.get_user_guilds(user_id))
        
        return jsonify(create_response(True, guilds))
            
    except Exception as e:
        logger.error(f"Error getting Discord guilds for user {user_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Guild info endpoint
@discord_bp.route("/discord/guilds/<guild_id>", methods=["GET"])
def get_guild_info_endpoint(guild_id):
    """Get Discord guild information"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        service = MockDiscordService()
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
        service = MockDiscordService()
        channels = asyncio.run(service.get_guild_channels(user_id, guild_id))
        
        return jsonify(create_response(True, channels))
            
    except Exception as e:
        logger.error(f"Error getting Discord guild channels for guild {guild_id}: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Channel messages endpoint
@discord_bp.route("/discord/channels/<channel_id>/messages", methods=["GET"])
def get_channel_messages_endpoint(channel_id):
    """Get Discord channel messages"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    # Get query parameters
    limit = int(request.args.get("limit", 50))
    before = request.args.get("before")
    after = request.args.get("after")
    
    try:
        service = MockDiscordService()
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
def send_message_endpoint(channel_id):
    """Send message to Discord channel"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data or 'content' not in data:
        return jsonify(create_response(False, error="message content is required")), 400
    
    try:
        service = MockDiscordService()
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
def create_channel_endpoint(guild_id):
    """Create Discord channel"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    data = request.get_json()
    if not data or 'name' not in data:
        return jsonify(create_response(False, error="channel name is required")), 400
    
    try:
        service = MockDiscordService()
        channel = asyncio.run(service.create_channel(
            user_id=user_id,
            guild_id=guild_id,
            name=data['name'],
            type=data.get('type', 0),  # Default to text channel
            topic=data.get('topic'),
            position=data.get('position')
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
def get_bot_info_endpoint():
    """Get Discord bot information"""
    user_id = request.headers.get("user-id")
    if not user_id:
        return jsonify(create_response(False, error="user-id header is required")), 400
    
    try:
        service = MockDiscordService()
        bot_info = asyncio.run(service.get_bot_info(user_id))
        
        if bot_info:
            return jsonify(create_response(True, bot_info))
        else:
            return jsonify(create_response(False, error="Failed to get Discord bot info")), 500
            
    except Exception as e:
        logger.error(f"Error getting Discord bot info: {e}")
        return jsonify(create_response(False, error=str(e))), 500


# Service info endpoint
@discord_bp.route("/discord/service-info", methods=["GET"])
def get_service_info_endpoint():
    """Get Discord service information"""
    try:
        service = MockDiscordService()
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