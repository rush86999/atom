from typing import List, Dict, Any, Optional
from datetime import datetime, timedelta
from pydantic import BaseModel

class ResolutionSlot(BaseModel):
    start: datetime
    end: datetime
    reason: str

class ConflictResolution(BaseModel):
    event_id: str
    original_start: datetime
    suggested_start: datetime
    suggested_end: datetime
    conflict_event_id: str

class ScheduleOptimizer:
    """Engine to resolve scheduling conflicts and find optimal gaps"""
    
    def __init__(self):
        pass

    async def find_resolution_slots(self, 
                                   conflicting_event: Dict[str, Any], 
                                   all_events: List[Dict[str, Any]],
                                   lookahead_days: int = 3) -> List[ResolutionSlot]:
        """
        Finds the first available slots for a conflicting event.
        """
        duration = (conflicting_event["end"] - conflicting_event["start"])
        start_search = conflicting_event["end"] # Start looking after the conflict
        end_search = start_search + timedelta(days=lookahead_days)
        
        # Sort all events by start time
        sorted_events = sorted(all_events, key=lambda x: x["start"])
        
        available_slots = []
        current_time = start_search
        
        # Simple gap search
        while current_time < end_search:
            # Check if current_time to current_time + duration is free
            potential_end = current_time + duration
            conflict = False
            
            for event in sorted_events:
                if current_time < event["end"] and potential_end > event["start"]:
                    conflict = True
                    # Jump to the end of this conflicting event to save cycles
                    current_time = event["end"]
                    break
            
            if not conflict:
                available_slots.append(ResolutionSlot(
                    start=current_time,
                    end=potential_end,
                    reason="First available gap after conflict"
                ))
                if len(available_slots) >= 3:
                    break
                current_time = potential_end # Move past this slot
            
            # Small increment if no conflict found but we want next gap
            current_time += timedelta(minutes=15)
            
        return available_slots

    async def calculate_priority(self, event: Dict[str, Any]) -> int:
        """Calculate priority score based on attendee roles"""
        role_weights = {
            "decision_maker": 100,
            "organizer": 80,
            "required": 50,
            "optional": 10
        }
        
        score = 0
        attendees = event.get("attendees", [])
        for attendee in attendees:
            role = attendee.get("role", "required") if isinstance(attendee, dict) else "required"
            score += role_weights.get(role, 50)
            
        return score

    async def detect_all_conflicts(self, all_events: List[Dict[str, Any]]) -> List[Dict[str, Any]]:
        """
        Identifies all overlapping events in a list, with priority info.
        """
        conflicts = []
        sorted_events = sorted(all_events, key=lambda x: x["start"])
        
        for i in range(len(sorted_events)):
            for j in range(i + 1, len(sorted_events)):
                e1 = sorted_events[i]
                e2 = sorted_events[j]
                
                # Check for overlap
                if e1["start"] < e2["end"] and e1["end"] > e2["start"]:
                    # New: add priority info
                    p1 = await self.calculate_priority(e1)
                    p2 = await self.calculate_priority(e2)
                    
                    conflicts.append({
                        "event1": e1,
                        "event2": e2,
                        "priority1": p1,
                        "priority2": p2,
                        "overlap_minutes": (min(e1["end"], e2["end"]) - max(e1["start"], e2["start"])).total_seconds() / 60
                    })
                elif e2["start"] > e1["end"]:
                    break
                    
        return conflicts

schedule_optimizer = ScheduleOptimizer()
