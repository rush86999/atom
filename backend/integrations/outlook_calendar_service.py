"""
Outlook Calendar Real API Integration Service
Provides real Microsoft Graph API access for event management and conflict detection
Uses delegated permissions with device code flow (no admin consent required)
"""

import asyncio
import json
import logging
import os
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional
import aiohttp

# Load environment variables from .env file
from dotenv import load_dotenv
from msal import PublicClientApplication

# Load .env from project root (atom/.env)
env_path = Path(__file__).parent.parent.parent / '.env'
load_dotenv(dotenv_path=env_path)

logger = logging.getLogger(__name__)

class OutlookCalendarService:
    """Service for real Outlook/Microsoft Graph Calendar API interactions"""
    
    def __init__(self):
        """Initialize Outlook Calendar service with delegated permissions"""
        self.client_id = os.getenv("OUTLOOK_CLIENT_ID")
        self.tenant_id = os.getenv("OUTLOOK_TENANT_ID", "common")
        self.access_token = None
        self.token_expiry = None
        self.app = None
        self.token_cache_file = Path(__file__).parent.parent.parent / '.outlook_token_cache.json'
        
        # Microsoft Graph API endpoints
        self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
        self.graph_url = "https://graph.microsoft.com/v1.0"
        # Delegated permissions (user consent, no admin required)
        self.scopes = ["Calendars.ReadWrite", "User.Read"]
        
    def _load_token_cache(self) -> Dict:
        """Load cached token if available"""
        if self.token_cache_file.exists():
            try:
                with open(self.token_cache_file, 'r') as f:
                    return json.load(f)
            except Exception as e:
                logger.warning(f"Failed to load token cache: {e}")
        return {}
    
    def _save_token_cache(self, cache_data: Dict):
        """Save token to cache for future use"""
        try:
            with open(self.token_cache_file, 'w') as f:
                json.dump(cache_data, f)
            logger.info("✅ Token cached successfully")
        except Exception as e:
            logger.warning(f"Failed to save token cache: {e}")
        
    def authenticate(self) -> bool:
        """Authenticate with Microsoft Graph API using delegated permissions (device code flow)"""
        try:
            if not self.client_id:
                logger.error("Missing Outlook credentials (OUTLOOK_CLIENT_ID)")
                return False
            
            # Create MSAL public client app (no secret needed for delegated permissions)
            self.app = PublicClientApplication(
                client_id=self.client_id,
                authority=self.authority
            )
            
            # Try to get token from cache first
            accounts = self.app.get_accounts()
            if accounts:
                logger.info("Found cached account, attempting silent authentication...")
                result = self.app.acquire_token_silent(self.scopes, account=accounts[0])
                if result and "access_token" in result:
                    self.access_token = result["access_token"]
                    self.token_expiry = datetime.now() + timedelta(seconds=result.get("expires_in", 3600))
                    logger.info("✅ Outlook Calendar authenticated via cached token")
                    return True
            
            # No cached token, use device code flow
            logger.info("No cached token found, initiating device code flow...")
            flow = self.app.initiate_device_flow(scopes=self.scopes)
            
            if "user_code" not in flow:
                raise ValueError("Failed to create device flow")
            
            # Display user instructions
            print("\n" + "="*60)
            print("🔐 OUTLOOK AUTHENTICATION REQUIRED")
            print("="*60)
            print(flow["message"])
            print("="*60 + "\n")
            
            # Wait for user to complete authentication
            result = self.app.acquire_token_by_device_flow(flow)
            
            if "access_token" in result:
                self.access_token = result["access_token"]
                self.token_expiry = datetime.now() + timedelta(seconds=result.get("expires_in", 3600))
                logger.info("✅ Outlook Calendar service authenticated successfully via device code")
                return True
            else:
                error = result.get("error_description", result.get("error", "Unknown error"))
                logger.error(f"Failed to acquire Outlook token: {error}")
                return False
                
        except Exception as e:
            logger.error(f"Failed to authenticate with Outlook: {e}")
            return False
    
    def _ensure_authenticated(self) -> bool:
        """Ensure we have a valid access token"""
        # Check if token exists and is not expired
        if not self.access_token or not self.token_expiry:
            return self.authenticate()
        
        # Refresh if token expires in less than 5 minutes
        if datetime.now() >= self.token_expiry - timedelta(minutes=5):
            return self.authenticate()
        
        return True
    
    async def get_events(
        self,
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Get events from Outlook Calendar
        
        Args:
            time_min: Start time filter
            time_max: End time filter
            max_results: Maximum number of events to return
            
        Returns:
            List of events in unified format
        """
        if not self._ensure_authenticated():
            return []
        
        try:
            # Default to next 7 days if not specified
            if not time_min:
                time_min = datetime.now(timezone.utc)
            if not time_max:
                time_max = time_min + timedelta(days=7)
            
            # Format times for Microsoft Graph API (ISO 8601 format)
            if time_min.tzinfo is None:
                time_min = time_min.replace(tzinfo=timezone.utc)
            if time_max.tzinfo is None:
                time_max = time_max.replace(tzinfo=timezone.utc)
            
            time_min_str = time_min.isoformat()
            time_max_str = time_max.isoformat()
            
            # Use calendarView endpoint to get instances of recurring events
            url = f"{self.graph_url}/me/calendarview"
            params = {
                "startDateTime": time_min_str,
                "endDateTime": time_max_str,
                "$top": max_results,
                "$orderby": "start/dateTime"
            }
            
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.get(url, headers=headers, params=params) as response:
                    if response.status == 200:
                        data = await response.json()
                        events = data.get("value", [])
                        return [self._convert_outlook_to_unified(event) for event in events]
                    else:
                        error_text = await response.text()
                        logger.error(f"Outlook API error: {response.status} - {error_text}")
                        return []
                        
        except Exception as error:
            logger.error(f"Failed to get Outlook events: {error}")
            return []
    
    async def create_event(self, event_data: Dict) -> Optional[Dict]:
        """
        Create an event in Outlook Calendar
        
        Args:
            event_data: Event data in unified format
            
        Returns:
            Created event in unified format or None
        """
        if not self._ensure_authenticated():
            return None
        
        try:
            # Convert unified format to Outlook format
            outlook_event = self._convert_unified_to_outlook(event_data)
            
            url = f"{self.graph_url}/me/events"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.post(url, headers=headers, json=outlook_event) as response:
                    if response.status in [200, 201]:
                        event = await response.json()
                        logger.info(f"✅ Created Outlook Calendar event: {event.get('id')}")
                        return self._convert_outlook_to_unified(event)
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to create Outlook event: {response.status} - {error_text}")
                        return None
                        
        except Exception as error:
            logger.error(f"Failed to create Outlook Calendar event: {error}")
            return None
    
    async def update_event(
        self,
        event_id: str,
        updates: Dict
    ) -> Optional[Dict]:
        """Update an existing event"""
        if not self._ensure_authenticated():
            return None
        
        try:
            url = f"{self.graph_url}/me/events/{event_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}",
                "Content-Type": "application/json"
            }
            
            # Build update payload
            update_payload = {}
            if 'title' in updates:
                update_payload['subject'] = updates['title']
            if 'description' in updates:
                update_payload['body'] = {
                    'contentType': 'text',
                    'content': updates['description']
                }
            if 'start_time' in updates:
                update_payload['start'] = {
                    'dateTime': updates['start_time'],
                    'timeZone': 'UTC'
                }
            if 'end_time' in updates:
                update_payload['end'] = {
                    'dateTime': updates['end_time'],
                    'timeZone': 'UTC'
                }
            
            async with aiohttp.ClientSession() as session:
                async with session.patch(url, headers=headers, json=update_payload) as response:
                    if response.status == 200:
                        event = await response.json()
                        return self._convert_outlook_to_unified(event)
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to update Outlook event: {response.status} - {error_text}")
                        return None
                        
        except Exception as error:
            logger.error(f"Failed to update Outlook Calendar event: {error}")
            return None
    
    async def delete_event(self, event_id: str) -> bool:
        """Delete an event from Outlook Calendar"""
        if not self._ensure_authenticated():
            return False
        
        try:
            url = f"{self.graph_url}/me/events/{event_id}"
            headers = {
                "Authorization": f"Bearer {self.access_token}"
            }
            
            async with aiohttp.ClientSession() as session:
                async with session.delete(url, headers=headers) as response:
                    if response.status == 204:
                        logger.info(f"✅ Deleted Outlook Calendar event: {event_id}")
                        return True
                    else:
                        error_text = await response.text()
                        logger.error(f"Failed to delete Outlook event: {response.status} - {error_text}")
                        return False
                        
        except Exception as error:
            logger.error(f"Failed to delete Outlook Calendar event: {error}")
            return False
    
    async def check_conflicts(
        self,
        start_time: datetime,
        end_time: datetime
    ) -> Dict:
        """
        Check for scheduling conflicts
        
        Args:
            start_time: Proposed event start time
            end_time: Proposed event end time
            
        Returns:
            Dict with conflict information
        """
        if not self._ensure_authenticated():
            return {"has_conflicts": False, "conflicts": [], "error": "Not authenticated"}
        
        try:
            # Get events in the time range
            events = await self.get_events(
                time_min=start_time,
                time_max=end_time
            )
            
            conflicts = []
            for event in events:
                # Parse event times
                event_start = datetime.fromisoformat(event['start_time'].replace('Z', '+00:00'))
                event_end = datetime.fromisoformat(event['end_time'].replace('Z', '+00:00'))
                
                # Check for overlap
                if (start_time < event_end and end_time > event_start):
                    conflicts.append({
                        "event_id": event['id'],
                        "title": event['title'],
                        "start_time": event['start_time'],
                        "end_time": event['end_time']
                    })
            
            logger.info(f"Outlook conflict check: {len(conflicts)} conflicts found")
            
            return {
                "success": True,
                "has_conflicts": len(conflicts) > 0,
                "conflict_count": len(conflicts),
                "conflicts": conflicts
            }
            
        except Exception as error:
            logger.error(f"Failed to check Outlook conflicts: {error}")
            return {
                "success": False,
                "has_conflicts": False,
                "conflicts": [],
                "error": str(error)
            }
    
    def _convert_outlook_to_unified(self, outlook_event: Dict) -> Dict:
        """Convert Outlook Calendar event to unified format"""
        start = outlook_event.get('start', {})
        end = outlook_event.get('end', {})
        
        # Outlook uses dateTime field
        start_time = start.get('dateTime', '')
        end_time = end.get('dateTime', '')
        
        # Get body content
        body = outlook_event.get('body', {})
        description = body.get('content', '') if isinstance(body, dict) else ''
        
        return {
            "id": outlook_event.get('id'),
            "title": outlook_event.get('subject', 'Untitled Event'),
            "description": description,
            "start_time": start_time,
            "end_time": end_time,
            "platform": "outlook",
            "attendees": [
                attendee.get('emailAddress', {}).get('address')
                for attendee in outlook_event.get('attendees', [])
                if attendee.get('emailAddress', {}).get('address')
            ],
            "location": outlook_event.get('location', {}).get('displayName', ''),
            "created_at": outlook_event.get('createdDateTime'),
            "updated_at": outlook_event.get('lastModifiedDateTime'),
        }
    
    def _convert_unified_to_outlook(self, unified_event: Dict) -> Dict:
        """Convert unified format to Outlook Calendar format"""
        outlook_event = {
            'subject': unified_event.get('title', 'Untitled Event'),
            'body': {
                'contentType': 'text',
                'content': unified_event.get('description', '')
            },
            'start': {
                'dateTime': unified_event.get('start_time', unified_event.get('start')),
                'timeZone': 'UTC'
            },
            'end': {
                'dateTime': unified_event.get('end_time', unified_event.get('end')),
                'timeZone': 'UTC'
            }
        }
        
        # Add optional fields
        if 'location' in unified_event and unified_event['location']:
            outlook_event['location'] = {
                'displayName': unified_event['location']
            }
        
        if 'attendees' in unified_event and unified_event['attendees']:
            outlook_event['attendees'] = [
                {
                    'emailAddress': {'address': email},
                    'type': 'required'
                }
                for email in unified_event['attendees']
            ]
        
        return outlook_event


# Singleton instance (will be initialized when credentials are available)
outlook_calendar_service = OutlookCalendarService()
