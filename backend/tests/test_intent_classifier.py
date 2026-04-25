"""
Tests for IntentClassifier - routing user requests to appropriate handlers.

Tests cover:
- CHAT intent classification (simple queries)
- WORKFLOW intent classification (structured tasks)
- TASK intent classification (unstructured complex tasks)
- Confidence scoring and thresholding
- Feature extraction (task complexity, structure detection)
- Routing logic (suggested_handler determination)
- Edge cases (ambiguous intents, low confidence)

TDD Pattern: AsyncMock for async methods, patch at import location
"""

import os
os.environ["TESTING"] = "1"

import pytest
import json
from unittest.mock import Mock, AsyncMock, patch, MagicMock
from sqlalchemy.orm import Session

from core.intent_classifier import (
    IntentClassifier,
    IntentCategory,
    IntentClassification,
    get_intent_classifier
)


class TestChatIntentClassification:
    """Test CHAT intent classification for simple queries."""

    @pytest.mark.asyncio
    async def test_classify_simple_question_as_chat(self):
        """Test that simple questions are classified as CHAT."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.95,
                    "reasoning": "Simple informational query",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("What is the weather today?")

            assert result.category == IntentCategory.CHAT
            assert result.suggested_handler == "llm_service"
            assert result.requires_execution is False
            assert result.confidence == 0.95

    @pytest.mark.asyncio
    async def test_classify_explanation_request_as_chat(self):
        """Test that explanation requests are classified as CHAT."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.90,
                    "reasoning": "Request for explanation",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Explain how agent maturity works")

            assert result.category == IntentCategory.CHAT
            assert result.requires_execution is False
            assert result.is_structured is False

    @pytest.mark.asyncio
    async def test_chat_intents_have_no_execution_required(self):
        """Test that CHAT intents never require execution."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.85,
                    "reasoning": "General query",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Tell me a joke")

            assert result.requires_execution is False
            assert result.suggested_handler == "llm_service"


class TestWorkflowIntentClassification:
    """Test WORKFLOW intent classification for structured tasks."""

    @pytest.mark.asyncio
    async def test_classify_blueprint_execution_as_workflow(self):
        """Test that blueprint execution requests are classified as WORKFLOW."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "workflow",
                    "confidence": 0.92,
                    "reasoning": "Structured blueprint execution",
                    "is_structured": True,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": True
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Execute the sales outreach blueprint")

            assert result.category == IntentCategory.WORKFLOW
            assert result.suggested_handler == "queen_agent"
            assert result.requires_execution is True
            assert result.is_structured is True
            assert result.blueprint_applicable is True

    @pytest.mark.asyncio
    async def test_classify_automation_request_as_workflow(self):
        """Test that automation requests are classified as WORKFLOW."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "workflow",
                    "confidence": 0.88,
                    "reasoning": "Recurring automation",
                    "is_structured": True,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": True
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Run the daily report automation")

            assert result.category == IntentCategory.WORKFLOW
            assert result.suggested_handler == "queen_agent"
            assert result.is_structured is True

    @pytest.mark.asyncio
    async def test_workflow_intents_require_execution(self):
        """Test that WORKFLOW intents always require execution."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "workflow",
                    "confidence": 0.90,
                    "reasoning": "Structured task",
                    "is_structured": True,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": True
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Start the monthly reconciliation workflow")

            assert result.requires_execution is True
            assert result.requires_agent_recruitment is False


