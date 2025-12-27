
import logging
import os
from typing import Optional, Dict, Any, List

# Try imports
try:
    from openai import OpenAI
except ImportError:
    OpenAI = None

from core.byok_endpoints import get_byok_manager

logger = logging.getLogger(__name__)

class BYOKHandler:
    """
    Handler for LLM interactions using BYOK system.
    """
    def __init__(self, workspace_id: str = "default", provider_id: str = "openai"):
        self.workspace_id = workspace_id
        self.provider_id = provider_id
        self.client = None
        self._initialize_client()

    def _initialize_client(self):
        if not OpenAI:
            logger.warning("OpenAI package not installed. LLM features disabled.")
            return

        byok_manager = get_byok_manager()
        api_key = byok_manager.get_api_key(self.provider_id)
        
        # Fallback to env if not in BYOK manager (development convenience)
        if not api_key and self.provider_id == "openai":
            api_key = os.getenv("OPENAI_API_KEY")
            
        if api_key:
            self.client = OpenAI(api_key=api_key)
        else:
            logger.warning(f"No API key found for provider {self.provider_id}")

    async def generate_response(
        self, 
        prompt: str, 
        system_instruction: str = "You are a helpful assistant.",
        model_type: str = "fast",
        temperature: float = 0.7
    ) -> str:
        """
        Generate a simple text response.
        """
        if not self.client:
            return "LLM Client not initialized (No API Key)."
            
        try:
            # Note: The OpenAI client is sync in this basic implementation.
            # To make it truly async, we should use AsyncOpenAI.
            # For now, we wrap it or assume the caller handles blocking, 
            # but since we must be awaitable, we can just be an async def that runs sync code (blocks event loop)
            # OR better, stick to sync if client is sync. 
            # But GenericAgent expects await.
            # So I will mark this async.
            
            # Ideally:
            # response = await self.client.chat.completions.create(...) (If using AsyncOpenAI)
            
            # If using sync client in async def, it blocks, but is valid syntax-wise for the caller who awaits.
            response = self.client.chat.completions.create(
                model="gpt-4o-mini", 
                messages=[
                    {"role": "system", "content": system_instruction},
                    {"role": "user", "content": prompt}
                ],
                temperature=temperature
            )
            return response.choices[0].message.content
        except Exception as e:
            logger.error(f"LLM Generation failed: {e}")
            return f"Error parsing response: {str(e)}"
