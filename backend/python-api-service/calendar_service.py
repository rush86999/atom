"""
Unified Calendar Service for Atom Personal Assistant

This service provides a unified interface to multiple calendar providers:
- Google Calendar
- Outlook Calendar
- Apple Calendar (via CalDAV)
- Other CalDAV-compliant calendars

The service handles OAuth authentication, event synchronization, and provides
a consistent API for calendar operations across all providers.
"""

import os
import logging
import asyncio
from datetime import datetime, timedelta
from typing import List, Dict, Optional, Any
from enum import Enum
import json

# Try to import calendar provider libraries
try:
    from google.oauth2.credentials import Credentials
    from google_auth_oauthlib.flow import Flow
    from googleapiclient.discovery import build
    from google.auth.transport.requests import Request
except ImportError:
    print("Google Calendar libraries not available")

try:
    import msal
    from office365.runtime.auth.authentication_context import AuthenticationContext
    from office365.sharepoint.client_context import ClientContext
except ImportError:
    print("Outlook/Office365 libraries not available")

try:
    import caldav
except ImportError:
    print("CalDAV libraries not available")

# Import database utilities
from db_utils import get_db_pool, get_user_tokens, save_user_tokens, save_calendar_event, get_user_calendar_events

logger = logging.getLogger(__name__)

class CalendarProvider(Enum):
    GOOGLE = "google"
    OUTLOOK = "outlook"
    APPLE = "apple"
    CALDAV = "caldav"

