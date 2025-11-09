#!/usr/bin/env python3
"""
Enhanced Slack Service
Complete Slack API service with advanced operations
"""

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
    """Enhanced Slack API Service with complete functionality"""
    
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
            
            self.db_pool = db_pool
            tokens = await get_user_slack_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self.team_id = tokens.get("team_id")
                self._initialized = True
                logger.info(f"Enhanced Slack service initialized for user {self.user_id}")
                return True
            else:
                logger.warning(f"No Slack tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to initialize enhanced Slack service: {e}")
            return False
    
    async def _ensure_initialized(self):
        """Ensure service is initialized"""
        if not self._initialized:
            raise Exception("Slack service not initialized. Call initialize() first.")
    
    def _get_headers(self) -> Dict[str, str]:
        """Get request headers with authorization"""
        return {
            "Authorization": f"Bearer {self.access_token}",
            "Content-Type": "application/json"
        }
    
    async def upload_file(self, file_data, channels: List[str], title: str = None, 
                         initial_comment: str = None) -> Dict[str, Any]:
        """Upload file to Slack"""
        try:
            await self._ensure_initialized()
            
            # Prepare form data
            files_data = {
                'file': (file_data.filename, file_data.read(), file_data.mimetype)
            }
            
            form_data = {}
            if channels:
                form_data['channels'] = ','.join(channels)
            if title:
                form_data['title'] = title
            if initial_comment:
                form_data['initial_comment'] = initial_comment
            
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/files.upload",
                    headers=headers,
                    files=files_data,
                    data=form_data
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    file_data = data.get("file", {})
                    return {
                        "success": True,
                        "data": {
                            "id": file_data.get("id"),
                            "name": file_data.get("name"),
                            "title": file_data.get("title"),
                            "mimetype": file_data.get("mimetype"),
                            "size": file_data.get("size"),
                            "url_private": file_data.get("url_private"),
                            "permalink": file_data.get("permalink"),
                            "channels": file_data.get("channels", [])
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to upload file to Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_file_download_url(self, file_id: str) -> Dict[str, Any]:
        """Get file download URL"""
        try:
            await self._ensure_initialized()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/files.sharedPublicURL",
                    headers=self._get_headers(),
                    json={"file": file_id}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    file_data = data.get("file", {})
                    return {
                        "success": True,
                        "data": {
                            "download_url": file_data.get("url_private_download"),
                            "permalink_public": file_data.get("permalink_public"),
                            "original_url": file_data.get("url_private")
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to get file download URL: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """Delete file from Slack"""
        try:
            await self._ensure_initialized()
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/files.delete",
                    headers=self._get_headers(),
                    json={"file": file_id}
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"File {file_id} deleted successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to delete file from Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def edit_message(self, channel_id: str, message_id: str, text: str) -> Dict[str, Any]:
        """Edit message in Slack"""
        try:
            await self._ensure_initialized()
            
            payload = {
                "channel": channel_id,
                "ts": message_id,
                "text": text
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/chat.update",
                    headers=self._get_headers(),
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
                            "text": message_data.get("text"),
                            "channel": channel_id,
                            "edited": True
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to edit message in Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_message(self, channel_id: str, message_id: str) -> Dict[str, Any]:
        """Delete message from Slack"""
        try:
            await self._ensure_initialized()
            
            payload = {
                "channel": channel_id,
                "ts": message_id
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/chat.delete",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Message {message_id} deleted successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to delete message from Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_reaction(self, channel_id: str, timestamp: str, name: str) -> Dict[str, Any]:
        """Remove reaction from message"""
        try:
            await self._ensure_initialized()
            
            params = {
                "channel": channel_id,
                "timestamp": timestamp,
                "name": name
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/reactions.remove",
                    headers={"Authorization": f"Bearer {self.access_token}"},
                    data=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Reaction {name} removed successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to remove reaction: {e}")
            return {"success": False, "error": str(e)}
    
    async def create_channel(self, name: str, is_private: bool = False, 
                           purpose: str = "") -> Dict[str, Any]:
        """Create new channel"""
        try:
            await self._ensure_initialized()
            
            payload = {
                "name": name,
                "is_private": is_private
            }
            
            if purpose:
                payload["purpose"] = purpose
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.create",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    channel_data = data.get("channel", {})
                    return {
                        "success": True,
                        "data": {
                            "id": channel_data.get("id"),
                            "name": channel_data.get("name"),
                            "name_normalized": channel_data.get("name_normalized"),
                            "is_private": channel_data.get("is_private"),
                            "purpose": channel_data.get("purpose", {}),
                            "created": channel_data.get("created"),
                            "creator": channel_data.get("creator")
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to create channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def join_channel(self, channel_id: str) -> Dict[str, Any]:
        """Join channel"""
        try:
            await self._ensure_initialized()
            
            payload = {"channel": channel_id}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.join",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    channel_data = data.get("channel", {})
                    return {
                        "success": True,
                        "data": {
                            "id": channel_data.get("id"),
                            "name": channel_data.get("name"),
                            "members": channel_data.get("members", [])
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to join channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def leave_channel(self, channel_id: str) -> Dict[str, Any]:
        """Leave channel"""
        try:
            await self._ensure_initialized()
            
            payload = {"channel": channel_id}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.leave",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Left channel {channel_id} successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to leave channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def archive_channel(self, channel_id: str) -> Dict[str, Any]:
        """Archive channel"""
        try:
            await self._ensure_initialized()
            
            payload = {"channel": channel_id}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.archive",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Channel {channel_id} archived successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to archive channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def unarchive_channel(self, channel_id: str) -> Dict[str, Any]:
        """Unarchive channel"""
        try:
            await self._ensure_initialized()
            
            payload = {"channel": channel_id}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.unarchive",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Channel {channel_id} unarchived successfully"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to unarchive channel: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_files(self, query: str, count: int = 50, 
                         sort: str = "timestamp_desc") -> Dict[str, Any]:
        """Search files in Slack"""
        try:
            await self._ensure_initialized()
            
            params = {
                "query": query,
                "count": count,
                "sort": sort
            }
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/search.files",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    files = data.get("files", {}).get("matches", [])
                    processed_files = []
                    
                    for file in files:
                        processed_files.append({
                            "id": file.get("id"),
                            "name": file.get("name"),
                            "title": file.get("title"),
                            "mimetype": file.get("mimetype"),
                            "filetype": file.get("filetype"),
                            "size": file.get("size"),
                            "permalink": file.get("permalink"),
                            "timestamp": file.get("timestamp"),
                            "user": file.get("user"),
                            "username": file.get("username"),
                            "channels": file.get("channels", [])
                        })
                    
                    return {
                        "success": True,
                        "data": processed_files,
                        "total_found": len(processed_files)
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to search files in Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_users(self, query: str) -> Dict[str, Any]:
        """Search users in Slack"""
        try:
            await self._ensure_initialized()
            
            # First get all users (Slack doesn't have a direct search users endpoint)
            users_result = await self.get_all_users()
            
            if not users_result.get("success"):
                return users_result
            
            users = users_result.get("data", [])
            query_lower = query.lower()
            
            # Filter users based on query
            matched_users = []
            for user in users:
                if (query_lower in user.get("name", "").lower() or 
                    query_lower in user.get("real_name", "").lower() or
                    query_lower in user.get("display_name", "").lower() or
                    query_lower in user.get("email", "").lower()):
                    matched_users.append(user)
            
            return {
                "success": True,
                "data": matched_users,
                "total_found": len(matched_users)
            }
            
        except Exception as e:
            logger.error(f"Failed to search users in Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_all_users(self) -> Dict[str, Any]:
        """Get all users from workspace"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": 1000}  # Get max number
            
            async with httpx.AsyncClient() as client:
                response = await client.get(
                    f"{SLACK_API_BASE}/users.list",
                    headers=self._get_headers(),
                    params=params
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    users = data.get("members", [])
                    processed_users = []
                    
                    for user in users:
                        processed_users.append({
                            "id": user.get("id"),
                            "name": user.get("name"),
                            "real_name": user.get("real_name"),
                            "display_name": user.get("profile", {}).get("display_name"),
                            "email": user.get("profile", {}).get("email"),
                            "avatar": user.get("profile", {}).get("image_512"),
                            "is_bot": user.get("is_bot"),
                            "is_admin": user.get("is_admin"),
                            "is_owner": user.get("is_owner"),
                            "presence": user.get("presence")
                        })
                    
                    return {
                        "success": True,
                        "data": processed_users
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to get users from Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def set_presence(self, presence: str) -> Dict[str, Any]:
        """Set user presence"""
        try:
            await self._ensure_initialized()
            
            payload = {"presence": presence}
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/users.setPresence",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": f"Presence set to {presence}"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to set user presence: {e}")
            return {"success": False, "error": str(e)}
    
    async def set_status(self, status_text: str = "", status_emoji: str = "", 
                        expiration: int = None) -> Dict[str, Any]:
        """Set user status"""
        try:
            await self._ensure_initialized()
            
            payload = {
                "profile": {}
            }
            
            if status_text:
                payload["profile"]["status_text"] = status_text
            if status_emoji:
                payload["profile"]["status_emoji"] = status_emoji
            if expiration:
                payload["profile"]["status_expiration"] = expiration
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/users.profile.set",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    profile = data.get("profile", {})
                    return {
                        "success": True,
                        "data": {
                            "status_text": profile.get("status_text"),
                            "status_emoji": profile.get("status_emoji"),
                            "status_expiration": profile.get("status_expiration")
                        }
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to set user status: {e}")
            return {"success": False, "error": str(e)}
    
    async def mark_conversation(self, channel_id: str, ts: str = None) -> Dict[str, Any]:
        """Mark conversation as read"""
        try:
            await self._ensure_initialized()
            
            payload = {"channel": channel_id}
            if ts:
                payload["ts"] = ts
            
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"{SLACK_API_BASE}/conversations.mark",
                    headers=self._get_headers(),
                    json=payload
                )
                response.raise_for_status()
                
                data = response.json()
                
                if data.get("ok"):
                    return {
                        "success": True,
                        "message": "Conversation marked as read"
                    }
                else:
                    return {"success": False, "error": data.get("error", "Unknown error")}
                    
        except Exception as e:
            logger.error(f"Failed to mark conversation: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_engagement_analytics(self, days: int = 30) -> Dict[str, Any]:
        """Get workspace engagement analytics"""
        try:
            await self._ensure_initialized()
            
            # This is a simplified implementation
            # In production, you'd use proper analytics endpoints or database queries
            
            analytics_data = {
                "period_days": days,
                "total_messages": 0,
                "active_users": 0,
                "total_files_shared": 0,
                "total_reactions": 0,
                "top_channels": [],
                "engagement_score": 0
            }
            
            # Get channels data
            channels_result = await self.get_channels()
            if channels_result.get("success"):
                analytics_data["total_channels"] = len(channels_result.get("data", []))
            
            # Get users data
            users_result = await self.get_all_users()
            if users_result.get("success"):
                users = users_result.get("data", [])
                analytics_data["total_users"] = len(users)
                analytics_data["active_users"] = len([u for u in users if u.get("presence") == "active"])
            
            return {
                "success": True,
                "data": analytics_data
            }
            
        except Exception as e:
            logger.error(f"Failed to get engagement analytics: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_channels(self) -> Dict[str, Any]:
        """Get channels (reuse from original service)"""
        try:
            from slack_enhanced_service import SlackEnhancedService as OriginalService
            
            original_service = OriginalService(self.user_id)
            await original_service.initialize(self.db_pool)
            
            return await original_service.get_channels()
            
        except Exception as e:
            logger.error(f"Failed to get channels: {e}")
            return {"success": False, "error": str(e)}