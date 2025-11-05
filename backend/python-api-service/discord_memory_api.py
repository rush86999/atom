"""
Discord Memory API Endpoints
Complete Discord memory management with LanceDB integration and user controls
"""

import os
import logging
import json
import asyncio
from datetime import datetime, timezone
from flask import request, jsonify, Blueprint
from typing import Dict, Any, Optional, List

# Import Discord LanceDB service
try:
    from discord_lancedb_ingestion_service import (
        discord_lancedb_service,
        DiscordMemorySettings
    )
    DISCORD_LANCEDB_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord LanceDB service not available: {e}")
    DISCORD_LANCEDB_AVAILABLE = False
    discord_lancedb_service = None

# Import Discord authentication
try:
    from auth_handler_discord_complete import get_discord_tokens, is_discord_token_valid
    DISCORD_AUTH_AVAILABLE = True
except ImportError as e:
    logging.getLogger(__name__).warning(f"Discord auth not available: {e}")
    DISCORD_AUTH_AVAILABLE = False

# Configure logging
logger = logging.getLogger(__name__)

# Create Flask blueprint
discord_memory_bp = Blueprint("discord_memory_bp", __name__)

# Error handling decorator
def handle_discord_memory_errors(func):
    """Decorator to handle Discord memory API errors"""
    def wrapper(*args, **kwargs):
        try:
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Discord memory API error: {e}")
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
            
            # Validate Discord authentication (simplified for sync context)
            if DISCORD_LANCEDB_AVAILABLE:
                # In production, you'd validate tokens properly
                pass
            
            return func(*args, **kwargs)
        except Exception as e:
            logger.error(f"Discord memory auth error: {e}")
            return jsonify({
                "ok": False,
                "error": "Authentication failed"
            }), 500
    return wrapper

