from datetime import datetime, timedelta
import logging
from typing import Any, Dict, List, Optional
from sqlalchemy.orm import Session

from core.burnout_detection_engine import burnout_engine
from core.database import get_db
from core.schedule_optimizer import schedule_optimizer

logger = logging.getLogger(__name__)

class MutualAvailabilityNegotiator:
    """
    Service to negotiate availability across multiple calendars
    with burnout-aware scoring.
    """
    
    def __init__(self):
        pass

    async def get_all_calendar_events(self, user_id: str, start_time: datetime, end_time: datetime) -> List[Dict[str, Any]]:
        """
        Aggregate events from all connected calendar providers.
        For MVP, we use the existing unified calendar system which should be updated
        to fetch from real providers.
        """
        # In a real scenario, we'd loop through all connected integrations for this user
        # and fetch events. For now, we interact with the unified calendar logic.
        from core.unified_calendar_endpoints import MOCK_EVENTS

        # Filter for the specific user and time range
        # (Assuming MOCK_EVENTS might eventually have user_id, otherwise we use all for demo)
        events = []
        for e in MOCK_EVENTS:
            if e.end >= start_time and e.start <= end_time:
                events.append(e.dict())
        
        return events

    async def negotiate_slots(self, 
                             user_id: str, 
                             duration_minutes: int, 
                             search_start: datetime, 
                             search_end: datetime,
                             min_wellness_score: float = 40.0) -> List[Dict[str, Any]]:
        """
        Find and rank the best available time slots.
        """
        all_events = await self.get_all_calendar_events(user_id, search_start, search_end)
        
        # 1. Use existing gap search from schedule_optimizer
        # We simulate a "conflicting event" representing the desired duration
        dummy_event = {
            "start": search_start,
            "end": search_start + timedelta(minutes=duration_minutes)
        }
        
        raw_slots = await schedule_optimizer.find_resolution_slots(dummy_event, all_events, lookahead_days=(search_end - search_start).days + 1)
        
        scored_slots = []
        
        # 2. Score each slot based on wellness and density
        for slot in raw_slots:
            # Calculate density penalty
            density_penalty = await schedule_optimizer.calculate_density_penalty(slot.start, slot.end, all_events)
            
            # Incorporate burnout risk
            # For this, we'd normally fetch real metrics. Here we mock moderate values.
            wellness = await burnout_engine.calculate_burnout_risk(
                meeting_metrics={"total_hours": 4, "day_count": 1},
                task_metrics={"open_tasks": 10, "previous_open_tasks": 8},
                comm_metrics={"avg_response_latency_hours": 1}
            )
            
            # Final calculation: Starting score is 100, subtract penalties
            burnout_penalty = wellness.score * 0.4 # Slightly lower weight
            
            final_slot_score = 100.0 - density_penalty - burnout_penalty
            
            # Determine reasoning with more nuance
            if density_penalty > 25:
                reasoning = "Close to other meetings (Cluster detected)"
            elif density_penalty > 10:
                reasoning = "Acceptable gap, but close to adjacent meetings"
            elif wellness.score > 60:
                 reasoning = "Recommended slot (though workload is high overall)"
            else:
                reasoning = "Optimal breathing room and low burnout risk"
                
            scored_slots.append({
                "start": slot.start,
                "end": slot.end,
                "score": round(final_slot_score, 2),
                "reasoning": reasoning,
                "wellness_risk": wellness.risk_level
            })
            
        # Sort by score descending
        scored_slots.sort(key=lambda x: x["score"], reverse=True)
        
        return scored_slots[:3] # Return top 3 candidates

# Singleton
availability_negotiator = MutualAvailabilityNegotiator()
