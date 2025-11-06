"""
ATOM Discord API Routes
Complete API with authentication, real-time features, and analytics integration
"""

import os
import json
import logging
import asyncio
import base64
import hashlib
import hmac
from datetime import datetime, timezone, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import enhanced services
try:
    from discord_enhanced_service import discord_enhanced_service
    from atom_discord_integration import atom_discord_integration
    from atom_ingestion_pipeline import atom_ingestion_pipeline
    from atom_memory_service import AtomMemoryService
    from atom_search_service import AtomSearchService
    from atom_workflow_service import atom_workflow_service
    from discord_analytics_engine import discord_analytics_engine
except ImportError as e:
    logger.warning(f"Discord integration services not available: {e}")
    discord_enhanced_service = None
    atom_discord_integration = None
    atom_ingestion_pipeline = None
    AtomMemoryService = None
    AtomSearchService = None
    atom_workflow_service = None
    discord_analytics_engine = None

# Create Discord API blueprint
discord_bp = Blueprint("discord_api", __name__, url_prefix="/api/integrations/discord")


# Configuration validation
def validate_discord_config():
    """Validate Discord configuration"""
    required_vars = [
        "DISCORD_CLIENT_ID",
        "DISCORD_CLIENT_SECRET",
        "DISCORD_REDIRECT_URI",
        "DISCORD_BOT_TOKEN",
        "ENCRYPTION_KEY",
    ]

    missing_vars = []
    for var in required_vars:
        if not os.getenv(var):
            missing_vars.append(var)

    if missing_vars:
        logger.error(f"Missing required environment variables: {missing_vars}")
        return False

    return True


# Utility functions
def create_discord_response(
    ok: bool,
    data: Any = None,
    error: str = None,
    message: str = None,
    metadata: Dict = None,
) -> Dict[str, Any]:
    """Create standardized Discord API response"""
    response = {
        "ok": ok,
        "timestamp": datetime.utcnow().isoformat(),
        "api_version": "4.0.0",
        "service": "Discord Integration",
    }

    if ok:
        if data is not None:
            response["data"] = data
        if message:
            response["message"] = message
        if metadata:
            response["metadata"] = metadata
    else:
        response["error"] = error or "Unknown error occurred"

    return response


def get_discord_request_data() -> Dict[str, Any]:
    """Get and validate Discord request data"""
    try:
        data = request.get_json() or {}
        user_id = data.get("user_id") or request.headers.get(
            "X-User-ID", "default-user"
        )
        data["user_id"] = user_id
        return data
    except Exception as e:
        logger.error(f"Error parsing Discord request data: {e}")
        return {}


def verify_discord_webhook(request_body: bytes, signature: str, secret: str) -> bool:
    """Verify Discord webhook signature"""
    try:
        if not signature or not secret:
            return False

        # Discord uses HMAC-SHA256 for webhook validation
        expected_signature = hmac.new(
            secret.encode("utf-8"), request_body, hashlib.sha256
        ).hexdigest()

        # Compare signatures securely
        return hmac.compare_digest(expected_signature, signature.replace("sha256=", ""))

    except Exception as e:
        logger.error(f"Error verifying Discord webhook: {e}")
        return False


# Health Check
@discord_bp.route("/enhanced_health", methods=["POST"])
def discord_enhanced_health_check():
    """Enhanced health check for all Discord services"""
    try:
        if not validate_discord_config():
            return create_discord_response(
                False, error="Configuration validation failed"
            )

        health_status = {
            "discord_enhanced_service": discord_enhanced_service is not None,
            "atom_discord_integration": atom_discord_integration is not None,
            "discord_analytics_engine": discord_analytics_engine is not None,
            "ingestion_pipeline": atom_ingestion_pipeline is not None,
            "memory_service": AtomMemoryService is not None,
            "search_service": AtomSearchService is not None,
            "workflow_service": atom_workflow_service is not None,
        }

        # Check service status
        all_healthy = all(health_status.values())

        # Get detailed status if services are available
        service_info = {}
        if discord_enhanced_service:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            service_info["discord_service"] = loop.run_until_complete(
                discord_enhanced_service.get_service_info()
            )
            loop.close()
        if atom_discord_integration:
            service_info["integration_service"] = {
                "initialized": atom_discord_integration.is_initialized,
                "active_guilds": len(atom_discord_integration.active_guilds),
                "unified_channels": len(
                    atom_discord_integration.communication_channels
                ),
            }

        return create_discord_response(
            all_healthy,
            data={
                "services": health_status,
                "service_info": service_info,
                "status": "healthy" if all_healthy else "degraded",
            },
            message="Enhanced Discord services operational"
            if all_healthy
            else "Some services unavailable",
        )

    except Exception as e:
        logger.error(f"Enhanced Discord health check error: {e}")
        return create_discord_response(False, error=str(e)), 500


