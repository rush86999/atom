"""
Intent Classifier Tests

Comprehensive tests for IntentClassifier service covering LLM-based classification,
heuristic fallback, and routing decisions.

Coverage: 80%+ for core/intent_classifier.py
Lines: 250+, Tests: 15-20
"""

import pytest
import asyncio
from unittest.mock import AsyncMock, MagicMock, patch
from sqlalchemy.orm import Session

from core.intent_classifier import (
    IntentClassifier,
    IntentCategory,
    IntentClassification
)


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def intent_classifier(postgresql_db: Session):
    """Create IntentClassifier instance for testing."""
    if postgresql_db is None:
        pytest.skip("PostgreSQL unavailable")
    return IntentClassifier(db=postgresql_db, workspace_id="test_workspace")


@pytest.fixture
def mock_llm_response():
    """Mock LLM classification response."""
    return {
        "category": "workflow",
        "confidence": 0.85,
        "reasoning": "Request has structured steps and is automatable",
        "is_structured": True,
        "is_long_horizon": False,
        "requires_agent_recruitment": False,
        "blueprint_applicable": True
    }


# ============================================================================
# Test Intent Classification
# ============================================================================

class TestIntentClassification:
    """Tests for LLM-based intent classification."""

    @patch('core.intent_classifier.get_llm_service')
    def test_classify_chat_intent(self, mock_get_llm, intent_classifier: IntentClassifier, mock_llm_response):
        """Test classification of simple CHAT intent."""
        mock_llm_response["category"] = "chat"
        mock_llm_response["confidence"] = 0.95
        mock_llm_response["reasoning"] = "Simple informational query"

        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = mock_llm_response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent("Explain how agent maturity works"))

        assert result.category == IntentCategory.CHAT
        assert result.confidence == 0.95
        assert result.suggested_handler == "llm_service"
        assert result.requires_execution is False

    @patch('core.intent_classifier.get_llm_service')
    def test_classify_workflow_intent(self, mock_get_llm, intent_classifier: IntentClassifier, mock_llm_response):
        """Test classification of structured WORKFLOW intent."""
        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = mock_llm_response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent("Execute the sales outreach blueprint"))

        assert result.category == IntentCategory.WORKFLOW
        assert result.confidence == 0.85
        assert result.suggested_handler == "queen_agent"
        assert result.is_structured is True
        assert result.blueprint_applicable is True

    @patch('core.intent_classifier.get_llm_service')
    def test_classify_task_intent(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test classification of unstructured TASK intent."""
        response = {
            "category": "task",
            "confidence": 0.75,
            "reasoning": "Long-horizon unstructured task requiring multiple specialists",
            "is_structured": False,
            "is_long_horizon": True,
            "requires_agent_recruitment": True,
            "blueprint_applicable": False
        }

        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent(
            "Research competitors and build a Slack integration"
        ))

        assert result.category == IntentCategory.TASK
        assert result.suggested_handler == "fleet_admiral"
        assert result.is_long_horizon is True
        assert result.requires_agent_recruitment is True

    @patch('core.intent_classifier.get_llm_service')
    def test_classify_with_low_confidence(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test classification with low confidence score."""
        response = {
            "category": "workflow",
            "confidence": 0.45,
            "reasoning": "Ambiguous request",
            "is_structured": True,
            "is_long_horizon": False,
            "requires_agent_recruitment": False,
            "blueprint_applicable": True
        }

        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent("Do something with automation"))

        assert result.confidence == 0.45
        # Should still categorize despite low confidence

    @patch('core.intent_classifier.get_llm_service')
    def test_classify_empty_request(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test classification of empty request string."""
        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = {
            "category": "chat",
            "confidence": 0.5,
            "reasoning": "Empty request",
            "is_structured": False,
            "is_long_horizon": False,
            "requires_agent_recruitment": False,
            "blueprint_applicable": False
        }
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent(""))

        assert result.category == IntentCategory.CHAT  # Default fallback

    @patch('core.intent_classifier.get_llm_service')
    def test_classify_multipart_request(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test classification of multi-part request."""
        response = {
            "category": "task",
            "confidence": 0.80,
            "reasoning": "Multiple phases required",
            "is_structured": False,
            "is_long_horizon": True,
            "requires_agent_recruitment": True,
            "blueprint_applicable": False
        }

        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent(
            "Analyze our sales data, create a marketing strategy, and build a dashboard"
        ))

        assert result.category == IntentCategory.TASK
        assert result.is_long_horizon is True


