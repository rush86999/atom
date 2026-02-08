"""
AI Service Module - Production-Ready AI Processing with Governance

This module provides access to the RealAIWorkflowService for natural language understanding,
text analysis, and AI-powered workflow execution with multi-provider support and governance.

Features:
- Multi-provider support (OpenAI, Anthropic, DeepSeek, Gemini)
- Governance integration with action complexity checks
- Automatic provider selection based on query complexity
- Trajectory recording for audit trails
- Graceful fallback with proper error handling

Usage:
    from core.ai_service import get_ai_service

    ai_service = get_ai_service()

    # NLU processing with workflow suggestions
    result = await ai_service.process_with_nlu(
        text="Schedule a meeting tomorrow",
        provider="openai",
        user_id="user123"
    )

    # Text analysis with governance
    analysis = await ai_service.analyze_text(
        prompt="Analyze this document",
        complexity=2,
        system_prompt="You are a helpful assistant",
        user_id="user123"
    )
"""

import logging
import os
from typing import Any, Optional

logger = logging.getLogger(__name__)

# Feature flag to allow mock in development/testing
# WARNING: Never set to true in production!
ALLOW_MOCK_AI = os.getenv("ALLOW_MOCK_AI", "false").lower() == "true"


def get_ai_service():
    """
    Returns the centralized AI service instance.

    The service provides:
    - process_with_nlu(): Natural language understanding with workflow suggestions
    - analyze_text(): Text analysis with governance checks
    - run_react_agent(): ReAct loop for agentic behavior
    - Multi-provider support (OpenAI, Anthropic, DeepSeek, Gemini)

    Returns:
        RealAIWorkflowService instance with multi-provider AI capabilities

    Raises:
        ImportError: If AI service is not available and ALLOW_MOCK_AI is False

    Environment Variables:
        ALLOW_MOCK_AI: Set to 'true' to allow mock fallback for development/testing only

    Example:
        >>> ai_service = get_ai_service()
        >>> result = await ai_service.process_with_nlu("Hello world")
        >>> print(result['intent'])
    """
    try:
        from enhanced_ai_workflow_endpoints import ai_service as _ai_service
        logger.info("RealAIWorkflowService loaded successfully")
        return _ai_service
    except ImportError as e:
        if ALLOW_MOCK_AI:
            logger.warning(
                f"RealAIWorkflowService not found ({e}), using mock (ALLOW_MOCK_AI=true). "
                "WARNING: Mock service should NEVER be used in production!"
            )
            return MockAIService()
        else:
            error_msg = (
                f"AI Service (RealAIWorkflowService) not found: {e}. "
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

    Attributes:
        All methods return static mock responses for testing purposes only.

    Usage:
        Only used when ALLOW_MOCK_AI=true is set (development/testing only)
    """

    async def process_with_nlu(
        self,
        text: str,
        provider: str = "openai",
        system_prompt: Optional[str] = None,
        user_id: str = "default"
    ) -> dict:
        """
        Mock NLU processing - returns static response.

        WARNING: This is a MOCK implementation for testing only.
        """
        logger.warning(
            f"MockAIService.process_with_nlu called for user '{user_id}' - "
            "returning mocked response. DO NOT USE IN PRODUCTION!"
        )
        return {
            "nlu_result": {"status": "mocked", "intent": "mock_intent"},
            "confidence": 0.5,
            "warning": "This is a mock response - enable RealAIWorkflowService for production"
        }

    async def analyze_text(
        self,
        prompt: str,
        complexity: int = 1,
        system_prompt: str = "",
        user_id: str = "default"
    ) -> str:
        """
        Mock text analysis - returns static response.

        WARNING: This is a MOCK implementation for testing only.
        """
        logger.warning(
            f"MockAIService.analyze_text called with complexity {complexity} for user '{user_id}' - "
            "returning mocked response. DO NOT USE IN PRODUCTION!"
        )
        return (
            "Mocked AI response - DO NOT USE IN PRODUCTION. "
            "Enable RealAIWorkflowService by setting ALLOW_MOCK_AI=false "
            "and ensuring enhanced_ai_workflow_endpoints is available."
        )

    async def run_react_agent(self, text: str, provider: str = None) -> dict:
        """
        Mock ReAct agent - returns static response.

        WARNING: This is a MOCK implementation for testing only.
        """
        logger.warning(
            f"MockAIService.run_react_agent called - "
            "returning mocked response. DO NOT USE IN PRODUCTION!"
        )
        return {
            "final_answer": "Mock ReAct agent response",
            "ai_generated_tasks": [],
            "confidence_score": 0.0,
            "warning": "This is a mock response"
        }
