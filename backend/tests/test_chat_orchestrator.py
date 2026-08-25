import pytest
import sys
import os
from unittest.mock import AsyncMock, patch, MagicMock

# Add backend to path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

from integrations.chat_orchestrator import ChatOrchestrator, ChatIntent, FeatureType

@pytest.mark.asyncio
class TestChatOrchestrator:

    async def _no_ai_response(self, orchestrator):
        # Current flow: when the LLM returns nothing usable, the orchestrator
        # falls back to the template/main-message path (feature responses).
        orchestrator._get_qwen_response = AsyncMock(return_value=None)

    async def test_fallback_to_agent_service(self):
        """Test that unhandled requests fallback to ComputerUseAgent"""
        orchestrator = ChatOrchestrator()
        
        # Mock dependencies
        orchestrator.ai_engines = {} # Disable AI engines to force fallback analysis
        await self._no_ai_response(orchestrator)
        
        # Helper to bypass _analyze_intent natural language processing.
        # NOTE (R82): agent dispatch is intentionally scoped to explicit
        # AGENT_REQUEST intents — SEARCH_REQUEST no longer falls back to
        # ComputerUseAgent (the feature handlers own that intent; the pre-2026
        # blanket fallback was removed to avoid recursive agent spend).
        orchestrator._analyze_intent = AsyncMock(return_value={
            "primary_intent": ChatIntent.AGENT_REQUEST,
            "confidence": 0.5,
            "entities": [],
            "platforms": [],
            "command_type": "agent_request"
        })
        
        # Mock feature handlers to fail or return nothing, triggering fallback
        # Important: SEARCH_REQUEST maps to [SEARCH, AI_ANALYTICS]. Both must fail/be missing.
        # We replace the entire feature_handlers dict to be sure.
        orchestrator.feature_handlers = {
            FeatureType.SEARCH: AsyncMock(return_value={"success": False}),
            FeatureType.AI_ANALYTICS: AsyncMock(return_value={"success": False})
        }
        
        # Mock agent_service
        # Patch the class method to ensure it catches all instances
        with patch("services.agent_service.ComputerUseAgent.execute_task", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"id": "task_123", "status": "running"}
            
            response = await orchestrator.process_chat_message("test_user", "Research quantum physics")
            
            # Should have called execute_task
            print(f"Mock called? {mock_execute.called}")
            print(f"Mock call count: {mock_execute.call_count}")
            print(f"Mock calls: {mock_execute.mock_calls}")
            
            mock_execute.assert_called_once()
            assert response["success"] is True
            assert "task_123" in response["message"]  # R82: message copy now "Task initiated. ID: <id>"
            
    async def test_explicit_agent_request(self):
        """Test explicit agent request routing"""
        orchestrator = ChatOrchestrator()
        await self._no_ai_response(orchestrator)
        
        # Mock FeatureType.AGENT handler to avoid DB calls
        orchestrator.feature_handlers[FeatureType.AGENT] = AsyncMock(return_value={"success": False})
        
        orchestrator._analyze_intent = AsyncMock(return_value={
            "primary_intent": ChatIntent.AGENT_REQUEST,
            "confidence": 1.0, 
            "entities": [],
            "platforms": [],
            "command_type": "agent"
        })
        
        with patch("services.agent_service.ComputerUseAgent.execute_task", new_callable=AsyncMock) as mock_execute:
            mock_execute.return_value = {"id": "task_456", "status": "running"}
            
            response = await orchestrator.process_chat_message("test_user", "Please research this")
            
            mock_execute.assert_called_once()
            assert response["success"] is True
