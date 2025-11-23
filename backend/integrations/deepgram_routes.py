from fastapi import APIRouter, HTTPException

router = APIRouter(prefix="/api/deepgram", tags=["deepgram"])

@router.get("/status")
async def deepgram_status():
    """Status check for Deepgram integration"""
    return {
        "status": "active",
        "service": "deepgram",
        "version": "1.0.0",
        "business_value": {
            "transcription": True,
            "audio_intelligence": True,
            "meeting_notes": True
        }
    }

@router.get("/health")
async def deepgram_health():
    """Health check for Deepgram integration"""
    return await deepgram_status()
