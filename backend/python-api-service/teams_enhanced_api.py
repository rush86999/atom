"""
ATOM Enhanced Microsoft Teams API Handler
Complete Teams integration with comprehensive API operations
"""

import os
import logging
import asyncio
import httpx
import json
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from flask import Blueprint, request, jsonify, current_app
from loguru import logger

# Import Teams service
try:
    from teams_service_real import teams_service

    TEAMS_SERVICE_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Teams service not available: {e}")
    TEAMS_SERVICE_AVAILABLE = False
    teams_service = None

# Import database handler
try:
    from db_oauth_teams import get_user_teams_tokens

    TEAMS_DB_AVAILABLE = True
except ImportError as e:
    logger.warning(f"Teams database handler not available: {e}")
    TEAMS_DB_AVAILABLE = False

teams_enhanced_bp = Blueprint("teams_enhanced_bp", __name__)

# Configuration
TEAMS_API_BASE_URL = "https://graph.microsoft.com/v1.0"
REQUEST_TIMEOUT = 30
RATE_LIMIT_HEADERS = ["X-RateLimit-Limit", "X-RateLimit-Remaining", "X-RateLimit-Reset"]


async def get_user_tokens(user_id: str) -> Optional[Dict[str, Any]]:
    """Get Teams tokens for user"""
    if not TEAMS_DB_AVAILABLE:
        # Mock implementation for testing
        return {
            "access_token": os.getenv("TEAMS_ACCESS_TOKEN"),
            "token_type": "Bearer",
            "scope": "Channel.ReadBasic.All,Team.ReadBasic.All,Chat.Read,User.Read.All",
            "expires_at": (datetime.utcnow() + timedelta(hours=1)).isoformat(),
        }

    try:
        tokens = await get_user_teams_tokens(user_id)
        return tokens
    except Exception as e:
        logger.error(f"Error getting Teams tokens for user {user_id}: {e}")
        return None


def create_teams_client(access_token: str) -> httpx.AsyncClient:
    """Create Teams API client"""
    headers = {
        "Authorization": f"Bearer {access_token}",
        "Accept": "application/json",
        "User-Agent": "ATOM-Platform/1.0",
    }

    return httpx.AsyncClient(
        base_url=TEAMS_API_BASE_URL, headers=headers, timeout=REQUEST_TIMEOUT
    )


def format_teams_response(data: Any, endpoint: str) -> Dict[str, Any]:
    """Format Teams API response"""
    return {
        "ok": True,
        "data": data,
        "endpoint": endpoint,
        "timestamp": datetime.utcnow().isoformat(),
        "source": "teams_graph_api",
    }


def format_error_response(error: Exception, endpoint: str) -> Dict[str, Any]:
    """Format error response"""
    return {
        "ok": False,
        "error": {
            "code": type(error).__name__,
            "message": str(error),
            "endpoint": endpoint,
        },
        "timestamp": datetime.utcnow().isoformat(),
        "source": "teams_graph_api",
    }


