import logging
import os
import time
from typing import Any, Dict, List, Optional, Union
import httpx
from fastapi import HTTPException

logger = logging.getLogger(__name__)

class OpenAIService:
    """Strategic OpenAI API Service Integration"""
    
    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or os.getenv("OPENAI_API_KEY")
        self.base_url = os.getenv("OPENAI_BASE_URL", "https://api.openai.com/v1")
        self.default_model = os.getenv("OPENAI_DEFAULT_MODEL", "gpt-4o")
        self.timeout = 60.0
        
    def _get_headers(self) -> Dict[str, str]:
        if not self.api_key:
            raise HTTPException(status_code=401, detail="OpenAI API Key not configured")
        return {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    async def generate_completion(
        self, 
        prompt: str, 
        model: Optional[str] = None,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        system_prompt: Optional[str] = None
    ) -> Dict[str, Any]:
        """Generate a chat completion"""
        try:
            async with httpx.AsyncClient(timeout=self.timeout) as client:
                url = f"{self.base_url}/chat/completions"
                
                messages = []
                if system_prompt:
                    messages.append({"role": "system", "content": system_prompt})
                messages.append({"role": "user", "content": prompt})
                
                payload = {
                    "model": model or self.default_model,
                    "messages": messages,
                    "max_tokens": max_tokens,
                    "temperature": temperature
                }
                
                start_time = time.time()
                response = await client.post(url, headers=self._get_headers(), json=payload)
                duration = time.time() - start_time
                
                if response.status_code != 200:
                    logger.error(f"OpenAI error: {response.text}")
                    raise HTTPException(status_code=response.status_code, detail=f"OpenAI API error: {response.text}")
                
                data = response.json()
                return {
                    "content": data["choices"][0]["message"]["content"],
                    "model": data["model"],
                    "usage": data.get("usage", {}),
                    "duration_ms": duration * 1000
                }
        except Exception as e:
            logger.error(f"OpenAI Completion failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def generate_embeddings(self, text: Union[str, List[str]], model: str = "text-embedding-3-small") -> Dict[str, Any]:
        """Generate embeddings for text"""
        try:
            async with httpx.AsyncClient(timeout=20.0) as client:
                url = f"{self.base_url}/embeddings"
                
                payload = {
                    "model": model,
                    "input": text
                }
                
                response = await client.post(url, headers=self._get_headers(), json=payload)
                if response.status_code != 200:
                    raise HTTPException(status_code=response.status_code, detail=f"OpenAI Embeddings error: {response.text}")
                
                return response.json()
        except Exception as e:
            logger.error(f"OpenAI Embeddings failed: {e}")
            raise HTTPException(status_code=500, detail=str(e))

    async def check_health(self) -> Dict[str, Any]:
        """Verify API connectivity and key validity"""
        try:
            # Small cheap call to verify key
            await self.generate_completion("ping", model="gpt-4o-mini", max_tokens=5)
            return {"status": "healthy", "service": "openai", "authenticated": True}
        except Exception as e:
            return {"status": "unhealthy", "service": "openai", "error": str(e), "authenticated": False}

# Global instance
openai_service = OpenAIService()