class TestTaskIntentClassification:
    """Test TASK intent classification for unstructured complex tasks."""

    @pytest.mark.asyncio
    async def test_classify_research_and_build_as_task(self):
        """Test that research + build requests are classified as TASK."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "task",
                    "confidence": 0.93,
                    "reasoning": "Unstructured multi-phase complex task",
                    "is_structured": False,
                    "is_long_horizon": True,
                    "requires_agent_recruitment": True,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Research competitors and build a Slack integration")

            assert result.category == IntentCategory.TASK
            assert result.suggested_handler == "fleet_admiral"
            assert result.requires_execution is True
            assert result.is_long_horizon is True
            assert result.requires_agent_recruitment is True

    @pytest.mark.asyncio
    async def test_classify_complex_analysis_as_task(self):
        """Test that complex analysis requests are classified as TASK."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "task",
                    "confidence": 0.89,
                    "reasoning": "Complex multi-domain analysis",
                    "is_structured": False,
                    "is_long_horizon": True,
                    "requires_agent_recruitment": True,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Analyze our sales data and create a marketing strategy")

            assert result.category == IntentCategory.TASK
            assert result.suggested_handler == "fleet_admiral"
            assert result.is_structured is False

    @pytest.mark.asyncio
    async def test_task_intents_require_agent_recruitment(self):
        """Test that TASK intents require multiple specialist agents."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "task",
                    "confidence": 0.91,
                    "reasoning": "Long-horizon unstructured task",
                    "is_structured": False,
                    "is_long_horizon": True,
                    "requires_agent_recruitment": True,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Investigate market trends and design a product strategy")

            assert result.requires_agent_recruitment is True
            assert result.is_long_horizon is True


class TestConfidenceScoring:
    """Test confidence scoring and thresholding."""

    @pytest.mark.asyncio
    async def test_high_confidence_classification(self):
        """Test classification with high confidence."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.98,
                    "reasoning": "Very clear intent",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("What is 2+2?")

            assert result.confidence >= 0.95
            assert result.category == IntentCategory.CHAT

    @pytest.mark.asyncio
    async def test_medium_confidence_classification(self):
        """Test classification with medium confidence."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "workflow",
                    "confidence": 0.75,
                    "reasoning": "Somewhat ambiguous but likely workflow",
                    "is_structured": True,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": True
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Run automation")

            assert 0.70 <= result.confidence <= 0.80

    @pytest.mark.asyncio
    async def test_low_confidence_classification(self):
        """Test classification with low confidence."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "task",
                    "confidence": 0.55,
                    "reasoning": "Ambiguous request",
                    "is_structured": False,
                    "is_long_horizon": True,
                    "requires_agent_recruitment": True,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Do something complex")

            assert result.confidence < 0.70


class TestFeatureExtraction:
    """Test feature extraction from user requests."""

    @pytest.mark.asyncio
    async def test_detects_structured_tasks(self):
        """Test that structured tasks are correctly identified."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "workflow",
                    "confidence": 0.90,
                    "reasoning": "Has clear steps",
                    "is_structured": True,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": True
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Execute step 1, then step 2, then step 3")

            assert result.is_structured is True

    @pytest.mark.asyncio
    async def test_detects_long_horizon_tasks(self):
        """Test that long-horizon tasks are correctly identified."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "task",
                    "confidence": 0.88,
                    "reasoning": "Multi-phase project",
                    "is_structured": False,
                    "is_long_horizon": True,
                    "requires_agent_recruitment": True,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Research market, design product, build MVP, launch")

            assert result.is_long_horizon is True


class TestRoutingLogic:
    """Test routing logic and suggested_handler determination."""

    @pytest.mark.asyncio
    async def test_chat_routes_to_llm_service(self):
        """Test that CHAT intents route to LLM service."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.95,
                    "reasoning": "Simple query",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("What is AI?")

            assert result.suggested_handler == "llm_service"

    @pytest.mark.asyncio
    async def test_workflow_routes_to_queen_agent(self):
        """Test that WORKFLOW intents route to Queen Agent."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "workflow",
                    "confidence": 0.92,
                    "reasoning": "Structured workflow",
                    "is_structured": True,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": True
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Execute blueprint")

            assert result.suggested_handler == "queen_agent"

    @pytest.mark.asyncio
    async def test_task_routes_to_fleet_admiral(self):
        """Test that TASK intents route to Fleet Admiral."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "task",
                    "confidence": 0.90,
                    "reasoning": "Unstructured complex task",
                    "is_structured": False,
                    "is_long_horizon": True,
                    "requires_agent_recruitment": True,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Research and build")

            assert result.suggested_handler == "fleet_admiral"


class TestEdgeCases:
    """Test edge cases and ambiguous intents."""

    @pytest.mark.asyncio
    async def test_ambiguous_request_defaults_to_chat(self):
        """Test that ambiguous requests default to CHAT."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.50,
                    "reasoning": "Ambiguous, defaulting to chat",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Something")

            assert result.category == IntentCategory.CHAT

    @pytest.mark.asyncio
    async def test_handles_markdown_json_wrapping(self):
        """Test that JSON wrapped in markdown is parsed correctly."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        wrapped_json = '''```json
{
    "category": "workflow",
    "confidence": 0.90,
    "reasoning": "Test",
    "is_structured": true,
    "is_long_horizon": false,
    "requires_agent_recruitment": false,
    "blueprint_applicable": true
}
```'''

        mock_llm.call = AsyncMock(
            return_value={"content": wrapped_json}
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Test request")

            assert result.category == IntentCategory.WORKFLOW

    @pytest.mark.asyncio
    async def test_llm_failure_falls_back_to_heuristics(self):
        """Test that LLM failures trigger heuristic classification."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock LLM failure
        mock_llm.call = AsyncMock(side_effect=Exception("LLM unavailable"))

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            result = await classifier.classify_intent("Explain something")

            # Should fall back to heuristic classification
            assert result is not None
            assert result.category in [IntentCategory.CHAT, IntentCategory.WORKFLOW, IntentCategory.TASK]

    @pytest.mark.asyncio
    async def test_json_parse_error_returns_default_chat(self):
        """Test that JSON parse errors return safe default."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock invalid JSON response
        mock_llm.call = AsyncMock(
            return_value={"content": "This is not valid JSON"}
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test")

            result = await classifier.classify_intent("Any request")

            # Should return default CHAT classification
            assert result.category == IntentCategory.CHAT
            assert result.confidence == 0.5

    @pytest.mark.asyncio
    async def test_heuristic_classification_works(self):
        """Test that heuristic classification works for keywords."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        # Mock LLM failure to trigger heuristics
        mock_llm.call = AsyncMock(side_effect=Exception("LLM down"))

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            # Test workflow keyword
            result = await classifier.classify_intent("Execute the automation")
            assert result.category == IntentCategory.WORKFLOW

            # Test task keyword
            result = await classifier.classify_intent("Research competitors")
            assert result.category == IntentCategory.TASK


