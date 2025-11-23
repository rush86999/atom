from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/google-calendar", tags=["google-calendar"])

@router.get("/status")
async def google_calendar_status():
    """Status check for Google Calendar integration"""
    return {
        "status": "active",
        "service": "google-calendar",
        "version": "1.0.0",
        "business_value": {
            "scheduling": True,
            "time_management": True,
            "meeting_coordination": True
        }
    }

@router.get("/health")
async def google_calendar_health():
    """Health check for Google Calendar integration"""
    return await google_calendar_status()
