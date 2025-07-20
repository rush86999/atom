import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import datetime

def get_google_calendar_data(calendar_id):
    """
    Fetches data from a Google Calendar.

    Args:
        calendar_id: The ID of the Google Calendar.

    Returns:
        A dictionary containing the Google Calendar data.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar.readonly"])

    if not creds or not creds.valid:
        raise Exception("Google Calendar credentials are not valid. Please run the authentication flow.")

    service = build("calendar", "v3", credentials=creds)

    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = service.events().list(
        calendarId=calendar_id, timeMin=now,
        maxResults=100, singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    meeting_count = len(events)
    total_meeting_duration = 0
    for event in events:
        if "start" in event and "end" in event and "dateTime" in event["start"] and "dateTime" in event["end"]:
            start = datetime.datetime.fromisoformat(event["start"]["dateTime"])
            end = datetime.datetime.fromisoformat(event["end"]["dateTime"])
            total_meeting_duration += (end - start).total_seconds()

    return {
        "meeting_count": meeting_count,
        "average_meeting_duration": total_meeting_duration / meeting_count if meeting_count > 0 else 0
    }
