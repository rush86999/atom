"""
Voice Service - Voice-to-text and voice command processing
Uses Web Speech API on frontend or Whisper for backend transcription.
"""

import logging
import asyncio
from typing import Dict, Any, Optional
from dataclasses import dataclass
from datetime import datetime
import base64
import io

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
    
    def __init__(self, workspace_id: str = "default"):
        self.workspace_id = workspace_id
        self._whisper_available = self._check_whisper_available()
    
    def _check_whisper_available(self) -> bool:
        """Check if Whisper is available"""
        try:
            import openai
            return True
        except ImportError:
            logger.warning("OpenAI not available for Whisper transcription")
            return False
    
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
        if self._whisper_available:
            return await self._transcribe_with_whisper(audio_bytes, audio_format, language)
        else:
            return await self._transcribe_fallback(audio_bytes, audio_format, language)
    
    async def _transcribe_with_whisper(
        self, 
        audio_bytes: bytes, 
        audio_format: str,
        language: str
    ) -> VoiceTranscription:
        """Use OpenAI Whisper API for transcription"""
        try:
            import openai
            from core.byok_manager import BYOKManager
            
            # Get API key
            byok = BYOKManager()
            api_key = byok.get_key("openai", self.workspace_id)
            
            if not api_key:
                logger.warning("No OpenAI API key found, using fallback")
                return await self._transcribe_fallback(audio_bytes, audio_format, language)
            
            client = openai.AsyncOpenAI(api_key=api_key)
            
            # Create a file-like object
            audio_file = io.BytesIO(audio_bytes)
            audio_file.name = f"audio.{audio_format}"
            
            # Call Whisper
            response = await client.audio.transcriptions.create(
                model="whisper-1",
                file=audio_file,
                language=language
            )
            
            return VoiceTranscription(
                text=response.text,
                confidence=0.95,  # Whisper doesn't return confidence
                language=language,
                duration_seconds=len(audio_bytes) / 16000,  # Rough estimate
                timestamp=datetime.utcnow()
            )
            
        except Exception as e:
            logger.error(f"Whisper transcription failed: {e}")
            return await self._transcribe_fallback(audio_bytes, audio_format, language)
    
    async def _transcribe_fallback(
        self, 
        audio_bytes: bytes, 
        audio_format: str,
        language: str
    ) -> VoiceTranscription:
        """Fallback transcription (mock for development)"""
        # In production, this would use another service
        # For now, return a mock response
        logger.info("Using fallback voice transcription (mock)")
        
        return VoiceTranscription(
            text="[Voice transcription requires Whisper API key]",
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
            from core.atom_meta_agent import get_atom_agent, AgentTriggerMode
            from core.reasoning_chain import get_reasoning_tracker, ReasoningStepType
            
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

def get_voice_service(workspace_id: str = "default") -> VoiceService:
    global _voice_service
    if _voice_service is None or _voice_service.workspace_id != workspace_id:
        _voice_service = VoiceService(workspace_id)
    return _voice_service
