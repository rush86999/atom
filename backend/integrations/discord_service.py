"""
Discord Service for ATOM Platform
Provides comprehensive Discord communication integration functionality
"""

from datetime import datetime
import logging
import os
from typing import Any, Dict, List, Optional
from fastapi import HTTPException
import httpx

logger = logging.getLogger(__name__)

class DiscordService:
    def __init__(self):
        self.client_id = os.getenv("DISCORD_CLIENT_ID")
        self.client_secret = os.getenv("DISCORD_CLIENT_SECRET")
        self.bot_token = os.getenv("DISCORD_BOT_TOKEN")
        self.base_url = "https://discord.com/api/v10"
        self.auth_url = "https://discord.com/api/oauth2/authorize"
        self.token_url = "https://discord.com/api/oauth2/token"
        self.access_token = None
        self.client = httpx.AsyncClient(timeout=30.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self, access_token: str = None, use_bot_token: bool = False) -> Dict[str, str]:
        """Get headers for API requests"""
        if use_bot_token and self.bot_token:
            return {
                "Authorization": f"Bot {self.bot_token}",
                "Content-Type": "application/json"
            }
        
        token = access_token or self.access_token
        return {
            "Authorization": f"Bearer {token}",
            "Content-Type": "application/json"
        }

    def get_authorization_url(
        self,
        redirect_uri: str,
        scope: str = "identify guilds",
        state: str = None
    ) -> str:
        """Generate OAuth authorization URL"""
        params = {
            "client_id": self.client_id,
            "response_type": "code",
            "redirect_uri": redirect_uri,
            "scope": scope
        }
        if state:
            params["state"] = state
        
        query_string = "&".join([f"{k}={v}" for k, v in params.items()])
        return f"{self.auth_url}?{query_string}"

    async def exchange_token(self, code: str, redirect_uri: str) -> Dict[str, Any]:
        """Exchange authorization code for access token"""
        try:
            data = {
                "grant_type": "authorization_code",
                "code": code,
                "redirect_uri": redirect_uri
            }
            
            auth = (self.client_id, self.client_secret)
            headers = {"Content-Type": "application/x-www-form-urlencoded"}
            
            response = await self.client.post(
                self.token_url,
                data=data,
                auth=auth,
                headers=headers
            )
            response.raise_for_status()
            
            token_data = response.json()
            self.access_token = token_data.get("access_token")
            
            return token_data
        except httpx.HTTPError as e:
            logger.error(f"Discord token exchange failed: {e}")
            raise HTTPException(
                status_code=400, 
                detail=f"Token exchange failed: {str(e)}"
            )

    async def get_current_user(self, access_token: str = None) -> Dict[str, Any]:
        """Get current user information"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            
            response = await self.client.get(
                f"{self.base_url}/users/@me",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get current user: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get user info: {str(e)}"
            )

    async def get_user_guilds(
        self,
        access_token: str = None,
        limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get guilds (servers) the user is a member of"""
        try:
            token = access_token or self.access_token
            if not token:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers(token)
            params = {"limit": limit}
            
            response = await self.client.get(
                f"{self.base_url}/users/@me/guilds",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get user guilds: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get guilds: {str(e)}"
            )

    async def get_guild_channels(
        self,
        guild_id: str,
        use_bot_token: bool = True,
        access_token: str = None
    ) -> List[Dict[str, Any]]:
        """Get channels in a guild"""
        try:
            headers = self._get_headers(access_token=access_token, use_bot_token=use_bot_token)
            
            response = await self.client.get(
                f"{self.base_url}/guilds/{guild_id}/channels",
                headers=headers
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get guild channels: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get channels: {str(e)}"
            )

    async def send_message(
        self,
        channel_id: str,
        content: str,
        use_bot_token: bool = True,
        embeds: List[Dict[str, Any]] = None,
        access_token: str = None
    ) -> Dict[str, Any]:
        """Send a message to a channel"""
        try:
            headers = self._get_headers(access_token=access_token, use_bot_token=use_bot_token)
            
            payload = {"content": content}
            if embeds:
                payload["embeds"] = embeds
            
            response = await self.client.post(
                f"{self.base_url}/channels/{channel_id}/messages",
                headers=headers,
                json=payload
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to send message: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to send message: {str(e)}"
            )

    async def get_channel_messages(
        self,
        channel_id: str,
        limit: int = 50,
        use_bot_token: bool = True,
        access_token: str = None
    ) -> List[Dict[str, Any]]:
        """Get messages from a channel"""
        try:
            headers = self._get_headers(access_token=access_token, use_bot_token=use_bot_token)
            params = {"limit": limit}
            
            response = await self.client.get(
                f"{self.base_url}/channels/{channel_id}/messages",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get messages: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get messages: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Discord service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "discord",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "discord",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

# Singleton instance
discord_service = DiscordService()

def get_discord_service() -> DiscordService:
    """Get Discord service instance"""
    return discord_service