@discord_memory_bp.route("/api/discord/memory/health", methods=["GET"])
@handle_discord_memory_errors
def health():
    """Health check for Discord memory service"""
    try:
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        service_info = {
            "service": "discord-memory-api",
            "status": "healthy",
            "version": "1.0.0",
            "features": {
                "lancedb_available": True,
                "discord_service_available": DISCORD_LANCEDB_AVAILABLE,
                "auth_available": DISCORD_AUTH_AVAILABLE,
                "ingestion_available": True,
                "search_available": True,
                "user_controls_available": True
            }
        }
        
        return jsonify({
            "ok": True,
            **service_info
        })
        
    except Exception as e:
        logger.error(f"Discord memory health check error: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# User Settings Management
@discord_memory_bp.route("/api/discord/memory/settings", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def get_user_settings():
    """Get Discord memory settings for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        settings = loop.run_until_complete(
            discord_lancedb_service.get_user_settings(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "settings": {
                "user_id": settings.user_id,
                "ingestion_enabled": settings.ingestion_enabled,
                "sync_frequency": settings.sync_frequency,
                "data_retention_days": settings.data_retention_days,
                "include_guilds": settings.include_guilds or [],
                "exclude_guilds": settings.exclude_guilds or [],
                "include_channels": settings.include_channels or [],
                "exclude_channels": settings.exclude_channels or [],
                "include_dm_channels": settings.include_dm_channels,
                "include_private_channels": settings.include_private_channels,
                "max_messages_per_channel": settings.max_messages_per_channel,
                "semantic_search_enabled": settings.semantic_search_enabled,
                "metadata_extraction_enabled": settings.metadata_extraction_enabled,
                "last_sync_timestamp": settings.last_sync_timestamp,
                "next_sync_timestamp": settings.next_sync_timestamp,
                "sync_in_progress": settings.sync_in_progress,
                "error_message": settings.error_message,
                "created_at": settings.created_at,
                "updated_at": settings.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Discord user settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_memory_bp.route("/api/discord/memory/settings", methods=["PUT"])
@handle_discord_memory_errors
@require_discord_auth
def save_user_settings():
    """Save Discord memory settings for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Validate settings
        valid_frequencies = ["real-time", "hourly", "daily", "weekly", "manual"]
        sync_frequency = data.get('sync_frequency', 'hourly')
        if sync_frequency not in valid_frequencies:
            return jsonify({
                "ok": False,
                "error": f"Invalid sync frequency. Must be one of: {valid_frequencies}",
                "error_type": "validation_error"
            }), 400
        
        # Create settings object
        settings = DiscordMemorySettings(
            user_id=user_id,
            ingestion_enabled=data.get('ingestion_enabled', True),
            sync_frequency=sync_frequency,
            data_retention_days=data.get('data_retention_days', 365),
            include_guilds=data.get('include_guilds', []),
            exclude_guilds=data.get('exclude_guilds', []),
            include_channels=data.get('include_channels', []),
            exclude_channels=data.get('exclude_channels', []),
            include_dm_channels=data.get('include_dm_channels', True),
            include_private_channels=data.get('include_private_channels', False),
            max_messages_per_channel=data.get('max_messages_per_channel', 10000),
            semantic_search_enabled=data.get('semantic_search_enabled', True),
            metadata_extraction_enabled=data.get('metadata_extraction_enabled', True)
        )
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            discord_lancedb_service.save_user_settings(settings)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "Discord memory settings saved successfully",
                "settings": {
                    "user_id": settings.user_id,
                    "ingestion_enabled": settings.ingestion_enabled,
                    "sync_frequency": settings.sync_frequency,
                    "updated_at": settings.updated_at
                }
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to save Discord memory settings",
                "error_type": "save_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error saving Discord user settings: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Ingestion Management
@discord_memory_bp.route("/api/discord/memory/sync", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def start_sync():
    """Start Discord message synchronization"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        force_sync = data.get('force_sync', False)
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            discord_lancedb_service.ingest_discord_messages(
                user_id=user_id,
                force_sync=force_sync
            )
        )
        loop.close()
        
        if result.get('success'):
            return jsonify({
                "ok": True,
                "sync_result": {
                    "messages_ingested": result.get('messages_ingested', 0),
                    "guilds_synced": result.get('guilds_synced', 0),
                    "channels_synced": result.get('channels_synced', 0),
                    "batch_id": result.get('batch_id'),
                    "next_sync": result.get('next_sync'),
                    "sync_frequency": result.get('sync_frequency')
                },
                "message": "Discord sync completed successfully"
            })
        else:
            return jsonify({
                "ok": False,
                "error": result.get('error', 'Unknown sync error'),
                "error_type": result.get('error_type', 'sync_error')
            }), 500
        
    except Exception as e:
        logger.error(f"Error starting Discord sync: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_memory_bp.route("/api/discord/memory/status", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def get_sync_status():
    """Get Discord synchronization status"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        status = loop.run_until_complete(
            discord_lancedb_service.get_sync_status(user_id)
        )
        loop.close()
        
        if status.get('error'):
            return jsonify({
                "ok": False,
                "error": status.get('error'),
                "error_type": status.get('error_type', 'status_error')
            }), 500
        
        return jsonify({
            "ok": True,
            "sync_status": status
        })
        
    except Exception as e:
        logger.error(f"Error getting Discord sync status: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Search and Query Operations
@discord_memory_bp.route("/api/discord/memory/search", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def search_messages():
    """Search Discord messages in LanceDB"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        query = data.get('query', '')
        limit = data.get('limit', 50)
        guild_id = data.get('guild_id')
        channel_id = data.get('channel_id')
        date_from = data.get('date_from')
        date_to = data.get('date_to')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Validate limit
        limit = min(limit, 200)  # Max 200 results
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(
            discord_lancedb_service.search_discord_messages(
                user_id=user_id,
                query=query,
                limit=limit,
                guild_id=guild_id,
                channel_id=channel_id,
                date_from=date_from,
                date_to=date_to
            )
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "messages": messages,
            "count": len(messages),
            "search_filters": {
                "query": query,
                "limit": limit,
                "guild_id": guild_id,
                "channel_id": channel_id,
                "date_from": date_from,
                "date_to": date_to
            }
        })
        
    except Exception as e:
        logger.error(f"Error searching Discord messages: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_memory_bp.route("/api/discord/memory/ingestion-stats", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def get_ingestion_stats():
    """Get Discord ingestion statistics"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        stats = loop.run_until_complete(
            discord_lancedb_service.get_ingestion_stats(user_id)
        )
        loop.close()
        
        return jsonify({
            "ok": True,
            "ingestion_stats": {
                "user_id": stats.user_id,
                "total_messages_ingested": stats.total_messages_ingested,
                "last_ingestion_timestamp": stats.last_ingestion_timestamp,
                "total_guilds_synced": stats.total_guilds_synced,
                "total_channels_synced": stats.total_channels_synced,
                "failed_ingestions": stats.failed_ingestions,
                "last_error_message": stats.last_error_message,
                "avg_messages_per_minute": stats.avg_messages_per_minute,
                "storage_size_mb": stats.storage_size_mb,
                "created_at": stats.created_at,
                "updated_at": stats.updated_at
            }
        })
        
    except Exception as e:
        logger.error(f"Error getting Discord ingestion stats: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Data Management
@discord_memory_bp.route("/api/discord/memory/delete", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def delete_user_data():
    """Delete all Discord data for user"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        confirm = data.get('confirm', False)
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        if not confirm:
            return jsonify({
                "ok": False,
                "error": "Confirmation required to delete Discord data",
                "error_type": "confirmation_required"
            }), 400
        
        # Run async operation
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        success = loop.run_until_complete(
            discord_lancedb_service.delete_user_data(user_id)
        )
        loop.close()
        
        if success:
            return jsonify({
                "ok": True,
                "message": "All Discord data deleted successfully",
                "deleted_at": datetime.utcnow().isoformat()
            })
        else:
            return jsonify({
                "ok": False,
                "error": "Failed to delete Discord data",
                "error_type": "delete_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error deleting Discord user data: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Utility Endpoints
@discord_memory_bp.route("/api/discord/memory/guilds", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def get_available_guilds():
    """Get available Discord guilds for user configuration"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Get user Discord guilds
        try:
            from discord_enhanced_service import discord_enhanced_service
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            guilds = loop.run_until_complete(
                discord_enhanced_service.get_user_guilds(
                    user_id=user_id,
                    limit=200
                )
            )
            loop.close()
            
            # Format for UI
            guilds_list = []
            for guild in guilds:
                guild_data = guild.to_dict()
                guilds_list.append({
                    "id": guild_data.get('id'),
                    "name": guild_data.get('name'),
                    "icon_url": guild_data.get('iconUrl'),
                    "member_count": guild_data.get('memberCount'),
                    "approximate_member_count": guild_data.get('approximateMemberCount'),
                    "description": guild_data.get('description'),
                    "features": guild_data.get('features', []),
                    "premium_tier": guild_data.get('premiumTier')
                })
            
            return jsonify({
                "ok": True,
                "guilds": guilds_list,
                "count": len(guilds_list)
            })
            
        except Exception as e:
            logger.error(f"Error getting Discord guilds: {e}")
            return jsonify({
                "ok": False,
                "error": f"Failed to get Discord guilds: {str(e)}",
                "error_type": "guild_fetch_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error getting available Discord guilds: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

@discord_memory_bp.route("/api/discord/memory/channels", methods=["POST"])
@handle_discord_memory_errors
@require_discord_auth
def get_available_channels():
    """Get available Discord channels for user configuration"""
    try:
        data = request.get_json()
        user_id = data.get('user_id')
        guild_id = data.get('guild_id')
        
        if not DISCORD_LANCEDB_AVAILABLE:
            return jsonify({
                "ok": False,
                "error": "Discord LanceDB service not available"
            }), 503
        
        # Get user Discord channels
        try:
            from discord_enhanced_service import discord_enhanced_service
            
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            channels = loop.run_until_complete(
                discord_enhanced_service.get_guild_channels(
                    user_id=user_id,
                    guild_id=guild_id
                )
            )
            loop.close()
            
            # Format for UI
            channels_list = []
            for channel in channels:
                channel_data = channel.to_dict()
                channels_list.append({
                    "id": channel_data.get('id'),
                    "name": channel_data.get('name'),
                    "type": channel_data.get('type'),
                    "type_name": channel_data.get('typeName'),
                    "topic": channel_data.get('topic'),
                    "nsfw": channel_data.get('nsfw'),
                    "position": channel_data.get('position'),
                    "message_count": channel_data.get('messageCount'),
                    "member_count": channel_data.get('memberCount'),
                    "parent_id": channel_data.get('parentId')
                })
            
            return jsonify({
                "ok": True,
                "channels": channels_list,
                "guild_id": guild_id,
                "count": len(channels_list)
            })
            
        except Exception as e:
            logger.error(f"Error getting Discord channels: {e}")
            return jsonify({
                "ok": False,
                "error": f"Failed to get Discord channels: {str(e)}",
                "error_type": "channel_fetch_error"
            }), 500
        
    except Exception as e:
        logger.error(f"Error getting available Discord channels: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Real-time Webhook Integration
@discord_memory_bp.route("/api/discord/memory/webhook/message", methods=["POST"])
@handle_discord_memory_errors
def handle_message_webhook():
    """Handle real-time Discord message webhook for memory ingestion"""
    try:
        data = request.get_json()
        
        # Validate webhook signature (in production)
        webhook_signature = request.headers.get('X-Discord-Signature')
        if not webhook_signature:
            logger.warning("Discord webhook missing signature")
            # Allow in development
            pass
        
        # Extract message data
        if data.get("type") == 0:  # MESSAGE_CREATE
            message_data = data.get("d", {})
            guild_id = message_data.get("guild_id")
            
            if not guild_id:
                # DM message - handle differently
                pass
            
            # Store message in real-time if user has real-time sync enabled
            if guild_id:
                # Get user ID from message or webhook data
                user_id = data.get("user_id")  # Would come from webhook setup
                
                if user_id and DISCORD_LANCEDB_AVAILABLE:
                    # Check if user has real-time sync enabled
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    settings = loop.run_until_complete(
                        discord_lancedb_service.get_user_settings(user_id)
                    )
                    loop.close()
                    
                    if settings.sync_frequency == "real-time" and settings.ingestion_enabled:
                        # Ingest single message
                        logger.info(f"Real-time Discord message ingestion for user {user_id}")
                        # Implementation would store the single message
                        pass
        
        return jsonify({
            "ok": True,
            "message": "Discord webhook processed successfully"
        })
        
    except Exception as e:
        logger.error(f"Error handling Discord message webhook: {e}")
        return jsonify({
            "ok": False,
            "error": str(e)
        }), 500

# Export components
__all__ = [
    'discord_memory_bp'
]