import logging
from typing import Optional, List, Dict, Any
from core.llm.byok_handler import BYOKHandler

logger = logging.getLogger(__name__)

class LLMRouter:
    """
    Compatibility layer for legacy LLMRouter.
    Routes calls to the new BYOKHandler system.
    """
    def __init__(self, workspace_id: str = "default"):
        # Note: workspace_id and tenant_id are often used interchangeably in legacy code
        self.handler = BYOKHandler(workspace_id=workspace_id)
        
    async def call(self, tenant_id: str, messages: List[Dict[str, str]], **kwargs) -> Dict[str, Any]:
        """
        Legacy call method.
        """
        # Extract prompt and system instruction
        prompt = ""
        system_instruction = "You are a helpful assistant."
        
        for msg in messages:
            if msg.get("role") == "system":
                system_instruction = msg.get("content", system_instruction)
            elif msg.get("role") == "user":
                prompt = msg.get("content", "")
        
        content = await self.handler.generate_response(
            prompt=prompt,
            system_instruction=system_instruction,
            **kwargs
        )
        
        return {"content": content}

def get_llm_router(workspace_id: str = "default") -> LLMRouter:
    return LLMRouter(workspace_id=workspace_id)
