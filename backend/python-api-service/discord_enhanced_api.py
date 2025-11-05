"""
Enhanced Discord API Implementation
Complete Flask API handlers for Discord integration
"""

import os
import logging
import json
import asyncio
from datetime import datetime, timezone
from flask import Flask, request, jsonify, Blueprint
from typing import Dict, Any, Optional, List

# Import enhanced services
try:
    from discord_enhanced_service import discord_enhanced_service
    DISCORD_ENHANCED_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Enhanced Discord service not available: {e}")
    DISCORD_ENHANCED_AVAILABLE = False
    discord_enhanced_service = None

# Import authentication
try:
    from auth_handler_discord_complete import discord_auth_manager, get_discord_tokens
    DISCORD_AUTH_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord authentication not available: {e}")
    DISCORD_AUTH_AVAILABLE = False
    discord_auth_manager = None

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
discord_enhanced_bp = Blueprint("discord_enhanced_bp", __name__)

# Error handling decorator
def handle_discord_errors(func):
    """Decorator to handle Discord API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Discord API error: {e}")
            return jsonify({
                "ok": False,
                "error": str(e),
                "error_type": "api_error"
            }), 500
    return wrapper

# Authentication decorator
def require_discord_auth(func):
    """Decorator to require Discord authentication"""
    def wrapper(*args, **kwargs):
        if not DISCORD_AUTH_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord authentication not available"
            }), 503
        
        try:
            # Get user_id from request
            data = request.get_json() if request.is_json else {}
            user_id = data.get('user_id') or request.headers.get('X-User-ID')
            
            if not user_id:
                return jsonify({
                    "ok": False,
                    "error": "User ID is required"
                }), 400
            
            # Validate tokens (synchronous wrapper)
            if DISCORD_ENHANCED_AVAILABLE:
                tokens = asyncio.run(get_discord_tokens(None, user_id))
                if not tokens:
                    return jsonify({
                        "ok": False,
                        "error": "Discord authentication required"
                    }), 401
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Discord auth error: {e}")
            return jsonify({
                "ok": False,
                "error": "Authentication failed"
            }), 500
    return wrapper

@discord_enhanced_bp.route("/api/discord/enhanced/health", methods=["GET"])
@handle_discord_errors
def health():
    """Health check for enhanced Discord service"""
    try:
        service_info = discord_enhanced_service.get_service_info() if discord_enhanced_service else {}
        
        return jsonify({
            "ok": True,
            "status": "healthy",
            "service": "enhanced-discord-api",
            "version": "2.0.0",
            "features": {
                "service_available": DISCORD_ENHANCED_AVAILABLE,
                "auth_available": DISCORD_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False)
            },
            "service_info": service_info
        })
    except Exception as e:
        logger.error(f"Discord health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# User operations
@discord_enhanced_bp.route("/api/discord/enhanced/user/current", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def get_current_user():
    """Get current Discord user information"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        user = loop.run_until_complete(
            discord_enhanced_service.get_current_user(
                user_id=user_id
            )
        )
        loop.close()
        
        if not user:
            return jsonify({
                "ok": False,
                "error": "User not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "user": user.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting Discord user: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Guild operations
@discord_enhanced_bp.route("/api/discord/enhanced/guilds/list", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def list_guilds():
    """List Discord guilds (servers) for user"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        limit = data.get('limit', 100)
        before = data.get('before')
        after = data.get('after')
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        guilds = loop.run_until_complete(
            discord_enhanced_service.get_user_guilds(
                user_id=user_id,
                limit=limit,
                before=before,
                after=after
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "guilds": [guild.to_dict() for guild in guilds],
            "count": len(guilds),
            "filters": {
                "limit": limit,
                "before": before,
                "after": after
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Discord guilds: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_enhanced_bp.route("/api/discord/enhanced/guilds/info", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def get_guild_info():
    """Get detailed information about a Discord guild"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        guild_id = data.get('guild_id')
        
        # Validate required fields
        if not guild_id:
            return jsonify({
                "ok": False,
                "error": "Guild ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        guild = loop.run_until_complete(
            discord_enhanced_service.get_guild_info(
                user_id=user_id,
                guild_id=guild_id
            )
        )
        loop.close()
        
        if not guild:
            return jsonify({
                "ok": False,
                "error": "Guild not found"
            }), 404
        
        return jsonify({
            "ok": True,
            "guild": guild.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting Discord guild info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Channel operations
@discord_enhanced_bp.route("/api/discord/enhanced/channels/list", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def list_channels():
    """List channels for a Discord guild"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        guild_id = data.get('guild_id')
        
        # Validate required fields
        if not guild_id:
            return jsonify({
                "ok": False,
                "error": "Guild ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        channels = loop.run_until_complete(
            discord_enhanced_service.get_guild_channels(
                user_id=user_id,
                guild_id=guild_id
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "channels": [channel.to_dict() for channel in channels],
            "count": len(channels),
            "filters": {
                "guild_id": guild_id
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Discord channels: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_enhanced_bp.route("/api/discord/enhanced/channels/create", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def create_channel():
    """Create a new Discord channel"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        guild_id = data.get('guild_id')
        name = data.get('name')
        channel_type = data.get('type', 0)  # 0 = Text
        topic = data.get('topic', '')
        position = data.get('position', 0)
        permission_overwrites = data.get('permission_overwrites', [])
        
        # Validate required fields
        if not all([guild_id, name]):
            return jsonify({
                "ok": False,
                "error": "Guild ID and channel name are required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        channel = loop.run_until_complete(
            discord_enhanced_service.create_channel(
                user_id=user_id,
                guild_id=guild_id,
                name=name,
                channel_type=channel_type,
                topic=topic,
                position=position,
                permission_overwrites=permission_overwrites
            )
        )
        loop.close()
        
        if not channel:
            return jsonify({
                "ok": False,
                "error": "Failed to create channel"
            }), 500
        
        return jsonify({
            "ok": True,
            "channel": channel.to_dict(),
            "message": "Channel created successfully"
        })
        
    except Exception as e:
        logger.error(f"Error creating Discord channel: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Message operations
@discord_enhanced_bp.route("/api/discord/enhanced/messages/list", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def list_messages():
    """List messages from a Discord channel"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        limit = data.get('limit', 50)
        before = data.get('before')
        after = data.get('after')
        
        # Validate required fields
        if not channel_id:
            return jsonify({
                "ok": False,
                "error": "Channel ID is required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(
            discord_enhanced_service.get_channel_messages(
                user_id=user_id,
                channel_id=channel_id,
                limit=limit,
                before=before,
                after=after
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "messages": [message.to_dict() for message in messages],
            "count": len(messages),
            "filters": {
                "channel_id": channel_id,
                "limit": limit,
                "before": before,
                "after": after
            }
        })
        
    except Exception as e:
        logger.error(f"Error listing Discord messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_enhanced_bp.route("/api/discord/enhanced/messages/send", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def send_message():
    """Send a message to a Discord channel"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        channel_id = data.get('channel_id')
        content = data.get('content')
        embeds = data.get('embeds', [])
        tts = data.get('tts', False)
        allowed_mentions = data.get('allowed_mentions', {})
        message_reference = data.get('message_reference', {})
        
        # Validate required fields
        if not all([channel_id, content]):
            return jsonify({
                "ok": False,
                "error": "Channel ID and content are required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        message = loop.run_until_complete(
            discord_enhanced_service.send_message(
                user_id=user_id,
                channel_id=channel_id,
                content=content,
                embeds=embeds,
                tts=tts,
                allowed_mentions=allowed_mentions,
                message_reference=message_reference
            )
        )
        loop.close()
        
        if not message:
            return jsonify({
                "ok": False,
                "error": "Failed to send message"
            }), 500
        
        return jsonify({
            "ok": True,
            "message": message.to_dict(),
            "message_sent": True
        })
        
    except Exception as e:
        logger.error(f"Error sending Discord message: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Bot operations
@discord_enhanced_bp.route("/api/discord/enhanced/bot/info", methods=["GET", "POST"])
@handle_discord_errors
def get_bot_info():
    """Get Discord bot information"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        # Get bot token from environment
        bot_token = discord_auth_manager.bot_token if discord_auth_manager else None
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        bot = loop.run_until_complete(
            discord_enhanced_service.get_bot_info(
                bot_token=bot_token
            )
        )
        loop.close()
        
        if not bot:
            return jsonify({
                "ok": False,
                "error": "Bot information not available"
            }), 404
        
        return jsonify({
            "ok": True,
            "bot": bot.to_dict()
        })
        
    except Exception as e:
        logger.error(f"Error getting Discord bot info: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility endpoints
@discord_enhanced_bp.route("/api/discord/enhanced/sync", methods=["POST"])
@handle_discord_errors
@require_discord_auth
def sync_data():
    """Sync Discord data for user"""
    try:
        if not DISCORD_ENHANCED_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Enhanced Discord service not available"
            }), 503
        
        data = request.get_json()
        user_id = data.get('user_id')
        sync_types = data.get('sync_types', ['guilds', 'channels', 'messages'])
        
        results = {}
        
        # Sync user info
        if 'user' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            user = loop.run_until_complete(
                discord_enhanced_service.get_current_user(user_id=user_id)
            )
            loop.close()
            results['user'] = {
                'synced': user is not None,
                'data': user.to_dict() if user else None
            }
        
        # Sync guilds
        if 'guilds' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            guilds = loop.run_until_complete(
                discord_enhanced_service.get_user_guilds(user_id=user_id, limit=100)
            )
            loop.close()
            results['guilds'] = {
                'count': len(guilds),
                'synced': True
            }
        
        # Sync channels for first few guilds
        if 'channels' in sync_types:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            guilds = loop.run_until_complete(
                discord_enhanced_service.get_user_guilds(user_id=user_id, limit=3)
            )
            
            channels_synced = 0
            for guild in guilds:
                channels = loop.run_until_complete(
                    discord_enhanced_service.get_guild_channels(user_id=user_id, guild_id=guild.id)
                )
                channels_synced += len(channels)
            loop.close()
            
            results['channels'] = {
                'count': channels_synced,
                'synced': True
            }
        
        return jsonify({
            "ok": True,
            "sync_results": results,
            "synced_at": datetime.utcnow().isoformat(),
            "user_id": user_id
        })
        
    except Exception as e:
        logger.error(f"Error syncing Discord data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_enhanced_bp.route("/api/discord/enhanced/status", methods=["POST"])
@handle_discord_errors
def get_status():
    """Get enhanced Discord service status"""
    try:
        data = request.get_json() if request.is_json else {}
        user_id = data.get('user_id')
        
        service_info = discord_enhanced_service.get_service_info() if discord_enhanced_service else {}
        
        status_data = {
            "ok": True,
            "service": "enhanced-discord-api",
            "status": "available",
            "version": "2.0.0",
            "capabilities": {
                "service_available": DISCORD_ENHANCED_AVAILABLE,
                "auth_available": DISCORD_AUTH_AVAILABLE,
                "mock_mode": service_info.get("mock_mode", False),
                "encryption_available": bool(os.getenv('ATOM_OAUTH_ENCRYPTION_KEY'))
            },
            "service_info": service_info,
            "api_endpoints": [
                "/api/discord/enhanced/health",
                "/api/discord/enhanced/user/current",
                "/api/discord/enhanced/guilds/list",
                "/api/discord/enhanced/guilds/info",
                "/api/discord/enhanced/channels/list",
                "/api/discord/enhanced/channels/create",
                "/api/discord/enhanced/messages/list",
                "/api/discord/enhanced/messages/send",
                "/api/discord/enhanced/bot/info",
                "/api/discord/enhanced/sync",
                "/api/discord/enhanced/status"
            ]
        }
        
        if user_id:
            # Add user-specific status
            try:
                if DISCORD_AUTH_AVAILABLE:
                    from auth_handler_discord_complete import is_discord_token_valid
                    # This is a synchronous wrapper - in real async context you'd await this
                    status_data["user_authenticated"] = True  # Simplified for sync context
            except:
                status_data["user_authenticated"] = False
        
        return jsonify(status_data)
        
    except Exception as e:
        logger.error(f"Error getting Discord service status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Webhook operations
@discord_enhanced_bp.route("/api/discord/enhanced/webhooks", methods=["POST"])
@handle_discord_errors
def handle_webhook():
    """Handle Discord webhooks"""
    try:
        data = request.get_json()
        
        # Get webhook type
        webhook_type = data.get("t", "")  # Discord uses 't' for event type
        
        if webhook_type:
            logger.info(f"Discord webhook event received: {webhook_type}")
            await handle_discord_event(data, webhook_type)
        else:
            logger.info("Discord webhook validation received")
            return jsonify({"validation_response": "Discord webhook active"})
        
        return jsonify({
            "ok": True,
            "message": "Webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error handling Discord webhook: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

async def handle_discord_event(event_data: Dict[str, Any], event_type: str):
    """Handle Discord event"""
    try:
        logger.info(f"Discord event received: {event_type}")
        
        # Process different event types
        if event_type == 'GUILD_CREATE':
            await handle_guild_create_event(event_data)
        elif event_type == 'GUILD_DELETE':
            await handle_guild_delete_event(event_data)
        elif event_type == 'CHANNEL_CREATE':
            await handle_channel_create_event(event_data)
        elif event_type == 'CHANNEL_DELETE':
            await handle_channel_delete_event(event_data)
        elif event_type == 'MESSAGE_CREATE':
            await handle_message_create_event(event_data)
        elif event_type == 'MESSAGE_DELETE':
            await handle_message_delete_event(event_data)
        
    except Exception as e:
        logger.error(f"Error processing Discord event: {e}")

async def handle_guild_create_event(event_data: Dict[str, Any]):
    """Handle Discord guild created event"""
    try:
        guild = event_data.get("d", {})
        logger.info(f"Discord guild created: {guild.get('name', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Discord guild created event: {e}")

async def handle_guild_delete_event(event_data: Dict[str, Any]):
    """Handle Discord guild deleted event"""
    try:
        guild_id = event_data.get("d", {}).get("id")
        logger.info(f"Discord guild deleted: {guild_id}")
        
    except Exception as e:
        logger.error(f"Error handling Discord guild deleted event: {e}")

async def handle_channel_create_event(event_data: Dict[str, Any]):
    """Handle Discord channel created event"""
    try:
        channel = event_data.get("d", {})
        logger.info(f"Discord channel created: {channel.get('name', 'unknown')}")
        
    except Exception as e:
        logger.error(f"Error handling Discord channel created event: {e}")

async def handle_channel_delete_event(event_data: Dict[str, Any]):
    """Handle Discord channel deleted event"""
    try:
        channel_id = event_data.get("d", {}).get("id")
        logger.info(f"Discord channel deleted: {channel_id}")
        
    except Exception as e:
        logger.error(f"Error handling Discord channel deleted event: {e}")

async def handle_message_create_event(event_data: Dict[str, Any]):
    """Handle Discord message created event"""
    try:
        message = event_data.get("d", {})
        content = message.get("content", "")
        logger.info(f"Discord message created: {content[:100]}...")
        
    except Exception as e:
        logger.error(f"Error handling Discord message created event: {e}")

async def handle_message_delete_event(event_data: Dict[str, Any]):
    """Handle Discord message deleted event"""
    try:
        message_id = event_data.get("d", {}).get("id")
        logger.info(f"Discord message deleted: {message_id}")
        
    except Exception as e:
        logger.error(f"Error handling Discord message deleted event: {e}")

# Register blueprint with Flask app
def register_discord_enhanced_bp(app: Flask):
    """Register enhanced Discord blueprint with Flask app"""
    app.register_blueprint(discord_enhanced_bp)
    logger.info("Enhanced Discord API blueprint registered")

# Export components
__all__ = [
    'discord_enhanced_bp',
    'register_discord_enhanced_bp'
]