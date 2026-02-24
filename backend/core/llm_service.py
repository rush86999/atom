"""
LLM Service module stub.

This is a placeholder for the LLM service that is referenced by other modules
but not yet fully implemented. The actual implementation will be added when
the feature is developed.
"""

from typing import Any, Dict, List, Optional

# Stub LLM service for imports
class LLMService:
    """
    Stub implementation of LLM service.

    Provides minimal interface to allow imports to work.
    The actual LLM functionality will be implemented separately.
    """

    def __init__(self, model: str = "gpt-4", api_key: Optional[str] = None):
        self.model = model
        self.api_key = api_key
        self.enabled = False  # Stub is always disabled

    async def generate(
        self,
        prompt: str,
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text from prompt."""
        return "[LLM Service Stub: Not Implemented]"

    async def generate_with_history(
        self,
        messages: List[Dict[str, str]],
        max_tokens: int = 1000,
        temperature: float = 0.7,
        **kwargs
    ) -> str:
        """Generate text from conversation history."""
        return "[LLM Service Stub: Not Implemented]"

    def is_available(self) -> bool:
        """Check if LLM service is available."""
        return False
