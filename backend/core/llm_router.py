import logging
from typing import Optional, List, Dict, Any
from core.llm_service import get_llm_service

logger = logging.getLogger(__name__)

class LLMRouter:
    """
    Compatibility layer for legacy LLMRouter.
    Routes calls to the new LLMService system.
    """
    def __init__(self, workspace_id: str = "default"):
        self.service = get_llm_service(workspace_id=workspace_id)
        
    async def call(self, tenant_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Legacy call method.
        """
        return await self.service.generate_completion(
            messages=messages,
            **kwargs
        )

def get_llm_router(workspace_id: str = "default") -> LLMRouter:
    return LLMRouter(workspace_id=workspace_id)
