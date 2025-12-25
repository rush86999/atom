"""
Voice API Routes - Voice input and reasoning chain endpoints
"""

import logging
from fastapi import APIRouter, Depends, HTTPException, UploadFile, File
from typing import Dict, Any, Optional
from pydantic import BaseModel

from core.models import User
from core.security_dependencies import require_permission
from core.rbac_service import Permission
from core.voice_service import get_voice_service, VoiceService
from core.reasoning_chain import get_reasoning_tracker

logger = logging.getLogger(__name__)

router = APIRouter()


class VoiceCommandRequest(BaseModel):
    text: str  # Transcribed text from Web Speech API
    language: str = "en"


class AudioTranscribeRequest(BaseModel):
    audio_base64: str  # Base64 encoded audio
    format: str = "webm"
    language: str = "en"


# ==================== VOICE ENDPOINTS ====================

@router.post("/transcribe")
async def transcribe_audio(
    request: AudioTranscribeRequest,
    user: User = Depends(require_permission(Permission.AGENT_VIEW))
):
    """
    Transcribe audio to text using Whisper or fallback.
    """
    import base64
    
    try:
        audio_bytes = base64.b64decode(request.audio_base64)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Invalid base64 audio: {e}")
    
    service = get_voice_service()
    transcription = await service.transcribe_audio(
        audio_bytes=audio_bytes,
        audio_format=request.format,
        language=request.language
    )
    
    return {
        "success": True,
        "text": transcription.text,
        "confidence": transcription.confidence,
        "language": transcription.language
    }


@router.post("/command")
async def process_voice_command(
    request: VoiceCommandRequest,
    user: User = Depends(require_permission(Permission.AGENT_RUN))
):
    """
    Process a voice command through Atom.
    Text is already transcribed (by Web Speech API in browser).
    """
    service = get_voice_service()
    result = await service.process_voice_command(
        transcribed_text=request.text,
        user_id=user.id
    )
    
    if not result.get("success"):
        raise HTTPException(status_code=500, detail=result.get("error"))
    
    return result


@router.post("/upload")
async def upload_and_process_audio(
    file: UploadFile = File(...),
    language: str = "en",
    user: User = Depends(require_permission(Permission.AGENT_RUN))
):
    """
    Upload audio file, transcribe, and process as command.
    """
    audio_bytes = await file.read()
    
    # Determine format from filename
    audio_format = file.filename.split(".")[-1] if file.filename else "webm"
    
    service = get_voice_service()
    
    # Transcribe
    transcription = await service.transcribe_audio(
        audio_bytes=audio_bytes,
        audio_format=audio_format,
        language=language
    )
    
    # Process command
    result = await service.process_voice_command(
        transcribed_text=transcription.text,
        user_id=user.id
    )
    
    return result


# ==================== REASONING CHAIN ENDPOINTS ====================

@router.get("/reasoning/{chain_id}")
async def get_reasoning_chain(
    chain_id: str,
    user: User = Depends(require_permission(Permission.AGENT_VIEW))
):
    """
    Get a reasoning chain by ID with Mermaid diagram.
    """
    tracker = get_reasoning_tracker()
    chain = tracker.get_chain(chain_id)
    
    if not chain:
        raise HTTPException(status_code=404, detail=f"Reasoning chain {chain_id} not found")
    
    return chain.to_dict()


@router.get("/reasoning")
async def list_reasoning_chains(
    limit: int = 20,
    user: User = Depends(require_permission(Permission.AGENT_VIEW))
):
    """
    List recent reasoning chains.
    """
    tracker = get_reasoning_tracker()
    chains = tracker.get_all_chains(limit=limit)
    
    return {
        "chains": [
            {
                "execution_id": c.execution_id,
                "started_at": c.started_at.isoformat(),
                "completed_at": c.completed_at.isoformat() if c.completed_at else None,
                "step_count": len(c.steps),
                "final_outcome": c.final_outcome,
                "total_duration_ms": c.total_duration_ms
            }
            for c in chains
        ]
    }


# ==================== REASONING FEEDBACK ENDPOINTS ====================

class StepFeedbackRequest(BaseModel):
    feedback_type: str  # "approve", "reject", "suggest", "explain"
    comment: str
    suggested_alternative: Optional[str] = None


@router.post("/reasoning/{chain_id}/steps/{step_id}/feedback")
async def submit_step_feedback(
    chain_id: str,
    step_id: str,
    request: StepFeedbackRequest,
    user: User = Depends(require_permission(Permission.AGENT_VIEW))
):
    """
    Submit feedback on a specific reasoning step.
    Users with matching specialty (or admin role) trigger agent learning.
    """
    from core.reasoning_chain import FeedbackType
    
    # Validate feedback type
    try:
        feedback_type = FeedbackType(request.feedback_type)
    except ValueError:
        raise HTTPException(
            status_code=400, 
            detail=f"Invalid feedback type. Must be one of: approve, reject, suggest, explain"
        )
    
    tracker = get_reasoning_tracker()
    feedback = await tracker.submit_step_feedback(
        chain_id=chain_id,
        step_id=step_id,
        user_id=user.id,
        feedback_type=feedback_type,
        comment=request.comment,
        suggested_alternative=request.suggested_alternative
    )
    
    if not feedback:
        raise HTTPException(status_code=404, detail="Chain or step not found")
    
    return {
        "success": True,
        "feedback_id": feedback.id,
        "is_trusted": feedback.is_trusted,
        "message": "Feedback submitted. Agent learning triggered." if feedback.is_trusted else "Feedback recorded for review."
    }

