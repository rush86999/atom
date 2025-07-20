import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials

def get_google_calendar_data(calendar_id):
    """
    Fetches data from a Google Calendar.

    Args:
        calendar_id: The ID of the Google Calendar.

    Returns:
        A dictionary containing the Google Calendar data.
    """
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar.readonly"])
    service = build("calendar", "v3", credentials=creds)

    events_result = service.events().list(calendarId=calendar_id, timeMin="2023-01-01T00:00:00Z").execute()
    events = events_result.get("items", [])

    return {
        "events": events
    }
