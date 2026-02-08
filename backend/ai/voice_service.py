from abc import ABC, abstractmethod
import base64
import json
import logging
import os
from typing import Any, Dict, Optional, Union
import aiohttp

logger = logging.getLogger(__name__)

class TextToSpeechProvider(ABC):
    @abstractmethod
    async def generate_audio(self, text: str, voice_id: Optional[str] = None) -> Optional[bytes]:
        """Generate audio from text and return raw bytes"""
        pass

class MockTTSProvider(TextToSpeechProvider):
    async def generate_audio(self, text: str, voice_id: Optional[str] = None) -> Optional[bytes]:
        # Return a tiny blank MP3 or similar dummy bytes
        # minimal 1 frame MP3
        return base64.b64decode("SUQzBAAAAAAAI1RTU0UAAAAPAAADTGF2ZjU4LjI5LjEwMAAAAAAAAAAAAAAA//OEAAAAAAAAAAAAAAAAAAAAAAA=")

class ElevenLabsProvider(TextToSpeechProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        self.base_url = "https://api.elevenlabs.io/v1"
        self.default_voice = "21m00Tcm4TlvDq8ikWAM" # Rachel

    async def generate_audio(self, text: str, voice_id: Optional[str] = None) -> Optional[bytes]:
        voice_id = voice_id or self.default_voice
        url = f"{self.base_url}/text-to-speech/{voice_id}"
        
        headers = {
            "xi-api-key": self.api_key,
            "Content-Type": "application/json"
        }
        
        payload = {
            "text": text,
            "model_id": "eleven_monolingual_v1",
            "voice_settings": {
                "stability": 0.5,
                "similarity_boost": 0.5
            }
        }

        async with aiohttp.ClientSession() as session:
            try:
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        error_text = await response.text()
                        logger.error(f"ElevenLabs error: {response.status} - {error_text}")
                        return None
            except Exception as e:
                logger.error(f"ElevenLabs connection failed: {e}")
                return None

class DeepgramProvider(TextToSpeechProvider):
    def __init__(self, api_key: str):
        self.api_key = api_key
        # Deepgram's TTS endpoint structure might vary, this is a standard Aura placeholder
        self.base_url = "https://api.deepgram.com/v1/speak" 

    async def generate_audio(self, text: str, voice_id: Optional[str] = None) -> Optional[bytes]:
        headers = {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }
        
        # Deepgram Aura defaults
        payload = {
            "text": text
        }
        
        # Add model/voice if specified, else generic default
        if voice_id:
            # Use the specified voice_id model instead of default
            url = f"{self.base_url}?model={voice_id}" 

        async with aiohttp.ClientSession() as session:
            try:
                # Note: Deepgram TTS is usually content negotiation or specific params
                # Assuming simple POST for MVP based on common patterns
                # Construct URL with model query param for Aura
                url = f"{self.base_url}?model=aura-asteria-en"
                
                async with session.post(url, json=payload, headers=headers) as response:
                    if response.status == 200:
                        return await response.read()
                    else:
                        logger.error(f"Deepgram error: {response.status} - {await response.text()}")
                        return None
            except Exception as e:
                logger.error(f"Deepgram connection failed: {e}")
                return None

class VoiceService:
    def __init__(self):
        # In a real scenario, we'd inject configuration or fetch from DB credentials
        # For now, we instantiate on demand or check env/db in methods
        pass

    async def text_to_speech(self, text: str, provider_name: str = "elevenlabs", api_key: Optional[str] = None) -> Optional[str]:
        """
        Convert text to speech and return base64 encoded audio.
        """
        if not text:
            return None

        provider: Optional[TextToSpeechProvider] = None

        if provider_name == "elevenlabs" and api_key:
            provider = ElevenLabsProvider(api_key)
        elif provider_name == "deepgram" and api_key:
            provider = DeepgramProvider(api_key)
        else:
             # Fallback to Mock for Dev/Testing if no keys
             logger.info("Using Mock TTS Provider")
             provider = MockTTSProvider()
        
        if not provider:
            logger.warning(f"No valid TTS provider found for {provider_name}")
            return None

        audio_bytes = await provider.generate_audio(text)
        if audio_bytes:
            return base64.b64encode(audio_bytes).decode('utf-8')
        
        return None

# Singleton or factory
voice_service = VoiceService()
