import os
from googleapiclient.discovery import build
from google.oauth2.credentials import Credentials
import datetime

def get_free_time_slots(calendar_id, start_time, end_time, duration_minutes):
    """
    Finds free time slots in a Google Calendar.

    Args:
        calendar_id: The ID of the Google Calendar.
        start_time: The start time for the search.
        end_time: The end time for the search.
        duration_minutes: The duration of the free time slot in minutes.

    Returns:
        A list of free time slots.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar.readonly"])

    if not creds or not creds.valid:
        raise Exception("Google Calendar credentials are not valid. Please run the authentication flow.")

    service = build("calendar", "v3", credentials=creds)

    body = {
        "timeMin": start_time.isoformat() + "Z",
        "timeMax": end_time.isoformat() + "Z",
        "items": [{"id": calendar_id}],
    }

    events_result = service.freebusy().query(body=body).execute()
    busy_slots = events_result[calendar_id]["busy"]

    free_slots = []
    previous_end_time = start_time
    for busy_slot in busy_slots:
        busy_start_time = datetime.datetime.fromisoformat(busy_slot["start"][:-1])
        busy_end_time = datetime.datetime.fromisoformat(busy_slot["end"][:-1])

        if busy_start_time > previous_end_time:
            free_slots.append({"start": previous_end_time, "end": busy_start_time})

        previous_end_time = busy_end_time

    if end_time > previous_end_time:
        free_slots.append({"start": previous_end_time, "end": end_time})

    return [
        slot for slot in free_slots
        if (slot["end"] - slot["start"]).total_seconds() >= duration_minutes * 60
    ]

def schedule_learning_session(calendar_id, start_time, end_time, summary, description):
    """
    Schedules a learning session in a Google Calendar.

    Args:
        calendar_id: The ID of the Google Calendar.
        start_time: The start time of the learning session.
        end_time: The end time of the learning session.
        summary: The summary of the learning session.
        description: The description of the learning session.
    """
    creds = None
    if os.path.exists("token.json"):
        creds = Credentials.from_authorized_user_file("token.json", ["https://www.googleapis.com/auth/calendar.events"])

    if not creds or not creds.valid:
        raise Exception("Google Calendar credentials are not valid. Please run the authentication flow.")

    service = build("calendar", "v3", credentials=creds)

    event = {
        "summary": summary,
        "description": description,
        "start": {
            "dateTime": start_time.isoformat(),
            "timeZone": "UTC",
        },
        "end": {
            "dateTime": end_time.isoformat(),
            "timeZone": "UTC",
        },
    }

    service.events().insert(calendarId=calendar_id, body=event).execute()
