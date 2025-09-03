from celery import shared_task
import logging
from typing import Dict, Any, List, Optional
import os
from datetime import datetime, timedelta
import google.auth
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError

logger = logging.getLogger(__name__)

# If modifying these scopes, delete the file token.json.
SCOPES = ['https://www.googleapis.com/auth/calendar']

@shared_task(bind=True, max_retries=3)
def create_calendar_event(self, summary: str, start_time: str, end_time: str,
                         calendar_id: str = "primary", timezone: str = "UTC",
                         description: Optional[str] = None, location: Optional[str] = None,
                         attendees: Optional[List[str]] = None) -> Dict[str, Any]:
    """
    Create a new event in Google Calendar

    Args:
        summary: Event title/summary
        start_time: Start time in ISO format
        end_time: End time in ISO format
        calendar_id: Calendar ID (default: "primary")
        timezone: Timezone for the event
        description: Event description
        location: Event location
        attendees: List of attendee email addresses

    Returns:
        Dictionary with created event information
    """
    try:
        logger.info(f"Creating calendar event: {summary}")

        # Get Google credentials
        creds = _get_google_credentials()
        if not creds:
            raise ValueError("Google Calendar credentials not configured")

        service = build('calendar', 'v3', credentials=creds)

        # Prepare event body
        event = {
            'summary': summary,
            'start': {
                'dateTime': start_time,
                'timeZone': timezone,
            },
            'end': {
                'dateTime': end_time,
                'timeZone': timezone,
            },
        }

        if description:
            event['description'] = description

        if location:
            event['location'] = location

        if attendees:
            event['attendees'] = [{'email': email} for email in attendees]

        # Create the event
        event = service.events().insert(
            calendarId=calendar_id,
            body=event
        ).execute()

        return {
            "event_id": event.get('id'),
            "html_link": event.get('htmlLink'),
            "summary": event.get('summary'),
            "start_time": event.get('start', {}).get('dateTime'),
            "end_time": event.get('end', {}).get('dateTime'),
            "status": event.get('status')
        }

    except Exception as e:
        logger.error(f"Error creating calendar event: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def list_calendar_events(self, calendar_id: str = "primary", time_min: Optional[str] = None,
                        time_max: Optional[str] = None, max_results: int = 10) -> List[Dict[str, Any]]:
    """
    List events from Google Calendar

    Args:
        calendar_id: Calendar ID (default: "primary")
        time_min: Minimum time for events (ISO format)
        time_max: Maximum time for events (ISO format)
        max_results: Maximum number of events to return

    Returns:
        List of calendar events
    """
    try:
        logger.info(f"Listing calendar events from: {calendar_id}")

        # Get Google credentials
        creds = _get_google_credentials()
        if not creds:
            raise ValueError("Google Calendar credentials not configured")

        service = build('calendar', 'v3', credentials=creds)

        # Prepare time parameters
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        time_min = time_min or now
        time_max = time_max or (datetime.utcnow() + timedelta(days=7)).isoformat() + 'Z'

        events_result = service.events().list(
            calendarId=calendar_id,
            timeMin=time_min,
            timeMax=time_max,
            maxResults=max_results,
            singleEvents=True,
            orderBy='startTime'
        ).execute()

        events = events_result.get('items', [])

        # Process and return events
        processed_events = []
        for event in events:
            processed_events.append({
                'id': event.get('id'),
                'summary': event.get('summary', 'No title'),
                'start': event.get('start', {}).get('dateTime', event.get('start', {}).get('date')),
                'end': event.get('end', {}).get('dateTime', event.get('end', {}).get('date')),
                'description': event.get('description'),
                'location': event.get('location'),
                'status': event.get('status'),
                'html_link': event.get('htmlLink')
            })

        return processed_events

    except Exception as e:
        logger.error(f"Error listing calendar events: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def update_calendar_event(self, event_id: str, calendar_id: str = "primary",
                         updates: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    """
    Update an existing calendar event

    Args:
        event_id: Event ID to update
        calendar_id: Calendar ID (default: "primary")
        updates: Dictionary of fields to update

    Returns:
        Dictionary with updated event information
    """
    try:
        logger.info(f"Updating calendar event: {event_id}")

        # Get Google credentials
        creds = _get_google_credentials()
        if not creds:
            raise ValueError("Google Calendar credentials not configured")

        service = build('calendar', 'v3', credentials=creds)

        # Get current event
        event = service.events().get(calendarId=calendar_id, eventId=event_id).execute()

        # Apply updates
        if updates:
            event.update(updates)

        # Update the event
        updated_event = service.events().update(
            calendarId=calendar_id,
            eventId=event_id,
            body=event
        ).execute()

        return {
            "event_id": updated_event.get('id'),
            "summary": updated_event.get('summary'),
            "status": updated_event.get('status'),
            "updated": True
        }

    except Exception as e:
        logger.error(f"Error updating calendar event: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def delete_calendar_event(self, event_id: str, calendar_id: str = "primary") -> Dict[str, Any]:
    """
    Delete a calendar event

    Args:
        event_id: Event ID to delete
        calendar_id: Calendar ID (default: "primary")

    Returns:
        Dictionary with deletion result
    """
    try:
        logger.info(f"Deleting calendar event: {event_id}")

        # Get Google credentials
        creds = _get_google_credentials()
        if not creds:
            raise ValueError("Google Calendar credentials not configured")

        service = build('calendar', 'v3', credentials=creds)

        # Delete the event
        service.events().delete(calendarId=calendar_id, eventId=event_id).execute()

        return {
            "event_id": event_id,
            "deleted": True,
            "message": "Event deleted successfully"
        }

    except Exception as e:
        logger.error(f"Error deleting calendar event: {e}")
        raise self.retry(exc=e, countdown=30)

@shared_task(bind=True, max_retries=3)
def create_calendar_reminder(self, summary: str, reminder_time: str,
                            description: Optional[str] = None) -> Dict[str, Any]:
    """
    Create a calendar reminder (uses calendar events as reminders)

    Args:
        summary: Reminder title
        reminder_time: Time for the reminder (ISO format)
        description: Reminder description

    Returns:
        Dictionary with created reminder information
    """
    try:
        logger.info(f"Creating calendar reminder: {summary}")

        # Calculate end time (15 minutes after reminder time)
        reminder_dt = datetime.fromisoformat(reminder_time.replace('Z', '+00:00'))
        end_dt = reminder_dt + timedelta(minutes=15)
        end_time = end_dt.isoformat()

        # Create a calendar event as a reminder
        return self.create_calendar_event(
            summary=f"Reminder: {summary}",
            start_time=reminder_time,
            end_time=end_time,
            description=description or summary,
            calendar_id="primary"
        )

    except Exception as e:
        logger.error(f"Error creating calendar reminder: {e}")
        raise self.retry(exc=e, countdown=30)

def _get_google_credentials():
    """Get Google API credentials for Calendar access"""
    try:
        creds = None
        token_path = os.getenv('GOOGLE_TOKEN_PATH', '/app/token.json')
        credentials_path = os.getenv('GOOGLE_CREDENTIALS_PATH', '/app/credentials.json')

        if os.path.exists(token_path):
            creds = Credentials.from_authorized_user_file(token_path, SCOPES)

        if not creds or not creds.valid:
            if creds and creds.expired and creds.refresh_token:
                creds.refresh(Request())
            else:
                if not os.path.exists(credentials_path):
                    raise ValueError("Google credentials file not found")

                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, SCOPES)
                creds = flow.run_local_server(port=0)

            # Save the credentials for the next run
            with open(token_path, 'w') as token:
                token.write(creds.to_json())

        return creds

    except Exception as e:
        logger.error(f"Error getting Google credentials: {e}")
        return None
