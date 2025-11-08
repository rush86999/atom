import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

logger = logging.getLogger(__name__)

# Slack API configuration
SLACK_API_BASE = "https://slack.com/api"

class SlackService:
    """Comprehensive Slack API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.bot_token = None
        self.db_pool = None
        self._initialized = False
    
    async def initialize(self, db_pool: Pool):
        """Initialize Slack service with database pool"""
        try:
            from db_oauth_slack import get_user_slack_tokens
            from main_api_app import get_db_pool
            
            self.db_pool = db_pool
            tokens = await get_user_slack_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self.bot_token = tokens.get("bot_token")
                self._initialized = True
                logger.info(f"Slack service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Slack tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize Slack service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Slack service not initialized. Call initialize() first.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get API headers with authentication"""
        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
        return headers
    
    def _get_bot_headers(self) -> Dict[str, str]:
        """Get API headers with bot authentication"""
        headers = {
            "Authorization": f"Bearer {self.bot_token}",
            "Content-Type": "application/json"
        }
        return headers
    
    async def _make_request(self, method: str, endpoint: str, 
                           data: Dict[str, Any] = None, 
                           params: Dict[str, Any] = None,
                           use_bot: bool = False) -> Dict[str, Any]:
        """Make authenticated API request with error handling"""
        try:
            url = f"{SLACK_API_BASE}{endpoint}"
            headers = self._get_bot_headers() if use_bot else self._get_headers()
            
            async with httpx.AsyncClient() as client:
                if method.upper() == "GET":
                    response = await client.get(url, headers=headers, params=params)
                elif method.upper() == "POST":
                    response = await client.post(url, headers=headers, json=data, params=params)
                elif method.upper() == "PUT":
                    response = await client.put(url, headers=headers, json=data, params=params)
                elif method.upper() == "DELETE":
                    response = await client.delete(url, headers=headers, params=params)
                else:
                    raise ValueError(f"Unsupported HTTP method: {method}")
                
                if response.status_code == 401:
                    # Token expired, try to refresh
                    await self._refresh_token()
                    # Retry request with new token
                    return await self._make_request(method, endpoint, data, params, use_bot)
                elif response.status_code >= 400:
                    error_data = response.json()
                    logger.error(f"Slack API error {response.status_code}: {error_data}")
                    return {
                        "success": False,
                        "error": f"API error {response.status_code}",
                        "details": error_data
                    }
                
                response.raise_for_status()
                api_response = response.json()
                
                # Check if Slack API call was successful
                if not api_response.get("ok", True):
                    logger.error(f"Slack API error: {api_response}")
                    return {
                        "success": False,
                        "error": "Slack API error",
                        "details": api_response
                    }
                
                return {
                    "success": True,
                    "data": api_response
                }
                
        except httpx.HTTPStatusError as e:
            logger.error(f"Slack API HTTP error: {e.response.status_code} - {e.response.text}")
            return {
                "success": False,
                "error": f"HTTP error {e.response.status_code}",
                "details": e.response.text
            }
        except Exception as e:
            logger.error(f"Slack API request failed: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def _refresh_token(self):
        """Refresh access token"""
        try:
            refresh_url = "https://slack.com/api/oauth.v2.access"
            
            data = {
                "grant_type": "refresh_token",
                "client_id": os.getenv("SLACK_CLIENT_ID"),
                "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
                "refresh_token": self.refresh_token
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(refresh_url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                
                if not token_data.get("ok", True):
                    raise Exception(f"Token refresh failed: {token_data}")
                
                # Update tokens
                self.access_token = token_data["access_token"]
                if "refresh_token" in token_data:
                    self.refresh_token = token_data["refresh_token"]
                if "bot_user_id" in token_data:
                    self.bot_user_id = token_data["bot_user_id"]
                
                # Update in database
                from db_oauth_slack import refresh_slack_tokens
                await refresh_slack_tokens(self.db_pool, self.user_id, token_data)
                
                logger.info("Slack token refreshed successfully")
                
        except Exception as e:
            logger.error(f"Failed to refresh Slack token: {e}")
            raise
    
    # Team and Workspace Management
    async def get_team_info(self) -> Dict[str, Any]:
        """Get Slack team/workspace information"""
        try:
            await self._ensure_initialized()
            
            result = await self._make_request("GET", "/team.info")
            
            if result["success"]:
                team = result["data"]["team"]
                
                return {
                    "success": True,
                    "data": {
                        "id": team.get("id"),
                        "name": team.get("name"),
                        "domain": team.get("domain"),
                        "email_domain": team.get("email_domain"),
                        "icon": team.get("icon"),
                        "is_verified": team.get("is_verified", False),
                        "created": team.get("created", 0),
                        "date_created": datetime.fromtimestamp(team.get("created", 0)).isoformat(),
                        "plan": team.get("plan", "free"),
                        "user_count": team.get("active_users", 0)
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get Slack team info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Users Management
    async def get_users(self, limit: int = 100, cursor: str = None) -> Dict[str, Any]:
        """Get Slack workspace users"""
        try:
            await self._ensure_initialized()
            
            params = {
                "limit": limit,
                "include_locale": True,
                "presence": True
            }
            
            if cursor:
                params["cursor"] = cursor
            
            result = await self._make_request("GET", "/users.list", params=params)
            
            if result["success"]:
                users = []
                for user in result["data"]["members"]:
                    users.append({
                        "id": user.get("id"),
                        "name": user.get("name"),
                        "real_name": user.get("real_name"),
                        "display_name": user.get("profile", {}).get("display_name", ""),
                        "email": user.get("profile", {}).get("email", ""),
                        "phone": user.get("profile", {}).get("phone", ""),
                        "title": user.get("profile", {}).get("title", ""),
                        "status": user.get("profile", {}).get("status_text", ""),
                        "status_emoji": user.get("profile", {}).get("status_emoji", ""),
                        "is_bot": user.get("is_bot", False),
                        "is_admin": user.get("is_admin", False),
                        "is_owner": user.get("is_owner", False),
                        "is_primary_owner": user.get("is_primary_owner", False),
                        "is_restricted": user.get("is_restricted", False),
                        "is_ultra_restricted": user.get("is_ultra_restricted", False),
                        "presence": user.get("presence", "offline"),
                        "tz": user.get("tz", ""),
                        "tz_label": user.get("tz_label", ""),
                        "updated": user.get("updated", 0),
                        "deleted": user.get("deleted", False),
                        "image": user.get("profile", {}).get("image_192", ""),
                        "hasImage": bool(user.get("profile", {}).get("image_192")),
                        "hasStatus": bool(user.get("profile", {}).get("status_text", "")),
                        "hasPhone": bool(user.get("profile", {}).get("phone", "")),
                        "hasTitle": bool(user.get("profile", {}).get("title", "")),
                        "hasEmail": bool(user.get("profile", {}).get("email", ""))
                    })
                
                # Cache users
                await self.cache_users(users)
                
                return {
                    "success": True,
                    "data": users,
                    "total": len(users),
                    "has_more": result["data"].get("response_metadata", {}).get("next_cursor") is not None,
                    "next_cursor": result["data"].get("response_metadata", {}).get("next_cursor")
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get Slack users: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_user_info(self, user_id: str) -> Dict[str, Any]:
        """Get specific user information"""
        try:
            await self._ensure_initialized()
            
            result = await self._make_request("GET", f"/users.info", params={"user": user_id})
            
            if result["success"]:
                user = result["data"]["user"]
                
                return {
                    "success": True,
                    "data": {
                        "id": user.get("id"),
                        "name": user.get("name"),
                        "real_name": user.get("real_name"),
                        "display_name": user.get("profile", {}).get("display_name", ""),
                        "email": user.get("profile", {}).get("email", ""),
                        "phone": user.get("profile", {}).get("phone", ""),
                        "title": user.get("profile", {}).get("title", ""),
                        "status": user.get("profile", {}).get("status_text", ""),
                        "status_emoji": user.get("profile", {}).get("status_emoji", ""),
                        "is_bot": user.get("is_bot", False),
                        "is_admin": user.get("is_admin", False),
                        "is_owner": user.get("is_owner", False),
                        "tz": user.get("tz", ""),
                        "tz_label": user.get("tz_label", ""),
                        "updated": user.get("updated", 0),
                        "image": user.get("profile", {}).get("image_192", ""),
                        "created": user.get("created", 0)
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get Slack user info: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Channels Management
    async def get_channels(self, types: List[str] = None, limit: int = 100, cursor: str = None) -> Dict[str, Any]:
        """Get Slack channels"""
        try:
            await self._ensure_initialized()
            
            # Default to all channel types
            if not types:
                types = ["public_channel", "private_channel", "mpim", "im"]
            
            all_channels = []
            
            for channel_type in types:
                endpoint = "/conversations.list"
                if channel_type == "im":
                    endpoint = "/conversations.list"
                
                params = {
                    "types": channel_type,
                    "limit": limit
                }
                
                if cursor:
                    params["cursor"] = cursor
                
                result = await self._make_request("GET", endpoint, params=params)
                
                if result["success"]:
                    for channel in result["data"]["channels"]:
                        channel_info = {
                            "id": channel.get("id"),
                            "name": channel.get("name", ""),
                            "name_normalized": channel.get("name_normalized", ""),
                            "topic": channel.get("topic", {}).get("value", ""),
                            "purpose": channel.get("purpose", {}).get("value", ""),
                            "is_archived": channel.get("is_archived", False),
                            "is_general": channel.get("is_general", False),
                            "is_private": channel.get("is_private", True),
                            "is_im": channel_type == "im",
                            "is_mpim": channel_type == "mpim",
                            "created": channel.get("created", 0),
                            "creator": channel.get("creator", ""),
                            "last_read": channel.get("last_read", ""),
                            "unread_count": channel.get("unread_count", 0),
                            "unread_count_display": channel.get("unread_count_display", 0),
                            "num_members": channel.get("num_members", 0),
                            "member_count": channel.get("member_count", channel.get("num_members", 0)),
                            "is_member": channel.get("is_member", True),
                            "has_topic": bool(channel.get("topic", {}).get("value", "")),
                            "has_purpose": bool(channel.get("purpose", {}).get("value", "")),
                            "is_active": not channel.get("is_archived", False)
                        }
                        
                        # Add user info for direct messages
                        if channel_type == "im" and channel.get("user"):
                            user_result = await self.get_user_info(channel.get("user"))
                            if user_result["success"]:
                                user_data = user_result["data"]
                                channel_info["user"] = user_data
                                channel_info["user_name"] = user_data.get("display_name") or user_data.get("real_name")
                                channel_info["user_image"] = user_data.get("image")
                        
                        all_channels.append(channel_info)
            
            # Cache channels
            await self.cache_channels(all_channels)
            
            return {
                "success": True,
                "data": all_channels,
                "total": len(all_channels)
            }
            
        except Exception as e:
            logger.error(f"Failed to get Slack channels: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_channel_messages(self, channel_id: str, limit: int = 100, 
                                 cursor: str = None, oldest: str = None, 
                                 latest: str = None) -> Dict[str, Any]:
        """Get messages from a channel"""
        try:
            await self._ensure_initialized()
            
            params = {
                "channel": channel_id,
                "limit": limit,
                "include_all_metadata": True
            }
            
            if cursor:
                params["cursor"] = cursor
            if oldest:
                params["oldest"] = oldest
            if latest:
                params["latest"] = latest
            
            result = await self._make_request("GET", "/conversations.history", params=params)
            
            if result["success"]:
                messages = []
                for message in result["data"]["messages"]:
                    message_info = {
                        "id": message.get("ts"),
                        "ts": message.get("ts"),
                        "type": message.get("type", "message"),
                        "text": message.get("text", ""),
                        "user": message.get("user"),
                        "team": message.get("team"),
                        "bot_id": message.get("bot_id"),
                        "is_bot": bool(message.get("bot_id")),
                        "thread_ts": message.get("thread_ts"),
                        "is_thread": bool(message.get("thread_ts")),
                        "reply_count": len(message.get("replies", [])),
                        "reactions": message.get("reactions", []),
                        "files": message.get("files", []),
                        "has_files": len(message.get("files", [])) > 0,
                        "has_reactions": len(message.get("reactions", [])) > 0,
                        "has_thread": bool(message.get("thread_ts")),
                        "edited": "edited" in message,
                        "pinned": message.get("pinned", False),
                        "time": datetime.fromtimestamp(float(message.get("ts", "0"))).isoformat(),
                        "date": datetime.fromtimestamp(float(message.get("ts", "0"))).strftime("%Y-%m-%d")
                    }
                    
                    # Add user info
                    if message.get("user"):
                        user_result = await self.get_user_info(message.get("user"))
                        if user_result["success"]:
                            user_data = user_result["data"]
                            message_info["user_name"] = user_data.get("display_name") or user_data.get("real_name")
                            message_info["user_image"] = user_data.get("image")
                    
                    messages.append(message_info)
                
                # Cache messages
                await self.cache_messages(channel_id, messages)
                
                return {
                    "success": True,
                    "data": messages,
                    "total": len(messages),
                    "has_more": result["data"].get("has_more", False),
                    "next_cursor": result["data"].get("response_metadata", {}).get("next_cursor")
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get Slack channel messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_message(self, channel_id: str, text: str, 
                          thread_ts: str = None, blocks: List[Dict] = None) -> Dict[str, Any]:
        """Send a message to a channel"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "text": text
            }
            
            if thread_ts:
                data["thread_ts"] = thread_ts
            if blocks:
                data["blocks"] = blocks
            
            result = await self._make_request("POST", "/chat.postMessage", data=data, use_bot=True)
            
            if result["success"]:
                message = result["data"]["message"]
                
                # Log activity
                await self.log_activity("send_message", {
                    "channel_id": channel_id,
                    "message_id": message.get("ts"),
                    "text": text,
                    "thread_ts": thread_ts,
                    "has_blocks": bool(blocks)
                })
                
                return {
                    "success": True,
                    "data": {
                        "id": message.get("ts"),
                        "channel": message.get("channel"),
                        "text": message.get("text"),
                        "ts": message.get("ts"),
                        "thread_ts": message.get("thread_ts"),
                        "user": message.get("user"),
                        "bot_id": message.get("bot_id"),
                        "time": datetime.fromtimestamp(float(message.get("ts", "0"))).isoformat()
                    }
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Files Management
    async def get_files(self, types: str = "all", limit: int = 100, 
                       page: int = 1) -> Dict[str, Any]:
        """Get Slack files"""
        try:
            await self._ensure_initialized()
            
            params = {
                "types": types,
                "count": limit,
                "page": page
            }
            
            result = await self._make_request("GET", "/files.list", params=params)
            
            if result["success"]:
                files = []
                for file in result["data"]["files"]:
                    files.append({
                        "id": file.get("id"),
                        "name": file.get("name"),
                        "title": file.get("title", ""),
                        "mimetype": file.get("mimetype", ""),
                        "filetype": file.get("filetype", ""),
                        "pretty_type": file.get("pretty_type", ""),
                        "user": file.get("user"),
                        "timestamp": file.get("timestamp", 0),
                        "size": file.get("size", 0),
                        "url_private": file.get("url_private", ""),
                        "url_private_download": file.get("url_private_download", ""),
                        "permalink": file.get("permalink", ""),
                        "permalink_public": file.get("permalink_public", ""),
                        "editable": file.get("editable", False),
                        "is_public": file.get("is_public", False),
                        "is_external": file.get("is_external", False),
                        "has_preview": file.get("has_preview", False),
                        "num_starred": file.get("num_starred", 0),
                        "time": datetime.fromtimestamp(file.get("timestamp", 0)).isoformat(),
                        "date": datetime.fromtimestamp(file.get("timestamp", 0)).strftime("%Y-%m-%d"),
                        "size_mb": round(file.get("size", 0) / (1024 * 1024), 2),
                        "has_image": file.get("mimetype", "").startswith("image/"),
                        "has_video": file.get("mimetype", "").startswith("video/"),
                        "has_audio": file.get("mimetype", "").startswith("audio/"),
                        "is_document": not file.get("mimetype", "").startswith(("image/", "video/", "audio/"))
                    })
                
                # Cache files
                await self.cache_files(files)
                
                return {
                    "success": True,
                    "data": files,
                    "total": len(files),
                    "paging": result["data"]["paging"]
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to get Slack files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Search
    async def search_messages(self, query: str, sort: str = "timestamp", 
                           sort_dir: str = "desc", count: int = 50) -> Dict[str, Any]:
        """Search Slack messages"""
        try:
            await self._ensure_initialized()
            
            params = {
                "query": query,
                "sort": sort,
                "sort_dir": sort_dir,
                "count": count
            }
            
            result = await self._make_request("GET", "/search.messages", params=params)
            
            if result["success"]:
                messages = []
                for message in result["data"]["messages"]["matches"]:
                    message_data = message.get("message", {})
                    
                    message_info = {
                        "id": message_data.get("ts"),
                        "ts": message_data.get("ts"),
                        "text": message_data.get("text", ""),
                        "user": message_data.get("user"),
                        "team": message_data.get("team"),
                        "channel": message.get("channel", {}).get("id"),
                        "channel_name": message.get("channel", {}).get("name", ""),
                        "bot_id": message_data.get("bot_id"),
                        "is_bot": bool(message_data.get("bot_id")),
                        "reactions": message_data.get("reactions", []),
                        "has_reactions": len(message_data.get("reactions", [])) > 0,
                        "score": message.get("score", 0),
                        "time": datetime.fromtimestamp(float(message_data.get("ts", "0"))).isoformat(),
                        "date": datetime.fromtimestamp(float(message_data.get("ts", "0"))).strftime("%Y-%m-%d")
                    }
                    
                    messages.append(message_info)
                
                # Log search activity
                await self.log_activity("search_messages", {
                    "query": query,
                    "sort": sort,
                    "sort_dir": sort_dir,
                    "results_count": len(messages)
                })
                
                return {
                    "success": True,
                    "data": messages,
                    "total": len(messages),
                    "query": query
                }
            else:
                return result
                
        except Exception as e:
            logger.error(f"Failed to search Slack messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Analytics and Stats
    async def get_workspace_stats(self) -> Dict[str, Any]:
        """Get workspace statistics"""
        try:
            await self._ensure_initialized()
            
            # Get basic counts
            users_result = await self.get_users(limit=1000)
            channels_result = await self.get_channels()
            
            # Calculate stats
            total_users = len(users_result.get("data", []))
            total_channels = len(channels_result.get("data", []))
            total_bots = len([u for u in users_result.get("data", []) if u.get("is_bot", False)])
            active_users = len([u for u in users_result.get("data", []) if u.get("presence") == "active"])
            
            public_channels = len([c for c in channels_result.get("data", []) if not c.get("is_private", True) and not c.get("is_im", False) and not c.get("is_mpim", False)])
            private_channels = len([c for c in channels_result.get("data", []) if c.get("is_private", True) and not c.get("is_im", False) and not c.get("is_mpim", False)])
            direct_messages = len([c for c in channels_result.get("data", []) if c.get("is_im", False)])
            
            return {
                "success": True,
                "data": {
                    "users": {
                        "total": total_users,
                        "active": active_users,
                        "bots": total_bots,
                        "humans": total_users - total_bots
                    },
                    "channels": {
                        "total": total_channels,
                        "public": public_channels,
                        "private": private_channels,
                        "direct_messages": direct_messages
                    },
                    "engagement": {
                        "active_rate": total_users > 0 and (active_users / total_users) or 0,
                        "bot_ratio": total_users > 0 and (total_bots / total_users) or 0
                    }
                }
            }
            
        except Exception as e:
            logger.error(f"Failed to get Slack workspace stats: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    # Caching methods
    async def cache_users(self, users: List[Dict[str, Any]]) -> bool:
        """Cache Slack user data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS slack_users_cache (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        user_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(user_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_slack_users_user_id ON slack_users_cache(user_id);
                """)
                
                # Update cache
                for user in users:
                    await conn.execute("""
                        INSERT INTO slack_users_cache 
                        (user_id, user_data)
                        VALUES ($1, $2)
                        ON CONFLICT (user_id)
                        DO UPDATE SET 
                            user_data = EXCLUDED.user_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, user["id"], json.dumps(user))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Slack users: {e}")
            return False
    
    async def cache_channels(self, channels: List[Dict[str, Any]]) -> bool:
        """Cache Slack channel data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS slack_channels_cache (
                        id SERIAL PRIMARY KEY,
                        channel_id VARCHAR(255) NOT NULL,
                        channel_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(channel_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_slack_channels_channel_id ON slack_channels_cache(channel_id);
                """)
                
                # Update cache
                for channel in channels:
                    await conn.execute("""
                        INSERT INTO slack_channels_cache 
                        (channel_id, channel_data)
                        VALUES ($1, $2)
                        ON CONFLICT (channel_id)
                        DO UPDATE SET 
                            channel_data = EXCLUDED.channel_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, channel["id"], json.dumps(channel))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Slack channels: {e}")
            return False
    
    async def cache_messages(self, channel_id: str, messages: List[Dict[str, Any]]) -> bool:
        """Cache Slack message data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS slack_messages_cache (
                        id SERIAL PRIMARY KEY,
                        channel_id VARCHAR(255) NOT NULL,
                        message_id VARCHAR(255) NOT NULL,
                        message_data JSONB,
                        created_at TIMESTAMP WITH TIME ZONE,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(channel_id, message_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_slack_messages_channel_id ON slack_messages_cache(channel_id);
                    CREATE INDEX IF NOT EXISTS idx_slack_messages_message_id ON slack_messages_cache(message_id);
                    CREATE INDEX IF NOT EXISTS idx_slack_messages_created_at ON slack_messages_cache(created_at);
                """)
                
                # Update cache
                for message in messages:
                    created_at = None
                    try:
                        created_at = datetime.fromisoformat(message.get("time", "").replace('Z', '+00:00'))
                    except:
                        pass
                    
                    await conn.execute("""
                        INSERT INTO slack_messages_cache 
                        (channel_id, message_id, message_data, created_at)
                        VALUES ($1, $2, $3, $4)
                        ON CONFLICT (channel_id, message_id)
                        DO UPDATE SET 
                            message_data = EXCLUDED.message_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, channel_id, message["id"], json.dumps(message), created_at)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Slack messages: {e}")
            return False
    
    async def cache_files(self, files: List[Dict[str, Any]]) -> bool:
        """Cache Slack file data"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create cache table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS slack_files_cache (
                        id SERIAL PRIMARY KEY,
                        file_id VARCHAR(255) NOT NULL,
                        file_data JSONB,
                        updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
                        UNIQUE(file_id)
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_slack_files_file_id ON slack_files_cache(file_id);
                """)
                
                # Update cache
                for file in files:
                    await conn.execute("""
                        INSERT INTO slack_files_cache 
                        (file_id, file_data)
                        VALUES ($1, $2)
                        ON CONFLICT (file_id)
                        DO UPDATE SET 
                            file_data = EXCLUDED.file_data,
                            updated_at = CURRENT_TIMESTAMP
                    """, file["id"], json.dumps(file))
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to cache Slack files: {e}")
            return False
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Slack activity"""
        try:
            async with self.db_pool.acquire() as conn:
                # Create activity log table if it doesn't exist
                await conn.execute("""
                    CREATE TABLE IF NOT EXISTS slack_activity_logs (
                        id SERIAL PRIMARY KEY,
                        user_id VARCHAR(255) NOT NULL,
                        action VARCHAR(255) NOT NULL,
                        action_details JSONB,
                        status VARCHAR(50),
                        error_message TEXT,
                        created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
                    );
                    
                    CREATE INDEX IF NOT EXISTS idx_slack_activity_user_id ON slack_activity_logs(user_id);
                    CREATE INDEX IF NOT EXISTS idx_slack_activity_action ON slack_activity_logs(action);
                """)
                
                await conn.execute("""
                    INSERT INTO slack_activity_logs 
                    (user_id, action, action_details, status, error_message)
                    VALUES ($1, $2, $3, $4, $5)
                """, self.user_id, action, json.dumps(details or {}), status, error_message)
        
            return True
            
        except Exception as e:
            logger.error(f"Failed to log Slack activity: {e}")
            return False