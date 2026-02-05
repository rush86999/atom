"""
Teams Service for ATOM Platform
Provides comprehensive Microsoft Teams integration functionality
"""

from datetime import datetime, timedelta
import json
import logging
import os
from typing import Any, Dict, List, Optional, Union
from urllib.parse import urlencode, urljoin
import requests

logger = logging.getLogger(__name__)

class TeamsService:
    """Microsoft Teams API integration service"""
    
    def __init__(self, access_token: Optional[str] = None):
        self.access_token = access_token or os.getenv('TEAMS_ACCESS_TOKEN')
        self.base_url = "https://graph.microsoft.com/v1.0"
        self.session = requests.Session()
        
        if self.access_token:
            self.session.headers.update({
                'Authorization': f'Bearer {self.access_token}',
                'Accept': 'application/json',
                'Content-Type': 'application/json',
                'User-Agent': 'ATOM-Platform/1.0'
            })
    
    def test_connection(self) -> Dict[str, Any]:
        """Test Microsoft Teams API connection"""
        try:
            response = self.session.get(f"{self.base_url}/me")
            if response.status_code == 200:
                user_data = response.json()
                return {
                    "status": "success",
                    "message": "Teams connection successful",
                    "user": user_data.get('displayName', ''),
                    "email": user_data.get('mail', user_data.get('userPrincipalName', '')),
                    "authenticated": True
                }
            else:
                return {
                    "status": "error", 
                    "message": f"Authentication failed: {response.status_code}",
                    "authenticated": False
                }
        except Exception as e:
            logger.error(f"Teams connection test failed: {e}")
            return {
                "status": "error",
                "message": str(e),
                "authenticated": False
            }
    
    def get_teams(self) -> List[Dict[str, Any]]:
        """Get Teams for current user"""
        try:
            response = self.session.get(f"{self.base_url}/me/joinedTeams")
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get teams: {e}")
            return []
    
    def get_team(self, team_id: str) -> Optional[Dict[str, Any]]:
        """Get specific team details"""
        try:
            response = self.session.get(f"{self.base_url}/teams/{team_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get team {team_id}: {e}")
            return None
    
    def get_channels(self, team_id: str) -> List[Dict[str, Any]]:
        """Get channels in a team"""
        try:
            response = self.session.get(f"{self.base_url}/teams/{team_id}/channels")
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get channels for team {team_id}: {e}")
            return []
    
    def get_channel(self, team_id: str, channel_id: str) -> Optional[Dict[str, Any]]:
        """Get specific channel details"""
        try:
            response = self.session.get(f"{self.base_url}/teams/{team_id}/channels/{channel_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get channel {channel_id}: {e}")
            return None
    
    def create_channel(self, team_id: str, display_name: str, description: str = "",
                     channel_type: str = "standard") -> Optional[Dict[str, Any]]:
        """Create a new channel in a team"""
        try:
            data = {
                "displayName": display_name,
                "description": description,
                "membershipType": channel_type  # standard, private
            }
            
            response = self.session.post(f"{self.base_url}/teams/{team_id}/channels", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create channel: {e}")
            return None
    
    def get_messages(self, team_id: str, channel_id: str, 
                    limit: int = 50) -> List[Dict[str, Any]]:
        """Get messages from a channel"""
        try:
            response = self.session.get(
                f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages",
                params={'$top': limit}
            )
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get messages: {e}")
            return []
    
    def send_message(self, team_id: str, channel_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Send a message to a channel"""
        try:
            data = {
                "body": {
                    "content": content,
                    "contentType": "html"
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send message: {e}")
            return None
    
    def reply_to_message(self, team_id: str, channel_id: str, 
                        message_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Reply to a message"""
        try:
            data = {
                "body": {
                    "content": content,
                    "contentType": "html"
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/teams/{team_id}/channels/{channel_id}/messages/{message_id}/replies",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to reply to message: {e}")
            return None
    
    def get_meetings(self, team_id: str = None) -> List[Dict[str, Any]]:
        """Get meetings"""
        try:
            if team_id:
                # Get team calendar events
                response = self.session.get(
                    f"{self.base_url}/teams/{team_id}/events",
                    params={'$top': 50}
                )
            else:
                # Get user calendar events
                response = self.session.get(
                    f"{self.base_url}/me/events",
                    params={'$top': 50}
                )
            
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get meetings: {e}")
            return []
    
    def create_meeting(self, subject: str, start_time: str, end_time: str,
                      attendees: List[str] = None, body: str = "") -> Optional[Dict[str, Any]]:
        """Create a meeting"""
        try:
            data = {
                "subject": subject,
                "body": {
                    "contentType": "html",
                    "content": body
                },
                "start": {
                    "dateTime": start_time,
                    "timeZone": "UTC"
                },
                "end": {
                    "dateTime": end_time,
                    "timeZone": "UTC"
                },
                "isOnlineMeeting": True
            }
            
            if attendees:
                data["attendees"] = [
                    {
                        "emailAddress": {
                            "address": attendee,
                            "name": attendee
                        },
                        "type": "required"
                    } for attendee in attendees
                ]
            
            response = self.session.post(f"{self.base_url}/me/events", json=data)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to create meeting: {e}")
            return None
    
    def get_team_members(self, team_id: str) -> List[Dict[str, Any]]:
        """Get members of a team"""
        try:
            response = self.session.get(f"{self.base_url}/groups/{team_id}/members")
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get team members: {e}")
            return []
    
    def get_channel_members(self, team_id: str, channel_id: str) -> List[Dict[str, Any]]:
        """Get members of a channel"""
        try:
            response = self.session.get(
                f"{self.base_url}/teams/{team_id}/channels/{channel_id}/members"
            )
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get channel members: {e}")
            return []
    
    def add_member_to_channel(self, team_id: str, channel_id: str, 
                             user_id: str, role: str = "member") -> bool:
        """Add member to channel"""
        try:
            data = {
                "@odata.id": f"https://graph.microsoft.com/v1.0/users/{user_id}",
                "roles": [role]
            }
            
            response = self.session.post(
                f"{self.base_url}/teams/{team_id}/channels/{channel_id}/members",
                json=data
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to add member to channel: {e}")
            return False
    
    def remove_member_from_channel(self, team_id: str, channel_id: str, 
                                 membership_id: str) -> bool:
        """Remove member from channel"""
        try:
            response = self.session.delete(
                f"{self.base_url}/teams/{team_id}/channels/{channel_id}/members/{membership_id}"
            )
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to remove member from channel: {e}")
            return False
    
    def get_online_meeting(self, meeting_id: str) -> Optional[Dict[str, Any]]:
        """Get online meeting details"""
        try:
            response = self.session.get(f"{self.base_url}/me/onlineMeetings/{meeting_id}")
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get online meeting: {e}")
            return None
    
    def join_meeting(self, join_url: str) -> Dict[str, Any]:
        """Get join meeting information"""
        try:
            return {
                "status": "success",
                "message": "Meeting join URL provided",
                "join_url": join_url,
                "note": "Use this URL to join the Teams meeting"
            }
        except Exception as e:
            logger.error(f"Failed to join meeting: {e}")
            return {"status": "error", "message": str(e)}
    
    def get_chat_messages(self, chat_id: str) -> List[Dict[str, Any]]:
        """Get messages from a chat"""
        try:
            response = self.session.get(
                f"{self.base_url}/chats/{chat_id}/messages",
                params={'$top': 50}
            )
            response.raise_for_status()
            return response.json().get('value', [])
        except Exception as e:
            logger.error(f"Failed to get chat messages: {e}")
            return []
    
    def send_chat_message(self, chat_id: str, content: str) -> Optional[Dict[str, Any]]:
        """Send message to a chat"""
        try:
            data = {
                "body": {
                    "content": content,
                    "contentType": "text"
                }
            }
            
            response = self.session.post(
                f"{self.base_url}/chats/{chat_id}/messages",
                json=data
            )
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to send chat message: {e}")
            return None
    
    def get_user_presence(self, user_id: str = None) -> Optional[Dict[str, Any]]:
        """Get user presence information"""
        try:
            if user_id:
                endpoint = f"{self.base_url}/users/{user_id}/presence"
            else:
                endpoint = f"{self.base_url}/me/presence"
            
            response = self.session.get(endpoint)
            response.raise_for_status()
            return response.json()
        except Exception as e:
            logger.error(f"Failed to get user presence: {e}")
            return None
    
    def set_user_presence(self, availability: str, activity: str) -> bool:
        """Set user presence"""
        try:
            data = {
                "availability": availability,  # Available, Busy, DoNotDisturb, Away, Offline
                "activity": activity  # Available, InACall, InAConferenceCall, Inactive, Away, BeRightBack, Busy, DoNotDisturb
            }
            
            response = self.session.post(f"{self.base_url}/me/presence/setPresence", json=data)
            response.raise_for_status()
            return True
        except Exception as e:
            logger.error(f"Failed to set user presence: {e}")
            return False

# Singleton instance for global access
teams_service = TeamsService()

def get_teams_service() -> TeamsService:
    """Get Teams service instance"""
    return teams_service