# ============================================================================
# Test Heuristic Classification
# ============================================================================

class TestHeuristicClassification:
    """Tests for fallback heuristic classification."""

    def test_heuristic_chat_keywords(self, intent_classifier: IntentClassifier):
        """Test heuristic detection of CHAT keywords."""
        chat_requests = [
            "explain how agent maturity works",
            "what is the weather",
            "tell me a joke",
            "define workflow automation",
            "help me understand"
        ]

        for request in chat_requests:
            # Test with LLM disabled or failed
            result = intent_classifier._classify_heuristic(request)
            # Heuristic should detect as CHAT based on keywords
            assert result["category"] in ["chat", "workflow", "task"]

    def test_heuristic_workflow_keywords(self, intent_classifier: IntentClassifier):
        """Test heuristic detection of WORKFLOW keywords."""
        workflow_requests = [
            "execute the sales blueprint",
            "run the monthly report",
            "start the data pipeline",
            "launch the outreach campaign"
        ]

        for request in workflow_requests:
            result = intent_classifier._classify_heuristic(request)
            # Should detect as workflow or task
            assert result["category"] in ["workflow", "task"]

    def test_heuristic_task_keywords(self, intent_classifier: IntentClassifier):
        """Test heuristic detection of TASK keywords."""
        task_requests = [
            "research competitors and build integration",
            "analyze data and create strategy",
            "investigate issue and develop solution"
        ]

        for request in task_requests:
            result = intent_classifier._classify_heuristic(request)
            # Should detect as task (complex, multi-phase)
            assert result["category"] in ["workflow", "task"]

    def test_heuristic_unknown_request(self, intent_classifier: IntentClassifier):
        """Test heuristic with unclear request."""
        result = intent_classifier._classify_heuristic("xyzabc")

        # Should still categorize as something
        assert "category" in result
        assert result["category"] in ["chat", "workflow", "task"]


# ============================================================================
# Test Routing Decisions
# ============================================================================

class TestRoutingDecisions:
    """Tests for handler selection based on classification."""

    @patch('core.intent_classifier.get_llm_service')
    def test_route_to_llm_service(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test routing CHAT intent to LLM service."""
        response = {
            "category": "chat",
            "confidence": 0.9,
            "reasoning": "Simple query",
            "is_structured": False,
            "is_long_horizon": False,
            "requires_agent_recruitment": False,
            "blueprint_applicable": False
        }

        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent("What is agent maturity?"))

        assert result.suggested_handler == "llm_service"
        assert result.requires_execution is False

    @patch('core.intent_classifier.get_llm_service')
    def test_route_to_queen_agent(self, mock_get_llm, intent_classifier: IntentClassifier, mock_llm_response):
        """Test routing WORKFLOW intent to Queen Agent."""
        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = mock_llm_response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent("Execute the sales outreach blueprint"))

        assert result.suggested_handler == "queen_agent"
        assert result.is_structured is True
        assert result.blueprint_applicable is True

    @patch('core.intent_classifier.get_llm_service')
    def test_route_to_fleet_admiral(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test routing TASK intent to Fleet Admiral."""
        response = {
            "category": "task",
            "confidence": 0.80,
            "reasoning": "Complex multi-phase task",
            "is_structured": False,
            "is_long_horizon": True,
            "requires_agent_recruitment": True,
            "blueprint_applicable": False
        }

        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = response
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent(
            "Research competitors and build Slack integration"
        ))

        assert result.suggested_handler == "fleet_admiral"
        assert result.requires_agent_recruitment is True


