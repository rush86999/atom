"""
ATOM Microsoft Teams Service Implementation
Real Teams integration using Microsoft Graph API
"""

import os
import json
import httpx
import asyncio
import httpx
from datetime import datetime, timedelta
from typing import Dict, Any, List, Optional
from loguru import logger

class TeamsService:
    """Real Microsoft Teams service using Microsoft Graph API"""
    
    def __init__(self):
        self.service_name = "MicrosoftTeams"
        self._client = None
        self._access_token = None
        self._refresh_token = None
        self._token_expires = None
        
    async def get_client(self) -> httpx.AsyncClient:
        """Get or create authenticated HTTP client"""
        if not self._client or self._is_token_expired():
            await self._refresh_access_token()
            
        self._client = httpx.AsyncClient(
            base_url="https://graph.microsoft.com/v1.0",
            headers={
                "Authorization": f"Bearer {self._access_token}",
                "Content-Type": "application/json",
                "Accept": "application/json"
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
        """Refresh Microsoft access token"""
        try:
            client_id = os.getenv('MICROSOFT_CLIENT_ID')
            client_secret = os.getenv('MICROSOFT_CLIENT_SECRET')
            tenant_id = os.getenv('MICROSOFT_TENANT_ID', 'common')
            
            if not all([client_id, client_secret]):
                logger.error("Microsoft Teams: Missing OAuth credentials")
                return False

            # If we have a refresh token, use it
            if self._refresh_token:
                token_data = await self._exchange_refresh_token(
                    client_id, client_secret, self._refresh_token, tenant_id
                )
            else:
                # Get new tokens using client credentials
                token_data = await self._exchange_client_credentials(
                    client_id, client_secret, tenant_id
                )

            if token_data:
                self._access_token = token_data['access_token']
                self._refresh_token = token_data.get('refresh_token')
                
                # Set expiry time (default 1 hour if not specified)
                expires_in = token_data.get('expires_in', 3600)
                self._token_expires = datetime.utcnow() + timedelta(seconds=expires_in)
                
                logger.info("Microsoft Teams: Token refreshed successfully")
                return True
            else:
                logger.error("Microsoft Teams: Failed to refresh token")
                return False

        except Exception as e:
            logger.error(f"Microsoft Teams: Token refresh error: {e}")
            return False

    async def _exchange_refresh_token(self, client_id: str, client_secret: str, 
                                 refresh_token: str, tenant_id: str) -> Optional[Dict[str, Any]]:
        """Exchange refresh token for new access token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                    data={
                        "grant_type": "refresh_token",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "refresh_token": refresh_token,
                        "scope": "https://graph.microsoft.com/.default"
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Microsoft Teams: Refresh token error: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Microsoft Teams: Refresh token exception: {e}")
            return None

    async def _exchange_client_credentials(self, client_id: str, client_secret: str,
                                      tenant_id: str) -> Optional[Dict[str, Any]]:
        """Exchange client credentials for access token"""
        try:
            async with httpx.AsyncClient() as client:
                response = await client.post(
                    f"https://login.microsoftonline.com/{tenant_id}/oauth2/v2.0/token",
                    data={
                        "grant_type": "client_credentials",
                        "client_id": client_id,
                        "client_secret": client_secret,
                        "scope": "https://graph.microsoft.com/.default"
                    },
                    headers={
                        "Content-Type": "application/x-www-form-urlencoded"
                    },
                    timeout=30.0
                )
                
                if response.status_code == 200:
                    return response.json()
                else:
                    logger.error(f"Microsoft Teams: Client credentials error: {response.text}")
                    return None
                    
        except Exception as e:
            logger.error(f"Microsoft Teams: Client credentials exception: {e}")
            return None

    async def get_teams(self) -> Dict[str, Any]:
        """Get user's joined teams"""
        try:
            client = await self.get_client()
            
            response = await client.get("/me/joinedTeams")
            
            if response.status_code == 200:
                teams_data = response.json()
                
                # Transform to unified format
                teams = []
                for team in teams_data.get('value', []):
                    teams.append({
                        "id": team["id"],
                        "name": team["displayName"],
                        "description": team.get("description", ""),
                        "team_type": team.get("teamType", "Standard"),
                        "visibility": team.get("visibility", "Public"),
                        "archived": team.get("isArchived", False),
                        "member_count": team.get("membersCount", 0),
                        "web_url": team.get("webUrl", ""),
                        "created_at": team.get("createdDateTime"),
                        "updated_at": team.get("lastModifiedDateTime")
                    })
                
                logger.info(f"Microsoft Teams: Retrieved {len(teams)} teams")
                return {
                    "teams": teams,
                    "total_count": len(teams),
                    "retrieved_at": datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Microsoft Teams: Get teams error: {response.status_code} - {response.text}")
                return {"teams": [], "error": f"HTTP {response.status_code}", "retrieved_at": datetime.utcnow().isoformat()}
                
        except Exception as e:
            logger.error(f"Microsoft Teams: Get teams exception: {e}")
            return {"teams": [], "error": str(e), "retrieved_at": datetime.utcnow().isoformat()}

    async def get_channels(self, team_id: str) -> Dict[str, Any]:
        """Get channels for a specific team"""
        try:
            client = await self.get_client()
            
            response = await client.get(f"/teams/{team_id}/channels")
            
            if response.status_code == 200:
                channels_data = response.json()
                
                # Transform to unified format
                channels = []
                for channel in channels_data.get('value', []):
                    channels.append({
                        "id": channel["id"],
                        "name": channel["displayName"],
                        "description": channel.get("description", ""),
                        "team_id": team_id,
                        "type": channel.get("membershipType", "standard"),
                        "is_favorite": channel.get("isFavoriteByDefault", False),
                        "web_url": channel.get("webUrl", ""),
                        "created_at": channel.get("createdDateTime"),
                        "updated_at": channel.get("lastModifiedDateTime")
                    })
                
                logger.info(f"Microsoft Teams: Retrieved {len(channels)} channels for team {team_id}")
                return {
                    "channels": channels,
                    "team_id": team_id,
                    "total_count": len(channels),
                    "retrieved_at": datetime.utcnow().isoformat()
                }
            else:
                logger.error(f"Microsoft Teams: Get channels error: {response.status_code} - {response.text}")
                return {"channels": [], "error": f"HTTP {response.status_code}", "retrieved_at": datetime.utcnow().isoformat()}
                
        except Exception as e:
            logger.error(f"Microsoft Teams: Get channels exception: {e}")
            return {"channels": [], "error": str(e), "retrieved_at": datetime.utcnow().isoformat()}

    async def get_messages(self, channel_id: str, team_id: Optional[str] = None, 
                        limit: int = 50) -> Dict[str, Any]:
        """Get messages from a specific channel"""
        try:
            client = await self.get_client()
            
            # For channel messages, we need the channel and team ID
            if team_id:
                endpoint = f"/teams/{team_id}/channels/{channel_id}/messages"
            else:
                # Try to get messages from channel directly (works for some endpoints)
                endpoint = f"/chats/{channel_id}/messages"
            
            params = {
                "$top": str(limit),
                "$orderby": "createdDateTime desc"
            }
            
            response = await client.get(endpoint, params=params)
            
            if response.status_code == 200:
                messages_data = response.json()
                
                # Transform to unified Message format
                messages = []
                for message in messages_data.get('value', []):
                    # Extract content
                    content = ""
                    if message.get('body'):
                        content = message['body'].get('content', '')
                    
                    # Get attachments
                    attachments = []
                    if message.get('attachments'):
                        for attachment in message['attachments']:
                            attachments.append({
                                "id": attachment.get('id'),
                                "name": attachment.get('name'),
                                "url": attachment.get('contentUrl', ''),
                                "type": attachment.get('contentType', 'unknown'),
                                "size": attachment.get('size', 0)
                            })
                    
                    # Get sender info
                    sender_name = "Unknown"
                    if message.get('from') and message['from'].get('user'):
                        sender_name = message['from']['user'].get('displayName', 'Unknown')
                    
                    # Create message object
                    messages.append({
                        "id": message["id"],
                        "thread_id": message.get("replyToId", message["id"]),
                        "channel_id": channel_id,
                        "team_id": team_id,
                        "from": sender_name,
                        "subject": message.get("subject", ""),
                        "preview": content[:100] if len(content) > 100 else content,
                        "content": content,
                        "timestamp": message.get("createdDateTime"),
                        "updated_at": message.get("lastModifiedDateTime"),
                        "priority": "normal",
                        "unread": not message.get("lastModifiedDateTime"),  # Approximation
                        "status": "received",
                        "attachments": attachments,
                        "mentions": self._extract_mentions(message.get("body", {}).get("content", "")),
                        "reactions": self._extract_reactions(message.get("reactions", [])),
                        "reply_count": message.get("replyCount", 0),
                        "is_deleted": message.get("deletedDateTime") is not None,
                        "is_edited": message.get("lastModifiedDateTime") != message.get("createdDateTime")
                    })
                
                logger.info(f"Microsoft Teams: Retrieved {len(messages)} messages from channel {channel_id}")
                return {
                    "messages": messages,
                    "channel_id": channel_id,
                    "team_id": team_id,
                    "total_count": len(messages),
                    "retrieved_at": datetime.utcnow().isoformat(),
                    "has_more": messages_data.get("@odata.nextLink") is not None
                }
            else:
                logger.error(f"Microsoft Teams: Get messages error: {response.status_code} - {response.text}")
                return {"messages": [], "error": f"HTTP {response.status_code}", "retrieved_at": datetime.utcnow().isoformat()}
                
        except Exception as e:
            logger.error(f"Microsoft Teams: Get messages exception: {e}")
            return {"messages": [], "error": str(e), "retrieved_at": datetime.utcnow().isoformat()}

    async def send_message(self, channel_id: str, content: str, team_id: Optional[str] = None) -> Dict[str, Any]:
        """Send a message to a Teams channel"""
        try:
            client = await self.get_client()
            
            message_data = {
                "body": {
                    "content": content
                }
            }
            
            # Determine endpoint
            if team_id:
                endpoint = f"/teams/{team_id}/channels/{channel_id}/messages"
            else:
                endpoint = f"/chats/{channel_id}/messages"
            
            response = await client.post(endpoint, json=message_data)
            
            if response.status_code == 201:  # Created
                message_response = response.json()
                logger.info(f"Microsoft Teams: Message sent to channel {channel_id}")
                
                return {
                    "success": True,
                    "message_id": message_response.get("id"),
                    "channel_id": channel_id,
                    "team_id": team_id,
                    "content": content,
                    "sent_at": message_response.get("createdDateTime"),
                    "status": "sent"
                }
            else:
                logger.error(f"Microsoft Teams: Send message error: {response.status_code} - {response.text}")
                return {
                    "success": False,
                    "error": f"HTTP {response.status_code}",
                    "channel_id": channel_id,
                    "content": content
                }
                
        except Exception as e:
            logger.error(f"Microsoft Teams: Send message exception: {e}")
            return {
                "success": False,
                "error": str(e),
                "channel_id": channel_id,
                "content": content
            }

    async def get_user_info(self) -> Dict[str, Any]:
        """Get current user information"""
        try:
            client = await self.get_client()
            
            response = await client.get("/me")
            
            if response.status_code == 200:
                user_data = response.json()
                
                user_info = {
                    "id": user_data.get("id"),
                    "display_name": user_data.get("displayName"),
                    "email": user_data.get("mail"),
                    "user_principal_name": user_data.get("userPrincipalName"),
                    "job_title": user_data.get("jobTitle"),
                    "department": user_data.get("department"),
                    "office_location": user_data.get("officeLocation"),
                    "retrieved_at": datetime.utcnow().isoformat()
                }
                
                logger.info(f"Microsoft Teams: Retrieved user info for {user_info['display_name']}")
                return user_info
            else:
                logger.error(f"Microsoft Teams: Get user info error: {response.status_code} - {response.text}")
                return {"error": f"HTTP {response.status_code}", "retrieved_at": datetime.utcnow().isoformat()}
                
        except Exception as e:
            logger.error(f"Microsoft Teams: Get user info exception: {e}")
            return {"error": str(e), "retrieved_at": datetime.utcnow().isoformat()}

    def _extract_mentions(self, content: str) -> List[Dict[str, Any]]:
        """Extract @mentions from Teams message content"""
        mentions = []
        
        # Simple regex to find @mentions in HTML content
        import re
        mention_pattern = r'<at[^>]*>([^<]+)</at>'
        
        for match in re.finditer(mention_pattern, content):
            mentions.append({
                "text": match.group(1),
                "raw": match.group(0)
            })
        
        return mentions

    def _extract_reactions(self, reactions_data: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Extract reactions from Teams message"""
        reactions = {
            "like": 0,
            "heart": 0,
            "laugh": 0,
            "surprised": 0,
            "sad": 0,
            "angry": 0
        }
        
        for reaction in reactions_data:
            reaction_type = reaction.get("reactionType", "").lower()
            count = reaction.get("count", 0)
            
            if reaction_type in reactions:
                reactions[reaction_type] = count
        
        return reactions

    async def health_check(self) -> Dict[str, Any]:
        """Check Teams service health"""
        try:
            # Test API connectivity
            client = await self.get_client()
            response = await client.get("/me")
            
            api_healthy = response.status_code == 200
            
            # Check configuration
            config_healthy = all([
                os.getenv('MICROSOFT_CLIENT_ID'),
                os.getenv('MICROSOFT_CLIENT_SECRET'),
                os.getenv('MICROSOFT_TENANT_ID')
            ])
            
            return {
                "status": "healthy" if api_healthy and config_healthy else "unhealthy",
                "api_healthy": api_healthy,
                "config_healthy": config_healthy,
                "token_valid": not self._is_token_expired(),
                "checked_at": datetime.utcnow().isoformat()
            }
            
        except Exception as e:
            logger.error(f"Microsoft Teams: Health check error: {e}")
            return {
                "status": "unhealthy",
                "error": str(e),
                "checked_at": datetime.utcnow().isoformat()
            }

# Initialize Teams service instance
teams_service = TeamsService()