class CalendarEvent:
    """Unified calendar event representation"""

    def __init__(self,
                 id: str,
                 title: str,
                 start: datetime,
                 end: datetime,
                 description: Optional[str] = None,
                 location: Optional[str] = None,
                 attendees: Optional[List[str]] = None,
                 provider: CalendarProvider = CalendarProvider.GOOGLE,
                 provider_event_id: Optional[str] = None,
                 status: str = "confirmed",
                 recurrence: Optional[List[datetime]] = None):
        self.id = id
        self.title = title
        self.start = start
        self.end = end
        self.description = description
        self.location = location
        self.attendees = attendees or []
        self.provider = provider
        self.provider_event_id = provider_event_id
        self.status = status
        self.recurrence = recurrence or []

    def to_dict(self) -> Dict[str, Any]:
        """Convert event to dictionary for JSON serialization"""
        return {
            "id": self.id,
            "title": self.title,
            "start": self.start.isoformat(),
            "end": self.end.isoformat(),
            "description": self.description,
            "location": self.location,
            "attendees": self.attendees,
            "provider": self.provider.value,
            "provider_event_id": self.provider_event_id,
            "status": self.status,
            "recurrence": [dt.isoformat() for dt in self.recurrence]
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'CalendarEvent':
        """Create event from dictionary"""
        return cls(
            id=data['id'],
            title=data['title'],
            start=datetime.fromisoformat(data['start']),
            end=datetime.fromisoformat(data['end']),
            description=data.get('description'),
            location=data.get('location'),
            attendees=data.get('attendees', []),
            provider=CalendarProvider(data['provider']),
            provider_event_id=data.get('provider_event_id'),
            status=data.get('status', 'confirmed'),
            recurrence=[datetime.fromisoformat(dt) for dt in data.get('recurrence', [])]
        )

class UnifiedCalendarService:
    """Service for unified calendar operations across multiple providers"""

    def __init__(self, db_conn_pool=None):
        self.db_conn_pool = db_conn_pool
        self.provider_services = {
            CalendarProvider.GOOGLE: GoogleCalendarService(),
            CalendarProvider.OUTLOOK: OutlookCalendarService(),
            CalendarProvider.CALDAV: CalDAVCalendarService()
        }

    async def get_events(self,
                        user_id: str,
                        start_date: datetime,
                        end_date: datetime,
                        providers: Optional[List[CalendarProvider]] = None) -> List[CalendarEvent]:
        """
        Get events from all configured calendar providers for a user

        Args:
            user_id: User identifier
            start_date: Start of date range
            end_date: End of date range
            providers: List of providers to query (None for all)

        Returns:
            List of unified calendar events
        """
        events = []
        providers_to_query = providers or list(self.provider_services.keys())

        for provider in providers_to_query:
            if provider in self.provider_services:
                try:
                    provider_events = await self.provider_services[provider].get_events(
                        user_id, start_date, end_date
                    )
                    events.extend(provider_events)
                except Exception as e:
                    logger.error(f"Error fetching events from {provider.value}: {e}")
                    continue

        # Sort events by start time
        events.sort(key=lambda x: x.start)
        return events

    async def create_event(self,
                         user_id: str,
                         event: CalendarEvent,
                         providers: Optional[List[CalendarProvider]] = None) -> List[CalendarEvent]:
        """
        Create event across multiple calendar providers

        Args:
            user_id: User identifier
            event: Event to create
            providers: List of providers to create event in (None for all)

        Returns:
            List of created events (with provider-specific IDs)
        """
        created_events = []
        providers_to_use = providers or list(self.provider_services.keys())

        for provider in providers_to_use:
            if provider in self.provider_services:
                try:
                    created_event = await self.provider_services[provider].create_event(
                        user_id, event
                    )
                    created_events.append(created_event)
                except Exception as e:
                    logger.error(f"Error creating event in {provider.value}: {e}")
                    continue

        return created_events

    async def update_event(self,
                         user_id: str,
                         event_id: str,
                         updates: Dict[str, Any],
                         provider: CalendarProvider) -> Optional[CalendarEvent]:
        """
        Update event in specific calendar provider

        Args:
            user_id: User identifier
            event_id: Event ID to update
            updates: Dictionary of fields to update
            provider: Calendar provider to update in

        Returns:
            Updated event if successful, None otherwise
        """
        if provider in self.provider_services:
            try:
                return await self.provider_services[provider].update_event(
                    user_id, event_id, updates
                )
            except Exception as e:
                logger.error(f"Error updating event in {provider.value}: {e}")

        return None

    async def delete_event(self,
                         user_id: str,
                         event_id: str,
                         provider: CalendarProvider) -> bool:
        """
        Delete event from specific calendar provider

        Args:
            user_id: User identifier
            event_id: Event ID to delete
            provider: Calendar provider to delete from

        Returns:
            True if successful, False otherwise
        """
        if provider in self.provider_services:
            try:
                return await self.provider_services[provider].delete_event(
                    user_id, event_id
                )
            except Exception as e:
                logger.error(f"Error deleting event from {provider.value}: {e}")

        return False

    async def get_free_busy(self,
                          user_id: str,
                          start_date: datetime,
                          end_date: datetime,
                          providers: Optional[List[CalendarProvider]] = None) -> List[Dict[str, Any]]:
        """
        Get free/busy information from all calendar providers

        Args:
            user_id: User identifier
            start_date: Start of date range
            end_date: End of date range
            providers: List of providers to query (None for all)

        Returns:
            List of free/busy periods
        """
        free_busy_info = []
        providers_to_query = providers or list(self.provider_services.keys())

        for provider in providers_to_query:
            if provider in self.provider_services:
                try:
                    provider_info = await self.provider_services[provider].get_free_busy(
                        user_id, start_date, end_date
                    )
                    free_busy_info.extend(provider_info)
                except Exception as e:
                    logger.error(f"Error fetching free/busy from {provider.value}: {e}")
                    continue

        return free_busy_info

class GoogleCalendarService:
    """Service for Google Calendar operations"""

    def __init__(self):
        self.service_name = 'calendar'
        self.version = 'v3'

    async def get_events(self, user_id: str, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from Google Calendar"""
        try:
            # Get user's Google credentials from database
            credentials = await self._get_user_credentials(user_id)
            if not credentials:
                logger.warning(f"No Google credentials found for user {user_id}")
                return []

            service = build(self.service_name, self.version, credentials=credentials)

            events_result = service.events().list(
                calendarId='primary',
                timeMin=start_date.isoformat() + 'Z',
                timeMax=end_date.isoformat() + 'Z',
                singleEvents=True,
                orderBy='startTime'
            ).execute()

            events = events_result.get('items', [])
            google_events = [self._convert_google_event(event) for event in events]

            # Save events to database for offline access
            for event in google_events:
                await save_calendar_event(user_id, event.to_dict())

            return google_events

        except Exception as e:
            logger.error(f"Error fetching Google Calendar events: {e}")
            # Fall back to database if online fetch fails
            logger.info(f"Falling back to database events for user {user_id}")
            return await self._get_events_from_db(user_id, start_date, end_date)

    def _convert_google_event(self, google_event: Dict[str, Any]) -> CalendarEvent:
        """Convert Google Calendar event to unified format"""
        start = google_event['start'].get('dateTime', google_event['start'].get('date'))
        end = google_event['end'].get('dateTime', google_event['end'].get('date'))

        return CalendarEvent(
            id=google_event.get('id', ''),
            title=google_event.get('summary', 'No Title'),
            start=datetime.fromisoformat(start.replace('Z', '+00:00')),
            end=datetime.fromisoformat(end.replace('Z', '+00:00')),
            description=google_event.get('description'),
            location=google_event.get('location'),
            attendees=[attendee['email'] for attendee in google_event.get('attendees', [])],
            provider=CalendarProvider.GOOGLE,
            provider_event_id=google_event.get('id'),
            status=google_event.get('status', 'confirmed')
        )

    async def _get_user_credentials(self, user_id: str):
        """Get user's Google OAuth credentials from database"""
        try:
            tokens = await get_user_tokens(user_id, 'google_calendar')
            if not tokens:
                logger.warning(f"No Google OAuth tokens found for user {user_id}")
                return None

            # Create credentials object from stored tokens
            credentials = Credentials(
                token=tokens['access_token'],
                refresh_token=tokens.get('refresh_token'),
                token_uri='https://oauth2.googleapis.com/token',
                client_id=os.getenv('GOOGLE_CLIENT_ID'),
                client_secret=os.getenv('GOOGLE_CLIENT_SECRET'),
                scopes=['https://www.googleapis.com/auth/calendar.readonly']
            )

            # Refresh token if expired
            if credentials.expired and credentials.refresh_token:
                credentials.refresh(Request())
                # Save refreshed tokens
                await save_user_tokens(
                    user_id,
                    'google_calendar',
                    credentials.token,
                    credentials.refresh_token,
                    int(credentials.expiry.timestamp()) if credentials.expiry else None,
                    ' '.join(credentials.scopes) if credentials.scopes else None
                )

            return credentials

        except Exception as e:
            logger.error(f"Error getting Google credentials for user {user_id}: {e}")
            return None

    async def _get_events_from_db(self, user_id: str, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get calendar events from database"""
        try:
            db_events = await get_user_calendar_events(
                user_id,
                start_date.isoformat(),
                end_date.isoformat()
            )

            events = []
            for event_data in db_events:
                try:
                    event = CalendarEvent(
                        id=event_data['event_id'],
                        title=event_data['title'],
                        start=datetime.fromisoformat(event_data['start_time'].replace('Z', '+00:00')),
                        end=datetime.fromisoformat(event_data['end_time'].replace('Z', '+00:00')),
                        description=event_data.get('description'),
                        location=event_data.get('location'),
                        attendees=event_data.get('attendees', []),
                        provider=CalendarProvider(event_data['provider']),
                        provider_event_id=event_data.get('provider_event_id'),
                        status=event_data.get('status', 'confirmed')
                    )
                    events.append(event)
                except Exception as e:
                    logger.error(f"Error converting database event: {e}")
                    continue

            return events

        except Exception as e:
            logger.error(f"Error getting events from database for user {user_id}: {e}")
            return []

class OutlookCalendarService:
    """Service for Outlook Calendar operations"""

    async def get_events(self, user_id: str, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from Outlook Calendar"""
        try:
            # Get user's Outlook credentials from database
            tokens = await get_user_tokens(user_id, 'outlook_calendar')
            if not tokens:
                logger.warning(f"No Outlook OAuth tokens found for user {user_id}")
                return []

            # Implementation would use Microsoft Graph API
            # Placeholder implementation - in production, this would call Microsoft Graph API
            logger.info(f"Fetching Outlook events for user {user_id} from {start_date} to {end_date}")

            # For now, return empty list - actual implementation would use Microsoft Graph SDK
            return []

        except Exception as e:
            logger.error(f"Error fetching Outlook Calendar events: {e}")
            return []

class CalDAVCalendarService:
    """Service for CalDAV calendar operations"""

    async def get_events(self, user_id: str, start_date: datetime, end_date: datetime) -> List[CalendarEvent]:
        """Get events from CalDAV calendar"""
        try:
            # Get user's CalDAV credentials from database
            tokens = await get_user_tokens(user_id, 'caldav_calendar')
            if not tokens:
                logger.warning(f"No CalDAV credentials found for user {user_id}")
                return []

            # Implementation would use CalDAV protocol
            # Placeholder implementation - in production, this would use caldav library
            logger.info(f"Fetching CalDAV events for user {user_id} from {start_date} to {end_date}")

            # For now, return empty list - actual implementation would use caldav library
            return []

        except Exception as e:
            logger.error(f"Error fetching CalDAV Calendar events: {e}")
            return []

# Utility functions
async def sync_user_calendars(user_id: str) -> Dict[str, Any]:
    """
    Synchronize all calendar providers for a user

    Args:
        user_id: User identifier

    Returns:
        Sync results with counts and status
    """
    calendar_service = UnifiedCalendarService()

    # Sync events from last 7 days to next 30 days
    start_date = datetime.now() - timedelta(days=7)
    end_date = datetime.now() + timedelta(days=30)

    try:
        events = await calendar_service.get_events(user_id, start_date, end_date)

        # Events are now automatically stored in database during fetch
        logger.info(f"Successfully synced {len(events)} calendar events for user {user_id}")

        return {
            "success": True,
            "events_synced": len(events),
            "providers": ["google", "outlook", "caldav"],
            "timestamp": datetime.now().isoformat()
        }

    except Exception as e:
        logger.error(f"Error syncing calendars for user {user_id}: {e}")
        return {
            "success": False,
            "error": str(e),
            "timestamp": datetime.now().isoformat()
        }

async def _store_events_in_db(user_id: str, events: List[CalendarEvent]):
    """Store calendar events in database"""
    # This function is now handled by the individual calendar services
    # during the get_events operation
    pass

async def find_available_time_slots(user_id: str,
                                  duration: timedelta,
                                  start_date: datetime,
                                  end_date: datetime) -> List[Dict[str, datetime]]:
    """
    Find available time slots across all calendar providers

    Args:
        user_id: User identifier
        duration: Duration of the desired time slot
        start_date: Start of search range
        end_date: End of search range

    Returns:
        List of available time slots
    """
    calendar_service = UnifiedCalendarService()

    try:
        # Get events from all providers
        events = await calendar_service.get_events(user_id, start_date, end_date)

        # Sort events by start time
        events.sort(key=lambda x: x.start)

        # Find available time slots between events
        available_slots = []
        current_time = start_date

        for event in events:
            if event.start > current_time:
                slot_duration = (event.start - current_time)
                if slot_duration >= duration:
                    available_slots.append({
                        "start": current_time,
                        "end": event.start,
                        "duration": slot_duration
                    })
            current_time = max(current_time, event.end)

        # Check for available time after last event
        if current_time < end_date:
            slot_duration = (end_date - current_time)
            if slot_duration >= duration:
                available_slots.append({
                    "start": current_time,
                    "end": end_date,
                    "duration": slot_duration
                })

        return available_slots

    except Exception as e:
        logger.error(f"Error finding available time slots for user {user_id}: {e}")
        return []