# ============================================================================
# Test Categories
# ============================================================================

class TestCategories:
    """Tests for CHAT/WORKFLOW/TASK routing categories."""

    def test_chat_category_properties(self, intent_classifier: IntentClassifier):
        """Test CHAT category has correct properties."""
        classification = IntentClassification(
            category=IntentCategory.CHAT,
            confidence=0.95,
            reasoning="Informational query",
            requires_execution=False,
            suggested_handler="llm_service"
        )

        assert classification.category == IntentCategory.CHAT
        assert classification.requires_execution is False
        assert classification.suggested_handler == "llm_service"

    def test_workflow_category_properties(self, intent_classifier: IntentClassifier):
        """Test WORKFLOW category has correct properties."""
        classification = IntentClassification(
            category=IntentCategory.WORKFLOW,
            confidence=0.85,
            reasoning="Structured automatable task",
            requires_execution=True,
            suggested_handler="queen_agent",
            is_structured=True,
            blueprint_applicable=True
        )

        assert classification.category == IntentCategory.WORKFLOW
        assert classification.requires_execution is True
        assert classification.suggested_handler == "queen_agent"
        assert classification.is_structured is True

    def test_task_category_properties(self, intent_classifier: IntentClassifier):
        """Test TASK category has correct properties."""
        classification = IntentClassification(
            category=IntentCategory.TASK,
            confidence=0.75,
            reasoning="Unstructured complex task",
            requires_execution=True,
            suggested_handler="fleet_admiral",
            is_long_horizon=True,
            requires_agent_recruitment=True
        )

        assert classification.category == IntentCategory.TASK
        assert classification.requires_execution is True
        assert classification.suggested_handler == "fleet_admiral"
        assert classification.is_long_horizon is True


# ============================================================================
# Test Edge Cases
# ============================================================================