@teams_enhanced_bp.route("/api/integrations/teams/teams", methods=["POST"])
async def list_teams():
    """List user Teams with filtering"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        include_private = data.get("include_private", False)
        limit = data.get("limit", 100)

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Teams tokens not found"}}
            ), 401

        # Create Teams client
        async with create_teams_client(tokens["access_token"]) as client:
            all_teams = []

            # Get joined teams
            url = "/me/joinedTeams"
            response = await client.get(url)

            if response.status_code == 200:
                teams_data = response.json()

                # Get detailed team information
                for team in teams_data.get("value", []):
                    # Get team details
                    team_url = f"/teams/{team['id']}"
                    team_response = await client.get(team_url)

                    if team_response.status_code == 200:
                        team_details = team_response.json()

                        # Get team members count
                        members_url = f"/teams/{team['id']}/members"
                        members_response = await client.get(members_url)
                        members_count = 0

                        if members_response.status_code == 200:
                            members_data = members_response.json()
                            members_count = len(members_data.get("value", []))

                        # Get team channels count
                        channels_url = f"/teams/{team['id']}/channels"
                        channels_response = await client.get(channels_url)
                        channels_count = 0

                        if channels_response.status_code == 200:
                            channels_data = channels_response.json()
                            channels_count = len(channels_data.get("value", []))

                        team_info = {
                            "id": team["id"],
                            "displayName": team_details.get(
                                "displayName", team["displayName"]
                            ),
                            "description": team_details.get("description"),
                            "visibility": team_details.get("visibility", "public"),
                            "specialization": team_details.get(
                                "specialization", "none"
                            ),
                            "webUrl": team_details.get("webUrl", team.get("webUrl")),
                            "tenantId": team.get("tenantId"),
                            "membersCount": members_count,
                            "channelsCount": channels_count,
                            "createdDateTime": team_details.get("createdDateTime"),
                            "classification": team_details.get("classification"),
                            "isArchived": team_details.get("isArchived", False),
                        }

                        all_teams.append(team_info)

                # Filter and limit
                if not include_private:
                    all_teams = [
                        t for t in all_teams if t.get("visibility") == "public"
                    ]

                if limit:
                    all_teams = all_teams[:limit]

            return jsonify(
                format_teams_response(
                    {
                        "teams": all_teams,
                        "total_count": len(all_teams),
                        "filters_applied": {"include_private": include_private},
                    },
                    "list_teams",
                )
            )

    except Exception as e:
        logger.error(f"Error listing teams: {e}")
        return jsonify(format_error_response(e, "list_teams")), 500


@teams_enhanced_bp.route("/api/integrations/teams/channels", methods=["POST"])
async def list_channels():
    """List channels from a team"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        team_id = data.get("team_id")
        include_private = data.get("include_private", False)
        limit = data.get("limit", 100)

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        if not team_id:
            return jsonify(
                {"ok": False, "error": {"message": "team_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Teams tokens not found"}}
            ), 401

        # Create Teams client
        async with create_teams_client(tokens["access_token"]) as client:
            url = f"/teams/{team_id}/channels"
            response = await client.get(url)

            if response.status_code == 200:
                channels_data = response.json()

                channels = []
                for channel in channels_data.get("value", []):
                    # Skip private channels unless requested
                    if (
                        channel.get("membershipType") == "private"
                        and not include_private
                    ):
                        continue

                    # Get channel members count
                    members_url = f"/teams/{team_id}/channels/{channel['id']}/members"
                    members_response = await client.get(members_url)
                    members_count = 0

                    if members_response.status_code == 200:
                        members_data = members_response.json()
                        members_count = len(members_data.get("value", []))

                    channel_info = {
                        "id": channel["id"],
                        "displayName": channel.get("displayName"),
                        "description": channel.get("description"),
                        "membershipType": channel.get("membershipType", "standard"),
                        "teamId": team_id,
                        "teamName": channel.get("teamName"),
                        "webUrl": channel.get("webUrl"),
                        "tenantId": channel.get("tenantId"),
                        "membersCount": members_count,
                        "createdDateTime": channel.get("createdDateTime"),
                        "isFavoriteByDefault": channel.get(
                            "isFavoriteByDefault", False
                        ),
                        "email": channel.get("email"),
                        "moderationSettings": channel.get("moderationSettings"),
                    }

                    channels.append(channel_info)

                # Apply limit
                if limit:
                    channels = channels[:limit]

                return jsonify(
                    format_teams_response(
                        {
                            "channels": channels,
                            "total_count": len(channels),
                            "team_id": team_id,
                            "filters_applied": {"include_private": include_private},
                        },
                        "list_channels",
                    )
                )
            else:
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "message": f"Teams API error: {response.status_code}"
                        },
                    }
                ), response.status_code

    except Exception as e:
        logger.error(f"Error listing channels: {e}")
        return jsonify(format_error_response(e, "list_channels")), 500