class TestWorkspaceHandling:
    """Test workspace ID handling."""

    def test_initialization_with_default_workspace(self):
        """Test classifier initialization with default workspace."""
        mock_db = Mock(spec=Session)

        with patch('core.intent_classifier.get_llm_service') as mock_get_llm:
            mock_llm_instance = Mock()
            mock_get_llm.return_value = mock_llm_instance

            classifier = IntentClassifier(db=mock_db, workspace_id="default")

            assert classifier.workspace_id == "default"
            mock_get_llm.assert_called_once_with(db=mock_db, workspace_id="default")

    def test_initialization_with_custom_workspace(self):
        """Test classifier initialization with custom workspace."""
        mock_db = Mock(spec=Session)

        with patch('core.intent_classifier.get_llm_service') as mock_get_llm:
            mock_llm_instance = Mock()
            mock_get_llm.return_value = mock_llm_instance

            classifier = IntentClassifier(db=mock_db, workspace_id="custom-workspace")

            assert classifier.workspace_id == "custom-workspace"

    @pytest.mark.asyncio
    async def test_workspace_id_passed_to_llm(self):
        """Test that workspace_id is passed to LLM service."""
        mock_db = Mock(spec=Session)
        mock_llm = Mock()

        mock_llm.call = AsyncMock(
            return_value={
                "content": json.dumps({
                    "category": "chat",
                    "confidence": 0.95,
                    "reasoning": "Test",
                    "is_structured": False,
                    "is_long_horizon": False,
                    "requires_agent_recruitment": False,
                    "blueprint_applicable": False
                })
            }
        )

        with patch('core.intent_classifier.get_llm_service', return_value=mock_llm):
            classifier = IntentClassifier(db=mock_db, workspace_id="test-workspace")

            await classifier.classify_intent("Test")

            # Verify workspace_id was passed to LLM
            mock_llm.call.assert_called_once()
            call_kwargs = mock_llm.call.call_args[1]
            assert call_kwargs["user_id"] == "test-workspace"


class TestSingletonPattern:
    """Test singleton pattern for intent classifier."""

    def test_get_intent_classifier_returns_singleton(self):
        """Test that get_intent_classifier returns singleton instance."""
        mock_db = Mock(spec=Session)

        with patch('core.intent_classifier.get_llm_service'):
            # Reset singleton
            import core.intent_classifier
            core.intent_classifier._intent_classifier_instance = None

            classifier1 = get_intent_classifier(db=mock_db, workspace_id="test")
            classifier2 = get_intent_classifier(db=mock_db, workspace_id="test")

            # Should return same instance
            assert classifier1 is classifier2