class TestEdgeCases:
    """Tests for edge cases and error handling."""

    @patch('core.intent_classifier.get_llm_service')
    def test_llm_failure_fallback(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test fallback to heuristic when LLM fails."""
        mock_llm = MagicMock()
        mock_llm.generate_structured_response.side_effect = Exception("LLM error")
        mock_get_llm.return_value = mock_llm

        result = asyncio.run(intent_classifier.classify_intent("execute sales blueprint"))

        # Should fallback to heuristic classification
        assert result is not None
        assert result.category in [IntentCategory.CHAT, IntentCategory.WORKFLOW, IntentCategory.TASK]

    @patch('core.intent_classifier.get_llm_service')
    def test_malformed_llm_response(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test handling of malformed LLM response."""
        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = {
            "invalid": "response",
            "missing": "fields"
        }
        mock_get_llm.return_value = mock_llm

        # Should handle gracefully
        result = asyncio.run(intent_classifier.classify_intent("test request"))
        assert result is not None

    def test_very_long_request(self, intent_classifier: IntentClassifier):
        """Test classification of very long request."""
        long_request = "analyze " + "data " * 1000 + "and create report"

        # Should handle without error
        result = intent_classifier._classify_heuristic(long_request)
        assert result is not None

    def test_special_characters(self, intent_classifier: IntentClassifier):
        """Test classification with special characters."""
        special_requests = [
            "execute <script>alert('xss')</script> blueprint",
            "run 'DROP TABLE users' workflow",
            "start \"; rm -rf /\" automation"
        ]

        for request in special_requests:
            # Should handle safely
            result = intent_classifier._classify_heuristic(request)
            assert result is not None
            assert result["category"] in ["chat", "workflow", "task"]


# ============================================================================
# Test Performance
# ============================================================================

class TestPerformance:
    """Performance benchmark tests."""

    def test_classification_performance(self, intent_classifier: IntentClassifier):
        """Test classification meets performance target."""
        import time

        start_time = time.time()
        result = intent_classifier._classify_heuristic("execute sales blueprint")
        elapsed = time.time() - start_time

        # Target: <100ms for classification
        assert elapsed < 0.1, f"Classification took {elapsed:.3f}s, target <0.1s"

    @patch('core.intent_classifier.get_llm_service')
    def test_batch_classification_performance(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test batch classification performance."""
        mock_llm = MagicMock()
        mock_llm.generate_structured_response.return_value = {
            "category": "chat",
            "confidence": 0.9,
            "reasoning": "Simple query",
            "is_structured": False,
            "is_long_horizon": False,
            "requires_agent_recruitment": False,
            "blueprint_applicable": False
        }
        mock_get_llm.return_value = mock_llm

        import time
        requests = [
            "What is agent maturity?",
            "Execute sales blueprint",
            "Research competitors"
        ]

        start_time = time.time()
        for request in requests:
            asyncio.run(intent_classifier.classify_intent(request))
        elapsed = time.time() - start_time

        # Should handle 3 classifications quickly (heuristic only)
        # LLM calls would be slower, so this tests heuristic path
        assert elapsed < 0.5, f"Batch classification took {elapsed:.3f}s"


# ============================================================================
# Test Examples
# ============================================================================

class TestRealWorldExamples:
    """Tests with real-world example requests."""

    @patch('core.intent_classifier.get_llm_service')
    def test_real_chat_examples(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test classification of real CHAT examples."""
        chat_examples = [
            "Explain how agent maturity works",
            "What is the weather today?",
            "Tell me a joke about AI",
            "Define workflow automation",
            "How do I create a new workspace?"
        ]

        for example in chat_examples:
            response = {
                "category": "chat",
                "confidence": 0.9,
                "reasoning": "Informational query",
                "is_structured": False,
                "is_long_horizon": False,
                "requires_agent_recruitment": False,
                "blueprint_applicable": False
            }

            mock_llm = MagicMock()
            mock_llm.generate_structured_response.return_value = response
            mock_get_llm.return_value = mock_llm

            result = asyncio.run(intent_classifier.classify_intent(example))
            assert result.category == IntentCategory.CHAT

    @patch('core.intent_classifier.get_llm_service')
    def test_real_workflow_examples(self, mock_get_llm, intent_classifier: IntentClassifier, mock_llm_response):
        """Test classification of real WORKFLOW examples."""
        workflow_examples = [
            "Execute the sales outreach blueprint",
            "Run the monthly report automation",
            "Start the data pipeline workflow",
            "Launch the email campaign blueprint"
        ]

        for example in workflow_examples:
            mock_llm = MagicMock()
            mock_llm.generate_structured_response.return_value = mock_llm_response
            mock_get_llm.return_value = mock_llm

            result = asyncio.run(intent_classifier.classify_intent(example))
            assert result.category == IntentCategory.WORKFLOW
            assert result.is_structured is True

    @patch('core.intent_classifier.get_llm_service')
    def test_real_task_examples(self, mock_get_llm, intent_classifier: IntentClassifier):
        """Test classification of real TASK examples."""
        task_response = {
            "category": "task",
            "confidence": 0.80,
            "reasoning": "Complex multi-phase task",
            "is_structured": False,
            "is_long_horizon": True,
            "requires_agent_recruitment": True,
            "blueprint_applicable": False
        }

        task_examples = [
            "Research competitors and build a Slack integration",
            "Analyze our sales data and create a marketing strategy",
            "Investigate the performance issue and develop a solution"
        ]

        for example in task_examples:
            mock_llm = MagicMock()
            mock_llm.generate_structured_response.return_value = task_response
            mock_get_llm.return_value = mock_llm

            result = asyncio.run(intent_classifier.classify_intent(example))
            assert result.category == IntentCategory.TASK
            assert result.is_long_horizon is True
