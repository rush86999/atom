"""
Deepgram Service for ATOM Platform
Provides comprehensive Deepgram speech recognition and AI audio processing integration functionality
"""

import logging
import os
from typing import Any, Dict, List, Optional
from datetime import datetime
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class DeepgramService:
    def __init__(self):
        self.api_key = os.getenv("DEEPGRAM_API_KEY")
        self.base_url = "https://api.deepgram.com/v1"
        self.client = httpx.AsyncClient(timeout=60.0)

    async def close(self):
        """Close the HTTP client connection"""
        await self.client.aclose()

    def _get_headers(self) -> Dict[str, str]:
        """Get headers for API requests"""
        return {
            "Authorization": f"Token {self.api_key}",
            "Content-Type": "application/json"
        }

    async def transcribe_url(
        self,
        audio_url: str,
        model: str = "nova-2",
        language: str = "en",
        punctuate: bool = True,
        diarize: bool = False
    ) -> Dict[str, Any]:
        """Transcribe audio from URL"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            params = {
                "model": model,
                "language": language,
                "punctuate": str(punctuate).lower(),
                "diarize": str(diarize).lower()
            }
            
            payload = {"url": audio_url}
            
            response = await self.client.post(
                f"{self.base_url}/listen",
                headers=headers,
                json=payload,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to transcribe audio: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to transcribe audio: {str(e)}"
            )

    async def transcribe_file(
        self,
        audio_data: bytes,
        mime_type: str = "audio/wav",
        model: str = "nova-2",
        language: str = "en",
        punctuate: bool = True,
        diarize: bool = False
    ) -> Dict[str, Any]:
        """Transcribe audio from file data"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = {
                "Authorization": f"Token {self.api_key}",
                "Content-Type": mime_type
            }
            
            params = {
                "model": model,
                "language": language,
                "punctuate": str(punctuate).lower(),
                "diarize": str(diarize).lower()
            }
            
            response = await self.client.post(
                f"{self.base_url}/listen",
                headers=headers,
                content=audio_data,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to transcribe file: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to transcribe file: {str(e)}"
            )

    async def get_projects(self) -> List[Dict[str, Any]]:
        """Get Deepgram projects"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            
            response = await self.client.get(
                f"{self.base_url}/projects",
                headers=headers
            )
            response.raise_for_status()
            
            data = response.json()
            return data.get("projects", [])
        except httpx.HTTPError as e:
            logger.error(f"Failed to get projects: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get projects: {str(e)}"
            )

    async def get_usage(
        self,
        project_id: str,
        start_date: str = None,
        end_date: str = None
    ) -> Dict[str, Any]:
        """Get usage statistics for a project"""
        try:
            if not self.api_key:
                raise HTTPException(status_code=401, detail="Not authenticated")
            
            headers = self._get_headers()
            params = {}
            
            if start_date:
                params["start"] = start_date
            if end_date:
                params["end"] = end_date
            
            response = await self.client.get(
                f"{self.base_url}/projects/{project_id}/usage",
                headers=headers,
                params=params
            )
            response.raise_for_status()
            
            return response.json()
        except httpx.HTTPError as e:
            logger.error(f"Failed to get usage: {e}")
            raise HTTPException(
                status_code=400,
                detail=f"Failed to get usage: {str(e)}"
            )

    async def health_check(self) -> Dict[str, Any]:
        """Health check for Deepgram service"""
        try:
            return {
                "ok": True,
                "status": "healthy",
                "service": "deepgram",
                "timestamp": datetime.now().isoformat(),
                "version": "1.0.0",
            }
        except Exception as e:
            return {
                "ok": False,
                "status": "unhealthy",
                "service": "deepgram",
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

deepgram_service = DeepgramService()

def get_deepgram_service() -> DeepgramService:
    return deepgram_service
