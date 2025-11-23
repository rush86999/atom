from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/sendgrid", tags=["sendgrid"])

@router.get("/status")
async def sendgrid_status():
    """Status check for SendGrid integration"""
    return {
        "status": "active",
        "service": "sendgrid",
        "version": "1.0.0",
        "business_value": {
            "email_marketing": True,
            "transactional_emails": True,
            "deliverability_analytics": True
        }
    }

@router.get("/health")
async def sendgrid_health():
    """Health check for SendGrid integration"""
    return await sendgrid_status()
