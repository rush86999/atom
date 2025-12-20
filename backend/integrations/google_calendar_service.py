"""
Google Calendar Real API Integration Service
Provides real Google Calendar API access for event management and conflict detection
"""

import os
import json
import logging
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta, timezone

# Make Google APIs optional for calendar integration
try:
    from google.oauth2.credentials import Credentials
    from google.auth.transport.requests import Request
    from google_auth_oauthlib.flow import InstalledAppFlow
    from googleapiclient.discovery import build
    from googleapiclient.errors import HttpError
    GOOGLE_APIS_AVAILABLE = True
except ImportError as e:
    GOOGLE_APIS_AVAILABLE = False
    # Create dummy classes to prevent type errors
    class Credentials: pass
    class Request: pass
    class InstalledAppFlow: pass
    class HttpError(Exception): pass
    def build(*args, **kwargs): return None

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the token file
SCOPES = ['https://www.googleapis.com/auth/calendar']

class GoogleCalendarService:
    """Service for real Google Calendar API interactions"""
    
    def __init__(self, credentials_json: Optional[str] = None, token_file: str = "token.json"):
        """
        Initialize Google Calendar service
        
        Args:
            credentials_json: Path to OAuth2 credentials file or JSON string
            token_file: Path to store/load user token
        """
        self.credentials_json = credentials_json or os.getenv("GOOGLE_CALENDAR_CREDENTIALS")
        self.token_file = token_file
        self.service = None
        self.creds = None
        
    def authenticate(self) -> bool:
        """Authenticate with Google Calendar API"""
        if not GOOGLE_APIS_AVAILABLE:
            logger.warning("Google APIs not available - calendar integration disabled")
            return False

        try:
            # Load existing token if available
            if os.path.exists(self.token_file):
                self.creds = Credentials.from_authorized_user_file(self.token_file, SCOPES)
            
            # If no valid credentials, refresh or get new ones
            if not self.creds or not self.creds.valid:
                if self.creds and self.creds.expired and self.creds.refresh_token:
                    self.creds.refresh(Request())
                else:
                    if not self.credentials_json:
                        logger.error("No Google Calendar credentials provided")
                        return False
                    
                    # Check if credentials_json is a file path or JSON string
                    if os.path.isfile(self.credentials_json):
                        flow = InstalledAppFlow.from_client_secrets_file(
                            self.credentials_json, SCOPES)
                    else:
                        # Assume it's a JSON string
                        client_config = json.loads(self.credentials_json)
                        flow = InstalledAppFlow.from_client_config(client_config, SCOPES)
                    
                    # Custom local server flow to handle Web Client "No Trailing Slash" requirement
                    # The standard flow.run_local_server() forces a trailing slash which Google rejects for Web clients
                    import socket
                    from wsgiref.simple_server import make_server, WSGIRequestHandler
                    
                    # Define the exact redirect URI (NO trailing slash)
                    redirect_uri = "http://localhost:8080"
                    flow.redirect_uri = redirect_uri
                    
                    # Create a simple WSGI app to catch the auth code
                    auth_code = None
                    
                    def simple_app(environ, start_response):
                        nonlocal auth_code
                        from urllib.parse import parse_qs
                        
                        query = parse_qs(environ['QUERY_STRING'])
                        if 'code' in query:
                            auth_code = query['code'][0]
                            start_response('200 OK', [('Content-type', 'text/html')])
                            return [b'<html><body><h1>Authentication successful!</h1><p>You can close this window.</p><script>window.close()</script></body></html>']
                        
                        start_response('404 Not Found', [('Content-type', 'text/plain')])
                        return [b'Not Found']

                    # Start local server on port 8080
                    try:
                        httpd = make_server('localhost', 8080, simple_app)
                    except OSError as e:
                        print(f"⚠️ Port 8080 is in use. Please free it or use a different port. Error: {e}")
                        raise e

                    # Print auth URL and open browser
                    auth_url, _ = flow.authorization_url(prompt='consent')
                    print(f"\n🔗 AUTHORIZATION URL: {auth_url}\n")
                    print("Opening browser...")
                    
                    import webbrowser
                    webbrowser.open(auth_url)
                    
                    # Wait for request
                    print("Waiting for authentication...")
                    httpd.handle_request()
                    
                    if auth_code:
                        flow.fetch_token(code=auth_code)
                        self.creds = flow.credentials
                    else:
                        raise Exception("Failed to catch auth code")

                # Save credentials for next run
                with open(self.token_file, 'w') as token:
                    token.write(self.creds.to_json())
            
            # Build the service
            self.service = build('calendar', 'v3', credentials=self.creds)
            logger.info("✅ Google Calendar service authenticated successfully")
            return True
            
        except Exception as e:
            logger.error(f"Failed to authenticate with Google Calendar: {e}")
            return False
    
    async def get_events(
        self, 
        calendar_id: str = 'primary',
        time_min: Optional[datetime] = None,
        time_max: Optional[datetime] = None,
        max_results: int = 100
    ) -> List[Dict]:
        """
        Get events from Google Calendar
        
        Args:
            calendar_id: Calendar ID (default: 'primary')
            time_min: Start time filter
            time_max: End time filter
            max_results: Maximum number of events to return
            
        Returns:
            List of events in unified format
        """
        if not GOOGLE_APIS_AVAILABLE:
            logger.warning("Google APIs not available - cannot get events")
            return []
        if not self.service:
            if not self.authenticate():
                return []
        
        try:
            # Default to next 7 days if not specified
            if not time_min:
                time_min = datetime.utcnow()
            if not time_max:
                time_max = time_min + timedelta(days=7)
            
            # Format times for API - Google expects UTC with Z suffix, not +00:00
            # If datetime is timezone-aware, convert to UTC and remove tz info before adding Z
            if time_min.tzinfo is not None:
                time_min_str = time_min.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
            else:
                time_min_str = time_min.isoformat() + 'Z'
                
            if time_max.tzinfo is not None:
                time_max_str = time_max.astimezone(timezone.utc).replace(tzinfo=None).isoformat() + 'Z'
            else:
                time_max_str = time_max.isoformat() + 'Z'
            
            # Call the Calendar API
            events_result = self.service.events().list(
                calendarId=calendar_id,
                timeMin=time_min_str,
                timeMax=time_max_str,
                maxResults=max_results,
                singleEvents=True,
                orderBy='startTime'
            ).execute()
            
            events = events_result.get('items', [])
            
            # Convert to unified format
            return [self._convert_google_to_unified(event) for event in events]
            
        except HttpError as error:
            logger.error(f"Google Calendar API error: {error}")
            return []
    
    async def create_event(self, event_data: Dict) -> Optional[Dict]:
        """
        Create an event in Google Calendar
        
        Args:
            event_data: Event data in unified format
            
        Returns:
            Created event in unified format or None
        """
        if not self.service:
            if not self.authenticate():
                return None
        
        try:
            # Convert unified format to Google format
            google_event = self._convert_unified_to_google(event_data)
            
            # Create the event
            event = self.service.events().insert(
                calendarId='primary',
                body=google_event
            ).execute()
            
            logger.info(f"✅ Created Google Calendar event: {event.get('id')}")
            return self._convert_google_to_unified(event)
            
        except HttpError as error:
            logger.error(f"Failed to create Google Calendar event: {error}")
            return None
    
    async def update_event(
        self,
        event_id: str,
        updates: Dict,
        calendar_id: str = 'primary'
    ) -> Optional[Dict]:
        """Update an existing event"""
        if not self.service:
            if not self.authenticate():
                return None
        
        try:
            # Get existing event
            event = self.service.events().get(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            # Apply updates
            if 'title' in updates:
                event['summary'] = updates['title']
            if 'description' in updates:
                event['description'] = updates['description']
            if 'start_time' in updates:
                event['start'] = {'dateTime': updates['start_time'], 'timeZone': 'UTC'}
            if 'end_time' in updates:
                event['end'] = {'dateTime': updates['end_time'], 'timeZone': 'UTC'}
            
            # Update the event
            updated_event = self.service.events().update(
                calendarId=calendar_id,
                eventId=event_id,
                body=event
            ).execute()
            
            return self._convert_google_to_unified(updated_event)
            
        except HttpError as error:
            logger.error(f"Failed to update Google Calendar event: {error}")
            return None
    
    async def delete_event(
        self,
        event_id: str,
        calendar_id: str = 'primary'
    ) -> bool:
        """Delete an event from Google Calendar"""
        if not self.service:
            if not self.authenticate():
                return False
        
        try:
            self.service.events().delete(
                calendarId=calendar_id,
                eventId=event_id
            ).execute()
            
            logger.info(f"✅ Deleted Google Calendar event: {event_id}")
            return True
            
        except HttpError as error:
            logger.error(f"Failed to delete Google Calendar event: {error}")
            return False
    
    async def check_conflicts(
        self,
        start_time: datetime,
        end_time: datetime,
        calendar_id: str = 'primary'
    ) -> Dict:
        """
        Check for scheduling conflicts
        
        Args:
            start_time: Proposed event start time
            end_time: Proposed event end time
            calendar_id: Calendar to check
            
        Returns:
            Dict with conflict information
        """
        if not self.service:
            if not self.authenticate():
                return {"has_conflicts": False, "conflicts": [], "error": "Not authenticated"}
        
        try:
            # Get events in the time range
            events = await self.get_events(
                calendar_id=calendar_id,
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
            
            logger.info(f"DEBUG: check_conflicts found {len(conflicts)} conflicts. Start: {start_time}, End: {end_time}")
            
            return {
                "success": True,
                "has_conflicts": len(conflicts) > 0,
                "conflict_count": len(conflicts),
                "conflicts": conflicts
            }
            
        except Exception as error:
            logger.error(f"Failed to check conflicts: {error}")
            return {
                "success": False,
                "has_conflicts": False,
                "conflicts": [],
                "error": str(error)
            }
    
    def _convert_google_to_unified(self, google_event: Dict) -> Dict:
        """Convert Google Calendar event to unified format"""
        start = google_event.get('start', {})
        end = google_event.get('end', {})
        
        # Handle both dateTime and date (all-day events)
        start_time = start.get('dateTime', start.get('date', ''))
        end_time = end.get('dateTime', end.get('date', ''))
        
        return {
            "id": google_event.get('id'),
            "title": google_event.get('summary', 'Untitled Event'),
            "description": google_event.get('description', ''),
            "start_time": start_time,
            "end_time": end_time,
            "platform": "google_calendar",
            "attendees": [
                attendee.get('email') 
                for attendee in google_event.get('attendees', [])
            ],
            "location": google_event.get('location', ''),
            "created_at": google_event.get('created'),
            "updated_at": google_event.get('updated'),
        }
    
    def _convert_unified_to_google(self, unified_event: Dict) -> Dict:
        """Convert unified format to Google Calendar format"""
        google_event = {
            'summary': unified_event.get('title', 'Untitled Event'),
            'description': unified_event.get('description', ''),
            'start': {
                'dateTime': unified_event.get('start_time'),
                'timeZone': 'UTC',
            },
            'end': {
                'dateTime': unified_event.get('end_time'),
                'timeZone': 'UTC',
            },
        }
        
        # Add optional fields
        if 'location' in unified_event:
            google_event['location'] = unified_event['location']
        
        if 'attendees' in unified_event and unified_event['attendees']:
            google_event['attendees'] = [
                {'email': email} for email in unified_event['attendees']
            ]
        
        return google_event


# Singleton instance (will be initialized when credentials are available)
google_calendar_service = GoogleCalendarService()
