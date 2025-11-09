#!/usr/bin/env python3
"""
Enhanced Slack Service
Provides improved Slack API integration with comprehensive error handling and monitoring
"""

import os
import json
import logging
import httpx
from typing import Dict, Any, Optional, List
from datetime import datetime, timezone
from asyncpg import Pool

from enhanced_integration_service import EnhancedIntegrationService

logger = logging.getLogger(__name__)

class EnhancedSlackService(EnhancedIntegrationService):
    """Enhanced Slack API Service with comprehensive monitoring"""
    
    def __init__(self, user_id: str):
        super().__init__("Slack", user_id)
        self.api_base = "https://slack.com/api"
        self.bot_token = None
    
    def get_api_base_url(self) -> str:
        return self.api_base
    
    async def initialize(self, db_pool: Pool) -> bool:
        """Initialize Slack service with database pool"""
        try:
            from db_oauth_slack import get_user_slack_tokens
            
            self.db_pool = db_pool
            tokens = await get_user_slack_tokens(db_pool, self.user_id)
            
            if tokens and tokens.get("access_token"):
                self.access_token = tokens["access_token"]
                self.bot_token = tokens.get("bot_token")
                self.refresh_token = tokens.get("refresh_token")
                self._initialized = True
                self.status.status = "active"
                logger.info(f"Slack service initialized for user {self.user_id}")
                return True
            else:
                self.status.status = "inactive"
                self.status.error_message = "No Slack tokens found"
                logger.warning(f"No Slack tokens found for user {self.user_id}")
                return False
                
        except Exception as e:
            self.status.status = "error"
            self.status.error_message = str(e)
            logger.error(f"Failed to initialize Slack service: {e}")
            return False
    
    def get_auth_headers(self) -> Dict[str, str]:
        """Get Slack API headers with authentication"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.access_token}"
        }
        return headers
    
    def get_bot_headers(self) -> Dict[str, str]:
        """Get Slack API headers for bot operations"""
        headers = {
            "Content-Type": "application/json",
            "Authorization": f"Bearer {self.bot_token}"
        }
        return headers
    
    async def refresh_access_token(self) -> bool:
        """Refresh Slack access token"""
        try:
            refresh_url = "https://slack.com/api/oauth.v2.access"
            
            data = {
                "grant_type": "refresh_token",
                "client_id": os.getenv("SLACK_CLIENT_ID"),
                "client_secret": os.getenv("SLACK_CLIENT_SECRET"),
                "refresh_token": self.refresh_token
            }
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(refresh_url, data=data)
                response.raise_for_status()
                
                token_data = response.json()
                
                if token_data.get("ok"):
                    auth_info = token_data.get("authed_user", {})
                    self.access_token = auth_info.get("access_token")
                    if auth_info.get("refresh_token"):
                        self.refresh_token = auth_info.get("refresh_token")
                    
                    # Update bot token if available
                    if token_data.get("access_token"):
                        self.bot_token = token_data.get("access_token")
                    
                    # Update in database
                    from db_oauth_slack import refresh_slack_tokens
                    await refresh_slack_tokens(self.db_pool, self.user_id, token_data)
                    
                    logger.info("Slack token refreshed successfully")
                    return True
                else:
                    logger.error(f"Slack token refresh failed: {token_data.get('error')}")
                    return False
                
        except Exception as e:
            logger.error(f"Failed to refresh Slack token: {e}")
            self.status.error_message = f"Token refresh failed: {e}"
            return False
    
    def _get_health_check_endpoint(self) -> Optional[str]:
        return "/auth.test"
    
    # Enhanced Team Management
    async def get_team_info(self) -> Dict[str, Any]:
        """Get current team information"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("GET", "/team.info")
            
        except Exception as e:
            logger.error(f"Failed to get Slack team info: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_user_profile(self, user_id: str = None) -> Dict[str, Any]:
        """Get user profile information"""
        try:
            await self._ensure_initialized()
            
            params = {}
            if user_id:
                params["user"] = user_id
            
            return await self._make_request("GET", "/users.profile.get", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack user profile: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_users_list(self, limit: int = 100, cursor: str = None) -> Dict[str, Any]:
        """Get list of users in the workspace"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 1000)}
            if cursor:
                params["cursor"] = cursor
            
            return await self._make_request("GET", "/users.list", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack users list: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Channel Management
    async def get_channels_list(self, types: str = "public_channel,private_channel", 
                               limit: int = 100, cursor: str = None) -> Dict[str, Any]:
        """Get list of channels"""
        try:
            await self._ensure_initialized()
            
            params = {
                "types": types,
                "limit": min(limit, 1000)
            }
            if cursor:
                params["cursor"] = cursor
            
            return await self._make_request("GET", "/conversations.list", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack channels list: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_channel_info(self, channel_id: str) -> Dict[str, Any]:
        """Get information about a specific channel"""
        try:
            await self._ensure_initialized()
            
            params = {"channel": channel_id}
            return await self._make_request("GET", "/conversations.info", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack channel info for {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def join_channel(self, channel_id: str) -> Dict[str, Any]:
        """Join a channel"""
        try:
            await self._ensure_initialized()
            
            data = {"channel": channel_id}
            return await self._make_request("POST", "/conversations.join", data=data)
            
        except Exception as e:
            logger.error(f"Failed to join Slack channel {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def leave_channel(self, channel_id: str) -> Dict[str, Any]:
        """Leave a channel"""
        try:
            await self._ensure_initialized()
            
            data = {"channel": channel_id}
            return await self._make_request("POST", "/conversations.leave", data=data)
            
        except Exception as e:
            logger.error(f"Failed to leave Slack channel {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Message Management
    async def send_message(self, channel_id: str, text: str, 
                          blocks: List[Dict[str, Any]] = None,
                          thread_ts: str = None) -> Dict[str, Any]:
        """Send a message to a channel"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "text": text
            }
            
            if blocks:
                data["blocks"] = blocks
            if thread_ts:
                data["thread_ts"] = thread_ts
            
            return await self._make_request("POST", "/chat.postMessage", data=data)
            
        except Exception as e:
            logger.error(f"Failed to send Slack message to {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def update_message(self, channel_id: str, ts: str, text: str,
                            blocks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Update a message"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "ts": ts,
                "text": text
            }
            
            if blocks:
                data["blocks"] = blocks
            
            return await self._make_request("POST", "/chat.update", data=data)
            
        except Exception as e:
            logger.error(f"Failed to update Slack message {ts} in {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_message(self, channel_id: str, ts: str) -> Dict[str, Any]:
        """Delete a message"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "ts": ts
            }
            
            return await self._make_request("POST", "/chat.delete", data=data)
            
        except Exception as e:
            logger.error(f"Failed to delete Slack message {ts} from {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_messages(self, channel_id: str, limit: int = 100, 
                          cursor: str = None, oldest: str = None,
                          latest: str = None) -> Dict[str, Any]:
        """Get messages from a channel"""
        try:
            await self._ensure_initialized()
            
            params = {
                "channel": channel_id,
                "limit": min(limit, 1000)
            }
            
            if cursor:
                params["cursor"] = cursor
            if oldest:
                params["oldest"] = oldest
            if latest:
                params["latest"] = latest
            
            return await self._make_request("GET", "/conversations.history", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack messages from {channel_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced File Management
    async def upload_file(self, file_path: str, channels: List[str], 
                         title: str = None, initial_comment: str = None) -> Dict[str, Any]:
        """Upload a file to Slack"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channels": ",".join(channels)
            }
            
            if title:
                data["title"] = title
            if initial_comment:
                data["initial_comment"] = initial_comment
            
            headers = self.get_auth_headers()
            headers.pop("Content-Type")  # Remove for multipart upload
            
            with open(file_path, 'rb') as file:
                files = {"file": file}
                async with httpx.AsyncClient(timeout=60.0) as client:
                    response = await client.post(
                        f"{self.api_base}/files.upload",
                        headers=headers,
                        data=data,
                        files=files
                    )
                    response.raise_for_status()
                    return {
                        "success": True,
                        "data": response.json()
                    }
                    
        except Exception as e:
            logger.error(f"Failed to upload file to Slack: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_files_list(self, limit: int = 100, page: int = 1) -> Dict[str, Any]:
        """Get list of uploaded files"""
        try:
            await self._ensure_initialized()
            
            params = {
                "limit": min(limit, 1000),
                "page": page
            }
            
            return await self._make_request("GET", "/files.list", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack files list: {e}")
            return {"success": False, "error": str(e)}
    
    async def delete_file(self, file_id: str) -> Dict[str, Any]:
        """Delete a file"""
        try:
            await self._ensure_initialized()
            
            data = {"file": file_id}
            return await self._make_request("POST", "/files.delete", data=data)
            
        except Exception as e:
            logger.error(f"Failed to delete Slack file {file_id}: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Reactions Management
    async def add_reaction(self, channel_id: str, timestamp: str, name: str) -> Dict[str, Any]:
        """Add a reaction to a message"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "timestamp": timestamp,
                "name": name
            }
            
            return await self._make_request("POST", "/reactions.add", data=data)
            
        except Exception as e:
            logger.error(f"Failed to add Slack reaction: {e}")
            return {"success": False, "error": str(e)}
    
    async def remove_reaction(self, channel_id: str, timestamp: str, name: str) -> Dict[str, Any]:
        """Remove a reaction from a message"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "timestamp": timestamp,
                "name": name
            }
            
            return await self._make_request("POST", "/reactions.remove", data=data)
            
        except Exception as e:
            logger.error(f"Failed to remove Slack reaction: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_reactions(self, channel_id: str, timestamp: str) -> Dict[str, Any]:
        """Get reactions for a message"""
        try:
            await self._ensure_initialized()
            
            params = {
                "channel": channel_id,
                "timestamp": timestamp
            }
            
            return await self._make_request("GET", "/reactions.get", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack reactions: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Scheduled Messages
    async def schedule_message(self, channel_id: str, text: str, post_at: int,
                             blocks: List[Dict[str, Any]] = None) -> Dict[str, Any]:
        """Schedule a message to be sent later"""
        try:
            await self._ensure_initialized()
            
            data = {
                "channel": channel_id,
                "text": text,
                "post_at": post_at
            }
            
            if blocks:
                data["blocks"] = blocks
            
            return await self._make_request("POST", "/chat.scheduleMessage", data=data)
            
        except Exception as e:
            logger.error(f"Failed to schedule Slack message: {e}")
            return {"success": False, "error": str(e)}
    
    async def get_scheduled_messages(self, channel_id: str = None, 
                                    latest: str = None, oldest: str = None,
                                    limit: int = 100) -> Dict[str, Any]:
        """Get list of scheduled messages"""
        try:
            await self._ensure_initialized()
            
            params = {"limit": min(limit, 1000)}
            
            if channel_id:
                params["channel"] = channel_id
            if latest:
                params["latest"] = latest
            if oldest:
                params["oldest"] = oldest
            
            return await self._make_request("GET", "/chat.scheduledMessages.list", params=params)
            
        except Exception as e:
            logger.error(f"Failed to get Slack scheduled messages: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Webhooks
    async def create_webhook(self, name: str, response_url: str) -> Dict[str, Any]:
        """Create a response webhook"""
        try:
            await self._ensure_initialized()
            
            data = {
                "name": name,
                "response_url": response_url
            }
            
            return await self._make_request("POST", "/hooks.create", data=data)
            
        except Exception as e:
            logger.error(f"Failed to create Slack webhook: {e}")
            return {"success": False, "error": str(e)}
    
    async def send_webhook_response(self, response_url: str, text: str,
                                  blocks: List[Dict[str, Any]] = None,
                                  response_type: str = "in_channel") -> Dict[str, Any]:
        """Send a response via webhook"""
        try:
            data = {
                "text": text,
                "response_type": response_type
            }
            
            if blocks:
                data["blocks"] = blocks
            
            async with httpx.AsyncClient(timeout=30.0) as client:
                response = await client.post(response_url, json=data)
                response.raise_for_status()
                return {
                    "success": True,
                    "data": response.json()
                }
                
        except Exception as e:
            logger.error(f"Failed to send Slack webhook response: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Search
    async def search_messages(self, query: str, sort: str = "timestamp",
                            sort_dir: str = "desc", count: int = 100) -> Dict[str, Any]:
        """Search for messages"""
        try:
            await self._ensure_initialized()
            
            params = {
                "query": query,
                "sort": sort,
                "sort_dir": sort_dir,
                "count": min(count, 1000)
            }
            
            return await self._make_request("GET", "/search.messages", params=params)
            
        except Exception as e:
            logger.error(f"Failed to search Slack messages: {e}")
            return {"success": False, "error": str(e)}
    
    async def search_files(self, query: str, sort: str = "timestamp",
                         sort_dir: str = "desc", count: int = 100) -> Dict[str, Any]:
        """Search for files"""
        try:
            await self._ensure_initialized()
            
            params = {
                "query": query,
                "sort": sort,
                "sort_dir": sort_dir,
                "count": min(count, 1000)
            }
            
            return await self._make_request("GET", "/search.files", params=params)
            
        except Exception as e:
            logger.error(f"Failed to search Slack files: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced Real Time Messaging (RTM)
    async def start_rtm_session(self) -> Dict[str, Any]:
        """Start a Real Time Messaging session"""
        try:
            await self._ensure_initialized()
            
            return await self._make_request("GET", "/rtm.connect")
            
        except Exception as e:
            logger.error(f"Failed to start Slack RTM session: {e}")
            return {"success": False, "error": str(e)}
    
    # Enhanced User Presence
    async def set_presence(self, presence: str = "auto") -> Dict[str, Any]:
        """Set user presence"""
        try:
            await self._ensure_initialized()
            
            data = {"presence": presence}
            return await self._make_request("POST", "/users.setPresence", data=data)
            
        except Exception as e:
            logger.error(f"Failed to set Slack presence: {e}")
            return {"success": False, "error": str(e)}