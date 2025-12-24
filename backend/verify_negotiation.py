import asyncio
import sys
from datetime import datetime, timedelta
from pathlib import Path

# Add project root to path
backend_root = Path(__file__).parent.parent.resolve()
if str(backend_root) not in sys.path:
    sys.path.insert(0, str(backend_root))

from core.availability_negotiator import availability_negotiator
from core.unified_calendar_endpoints import MOCK_EVENTS, CalendarEvent, Attendee

async def verify_negotiation():
    print("🚀 Starting Mutual Availability Negotiation Verification...")
    
    user_id = "test_user"
    search_start = datetime.now().replace(hour=9, minute=0, second=0, microsecond=0)
    search_end = search_start + timedelta(days=2)
    
    # 1. Setup a busy calendar with a cluster
    # 10:00 - 11:00 (Busy)
    # 11:00 - 12:00 (Busy)
    # 12:00 - 13:00 (Free)
    # 13:00 - 14:00 (Busy)
    # 15:00 - 17:00 (Free - Big Gap)
    
    MOCK_EVENTS.clear()
    MOCK_EVENTS.extend([
        CalendarEvent(
            id="e1", title="Meeting 1", start=search_start + timedelta(hours=1), 
            end=search_start + timedelta(hours=2), platform="google"
        ),
        CalendarEvent(
            id="e2", title="Meeting 2", start=search_start + timedelta(hours=2), 
            end=search_start + timedelta(hours=3), platform="outlook"
        ),
        CalendarEvent(
            id="e3", title="Meeting 3", start=search_start + timedelta(hours=4), 
            end=search_start + timedelta(hours=5), platform="local"
        )
    ])
    
    print("\nSimulated Schedule:")
    print("- 10:00-11:00: Meeting 1")
    print("- 11:00-12:00: Meeting 2")
    print("- 12:00-13:00: GAP")
    print("- 13:00-14:00: Meeting 3")
    print("- 14:00 onwards: WIDE OPEN")

    # Request a 30 min meeting
    print("\nNegotiating for a 60-minute meeting...")
    slots = await availability_negotiator.negotiate_slots(
        user_id=user_id,
        duration_minutes=60,
        search_start=search_start,
        search_end=search_end
    )
    
    for i, slot in enumerate(slots):
        print(f"Option {i+1}: {slot['start'].strftime('%H:%M')} - {slot['end'].strftime('%H:%M')} | Score: {slot['score']} | {slot['reasoning']}")

    # Verification:
    # Option 1 should be the wide open gap (no cluster penalty)
    # Option 2/3 might be the 12:00-13:00 slot (high cluster penalty because it's between e2 and e3)
    
    best_slot = slots[0]
    if "Recommended slot" in best_slot["reasoning"] and best_slot["start"].hour >= 14:
        print("\n✅ Verification SUCCESS: Negotiator prioritized the slot with breathing room!")
    else:
        print("\n❌ Verification FAILED: Negotiator did not prioritize the open gap correctly.")

    print("\n🎉 Mutual Availability Negotiation Verification Complete!")

if __name__ == "__main__":
    asyncio.run(verify_negotiation())
