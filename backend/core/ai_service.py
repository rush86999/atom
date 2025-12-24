import logging
from typing import Any

logger = logging.getLogger(__name__)

def get_ai_service():
    """
    Returns the centralized AI service instance.
    Uses RealAIWorkflowService for production-grade NLU.
    """
    try:
        from enhanced_ai_workflow_endpoints import ai_service
        return ai_service
    except ImportError:
        logger.warning("RealAIWorkflowService not found, falling back to mock.")
        return MockAIService()

class MockAIService:
    """Fallback mock AI service for environments where APIs are not enabled"""
    async def process_with_nlu(self, text, provider="openai", system_prompt=None, user_id="default"):
        return {"nlu_result": {"status": "mocked"}, "confidence": 0.5}
    
    async def analyze_text(self, prompt, complexity=1, system_prompt="", user_id="default"):
        return "Mocked AI response"
