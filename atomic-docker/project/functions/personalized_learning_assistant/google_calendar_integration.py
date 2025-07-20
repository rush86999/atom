import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import datetime

def find_free_time(calendar_id, duration_minutes):
    """
    Finds free time in a Google Calendar.

    Args:
        calendar_id: The ID of the Google Calendar.
        duration_minutes: The duration of the free time slot in minutes.

    Returns:
        A list of free time slots.
    """
    creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar.readonly"])
    service = build("calendar", "v3", credentials=creds)

    now = datetime.datetime.utcnow().isoformat() + 'Z'  # 'Z' indicates UTC time
    events_result = service.events().list(
        calendarId=calendar_id, timeMin=now,
        maxResults=10, singleEvents=True,
        orderBy='startTime').execute()
    events = events_result.get('items', [])

    free_time_slots = []
    if not events:
        free_time_slots.append({
            "start": now,
            "end": (datetime.datetime.utcnow() + datetime.timedelta(days=1)).isoformat() + 'Z'
        })
    else:
        last_event_end = now
        for event in events:
            event_start = event['start'].get('dateTime', event['start'].get('date'))
            if (datetime.fromisoformat(event_start[:-1]) - datetime.fromisoformat(last_event_end[:-1])).total_seconds() >= duration_minutes * 60:
                free_time_slots.append({
                    "start": last_event_end,
                    "end": event_start
                })
            last_event_end = event['end'].get('dateTime', event['end'].get('date'))

    return free_time_slots
