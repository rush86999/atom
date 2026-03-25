"""
Voice Service - Voice-to-text and voice command processing
Uses Web Speech API on frontend or Whisper for backend transcription.
"""

import asyncio
import base64
from dataclasses import dataclass
from datetime import datetime
import io
import logging
from typing import Any, Dict, Optional

from core.llm_service import LLMService

logger = logging.getLogger(__name__)


@dataclass
class VoiceTranscription:
    """Result of voice transcription"""
    text: str
    confidence: float
    language: str
    duration_seconds: float
    timestamp: datetime


class VoiceService:
    """
    Voice-to-text service.
    Supports multiple transcription backends:
    - Browser Web Speech API (via frontend)
    - OpenAI Whisper (server-side)
    - Google Cloud Speech-to-Text (future)
    """
    
    def __init__(self, workspace_id: str = "default", tenant_id: str = "default"):
        self.workspace_id = workspace_id
        self.tenant_id = tenant_id
        # Initialize LLMService for unified LLM interactions and BYOK key resolution
        self.llm_service = LLMService(workspace_id=workspace_id, tenant_id=tenant_id)
        self._whisper_available = self._check_whisper_available()
    
    def _check_whisper_available(self) -> bool:
        """Check if transcription is available via LLMService"""
        # We assume it's available if the LLM service is available
        # The actual check happens during transcription
        return self.llm_service.is_available()
    
    async def transcribe_audio(
        self, 
        audio_bytes: bytes, 
        audio_format: str = "webm",
        language: str = "en"
    ) -> VoiceTranscription:
        """
        Transcribe audio to text.
        
        Args:
            audio_bytes: Raw audio bytes
            audio_format: Audio format (webm, wav, mp3)
            language: Language code
            
        Returns:
            VoiceTranscription with text and metadata
        """
        # Always try Whisper via LLMService first
        try:
            return await self._transcribe_with_llm_service(audio_bytes, audio_format, language)
        except Exception as e:
            logger.warning(f"Unified transcription failed, falling back: {e}")
            return await self._transcribe_fallback(audio_bytes, audio_format, language)
    
    async def _transcribe_with_llm_service(
        self,
        audio_bytes: bytes,
        audio_format: str,
        language: str
    ) -> VoiceTranscription:
        """Use unified LLMService for transcription."""
        # Create a file-like object for the API
        audio_file = io.BytesIO(audio_bytes)
        audio_file.name = f"audio.{audio_format}"

        # Call LLMService (which handles BYOK and provider selection)
        result = await self.llm_service.transcribe_audio(
            file=audio_file,
            model="whisper-1",
            language=language
        )

        return VoiceTranscription(
            text=result.get("text", ""),
            confidence=0.95,
            language=language,
            duration_seconds=len(audio_bytes) / 16000,
            timestamp=datetime.utcnow()
        )
    
    async def _transcribe_with_whisper(self, *args, **kwargs):
        """Deprecated: Use _transcribe_with_llm_service instead."""
        return await self._transcribe_with_llm_service(*args, **kwargs)

    async def _transcribe_fallback(
        self, 
        audio_bytes: bytes, 
        audio_format: str,
        language: str
    ) -> VoiceTranscription:
        """Fallback transcription (mock for development)"""
        logger.info("Using fallback voice transcription (mock)")
        
        return VoiceTranscription(
            text="[Voice transcription unavailable]",
            confidence=0.0,
            language=language,
            duration_seconds=0.0,
            timestamp=datetime.utcnow()
        )
    
    async def process_voice_command(
        self, 
        audio_bytes: bytes = None,
        transcribed_text: str = None,
        user_id: str = None
    ) -> Dict[str, Any]:
        """
        Process a voice command through Atom.
        
        Args:
            audio_bytes: Raw audio (will be transcribed)
            transcribed_text: Already transcribed text (from Web Speech API)
            user_id: User making the command
            
        Returns:
            Atom execution result
        """
        # Get text from audio or use provided text
        if transcribed_text:
            text = transcribed_text
            transcription = VoiceTranscription(
                text=text,
                confidence=0.9,
                language="en",
                duration_seconds=0.0,
                timestamp=datetime.utcnow()
            )
        elif audio_bytes:
            transcription = await self.transcribe_audio(audio_bytes)
            text = transcription.text
        else:
            return {"error": "No audio or text provided"}
        
        # Execute through Atom
        try:
            from core.atom_meta_agent import AgentTriggerMode, get_atom_agent
            from core.reasoning_chain import ReasoningStepType, get_reasoning_tracker

            # Start reasoning chain
            tracker = get_reasoning_tracker()
            chain_id = tracker.start_chain()
            
            # Record voice input step
            tracker.add_step(
                step_type=ReasoningStepType.INTENT_ANALYSIS,
                description=f"Voice input received: {text[:50]}...",
                inputs={"transcribed_text": text, "confidence": transcription.confidence},
                outputs={},
                confidence=transcription.confidence
            )
            
            # Execute via Atom
            atom = get_atom_agent(self.workspace_id)
            result = await atom.execute(
                request=text,
                context={"voice_input": True, "user_id": user_id},
                trigger_mode=AgentTriggerMode.MANUAL
            )
            
            # Complete chain
            tracker.complete_chain(outcome=result.get("final_output"), chain_id=chain_id)
            
            return {
                "success": True,
                "transcription": {
                    "text": transcription.text,
                    "confidence": transcription.confidence,
                    "language": transcription.language
                },
                "result": result,
                "reasoning_chain_id": chain_id
            }
            
        except Exception as e:
            logger.error(f"Voice command processing failed: {e}")
            return {"success": False, "error": str(e)}


# Singleton
_voice_service: Optional[VoiceService] = None

def get_voice_service(workspace_id: str = "default", tenant_id: str = "default") -> VoiceService:
    global _voice_service
    if _voice_service is None or _voice_service.workspace_id != workspace_id or getattr(_voice_service, 'tenant_id', 'default') != tenant_id:
        _voice_service = VoiceService(workspace_id, tenant_id)
    return _voice_service
