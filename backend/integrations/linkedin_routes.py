from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/linkedin", tags=["linkedin"])

@router.get("/status")
async def linkedin_status():
    """Status check for LinkedIn integration"""
    return {
        "status": "active",
        "service": "linkedin",
        "version": "1.0.0",
        "business_value": {
            "networking": True,
            "lead_generation": True,
            "brand_awareness": True
        }
    }

@router.get("/health")
async def linkedin_health():
    """Health check for LinkedIn integration"""
    return await linkedin_status()
