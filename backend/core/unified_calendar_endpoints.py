from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional
import uuid
from fastapi import APIRouter, Body, HTTPException, Query
from pydantic import BaseModel, Field

from core.schedule_optimizer import ResolutionSlot, schedule_optimizer

router = APIRouter(prefix="/api/v1/calendar", tags=["unified_calendar"])

# --- Models ---

class Attendee(BaseModel):
    id: str
    name: str
    email: str
    role: str = "required"  # "required" | "optional" | "decision_maker" | "organizer"

class CalendarEvent(BaseModel):
    id: str
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    location: Optional[str] = None
    attendees: Optional[List[Attendee]] = []
    status: str = "confirmed"
    platform: str = "local"
    color: Optional[str] = "#3182CE"
    metadata: Optional[Dict[str, Any]] = {} # Cross-system context (deal_id, etc.)

class CreateEventRequest(BaseModel):
    title: str
    description: Optional[str] = None
    start: datetime
    end: datetime
    location: Optional[str] = None
    status: str = "confirmed"
    platform: str = "local"
    color: Optional[str] = "#3182CE"
    metadata: Optional[Dict[str, Any]] = {}

class UpdateEventRequest(BaseModel):
    title: Optional[str] = None
    description: Optional[str] = None
    start: Optional[datetime] = None
    end: Optional[datetime] = None
    location: Optional[str] = None
    status: Optional[str] = None
    platform: Optional[str] = None
    color: Optional[str] = None

class ConflictCheckRequest(BaseModel):
    start: datetime
    end: datetime
    exclude_event_id: Optional[str] = None  # Exclude this event when checking (for updates)

class ConflictingEvent(BaseModel):
    id: str
    title: str
    start: datetime
    end: datetime
    platform: str

class ConflictResponse(BaseModel):
    has_conflicts: bool
    conflicts: List[ConflictingEvent] = []
    conflict_count: int = 0
    message: str

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
        color="#4285F4",
        attendees=[
            Attendee(id="u1", name="Alice", email="alice@example.com", role="organizer"),
            Attendee(id="u2", name="Bob", email="bob@example.com", role="required")
        ]
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
        color="#0078D4",
        attendees=[
            Attendee(id="u1", name="Alice", email="alice@example.com", role="decision_maker"),
            Attendee(id="u3", name="Charlie", email="charlie@example.com", role="required")
        ]
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

@router.post("/check-conflicts", response_model=ConflictResponse)
async def check_conflicts(request: ConflictCheckRequest):
    """
    Check for scheduling conflicts with existing events.
    Business Outcome: Prevent users from double-booking.
    """
    conflicts = []
    
    for event in MOCK_EVENTS:
        # Skip the event being updated (if checking for update conflicts)
        if request.exclude_event_id and event.id == request.exclude_event_id:
            continue
            
        # Check if events overlap
        # Events overlap if: start1 < end2 AND start2 < end1
        if request.start < event.end and request.end > event.start:
            conflicts.append(ConflictingEvent(
                id=event.id,
                title=event.title,
                start=event.start,
                end=event.end,
                platform=event.platform
            ))
    
    has_conflicts = len(conflicts) > 0
    
    if has_conflicts:
        conflict_titles = [c.title for c in conflicts]
        message = f"⚠️ Scheduling conflict detected with {len(conflicts)} event(s): {', '.join(conflict_titles)}"
    else:
        message = "✅ No conflicts found - time slot is available"
    
    return ConflictResponse(
        has_conflicts=has_conflicts,
        conflicts=conflicts,
        conflict_count=len(conflicts),
        message=message
    )

@router.get("/optimize", response_model=List[Dict[str, Any]])
async def get_schedule_optimization():
    """
    Detect all conflicts and provide resolution suggestions.
    """
    # Convert mock events to dicts for optimizer
    events_as_dict = [e.dict() for e in MOCK_EVENTS]
    conflicts = await schedule_optimizer.detect_all_conflicts(events_as_dict)
    
    resolutions = []
    for conflict in conflicts:
        e1 = conflict["event1"]
        e2 = conflict["event2"]
        p1 = conflict["priority1"]
        p2 = conflict["priority2"]
        
        # Move the event with lower priority
        event_to_move = e2 if p2 <= p1 else e1
        conflict_with = e1 if p2 <= p1 else e2
        
        slots = await schedule_optimizer.find_resolution_slots(event_to_move, events_as_dict)
        
        if slots:
            resolutions.append({
                "type": "conflict",
                "event_to_move": event_to_move["title"],
                "event_id": event_to_move["id"],
                "event_priority": min(p1, p2),
                "conflict_with": conflict_with["title"],
                "suggested_slots": [s.dict() for s in slots],
                "reason": f"Rescheduling lower priority event '{event_to_move['title']}' ({min(p1, p2)} pts) to respect higher priority '{conflict_with['title']}' ({max(p1, p2)} pts)."
            })
            
    return resolutions
