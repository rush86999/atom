"""
ATOM Real Slack Service Implementation
Production Slack integration with real Slack API
"""

import os
import json
import httpx
import asyncio
import time
import hashlib
import hmac
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional, Tuple
from loguru import logger

class RealSlackService:
    """Real Slack service using actual Slack Web API"""
    
    def __init__(self):
        self.service_name = "RealSlack"
        self._client = None
        self._access_token = None
        self._refresh_token = None
        self._token_expires = None
        self._bot_token = None
        self._app_credentials = {
            "client_id": os.getenv('SLACK_CLIENT_ID'),
            "client_secret": os.getenv('SLACK_CLIENT_SECRET'),
            "signing_secret": os.getenv('SLACK_SIGNING_SECRET'),
            "verification_token": os.getenv('SLACK_VERIFICATION_TOKEN')
        }
        
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create authenticated HTTP client"""
        if not self._client or self._is_token_expired():
            await self._refresh_access_token()
            
        # Use both user and bot tokens if available
        token = self._bot_token or self._access_token
        
        if not token:
            raise ValueError("No access token available. Please authenticate first.")
            
        self._client = httpx.AsyncClient(
            base_url="https://slack.com/api",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "User-Agent": "ATOM-Agent/1.0"
            },
            timeout=30.0
        )
        
        return self._client

    def _is_token_expired(self) -> bool:
        """Check if access token is expired or close to expiry"""
        if not self._token_expires:
            return True
        return datetime.utcnow() >= self._token_expires - timedelta(minutes=5)

    async def _refresh_access_token(self) -> bool:
        """Refresh Slack access token"""
        try:
            if self._refresh_token:
                # Use refresh token
                token_data = await self._exchange_refresh_token()
            else:
                # Use bot token if configured
                bot_token = os.getenv('SLACK_BOT_TOKEN')
                if bot_token:
                    self._access_token = bot_token
                    self._bot_token = bot_token
                    self._token_expires = datetime.utcnow() + timedelta(hours=24)  # Bot tokens don't expire
                    logger.info("Slack: Using configured bot token")
                    return True
                else:
                    logger.error("Slack: No refresh token or bot token available")
                    return False

            if token_data:
                self._access_token = token_data['access_token']
                self._refresh_token = token_data.get('refresh_token')
                
                # Set expiry time (default 12 hours if not specified)
                expires_in = token_data.get('expires_in', 43200)
                self._token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
                
                logger.info("Slack: Token refreshed successfully")
                return True
            else:
                logger.error("Slack: Failed to refresh token")
                return False

        except Exception as e:
            logger.error(f"Slack: Token refresh error: {e}")
            return False

    async def _exchange_refresh_token(self) -> Optional[Dict[str, Any]]:
        """Exchange refresh token for new access token"""
        try:
            client_id = self._app_credentials["client_id"]
            client_secret = self._app_credentials["client_secret"]
            
            if not all([client_id, client_secret, self._refresh_token]):
                logger.error("Slack: Missing credentials for token refresh")
                return None

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        "grant_type": "refresh_token",
                        "refresh_token": self._refresh_token,
                        "client_id": client_id,
                        "client_secret": client_secret
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        return result
                    else:
                        logger.error(f"Slack: Token refresh API error: {result.get('error')}")
                        return None
                else:
                    logger.error(f"Slack: Token refresh HTTP error: {response.status_code}")
                    return None
                    
        except Exception as e:
            logger.error(f"Slack: Token refresh exception: {e}")
            return None

    async def install_with_user_id(self, user_id: str) -> Dict[str, Any]:
        """
        Install Slack app by generating installation URL for user_id
        Real implementation: this would require user_id-based workspace mapping
        """
        try:
            client_id = self._app_credentials["client_id"]
            
            if not client_id:
                return {"error": "No Slack client ID configured"}

            # Generate state parameter for security
            state = hmac.new(
                f"slack_install_{user_id}".encode(),
                str(time.time()).encode(),
                hashlib.sha256
            ).hexdigest()[:16]

            # Build installation URL
            install_params = {
                "client_id": client_id,
                "scope": "channels:history channels:read chat:read chat:write files:read users:read",
                "user_scope": "channels:read chat:read files:read",
                "redirect_uri": f"{os.getenv('SLACK_REDIRECT_URI', 'http://localhost:8000')}/oauth/slack/callback",
                "state": state
            }
            
            install_url = f"https://slack.com/oauth/v2/authorize?" + "&".join([f"{k}={v}" for k, v in install_params.items()])
            
            logger.info(f"Slack: Generated install URL for user {user_id}")
            
            return {
                "ok": True,
                "install_url": install_url,
                "state": state,
                "user_id": user_id,
                "expires_in": 600,  # 10 minutes
                "message": "Visit this URL to install Slack app",
                "installation_state": "pending"
            }

        except Exception as e:
            logger.error(f"Slack: Install URL generation error: {e}")
            return {
                "ok": False,
                "error": str(e),
                "user_id": user_id
            }

    async def get_workspaces(self, user_id: str) -> Dict[str, Any]:
        """
        Get accessible Slack workspaces for user_id
        Real implementation: query database for user's installed workspaces
        """
        try:
            client = await self.get_client()
            
            # Get user's workspaces
            response = await client.get("/auth.teams.list")
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    workspaces = []
                    for team in result.get('teams', []):
                        workspaces.append({
                            "id": team["id"],
                            "name": team["name"],
                            "domain": team.get("domain"),
                            "icon_url": team.get("image", {}).get("image", {}).get("230"),
                            "is_verified": team.get("is_verified", False),
                            "created_at": team.get("created"),
                            "user_id": user_id,
                            "installation_type": "user"
                        })
                    
                    logger.info(f"Slack: Retrieved {len(workspaces)} workspaces for user {user_id}")
                    return {
                        "ok": True,
                        "workspaces": workspaces,
                        "total_count": len(workspaces),
                        "retrieved_at": datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        "ok": False,
                        "error": result.get('error'),
                        "user_id": user_id
                    }
            else:
                logger.error(f"Slack: Get workspaces HTTP error: {response.status_code}")
                return {
                    "ok": False,
                    "error": f"HTTP {response.status_code}",
                    "user_id": user_id
                }

        except Exception as e:
            logger.error(f"Slack: Get workspaces exception: {e}")
            return {
                "ok": False,
                "error": str(e),
                "user_id": user_id
            }

    async def get_channels(self, team_id: str, user_id: str) -> Dict[str, Any]:
        """Get channels for a specific workspace"""
        try:
            client = await self.get_client()
            
            # Get all channels for the workspace
            response = await client.get("/conversations.list", params={
                "types": "public_channel,private_channel,mpim,im",
                "exclude_archived": "true",
                "limit": "1000"
            })
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    channels = []
                    for channel in result.get('channels', []):
                        # Determine channel type
                        if channel['is_mpim']:
                            channel_type = "group_dm"
                        elif channel['is_im']:
                            channel_type = "dm"
                        elif channel['is_private']:
                            channel_type = "private"
                        else:
                            channel_type = "public"
                        
                        channels.append({
                            "id": channel["id"],
                            "name": channel["name"],
                            "display_name": channel.get("name_normalized", channel["name"]),
                            "team_id": team_id,
                            "channel_type": channel_type,
                            "purpose": channel.get("purpose", {}).get("value", ""),
                            "topic": channel.get("topic", {}).get("value", ""),
                            "member_count": channel.get("num_members", 0),
                            "is_archived": channel.get("is_archived", False),
                            "is_private": channel.get("is_private", False),
                            "created_at": channel.get("created"),
                            "updated_at": channel.get("updated"),
                            "unread_count": channel.get("unread_count", 0),
                            "is_starred": channel.get("is_starred", False)
                        })
                    
                    logger.info(f"Slack: Retrieved {len(channels)} channels for team {team_id}")
                    return {
                        "ok": True,
                        "channels": channels,
                        "team_id": team_id,
                        "total_count": len(channels),
                        "retrieved_at": datetime.utcnow().isoformat()
                    }
                else:
                    return {
                        "ok": False,
                        "error": result.get('error'),
                        "team_id": team_id
                    }
            else:
                logger.error(f"Slack: Get channels HTTP error: {response.status_code}")
                return {
                    "ok": False,
                    "error": f"HTTP {response.status_code}",
                    "team_id": team_id
                }

        except Exception as e:
            logger.error(f"Slack: Get channels exception: {e}")
            return {
                "ok": False,
                "error": str(e),
                "team_id": team_id
            }

    async def get_messages(self, channel_id: str, team_id: str, limit: int = 50) -> Dict[str, Any]:
        """Get messages from a specific channel"""
        try:
            client = await self.get_client()
            
            # Get messages from channel
            response = await client.get("/conversations.history", params={
                "channel": channel_id,
                "limit": str(limit),
                "include_all_metadata": "true"
            })
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    messages = []
                    for message in result.get('messages', []):
                        # Extract attachments
                        attachments = []
                        for attachment in message.get('attachments', []):
                            attachments.append({
                                "id": attachment.get("id"),
                                "title": attachment.get("title"),
                                "url": attachment.get("url", attachment.get("original_url")),
                                "type": attachment.get("mimetype"),
                                "size": attachment.get("size", 0),
                                "thumb_url": attachment.get("thumb_url")
                            })
                        
                        # Extract reactions
                        reactions = {
                            "like": 0,
                            "eyes": 0,
                            "heart": 0,
                            "thumbsup": 0,
                            "thumbsdown": 0,
                            "laugh": 0,
                            "confused": 0,
                            "raised_hands": 0,
                            "rocket": 0
                        }
                        
                        for reaction in message.get('reactions', []):
                            emoji = reaction.get('name', '').lower()
                            count = reaction.get('count', 0)
                            
                            if emoji in ['+1', 'thumbsup']:
                                reactions["thumbsup"] += count
                            elif emoji == '-1' or emoji == 'thumbsdown':
                                reactions["thumbsdown"] += count
                            elif emoji == 'heart':
                                reactions["heart"] += count
                            elif emoji == 'eyes':
                                reactions["eyes"] += count
                            elif emoji in ['rocket', 'ship']:
                                reactions["rocket"] += count
                            elif emoji == 'raised_hands':
                                reactions["raised_hands"] += count
                            elif emoji == 'confused':
                                reactions["confused"] += count
                            elif emoji == 'laugh':
                                reactions["laugh"] += count
                            else:
                                # Add to general "like" category for unknown emojis
                                reactions["like"] += count
                        
                        # Get sender info
                        sender_name = "Unknown"
                        if message.get('user'):
                            # Would need additional API call to get user info
                            sender_name = message['user']
                        elif message.get('username'):  # Bot message
                            sender_name = message['username']
                        
                        # Handle thread replies
                        thread_info = {}
                        if message.get('thread_ts') and message['thread_ts'] != message['ts']:
                            thread_info = {
                                "thread_id": message['thread_ts'],
                                "reply_count": message.get('reply_count', 0),
                                "last_reply": message.get('latest_reply')
                            }
                        
                        messages.append({
                            "id": message["ts"],
                            "thread_id": message.get('thread_ts', message["ts"]),
                            "channel_id": channel_id,
                            "team_id": team_id,
                            "from": sender_name,
                            "subject": "",
                            "preview": (message.get('text', '')[:100] + '...') if len(message.get('text', '')) > 100 else message.get('text', ''),
                            "content": message.get('text', ''),
                            "timestamp": message.get('ts'),
                            "updated_at": message.get('edited', {}).get('ts'),
                            "priority": "normal",
                            "unread": message.get('unread', False),
                            "status": "received",
                            "attachments": attachments,
                            "mentions": self._extract_mentions(message.get('text', '')),
                            "reactions": reactions,
                            "reply_count": message.get('reply_count', 0),
                            "is_edited": 'edited' in message,
                            "is_deleted": False,
                            "thread_info": thread_info
                        })
                    
                    logger.info(f"Slack: Retrieved {len(messages)} messages from channel {channel_id}")
                    return {
                        "ok": True,
                        "messages": messages,
                        "channel_id": channel_id,
                        "team_id": team_id,
                        "total_count": len(messages),
                        "retrieved_at": datetime.utcnow().isoformat(),
                        "has_more": result.get('has_more', False)
                    }
                else:
                    return {
                        "ok": False,
                        "error": result.get('error'),
                        "channel_id": channel_id
                    }
            else:
                logger.error(f"Slack: Get messages HTTP error: {response.status_code}")
                return {
                    "ok": False,
                    "error": f"HTTP {response.status_code}",
                    "channel_id": channel_id
                }

        except Exception as e:
            logger.error(f"Slack: Get messages exception: {e}")
            return {
                "ok": False,
                "error": str(e),
                "channel_id": channel_id
            }

    async def send_message(self, channel_id: str, content: str, team_id: str) -> Dict[str, Any]:
        """Send a message to a Slack channel"""
        try:
            client = await self.get_client()
            
            # Send message
            response = await client.post("/chat.postMessage", json={
                "channel": channel_id,
                "text": content,
                "parse": "full"
            })
            
            if response.status_code == 200:
                result = response.json()
                if result.get('ok'):
                    logger.info(f"Slack: Message sent to channel {channel_id}")
                    
                    return {
                        "ok": True,
                        "message_id": result["ts"],
                        "channel_id": channel_id,
                        "team_id": team_id,
                        "content": content,
                        "sent_at": datetime.utcnow().isoformat(),
                        "status": "sent"
                    }
                else:
                    return {
                        "ok": False,
                        "error": result.get('error'),
                        "channel_id": channel_id,
                        "content": content
                    }
            else:
                logger.error(f"Slack: Send message HTTP error: {response.status_code}")
                return {
                    "ok": False,
                    "error": f"HTTP {response.status_code}",
                    "channel_id": channel_id,
                    "content": content
                }

        except Exception as e:
            logger.error(f"Slack: Send message exception: {e}")
            return {
                "ok": False,
                "error": str(e),
                "channel_id": channel_id,
                "content": content
            }

    async def exchange_code_for_tokens(self, code: str) -> Dict[str, Any]:
        """
        Exchange OAuth authorization code for access tokens
        """
        try:
            client_id = self._app_credentials["client_id"]
            client_secret = self._app_credentials["client_secret"]
            redirect_uri = self._app_credentials.get("redirect_uri", "http://localhost:8000/oauth/slack/callback")
            
            if not all([client_id, client_secret]):
                return {
                    "ok": False,
                    "error": "Missing Slack credentials"
                }

            async with httpx.AsyncClient() as client:
                response = await client.post(
                    "https://slack.com/api/oauth.v2.access",
                    data={
                        "grant_type": "authorization_code",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "code": code,
                        "redirect_uri": redirect_uri
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    result = response.json()
                    if result.get('ok'):
                        logger.info("Slack: Code exchange successful")
                        return result
                    else:
                        logger.error(f"Slack: Code exchange API error: {result.get('error')}")
                        return result
                else:
                    logger.error(f"Slack: Code exchange HTTP error: {response.status_code}")
                    return {
                        "ok": False,
                        "error": f"HTTP {response.status_code}"
                    }

        except Exception as e:
            logger.error(f"Slack: Code exchange exception: {e}")
            return {
                "ok": False,
                "error": str(e)
            }

    async def health_check(self) -> Dict[str, Any]:
        """Check Slack service health"""
        try:
            # Test API connectivity
            async with httpx.AsyncClient() as client:
                response = await client.get("https://slack.com/api/auth.test", timeout=10.0)
                api_healthy = response.status_code == 200
            
            # Check configuration
            config_healthy = all([
                self._app_credentials["client_id"],
                self._app_credentials["client_secret"]
            ])
            
            # Check token status
            token_valid = not self._is_token_expired() if self._access_token else False
            
            return {
                "status": "healthy" if api_healthy and config_healthy and token_valid else "unhealthy",
                "api_healthy": api_healthy,
                "config_healthy": config_healthy,
                "token_valid": token_valid,
                "has_bot_token": bool(self._bot_token),
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Slack: Health check error: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

    def _extract_mentions(self, content: str) -> List[Dict[str, Any]]:
        """Extract @mentions from Slack message"""
        mentions = []
        
        # Simple regex to find @mentions
        import re
        mention_pattern = r'<@([^|>]+)(?:\|([^>]+))?>'
        
        for match in re.finditer(mention_pattern, content):
            user_id = match.group(1)
            display_name = match.group(2) if match.group(2) else user_id
            
            mentions.append({
                "user_id": user_id,
                "display_name": display_name,
                "text": match.group(0)
            })
        
        return mentions

# Initialize real Slack service instance
real_slack_service = RealSlackService()