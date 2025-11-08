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

class SlackEnhancedService:
    """Comprehensive Slack API Service"""
    
    def __init__(self, user_id: str):
        self.user_id = user_id
        self.access_token = None
        self.team_id = None
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
                self.team_id = tokens.get("team_id")
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
    
    async def get_user_info(self, user_id: str = None) -> Dict[str, Any]:
        """Get user information"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            target_user = user_id or "me"
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/users.info",
                    headers=headers,
                    params={"user": target_user}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    user_data = data.get("user", {})
                    return {
                        "id": user_data.get("id"),
                        "name": user_data.get("name"),
                        "real_name": user_data.get("real_name"),
                        "display_name": user_data.get("profile", {}).get("display_name"),
                        "email": user_data.get("profile", {}).get("email"),
                        "avatar": user_data.get("profile", {}).get("image_512"),
                        "is_admin": user_data.get("is_admin"),
                        "is_owner": user_data.get("is_owner"),
                        "team_id": user_data.get("team_id"),
                        "presence": user_data.get("presence")
                    }
                else:
                    return {"error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to get Slack user info: {e}")
            return {"error": str(e)}
    
    async def get_channels(self, types: List[str] = None) -> Dict[str, Any]:
        """Get Slack channels"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Get different channel types
            channel_types = types or ["public_channel", "private_channel", "mpim", "im"]
            all_channels = []
            
            async with httpx.AsyncClient() as client:
                for channel_type in channel_types:
                    endpoint = "conversations.list"
                    params = {"types": channel_type}
                    
                    response = await client.get(
                        f"{SLACK_API_BASE}/{endpoint}",
                        headers=headers,
                        params=params
                    )
                    response.raise_for_status()
                    
                    data = response.json()
                    
                    if data.get("ok"):
                        channels = data.get("channels", [])
                        for channel in channels:
                            all_channels.append({
                                "id": channel.get("id"),
                                "name": channel.get("name"),
                                "type": self._get_channel_type(channel),
                                "topic": channel.get("topic", {}).get("value"),
                                "purpose": channel.get("purpose", {}).get("value"),
                                "created": channel.get("created"),
                                "creator": channel.get("creator"),
                                "is_archived": channel.get("is_archived"),
                                "is_general": channel.get("is_general"),
                                "is_private": channel.get("is_private"),
                                "member_count": channel.get("num_members", 0),
                                "last_read": channel.get("last_read"),
                                "latest": channel.get("latest"),
                                "unread_count": channel.get("unread_count_display", 0),
                                "team_id": channel.get("team_id")
                            })
            
            # Cache channels
            from db_oauth_slack import cache_slack_channels
            await cache_slack_channels(self.db_pool, self.user_id, self.team_id, all_channels)
            
            return {
                "success": True,
                "data": all_channels
            }
            
        except Exception as e:
            logger.error(f"Failed to get Slack channels: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_messages(self, channel_id: str, limit: int = 50, 
                         oldest: str = None, latest: str = None) -> Dict[str, Any]:
        """Get messages from a channel"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "channel": channel_id,
                "limit": limit
            }
            
            if oldest:
                params["oldest"] = oldest
            if latest:
                params["latest"] = latest
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/conversations.history",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    messages = data.get("messages", [])
                    processed_messages = []
                    
                    for msg in messages:
                        # Get user info for message author
                        user_info = await self.get_user_info(msg.get("user"))
                        
                        processed_messages.append({
                            "id": msg.get("ts"),
                            "user_id": msg.get("user"),
                            "user_name": user_info.get("real_name", "Unknown"),
                            "text": msg.get("text"),
                            "type": msg.get("type", "message"),
                            "subtype": msg.get("subtype"),
                            "channel_id": channel_id,
                            "timestamp": msg.get("ts"),
                            "thread_ts": msg.get("thread_ts"),
                            "reply_count": msg.get("reply_count", 0),
                            "has_files": len(msg.get("files", [])) > 0,
                            "file_count": len(msg.get("files", [])),
                            "reactions": msg.get("reactions", []),
                            "is_edited": "edited" in msg,
                            "edited_timestamp": msg.get("edited", {}).get("ts") if "edited" in msg else None
                        })
                    
                    return {
                        "success": True,
                        "data": processed_messages,
                        "has_more": data.get("has_more", False),
                        "pin_count": data.get("pin_count", 0)
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to get Slack messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def send_message(self, channel_id: str, text: str, thread_ts: str = None,
                          blocks: List[Dict[str, Any]] = None, attachments: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Send message to channel"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            payload = {
                "channel": channel_id,
                "text": text
            }
            
            if thread_ts:
                payload["thread_ts"] = thread_ts
            if blocks:
                payload["blocks"] = blocks
            if attachments:
                payload["attachments"] = attachments
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/chat.postMessage",
                    headers=headers,
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    message_data = data.get("message", {})
                    return {
                        "success": True,
                        "data": {
                            "ts": message_data.get("ts"),
                            "channel": channel_id,
                            "text": message_data.get("text"),
                            "message_id": message_data.get("ts")
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to send Slack message: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_files(self, user_id: str = None, channel_id: str = None, 
                       types: str = "all", limit: int = 50) -> Dict[str, Any]:
        """Get files from Slack"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "count": limit
            }
            
            if user_id:
                params["user"] = user_id
            if channel_id:
                params["channel"] = channel_id
            if types != "all":
                params["types"] = types
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/files.list",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    files = data.get("files", [])
                    processed_files = []
                    
                    for file in files:
                        processed_files.append({
                            "id": file.get("id"),
                            "name": file.get("name"),
                            "title": file.get("title"),
                            "mimetype": file.get("mimetype"),
                            "filetype": file.get("filetype"),
                            "size": file.get("size"),
                            "url_private": file.get("url_private"),
                            "url_private_download": file.get("url_private_download"),
                            "permalink": file.get("permalink"),
                            "user_id": file.get("user"),
                            "username": file.get("username"),
                            "channel_ids": file.get("channels", []),
                            "is_public": file.get("is_public"),
                            "timestamp": file.get("timestamp"),
                            "created": file.get("created"),
                            "has_expiration": file.get("has_expiration"),
                            "expires": file.get("expires"),
                            "editable": file.get("editable"),
                            "preview": file.get("preview"),
                            "thumb_64": file.get("thumb_64"),
                            "thumb_80": file.get("thumb_80"),
                            "thumb_360": file.get("thumb_360"),
                            "thumb_360_w": file.get("thumb_360_w"),
                            "thumb_360_h": file.get("thumb_360_h"),
                            "original_w": file.get("original_w"),
                            "original_h": file.get("original_h")
                        })
                    
                    return {
                        "success": True,
                        "data": processed_files,
                        "total_files": len(processed_files)
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to get Slack files: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def search_messages(self, query: str, count: int = 50, sort: str = "timestamp_desc",
                           channel_id: str = None) -> Dict[str, Any]:
        """Search messages in Slack"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "query": query,
                "count": count,
                "sort": sort
            }
            
            if channel_id:
                params["channel"] = channel_id
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/search.messages",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    messages = data.get("messages", {}).get("matches", [])
                    processed_messages = []
                    
                    for msg in messages:
                        processed_messages.append({
                            "id": msg.get("ts"),
                            "user_id": msg.get("user"),
                            "username": msg.get("username"),
                            "text": msg.get("text"),
                            "type": msg.get("type", "message"),
                            "channel_id": msg.get("channel", {}).get("id"),
                            "channel_name": msg.get("channel", {}).get("name"),
                            "timestamp": msg.get("ts"),
                            "score": msg.get("score"),
                            "permalink": msg.get("permalink")
                        })
                    
                    return {
                        "success": True,
                        "data": processed_messages,
                        "total_found": len(processed_messages)
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to search Slack messages: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_reactions(self, channel_id: str, timestamp: str) -> Dict[str, Any]:
        """Get reactions for a message"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "channel": channel_id,
                "timestamp": timestamp,
                "full": "true"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/reactions.get",
                    headers=headers,
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "data": data.get("message", {})
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to get Slack reactions: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def add_reaction(self, channel_id: str, timestamp: str, name: str) -> Dict[str, Any]:
        """Add reaction to message"""
        try:
            await self._ensure_initialized()
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            params = {
                "channel": channel_id,
                "timestamp": timestamp,
                "name": name
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/reactions.add",
                    headers=headers,
                    data=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Reaction {name} added successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to add Slack reaction: {e}")
            return {
                "success": False,
                "error": str(e)
            }
    
    def _get_channel_type(self, channel: Dict[str, Any]) -> str:
        """Determine channel type from channel data"""
        if channel.get("is_im"):
            return "dm"
        elif channel.get("is_mpim"):
            return "group_dm"
        elif channel.get("is_private"):
            return "private"
        else:
            return "public"
    
    async def log_activity(self, action: str, details: Dict[str, Any] = None, 
                         status: str = "success", error_message: str = None):
        """Log Slack activity"""
        try:
            from db_oauth_slack import log_slack_activity
            await log_slack_activity(
                self.db_pool, self.user_id, action,
                self.team_id, details=details, status=status, error_message=error_message
            )
            return True
        except Exception as e:
            logger.error(f"Failed to log Slack activity: {e}")
            return False