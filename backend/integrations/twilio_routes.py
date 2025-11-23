from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/twilio", tags=["twilio"])

@router.get("/status")
async def twilio_status():
    """Status check for Twilio integration"""
    return {
        "status": "active",
        "service": "twilio",
        "version": "1.0.0",
        "business_value": {
            "sms_automation": True,
            "voice_calls": True,
            "customer_engagement": True
        }
    }

@router.get("/health")
async def twilio_health():
    """Health check for Twilio integration"""
    return await twilio_status()