# OAuth and Authentication
@discord_bp.route("/oauth_url", methods=["POST"])
def get_discord_oauth_url():
    """Generate OAuth authorization URL for Discord"""
    try:
        data = get_discord_request_data()
        user_id = data.get("user_id")

        if not discord_enhanced_service:
            return create_discord_response(
                False, error="Discord service not available"
            ), 503

        # Generate secure state token
        state_token = f"discord_auth_{user_id}_{int(datetime.utcnow().timestamp())}"

        # Generate OAuth URL
        oauth_url = discord_enhanced_service.generate_oauth_url(
            state=state_token, user_id=user_id
        )

        return create_discord_response(
            True,
            data={
                "oauth_url": oauth_url,
                "state": state_token,
                "scopes": discord_enhanced_service.required_scopes,
                "permissions": discord_enhanced_service.bot_permissions,
                "expires_in": 600,  # 10 minutes
            },
            message="Discord OAuth URL generated successfully",
        )

    except Exception as e:
        logger.error(f"Discord OAuth URL generation error: {e}")
        return create_discord_response(False, error=str(e)), 500


@discord_bp.route("/oauth_callback", methods=["POST"])
def handle_discord_oauth_callback():
    """Handle Discord OAuth callback"""
    try:
        data = get_discord_request_data()
        code = data.get("code")
        state = data.get("state")

        if not code or not state:
            return create_discord_response(
                False, error="Missing code or state parameter"
            )

        if not discord_enhanced_service:
            return create_discord_response(
                False, error="Discord service not available"
            ), 503

        # Exchange code for tokens
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            discord_enhanced_service.exchange_code_for_tokens(code, state)
        )
        loop.close()

        if result.get("ok"):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    "type": "discord_oauth_success",
                    "guild_ids": [
                        guild.get("guild_id") for guild in result.get("guilds", [])
                    ],
                    "user_id": data.get("user_id"),
                    "timestamp": datetime.utcnow().isoformat(),
                }
                if AtomMemoryService:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(AtomMemoryService.store(memory_data))
                    loop.close()

            return create_discord_response(
                True,
                data=result.get("guilds"),
                message=f"Connected to {len(result.get('guilds', []))} Discord servers successfully",
            )
        else:
            return create_discord_response(False, error=result.get("error")), 400

    except Exception as e:
        logger.error(f"Discord OAuth callback error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Enhanced Guild Management
@discord_bp.route("/guilds/enhanced", methods=["POST"])
def get_enhanced_discord_guilds():
    """Get Discord guilds with enhanced metadata"""
    try:
        data = get_discord_request_data()
        user_id = data.get("user_id")
        include_permissions = data.get("include_permissions", True)
        include_channels = data.get("include_channels", False)
        include_roles = data.get("include_roles", False)

        if not atom_discord_integration:
            return create_discord_response(
                False, error="Discord integration not available"
            ), 503

        # Get unified workspaces (Discord guilds become workspaces)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        workspaces = loop.run_until_complete(
            atom_discord_integration.get_unified_workspaces(user_id)
        )
        loop.close()

        # Test connections
        workspace_data = []
        for workspace in workspaces:
            # Test connection status
            guild_id = workspace["integration_data"]["guild_id"]
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            connection_test = loop.run_until_complete(
                discord_enhanced_service.test_connection(guild_id)
            )
            loop.close()

            workspace_info = {
                "id": workspace["id"],
                "name": workspace["name"],
                "platform": workspace["platform"],
                "type": workspace["type"],
                "status": connection_test.get("status", "unknown"),
                "member_count": workspace["member_count"],
                "channel_count": workspace["channel_count"],
                "icon_url": workspace["icon_url"],
                "description": workspace["description"],
                "connectionStatus": connection_test.get("connected", False),
                "capabilities": workspace["capabilities"],
                "integration_data": workspace["integration_data"],
            }

            # Add additional data if requested
            if include_permissions:
                workspace_info["permissions"] = workspace.get("permissions", 0)

            if include_channels:
                # Get channels for this guild
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                channels = loop.run_until_complete(
                    discord_enhanced_service.get_guild_channels(guild_id)
                )
                loop.close()
                workspace_info["channels"] = [
                    {
                        "id": channel["id"],
                        "name": channel["name"],
                        "type": channel["type"],
                        "position": channel["position"],
                    }
                    for channel in channels[:10]  # Limit for performance
                ]

            if include_roles:
                # Get roles for this guild
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                roles = loop.run_until_complete(
                    discord_enhanced_service.get_guild_roles(guild_id)
                )
                loop.close()
                workspace_info["roles"] = [
                    {
                        "id": role["id"],
                        "name": role["name"],
                        "color": role.get("color"),
                        "position": role["position"],
                    }
                    for role in roles[:10]  # Limit for performance
                ]

            workspace_data.append(workspace_info)

        return create_discord_response(
            True,
            data={
                "workspaces": workspace_data,
                "total_count": len(workspace_data),
                "connected_count": len(
                    [w for w in workspace_data if w["connectionStatus"] == True]
                ),
            },
            message="Enhanced Discord workspaces retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Enhanced Discord workspaces error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Enhanced Channel Management
@discord_bp.route("/channels/enhanced", methods=["POST"])
def get_enhanced_discord_channels():
    """Get Discord channels with enhanced metadata"""
    try:
        data = get_discord_request_data()
        workspace_id = data.get("workspace_id")
        user_id = data.get("user_id")
        include_voice_states = data.get("include_voice_states", True)
        include_permissions = data.get("include_permissions", True)
        include_stats = data.get("include_stats", True)

        if not workspace_id:
            return create_discord_response(False, error="workspace_id is required")

        if not atom_discord_integration:
            return create_discord_response(
                False, error="Discord integration not available"
            ), 503

        # Get channels (Discord channels become unified channels)
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        channels = loop.run_until_complete(
            atom_discord_integration.get_unified_channels(workspace_id, user_id)
        )
        loop.close()

        channel_data = []
        for channel in channels:
            channel_info = {
                "id": channel["id"],
                "name": channel["name"],
                "display_name": channel["display_name"],
                "description": channel["description"],
                "type": channel["type"],
                "platform": channel["platform"],
                "workspace_id": channel["workspace_id"],
                "workspace_name": channel["workspace_name"],
                "status": channel["status"],
                "member_count": channel["member_count"],
                "message_count": channel["message_count"],
                "unread_count": channel["unread_count"],
                "last_activity": channel["last_activity"],
                "is_private": channel["is_private"],
                "is_muted": channel["is_muted"],
                "is_favorite": channel["is_favorite"],
                "is_text": channel["is_text"],
                "is_voice": channel["is_voice"],
                "is_stage": channel["is_stage"],
                "is_news": channel["is_news"],
                "is_thread": channel["is_thread"],
                "position": channel["position"],
                "parent_id": channel["parent_id"],
                "permissions": channel["permissions"],
                "rate_limit": channel["rate_limit"],
                "capabilities": channel["capabilities"],
                "integration_data": channel["integration_data"],
            }

            # Add voice states if requested
            if include_voice_states and channel["is_voice"]:
                # Get voice states for this channel
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                voice_states = loop.run_until_complete(
                    discord_enhanced_service.get_channel_voice_states(
                        channel["integration_data"]["channel_id"]
                    )
                )
                loop.close()
                channel_info["voice_states"] = [
                    {
                        "user_id": state["user_id"],
                        "user_name": state["user_name"],
                        "deaf": state["deaf"],
                        "mute": state["mute"],
                        "self_deaf": state["self_deaf"],
                        "self_mute": state["self_mute"],
                        "self_video": state.get("self_video", False),
                        "self_stream": state.get("self_stream", False),
                    }
                    for state in voice_states
                ]

            # Add statistics if requested
            if include_stats:
                channel_info["stats"] = {
                    "messageCount": channel["message_count"],
                    "memberCount": channel["member_count"],
                    "voiceUsers": len(channel_info.get("voice_states", [])),
                    "lastActivity": channel["last_activity"],
                }

            channel_data.append(channel_info)

        return create_discord_response(
            True,
            data={
                "channels": channel_data,
                "total_count": len(channel_data),
                "workspace_id": workspace_id,
                "voice_channels": len([c for c in channel_data if c["is_voice"]]),
                "text_channels": len([c for c in channel_data if c["is_text"]]),
                "active_voice_channels": len(
                    [
                        c
                        for c in channel_data
                        if c["is_voice"] and len(c.get("voice_states", [])) > 0
                    ]
                ),
            },
            message="Enhanced Discord channels retrieved successfully",
        )
        loop.close()

    except Exception as e:
        logger.error(f"Enhanced Discord channels error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Enhanced Message Operations
@discord_bp.route("/messages/enhanced", methods=["POST"])
def get_enhanced_discord_messages():
    """Get Discord messages with enhanced metadata and analysis"""
    try:
        data = get_discord_request_data()
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        user_id = data.get("user_id")

        if not workspace_id or not channel_id:
            return create_discord_response(
                False, error="workspace_id and channel_id are required"
            )

        if not atom_discord_integration:
            return create_discord_response(
                False, error="Discord integration not available"
            ), 503

        # Get messages
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        messages = loop.run_until_complete(
            atom_discord_integration.get_unified_messages(
                workspace_id,
                channel_id,
                limit=data.get("limit", 100),
                options={
                    "before": data.get("before"),
                    "after": data.get("after"),
                    "around": data.get("around"),
                    "include_reactions": data.get("include_reactions", True),
                    "include_attachments": data.get("include_attachments", True),
                    "include_embeds": data.get("include_embeds", True),
                    "include_mentions": data.get("include_mentions", True),
                    "include_components": data.get("include_components", True),
                    "include_stickers": data.get("include_stickers", True),
                },
            )
        )
        loop.close()

        message_data = []
        for message in messages:
            message_info = {
                "id": message["id"],
                "content": message["content"],
                "html_content": message["html_content"],
                "userId": message["user_id"],
                "userName": message["user_name"],
                "userDisplayName": message["user_display_name"],
                "userDiscriminator": message["user_discriminator"],
                "userAvatar": message["user_avatar"],
                "channelId": message["channel_id"],
                "workspaceId": message["workspace_id"],
                "timestamp": message["timestamp"],
                "threadId": message["thread_id"],
                "replyToId": message["reply_to_id"],
                "messageType": message["message_type"],
                "isEdited": message["is_edited"],
                "editTimestamp": message["edit_timestamp"],
                "isPinned": message["is_pinned"],
                "isCrossposted": message["is_crossposted"],
                "isCommand": message["is_command"],
                "isBot": message["is_bot"],
                "isWebhook": message["is_webhook"],
                "isSystem": message["is_system"],
                "reactions": message["reactions"],
                "attachments": message["attachments"],
                "mentions": message["mentions"],
                "roleMentions": message.get("role_mentions", []),
                "channelMentions": message.get("channel_mentions", []),
                "mentionEveryone": message.get("mention_everyone", False),
                "embeds": message["embeds"],
                "components": message["components"],
                "stickers": message["stickers"],
                "tts": message.get("tts", False),
                "pinned": message.get("pinned", False),
                "integration_data": message["integration_data"],
                "metadata": message["metadata"],
            }
            message_data.append(message_info)

        return create_discord_response(
            True,
            data={
                "messages": message_data,
                "total_count": len(message_data),
                "channel_id": channel_id,
                "workspace_id": workspace_id,
                "has_more": len(message_data) == data.get("limit", 100),
                "bot_messages": len([m for m in message_data if m["is_bot"]]),
                "pinned_messages": len([m for m in message_data if m["is_pinned"]]),
                "message_types": list(set(m["messageType"] for m in message_data)),
            },
            message="Enhanced Discord messages retrieved successfully",
        )
        loop.close()

    except Exception as e:
        logger.error(f"Enhanced Discord messages error: {e}")
        return create_discord_response(False, error=str(e)), 500


@discord_bp.route("/messages/enhanced_send", methods=["POST"])
def send_enhanced_discord_message():
    """Send Discord message with enhanced features"""
    try:
        data = get_discord_request_data()
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        content = data.get("content")
        user_id = data.get("user_id")

        if not all([workspace_id, channel_id, content]):
            return create_discord_response(
                False, error="workspace_id, channel_id, and content are required"
            )

        if not atom_discord_integration:
            return create_discord_response(
                False, error="Discord integration not available"
            ), 503

        # Send message
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            atom_discord_integration.send_unified_message(
                workspace_id,
                channel_id,
                content,
                options={
                    "guild_id": data.get("guild_id"),
                    "embed": data.get("embed"),
                    "components": data.get("components", []),
                    "tts": data.get("tts", False),
                    "allowed_mentions": data.get("allowed_mentions"),
                    "message_reference": data.get("message_reference"),
                    "attachments": data.get("attachments"),
                },
            )
        )

        if result.get("ok"):
            # Store in memory service
            if AtomMemoryService:
                memory_data = {
                    "type": "sent_discord_message",
                    "workspace_id": workspace_id,
                    "channel_id": channel_id,
                    "message_id": result.get("message_id"),
                    "content": content,
                    "user_id": user_id,
                    "timestamp": datetime.utcnow().isoformat(),
                }
                if AtomMemoryService:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(AtomMemoryService.store(memory_data))
                    loop.close()

            return create_discord_response(
                True, data=result, message="Discord message sent successfully"
            )
        else:
            return create_discord_response(False, error=result.get("error")), 400

    except Exception as e:
        logger.error(f"Enhanced Discord send message error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Enhanced Search
@discord_bp.route("/search/enhanced", methods=["POST"])
def enhanced_discord_search():
    """Enhanced Discord search with analytics and insights"""
    try:
        data = get_discord_request_data()
        query = data.get("query")
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        user_id = data.get("user_id")

        if not query:
            return create_discord_response(False, error="query is required")

        if not atom_discord_integration:
            return create_discord_response(
                False, error="Discord integration not available"
            ), 503

        # Perform search
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        search_results = loop.run_until_complete(
            atom_discord_integration.unified_search(
                query,
                workspace_id,
                options={
                    "channel_id": channel_id,
                    "user_id": user_id,
                    "limit": data.get("limit", 50),
                    "include_highlights": data.get("include_highlights", True),
                    "include_relevance": data.get("include_relevance", True),
                    "search_type": data.get("search_type", "content"),
                    "min_id": data.get("min_id"),
                    "max_id": data.get("max_id"),
                    "has_attachment": data.get("has_attachment"),
                    "has_embed": data.get("has_embed"),
                    "is_bot": data.get("is_bot"),
                },
            )
        )
        loop.close()

        # Store search in memory
        if AtomMemoryService:
            memory_data = {
                "type": "discord_search",
                "query": query,
                "workspace_id": workspace_id,
                "channel_id": channel_id,
                "user_id": user_id,
                "results_count": len(search_results),
                "timestamp": datetime.utcnow().isoformat(),
            }
            if AtomMemoryService:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(AtomMemoryService.store(memory_data))
                loop.close()

        # Index for search service
        if AtomSearchService:
            for result in search_results:
                search_data = {
                    "type": "discord_message",
                    "id": result["id"],
                    "title": result["title"],
                    "content": result["content"],
                    "metadata": {
                        "workspace_id": result["workspace_id"],
                        "channel_id": result["channel_id"],
                        "user_id": result["user_id"],
                        "user_name": result["user_name"],
                        "timestamp": result["timestamp"],
                        "platform": result["platform"],
                        "relevance_score": result["relevance_score"],
                        "message_type": result.get("message_type"),
                        "is_bot": result.get("is_bot", False),
                        "has_attachments": result.get("has_attachments", False),
                        "has_embeds": result.get("has_embeds", False),
                    },
                }
                if AtomSearchService:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(AtomSearchService.index(search_data))
                    loop.close()

        return create_discord_response(
            True,
            data={
                "query": query,
                "results": search_results,
                "total": len(search_results),
                "search_time": datetime.utcnow().isoformat(),
                "insights": {
                    "top_channels": len(
                        set(result.get("channel_id") for result in search_results)
                    ),
                    "top_users": len(
                        set(result.get("user_id") for result in search_results)
                    ),
                    "bot_messages": len(
                        [r for r in search_results if r.get("is_bot", False)]
                    ),
                    "avg_relevance": sum(
                        r.get("relevance_score", 0) for r in search_results
                    )
                    / len(search_results)
                    if search_results
                    else 0,
                    "attachment_count": len(
                        [r for r in search_results if r.get("has_attachments", False)]
                    ),
                    "embed_count": len(
                        [r for r in search_results if r.get("has_embeds", False)]
                    ),
                },
            },
            message="Enhanced Discord search completed successfully",
        )

    except Exception as e:
        logger.error(f"Enhanced Discord search error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Voice Chat Operations
@discord_bp.route("/voice/states", methods=["POST"])
def get_discord_voice_states():
    """Get voice states for Discord guild"""
    try:
        data = get_discord_request_data()
        workspace_id = data.get("workspace_id")
        guild_id = data.get("guild_id")
        channel_id = data.get("channel_id")

        if not guild_id:
            if workspace_id.startswith("discord_"):
                guild_id = workspace_id[8:]  # Remove 'discord_' prefix
            else:
                return create_discord_response(
                    False, error="guild_id or discord workspace_id is required"
                )

        if not discord_enhanced_service:
            return create_discord_response(
                False, error="Discord service not available"
            ), 503

        # Get voice states
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voice_states = loop.run_until_complete(
            discord_enhanced_service.get_guild_voice_states(guild_id, channel_id)
        )
        loop.close()

        # Process voice states
        processed_states = []
        for state in voice_states:
            processed_state = {
                "userId": state["user_id"],
                "userName": state["user_name"],
                "userAvatar": state.get("user_avatar"),
                "channelId": state["channel_id"],
                "guildId": state["guild_id"],
                "sessionId": state["session_id"],
                "deaf": state["deaf"],
                "mute": state["mute"],
                "selfDeaf": state["self_deaf"],
                "selfMute": state["self_mute"],
                "selfVideo": state.get("self_video", False),
                "selfStream": state.get("self_stream", False),
                "suppress": state.get("suppress", False),
                "requestToSpeakTimestamp": state.get("request_to_speak_timestamp"),
            }
            processed_states.append(processed_state)

        return create_discord_response(
            True,
            data={
                "voice_states": processed_states,
                "total_users": len(processed_states),
                "guild_id": guild_id,
                "channel_id": channel_id,
                "muted_users": len(
                    [s for s in processed_states if s["mute"] or s["selfMute"]]
                ),
                "deafened_users": len(
                    [s for s in processed_states if s["deaf"] or s["selfDeaf"]]
                ),
                "video_users": len([s for s in processed_states if s["selfVideo"]]),
                "streaming_users": len(
                    [s for s in processed_states if s["selfStream"]]
                ),
            },
            message="Discord voice states retrieved successfully",
        )
        loop.close()

    except Exception as e:
        logger.error(f"Discord voice states error: {e}")
        return create_discord_response(False, error=str(e)), 500


@discord_bp.route("/voice/move", methods=["POST"])
def move_discord_voice_user():
    """Move user to different voice channel"""
    try:
        data = get_discord_request_data()
        guild_id = data.get("guild_id")
        user_id = data.get("user_id")
        channel_id = data.get("channel_id")
        current_user_id = data.get("user_id")  # User making the request

        if not all([guild_id, user_id, channel_id]):
            return create_discord_response(
                False, error="guild_id, user_id, and channel_id are required"
            )

        if not discord_enhanced_service:
            return create_discord_response(
                False, error="Discord service not available"
            ), 503

        # Check permissions
        if current_user_id:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            has_permission = loop.run_until_complete(
                discord_enhanced_service.check_voice_permission(
                    guild_id, current_user_id, DiscordPermission.MOVE_MEMBERS.value
                )
            )
            loop.close()
            if not has_permission:
                return create_discord_response(
                    False, error="Insufficient permissions"
                ), 403

        # Move user
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            discord_enhanced_service.move_voice_user(guild_id, user_id, channel_id)
        )
        loop.close()

        return create_discord_response(
            True, data=result, message="User moved to voice channel successfully"
        )

    except Exception as e:
        logger.error(f"Discord voice move error: {e}")
        return create_discord_response(False, error=str(e)), 500


# File Operations
@discord_bp.route("/files/enhanced_upload", methods=["POST"])
def enhanced_discord_file_upload():
    """Enhanced Discord file upload with analysis"""
    try:
        data = get_discord_request_data()
        workspace_id = data.get("workspace_id")
        channel_id = data.get("channel_id")
        file_data = data.get("file_data")  # Base64 encoded file
        file_name = data.get("file_name")
        file_type = data.get("file_type")
        description = data.get("description")
        user_id = data.get("user_id")

        if not all([workspace_id, channel_id, file_data, file_name]):
            return create_discord_response(
                False,
                error="workspace_id, channel_id, file_data, and file_name are required",
            )

        if not discord_enhanced_service:
            return create_discord_response(
                False, error="Discord service not available"
            ), 503

        # Decode and upload file
        file_bytes = base64.b64decode(file_data)

        # Upload file
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        file_info = loop.run_until_complete(
            discord_enhanced_service.upload_file(
                guild_id=workspace_id[8:]
                if workspace_id.startswith("discord_")
                else workspace_id,
                channel_id=channel_id[8:]
                if channel_id.startswith("discord_")
                else channel_id,
                file_bytes=file_bytes,
                file_name=file_name,
                content_type=file_type,
                description=description,
            )
        )

        if file_info:
            # Index file for search
            if AtomSearchService:
                search_data = {
                    "type": "discord_file",
                    "id": file_info["file_id"],
                    "title": file_info["file_name"],
                    "content": description or "",
                    "metadata": {
                        "mime_type": file_type,
                        "size": file_info["size"],
                        "file_type": file_info["file_type"],
                        "workspace_id": workspace_id,
                        "channel_id": channel_id,
                        "user_id": user_id,
                        "timestamp": file_info["timestamp"],
                        "platform": "Discord",
                        "is_image": file_info["is_image"],
                        "is_video": file_info["is_video"],
                        "is_audio": file_info["is_audio"],
                    },
                }
                if AtomSearchService:
                    loop = asyncio.new_event_loop()
                    asyncio.set_event_loop(loop)
                    loop.run_until_complete(AtomSearchService.index(search_data))
                    loop.close()

            return create_discord_response(
                True,
                data={"file": file_info, "uploaded": True},
                message="Discord file uploaded successfully",
            )
        else:
            return create_discord_response(False, error="File upload failed"), 500

    except Exception as e:
        logger.error(f"Enhanced Discord file upload error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Analytics and Reporting
@discord_bp.route("/analytics/metrics", methods=["POST"])
def get_discord_analytics_metrics():
    """Get Discord analytics metrics"""
    try:
        data = get_discord_request_data()
        metric_name = data.get("metric")
        time_range_name = data.get("time_range", "last_7_days")
        granularity_name = data.get("granularity", "day")
        workspace_id = data.get("workspace_id")
        guild_ids = data.get("guild_ids", [])
        channel_ids = data.get("channel_ids", [])
        user_ids = data.get("user_ids", [])

        if not metric_name:
            return create_discord_response(False, error="metric is required")

        if not atom_discord_integration:
            return create_discord_response(
                False, error="Discord integration not available"
            ), 503

        # Get analytics data
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        analytics_data = loop.run_until_complete(
            atom_discord_integration.get_unified_analytics(
                metric_name,
                time_range_name,
                workspace_id,
                options={
                    "granularity": granularity_name,
                    "filters": data.get("filters", {}),
                    "guild_ids": guild_ids,
                    "channel_ids": channel_ids,
                    "user_ids": user_ids,
                },
            )
        )
        loop.close()

        return create_discord_response(
            True,
            data=analytics_data,
            message="Discord analytics data retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Discord analytics metrics error: {e}")
        return create_discord_response(False, error=str(e)), 500


@discord_bp.route("/analytics/top_guilds", methods=["POST"])
def get_discord_top_guilds():
    """Get top Discord guilds by metric"""
    try:
        data = get_discord_request_data()
        metric_name = data.get("metric")
        time_range_name = data.get("time_range", "last_7_days")
        limit = data.get("limit", 10)
        workspace_id = data.get("workspace_id")

        if not metric_name:
            return create_discord_response(False, error="metric is required")

        if not discord_analytics_engine:
            return create_discord_response(
                False, error="Discord analytics not available"
            ), 503

        # Get top guilds
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        top_guilds = loop.run_until_complete(
            discord_analytics_engine.get_top_guilds(
                metric=metric_name,
                time_range=time_range_name,
                limit=limit,
                filters=data.get("filters", {}),
                workspace_id=workspace_id[8:]
                if workspace_id and workspace_id.startswith("discord_")
                else None,
            )
        )
        loop.close()

        return create_discord_response(
            True,
            data={
                "metric": metric_name,
                "time_range": time_range_name,
                "guilds": top_guilds,
                "total_guilds": len(top_guilds),
            },
            message="Discord top guilds retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Discord top guilds error: {e}")
        return create_discord_response(False, error=str(e)), 500


@discord_bp.route("/analytics/voice_chat", methods=["POST"])
def get_discord_voice_chat_analytics():
    """Get voice chat analytics for Discord guild"""
    try:
        data = get_discord_request_data()
        workspace_id = data.get("workspace_id")
        guild_id = data.get("guild_id")
        time_range_name = data.get("time_range", "last_7_days")

        if not guild_id:
            if workspace_id.startswith("discord_"):
                guild_id = workspace_id[8:]  # Remove 'discord_' prefix
            else:
                return create_discord_response(
                    False, error="guild_id or discord workspace_id is required"
                )

        if not discord_analytics_engine:
            return create_discord_response(
                False, error="Discord analytics not available"
            ), 503

        # Get voice chat analytics
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        voice_analytics = loop.run_until_complete(
            discord_analytics_engine.get_voice_chat_analytics(
                guild_id=guild_id, time_range=time_range_name
            )
        )
        loop.close()

        return create_discord_response(
            True,
            data=voice_analytics,
            message="Discord voice chat analytics retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Discord voice chat analytics error: {e}")
        return create_discord_response(False, error=str(e)), 500


@discord_bp.route("/analytics/user_activity", methods=["POST"])
def get_discord_user_activity():
    """Get user activity analytics for Discord"""
    try:
        data = get_discord_request_data()
        user_id = data.get("user_id")
        time_range_name = data.get("time_range", "last_7_days")
        workspace_id = data.get("workspace_id")

        if not user_id:
            return create_discord_response(False, error="user_id is required")

        if not discord_analytics_engine:
            return create_discord_response(
                False, error="Discord analytics not available"
            ), 503

        # Get user activity
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        user_activity = loop.run_until_complete(
            discord_analytics_engine.get_user_activity_summary(
                user_id=user_id, time_range=time_range_name
            )
        )
        loop.close()

        return create_discord_response(
            True,
            data=user_activity,
            message="Discord user activity retrieved successfully",
        )

    except Exception as e:
        logger.error(f"Discord user activity error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Workflow Automation
@discord_bp.route("/workflows", methods=["GET", "POST"])
def manage_discord_workflows():
    """Get or create Discord workflows"""
    try:
        data = get_discord_request_data()
        user_id = data.get("user_id")

        if request.method == "GET":
            # Get workflows
            workspace_id = data.get("workspace_id")

            if not atom_discord_integration:
                return create_discord_response(
                    False, error="Discord integration not available"
                ), 503

            # Return mock workflows
            workflows = [
                {
                    "id": "discord_workflow_1",
                    "name": "Auto-react to messages",
                    "description": "Automatically add reactions to new messages in gaming channels",
                    "platform": "discord",
                    "triggers": [
                        {"event": "message_create", "channel_id": "gaming_channel_id"}
                    ],
                    "actions": [
                        {"action": "add_reaction", "emoji": "👍"},
                        {"action": "add_reaction", "emoji": "🎮"},
                    ],
                    "enabled": True,
                    "created_at": "2023-12-04T10:00:00Z",
                },
                {
                    "id": "discord_workflow_2",
                    "name": "Welcome new members",
                    "description": "Send welcome message to new members who join",
                    "platform": "discord",
                    "triggers": [{"event": "guild_member_add", "guild_id": "guild_id"}],
                    "actions": [
                        {
                            "action": "send_message",
                            "channel_id": "welcome_channel_id",
                            "content": "Welcome to the server! 🎉",
                        }
                    ],
                    "enabled": True,
                    "created_at": "2023-12-04T10:00:00Z",
                },
            ]

            return create_discord_response(
                True,
                data={"workflows": workflows, "total_count": len(workflows)},
                message="Discord workflows retrieved successfully",
            )

        elif request.method == "POST":
            # Create workflow
            workflow_data = data.get("workflow", {})

            if not atom_discord_integration:
                return create_discord_response(
                    False, error="Discord integration not available"
                ), 503

            # Create workflow
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            result = loop.run_until_complete(
                atom_discord_integration.create_unified_workflow(workflow_data)
            )
            loop.close()

            if result.get("ok"):
                return create_discord_response(
                    True, data=result, message="Discord workflow created successfully"
                )
            else:
                return create_discord_response(False, error=result.get("error")), 500

    except Exception as e:
        logger.error(f"Discord workflow management error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Enhanced Webhook Handler
@discord_bp.route("/enhanced_events", methods=["POST"])
def enhanced_discord_webhook_handler():
    """Enhanced Discord webhook event handler"""
    try:
        # Get request data
        body = request.get_data()
        headers = request.headers

        # Verify signature (if provided)
        signature = headers.get("X-Signature-Ed25519")
        signing_secret = os.getenv("DISCORD_SIGNING_SECRET")

        if signing_secret and not verify_discord_webhook(
            body, signature, signing_secret
        ):
            return create_discord_response(False, error="Invalid signature"), 401

        # Parse event data
        event_data = json.loads(body.decode("utf-8"))

        if not discord_enhanced_service:
            return create_discord_response(
                False, error="Discord service not available"
            ), 503

        # Process event
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            discord_enhanced_service.handle_webhook_event(event_data)
        )
        loop.close()

        # Store event for analytics
        if AtomMemoryService:
            memory_data = {
                "type": "discord_webhook_event",
                "event_type": event_data.get("t", "unknown"),
                "event_data": event_data.get("d", {}),
                "sequence": event_data.get("s"),
                "timestamp": datetime.utcnow().isoformat(),
            }
            if AtomMemoryService:
                loop = asyncio.new_event_loop()
                asyncio.set_event_loop(loop)
                loop.run_until_complete(AtomMemoryService.store(memory_data))
                loop.close()

        return create_discord_response(
            result.get("ok", True),
            message="Discord webhook event processed successfully",
        )

    except Exception as e:
        logger.error(f"Enhanced Discord webhook error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Data Ingestion
@discord_bp.route("/ingestion/start", methods=["POST"])
def start_discord_data_ingestion():
    """Start enhanced Discord data ingestion"""
    try:
        data = get_discord_request_data()
        user_id = data.get("user_id")
        workspace_id = data.get("workspace_id")
        guild_ids = data.get("guild_ids", [])
        config = data.get("config", {})

        if not atom_ingestion_pipeline:
            return create_discord_response(
                False, error="Ingestion pipeline not available"
            ), 503

        # Start ingestion
        ingestion_config = {
            "sourceType": "discord_enhanced",
            "workspace_id": workspace_id,
            "guild_ids": guild_ids,
            "config": {
                "syncOptions": {
                    "messageTypes": config.get(
                        "message_types", ["messages", "replies", "files", "embeds"]
                    ),
                    "realTimeSync": config.get("real_time_sync", True),
                    "syncFrequency": config.get("sync_frequency", "realtime"),
                    "includeVoiceStates": config.get("include_voice_states", True),
                    "includeReactions": config.get("include_reactions", True),
                    "includeThreadSync": config.get("include_thread_sync", True),
                    "includePresence": config.get("include_presence", True),
                },
                "filters": config.get("filters", {}),
                "processing": {
                    "indexForSearch": config.get("index_for_search", True),
                    "analyzeSentiment": config.get("analyze_sentiment", False),
                    "extractTopics": config.get("extract_topics", True),
                    "processVoiceData": config.get("process_voice_data", True),
                    "trackUserActivity": config.get("track_user_activity", True),
                },
            },
        }

        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        result = loop.run_until_complete(
            atom_ingestion_pipeline.startIngestion(
                ingestion_config, callback=data.get("callback")
            )
        )
        loop.close()

        return create_discord_response(
            True, data=result, message="Discord data ingestion started successfully"
        )

    except Exception as e:
        logger.error(f"Discord data ingestion start error: {e}")
        return create_discord_response(False, error=str(e)), 500


# Error handlers
@discord_bp.errorhandler(404)
def discord_not_found(error):
    return create_discord_response(False, error="Endpoint not found"), 404


@discord_bp.errorhandler(500)
def discord_internal_error(error):
    logger.error(f"Discord internal server error: {error}")
    return create_discord_response(False, error="Internal server error"), 500


# Register blueprint
def register_discord_api(app):
    """Register Discord API blueprint"""
    app.register_blueprint(discord_bp)
    logger.info("Discord API blueprint registered")


# Service initialization
def initialize_discord_services():
    """Initialize Discord services"""
    try:
        # Validate configuration
        if not validate_discord_config():
            return False

        # Initialize services
        if discord_enhanced_service:
            logger.info("Discord Enhanced service initialized")

        if atom_discord_integration:
            logger.info("Discord integration service initialized")

        if discord_analytics_engine:
            logger.info("Discord analytics engine initialized")

        return True

    except Exception as e:
        logger.error(f"Error initializing Discord services: {e}")
        return False


# Export for external use
__all__ = [
    "discord_bp",
    "register_discord_api",
    "initialize_discord_services",
    "create_discord_response",
    "get_discord_request_data",
]
