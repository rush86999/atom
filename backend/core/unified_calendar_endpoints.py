from fastapi import APIRouter, HTTPException, Query, Body
from pydantic import BaseModel, Field
from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
import uuid

router = APIRouter(prefix="/api/v1/calendar", tags=["unified_calendar"])

# --- Models ---

class CalendarEvent(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees: Optional[List[str]] = []
    status: str = "confirmed"  # "confirmed" | "tentative" | "cancelled"
    platform: str = "local"  # "google" | "outlook" | "local"
    color: Optional[str] = "#3182CE"

class CreateEventRequest(BaseModel):
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    location: Optional[str] = None
    status: str = "confirmed"
    platform: str = "local"
    color: Optional[str] = "#3182CE"

class UpdateEventRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    platform: Optional[str] = None
    color: Optional[str] = None

# --- Mock Storage ---

MOCK_EVENTS: List[CalendarEvent] = [
    CalendarEvent(
        id="1",
        title="Team Standup",
        description="Daily sync",
        start=datetime.now().replace(hour=10, minute=0, second=0, microsecond=0),
        end=datetime.now().replace(hour=10, minute=30, second=0, microsecond=0),
        location="Zoom",
        status="confirmed",
        platform="google",
        color="#4285F4"
    ),
    CalendarEvent(
        id="2",
        title="Project Review",
        description="Weekly review with stakeholders",
        start=datetime.now().replace(hour=14, minute=0, second=0, microsecond=0) + timedelta(days=1),
        end=datetime.now().replace(hour=15, minute=0, second=0, microsecond=0) + timedelta(days=1),
        location="Conference Room A",
        status="confirmed",
        platform="outlook",
        color="#0078D4"
    )
]

# --- Endpoints ---

@router.get("/events", response_model=Dict[str, Any])
async def get_events(
    start: Optional[datetime] = None,
    end: Optional[datetime] = None
):
    # Filter by date range if provided
    filtered_events = MOCK_EVENTS
    if start:
        filtered_events = [e for e in filtered_events if e.end >= start]
    if end:
        filtered_events = [e for e in filtered_events if e.start <= end]
        
    return {"success": True, "events": filtered_events}

@router.post("/events", response_model=Dict[str, Any])
async def create_event(event_data: CreateEventRequest):
    new_event = CalendarEvent(
        id=str(uuid.uuid4()),
        **event_data.dict()
    )
    MOCK_EVENTS.append(new_event)
    return {"success": True, "event": new_event}

@router.put("/events/{event_id}", response_model=Dict[str, Any])
async def update_event(event_id: str, updates: UpdateEventRequest):
    for i, event in enumerate(MOCK_EVENTS):
        if event.id == event_id:
            update_data = updates.dict(exclude_unset=True)
            updated_event = event.copy(update=update_data)
            MOCK_EVENTS[i] = updated_event
            return {"success": True, "event": updated_event}
            
    raise HTTPException(status_code=404, detail="Event not found")

@router.delete("/events/{event_id}", response_model=Dict[str, Any])
async def delete_event(event_id: str):
    global MOCK_EVENTS
    event_to_delete = next((e for e in MOCK_EVENTS if e.id == event_id), None)
    if not event_to_delete:
        raise HTTPException(status_code=404, detail="Event not found")
        
    MOCK_EVENTS = [e for e in MOCK_EVENTS if e.id != event_id]
    return {"success": True, "id": event_id}
