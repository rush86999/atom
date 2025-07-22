import os
from google.oauth2.credentials import Credentials
from google.auth.transport.requests import Request
from google_auth_oauthlib.flow import InstalledAppFlow
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from datetime import datetime, timedelta
from typing import Dict, Any, List

class GoogleCalendarManager:
    """A manager for interacting with the Google Calendar API."""

    def __init__(self, credentials_path: str = 'credentials.json', token_path: str = 'token.json'):
        self.creds = None
        if os.path.exists(token_path):
            self.creds = Credentials.from_authorized_user_file(token_path, ['https://www.googleapis.com/auth/calendar.readonly'])
        if not self.creds or not self.creds.valid:
            if self.creds and self.creds.expired and self.creds.refresh_token:
                self.creds.refresh(Request())
            else:
                flow = InstalledAppFlow.from_client_secrets_file(credentials_path, ['https://www.googleapis.com/auth/calendar.readonly'])
                self.creds = flow.run_local_server(port=0)
            with open(token_path, 'w') as token:
                token.write(self.creds.to_json())
        self.service = build('calendar', 'v3', credentials=self.creds)

    def get_upcoming_events(self, calendar_id: str, max_results: int = 100) -> List[Dict[str, Any]]:
        """Fetches upcoming events from a specific calendar."""
        now = datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
        try:
            events_result = self.service.events().list(
                calendarId=calendar_id, timeMin=now,
                maxResults=max_results, singleEvents=True,
                orderBy='startTime'
            ).execute()
            return events_result.get('items', [])
        except HttpError as e:
            print(f"An error occurred while fetching Google Calendar events: {e}")
            return []

def get_google_calendar_data(calendar_id: str = 'primary') -> Dict[str, Any]:
    """
    Fetches and processes data from a Google Calendar to assess meeting load.

    Args:
        calendar_id: The ID of the Google Calendar to fetch data from.
                     Defaults to 'primary'.

    Returns:
        A dictionary containing Google Calendar data points for project health.
    """
    try:
        gcal_manager = GoogleCalendarManager()
        events = gcal_manager.get_upcoming_events(calendar_id)

        if not events:
            return {
                "number_of_meetings": 0,
                "total_meeting_length": 0,
            }

        total_meeting_length = 0
        for event in events:
            start_str = event.get('start', {}).get('dateTime', event.get('start', {}).get('date'))
            end_str = event.get('end', {}).get('dateTime', event.get('end', {}).get('date'))

            if start_str and end_str:
                # Handle both datetime and date formats
                start_time = datetime.fromisoformat(start_str.replace('Z', '+00:00'))
                end_time = datetime.fromisoformat(end_str.replace('Z', '+00:00'))
                total_meeting_length += (end_time - start_time).total_seconds()

        return {
            "number_of_meetings": len(events),
            "total_meeting_length": total_meeting_length,
        }
    except Exception as e:
        print(f"An unexpected error occurred while processing Google Calendar data: {e}")
        return {
            "number_of_meetings": -1,
            "total_meeting_length": -1,
            "error": str(e),
        }
