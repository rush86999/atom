from datetime import datetime
from typing import Optional
from fastapi import APIRouter, File, HTTPException, UploadFile
from pydantic import BaseModel

try:
    from .deepgram_service import get_deepgram_service
    DEEPGRAM_AVAILABLE = True
except ImportError:
    DEEPGRAM_AVAILABLE = False

# Auth Type: API Key
router = APIRouter(prefix="/api/deepgram", tags=["deepgram"])

class TranscribeURLRequest(BaseModel):
    audio_url: str
    model: str = "nova-2"
    language: str = "en"
    punctuate: bool = True
    diarize: bool = False

@router.post("/transcribe/url")
async def transcribe_url(request: TranscribeURLRequest):
    """Transcribe audio from URL"""
    if not DEEPGRAM_AVAILABLE:
        return {
            "transcript": "Mock transcription of audio from URL",
            "ok": True
        }
    
    try:
        service = get_deepgram_service()
        result = await service.transcribe_url(
            audio_url=request.audio_url,
            model=request.model,
            language=request.language,
            punctuate=request.punctuate,
            diarize=request.diarize
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.post("/transcribe/file")
async def transcribe_file(
    file: UploadFile = File(...),
    model: str = "nova-2",
    language: str = "en",
    punctuate: bool = True,
    diarize: bool = False
):
    """Transcribe audio from uploaded file"""
    if not DEEPGRAM_AVAILABLE:
        return {
            "transcript": "Mock transcription of uploaded file",
            "ok": True
        }
    
    try:
        service = get_deepgram_service()
        audio_data = await file.read()
        mime_type = file.content_type or "audio/wav"
        
        result = await service.transcribe_file(
            audio_data=audio_data,
            mime_type=mime_type,
            model=model,
            language=language,
            punctuate=punctuate,
            diarize=diarize
        )
        return result
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/projects")
async def get_projects():
    """Get Deepgram projects"""
    if not DEEPGRAM_AVAILABLE:
        return {"projects": []}
    
    try:
        service = get_deepgram_service()
        projects = await service.get_projects()
        return {"projects": projects}
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/usage/{project_id}")
async def get_usage(
    project_id: str,
    start_date: Optional[str] = None,
    end_date: Optional[str] = None
):
    """Get usage statistics for a project"""
    if not DEEPGRAM_AVAILABLE:
        return {"usage": {}}
    
    try:
        service = get_deepgram_service()
        usage = await service.get_usage(project_id, start_date, end_date)
        return usage
    except Exception as e:
        raise HTTPException(status_code=400, detail=str(e))

@router.get("/status")
async def deepgram_status():
    """Status check for Deepgram integration"""
    return {
        "status": "active",
        "service": "deepgram",
        "version": "1.0.0",
        "available": DEEPGRAM_AVAILABLE,
        "business_value": {
            "transcription": True,
            "audio_intelligence": True,
            "meeting_notes": True
        }
    }

@router.get("/health")
async def deepgram_health():
    """Health check for Deepgram integration"""
    if DEEPGRAM_AVAILABLE:
        service = get_deepgram_service()
        return await service.health_check()
    return await deepgram_status()