@teams_enhanced_bp.route("/api/integrations/teams/messages", methods=["POST"])
async def list_messages():
    """List messages from channels"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        team_id = data.get("team_id")
        channel_id = data.get("channel_id")
        filters = data.get("filters", {})
        limit = data.get("limit", 100)

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        if not channel_id and not team_id:
            return jsonify(
                {"ok": False, "error": {"message": "channel_id or team_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Teams tokens not found"}}
            ), 401

        # Create Teams client
        async with create_teams_client(tokens["access_token"]) as client:
            all_messages = []

            # If team_id is provided, get all channels first
            if team_id and not channel_id:
                channels_response = await client.get(f"/teams/{team_id}/channels")
                if channels_response.status_code == 200:
                    channels_data = channels_response.json()
                    channel_ids = [ch["id"] for ch in channels_data.get("value", [])]
                else:
                    channel_ids = []
            else:
                channel_ids = [channel_id]

            # Get messages from each channel
            for ch_id in channel_ids:
                url = f"/teams/{team_id}/channels/{ch_id}/messages"

                # Add filters to query
                params = {
                    "$top": min(limit // len(channel_ids) if channel_ids else limit, 50)
                }

                if filters.get("from") == "me":
                    params["$filter"] = f"from/user/id eq '{user_id}'"

                response = await client.get(url, params=params)

                if response.status_code == 200:
                    messages_data = response.json()

                    for message in messages_data.get("value", []):
                        # Skip system messages
                        if message.get("messageType") == "systemEventMessage":
                            continue

                        message_info = {
                            "id": message["id"],
                            "messageType": message.get("messageType"),
                            "createdDateTime": message.get("createdDateTime"),
                            "lastModifiedDateTime": message.get("lastModifiedDateTime"),
                            "subject": message.get("subject"),
                            "summary": message.get("summary"),
                            "importance": message.get("importance", "normal"),
                            "locale": message.get("locale"),
                            "webUrl": message.get("webUrl"),
                            "policyHint": message.get("policyHint"),
                            "fromMe": message.get("from", {}).get("user", {}).get("id")
                            == user_id,
                            "channelId": ch_id,
                            "teamId": team_id,
                            "author": {
                                "id": message.get("from", {}).get("user", {}).get("id"),
                                "displayName": message.get("from", {})
                                .get("user", {})
                                .get("displayName"),
                                "email": message.get("from", {})
                                .get("user", {})
                                .get("email"),
                            },
                            "body": {
                                "content": message.get("body", {}).get("content"),
                                "contentType": message.get("body", {}).get(
                                    "contentType", "text"
                                ),
                            },
                            "attachments": message.get("attachments", []),
                            "mentions": message.get("mentions", []),
                            "reactions": message.get("reactions", []),
                            "replyToId": message.get("replyToId"),
                            "etag": message.get("etag"),
                        }

                        all_messages.append(message_info)

            # Sort and limit
            all_messages.sort(key=lambda x: x["createdDateTime"], reverse=True)
            if limit:
                all_messages = all_messages[:limit]

            return jsonify(
                format_teams_response(
                    {
                        "messages": all_messages,
                        "total_count": len(all_messages),
                        "filters_applied": filters,
                    },
                    "list_messages",
                )
            )

    except Exception as e:
        logger.error(f"Error listing messages: {e}")
        return jsonify(format_error_response(e, "list_messages")), 500


@teams_enhanced_bp.route("/api/integrations/teams/user/profile", methods=["POST"])
async def get_user_profile():
    """Get authenticated user profile"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Teams tokens not found"}}
            ), 401

        # Create Teams client
        async with create_teams_client(tokens["access_token"]) as client:
            response = await client.get("/me")

            if response.status_code == 200:
                user_data = response.json()

                profile = {
                    "id": user_data["id"],
                    "displayName": user_data.get("displayName"),
                    "mail": user_data.get("mail"),
                    "userPrincipalName": user_data.get("userPrincipalName"),
                    "jobTitle": user_data.get("jobTitle"),
                    "department": user_data.get("department"),
                    "officeLocation": user_data.get("officeLocation"),
                    "businessPhones": user_data.get("businessPhones", []),
                    "mobilePhone": user_data.get("mobilePhone"),
                    "preferredLanguage": user_data.get("preferredLanguage"),
                    "surname": user_data.get("surname"),
                    "givenName": user_data.get("givenName"),
                    "avatar": user_data.get("photo"),
                    "tenantId": user_data.get("tenantId"),
                    "usageLocation": user_data.get("usageLocation"),
                    "userType": user_data.get("userType"),
                    "accountEnabled": user_data.get("accountEnabled"),
                    "createdDateTime": user_data.get("createdDateTime"),
                    "lastPasswordChangeDateTime": user_data.get(
                        "lastPasswordChangeDateTime"
                    ),
                }

                return jsonify(format_teams_response(profile, "get_user_profile"))
            else:
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "message": f"Teams API error: {response.status_code}"
                        },
                    }
                ), response.status_code

    except Exception as e:
        logger.error(f"Error getting user profile: {e}")
        return jsonify(format_error_response(e, "get_user_profile")), 500


