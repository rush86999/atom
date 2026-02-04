import logging
import os
from typing import Any

logger = logging.getLogger(__name__)

# Feature flag to allow mock in development/testing
ALLOW_MOCK_AI = os.getenv("ALLOW_MOCK_AI", "false").lower() == "true"

def get_ai_service():
    """
    Returns the centralized AI service instance.
    Uses RealAIWorkflowService for production-grade NLU.

    Raises:
        ImportError: If AI service is not available and ALLOW_MOCK_AI is False

    Environment Variables:
        ALLOW_MOCK_AI: Set to 'true' to allow mock fallback for development/testing
    """
    try:
        from enhanced_ai_workflow_endpoints import ai_service
        return ai_service
    except ImportError:
        if ALLOW_MOCK_AI:
            logger.warning("RealAIWorkflowService not found, using mock (ALLOW_MOCK_AI=true)")
            return MockAIService()
        else:
            error_msg = (
                "AI Service (RealAIWorkflowService) not found. "
                "Please ensure the enhanced AI workflow endpoints are available. "
                "For development/testing only, set ALLOW_MOCK_AI=true environment variable."
            )
            logger.error(error_msg)
            raise ImportError(error_msg)

class MockAIService:
    """
    Fallback mock AI service for development/testing environments only.

    WARNING: This mock should NEVER be used in production as it returns
    hardcoded responses without any actual AI processing.
    """
    async def process_with_nlu(self, text, provider="openai", system_prompt=None, user_id="default"):
        logger.warning("MockAIService.process_with_nlu called - returning mocked response")
        return {"nlu_result": {"status": "mocked"}, "confidence": 0.5}

    async def analyze_text(self, prompt, complexity=1, system_prompt="", user_id="default"):
        logger.warning("MockAIService.analyze_text called - returning mocked response")
        return "Mocked AI response - DO NOT USE IN PRODUCTION"
