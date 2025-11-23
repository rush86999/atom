from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/calendly", tags=["calendly"])

@router.get("/status")
async def calendly_status():
    """Status check for Calendly integration"""
    return {
        "status": "active",
        "service": "calendly",
        "version": "1.0.0",
        "business_value": {
            "scheduling_automation": True,
            "availability_management": True,
            "meeting_booking": True
        }
    }

@router.get("/health")
async def calendly_health():
    """Health check for Calendly integration"""
    return await calendly_status()