@teams_enhanced_bp.route("/api/integrations/teams/search", methods=["POST"])
async def search_teams():
    """Search across Teams (messages, channels, files)"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        query = data.get("query")
        search_type = data.get("type", "messages")
        limit = data.get("limit", 50)

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        if not query:
            return jsonify(
                {"ok": False, "error": {"message": "query is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Teams tokens not found"}}
            ), 401

        # Create Teams client
        async with create_teams_client(tokens["access_token"]) as client:
            # Microsoft Search API
            search_url = "/search/query"
            search_request = {
                "requests": [
                    {
                        "entityTypes": [search_type],
                        "query": {"queryString": query},
                        "from": 0,
                        "size": min(limit, 100),
                        "fields": [],
                    }
                ]
            }

            response = await client.post(search_url, json=search_request)

            if response.status_code == 200:
                search_data = response.json()

                # Extract results
                results = []
                if search_data.get("value") and len(search_data["value"]) > 0:
                    hits = search_data["value"][0].get("hitsContainers", [])
                    if hits and len(hits) > 0:
                        hits_content = hits[0].get("hits", [])
                        results = [hit.get("resource") for hit in hits_content]

                return jsonify(
                    format_teams_response(
                        {
                            "results": results,
                            "total_count": len(results),
                            "query": query,
                            "search_type": search_type,
                        },
                        "search_teams",
                    )
                )
            else:
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "message": f"Teams API error: {response.status_code}"
                        },
                    }
                ), response.status_code

    except Exception as e:
        logger.error(f"Error searching Teams: {e}")
        return jsonify(format_error_response(e, "search_teams")), 500


@teams_enhanced_bp.route("/api/integrations/teams/messages", methods=["POST"])
async def create_message():
    """Send a message to a channel"""
    try:
        data = request.get_json()
        user_id = data.get("user_id")
        operation = data.get("operation", "create")
        message_data = data.get("data", {})

        if not user_id:
            return jsonify(
                {"ok": False, "error": {"message": "user_id is required"}}
            ), 400

        if operation != "create":
            return jsonify(
                {
                    "ok": False,
                    "error": {"message": "Only create operation is supported"},
                }
            ), 400

        if not message_data.get("channelId"):
            return jsonify(
                {"ok": False, "error": {"message": "channelId is required"}}
            ), 400

        if not message_data.get("content"):
            return jsonify(
                {"ok": False, "error": {"message": "content is required"}}
            ), 400

        # Get user tokens
        tokens = await get_user_tokens(user_id)
        if not tokens:
            return jsonify(
                {"ok": False, "error": {"message": "Teams tokens not found"}}
            ), 401

        # Create Teams client
        async with create_teams_client(tokens["access_token"]) as client:
            team_id = message_data.get("teamId")
            channel_id = message_data.get("channelId")

            url = f"/teams/{team_id}/channels/{channel_id}/messages"

            message_payload = {
                "body": {"contentType": "html", "content": message_data["content"]},
                "subject": message_data.get("subject"),
                "importance": message_data.get("importance", "normal"),
            }

            response = await client.post(url, json=message_payload)

            if response.status_code == 201:
                message_result = response.json()

                return jsonify(
                    format_teams_response(
                        {
                            "message": message_result,
                            "webUrl": message_result.get("webUrl"),
                            "message": "Message sent successfully",
                        },
                        "create_message",
                    )
                )
            else:
                return jsonify(
                    {
                        "ok": False,
                        "error": {
                            "message": f"Teams API error: {response.status_code}"
                        },
                    }
                ), response.status_code

    except Exception as e:
        logger.error(f"Error creating message: {e}")
        return jsonify(format_error_response(e, "create_message")), 500


# Health check endpoint
@teams_enhanced_bp.route("/api/integrations/teams/health", methods=["GET"])
async def health_check():
    """Teams service health check"""
    try:
        if not TEAMS_SERVICE_AVAILABLE:
            return jsonify(
                {
                    "status": "unhealthy",
                    "error": "Teams service not available",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            )

        # Test Microsoft Graph API connectivity
        async with httpx.AsyncClient() as client:
            response = await client.get(f"{TEAMS_API_BASE_URL}/", timeout=5)

            if response.status_code == 200:
                return jsonify(
                    {
                        "status": "healthy",
                        "message": "Microsoft Graph API is accessible",
                        "service_available": TEAMS_SERVICE_AVAILABLE,
                        "database_available": TEAMS_DB_AVAILABLE,
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )
            else:
                return jsonify(
                    {
                        "status": "degraded",
                        "error": f"Microsoft Graph API returned {response.status_code}",
                        "timestamp": datetime.utcnow().isoformat(),
                    }
                )

    except Exception as e:
        return jsonify(
            {
                "status": "unhealthy",
                "error": str(e),
                "timestamp": datetime.utcnow().isoformat(),
            }
        )


# Error handlers
@teams_enhanced_bp.errorhandler(404)
async def not_found(error):
    return jsonify(
        {"ok": False, "error": {"code": "NOT_FOUND", "message": "Endpoint not found"}}
    ), 404


@teams_enhanced_bp.errorhandler(500)
async def internal_error(error):
    logger.error(f"Internal server error: {error}")
    return jsonify(
        {
            "ok": False,
            "error": {"code": "INTERNAL_ERROR", "message": "Internal server error"},
        }
    ), 500
