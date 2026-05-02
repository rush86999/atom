"""
Unit Tests for Intent Classifier

Tests intent classification system:
- classify_intent: Main classification entry point
- _heuristic_classify: Rule-based classification fallback
- IntentCategory enum values
- IntentClassification result structure
- Routing decisions (CHAT vs WORKFLOW vs TASK)

Target Coverage: 90%
Target Branch Coverage: 70%+
Pass Rate Target: 100%
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.intent_classifier import IntentClassifier, IntentCategory, IntentClassification


# =============================================================================
# Test Fixtures
# =============================================================================

@pytest.fixture
def classifier():
    """Create IntentClassifier instance."""
    return IntentClassifier()


# =============================================================================
# Test Class: IntentCategory Enum
# =============================================================================

class TestIntentCategory:
    """Tests for IntentCategory enum."""

    def test_chat_category_exists(self):
        """RED: Test CHAT category exists."""
        assert IntentCategory.CHAT == "chat"
        assert hasattr(IntentCategory, 'CHAT')

    def test_workflow_category_exists(self):
        """RED: Test WORKFLOW category exists."""
        assert IntentCategory.WORKFLOW == "workflow"
        assert hasattr(IntentCategory, 'WORKFLOW')

    def test_task_category_exists(self):
        """RED: Test TASK category exists."""
        assert IntentCategory.TASK == "task"
        assert hasattr(IntentCategory, 'TASK')


# =============================================================================
# Test Class: Heuristic Classification
# =============================================================================

class TestHeuristicClassify:
    """Tests for _heuristic_classify method."""

    def test_classify_simple_query(self, classifier):
        """RED: Test classifying simple query as CHAT."""
        result = classifier._heuristic_classify("What is the weather?")
        assert result.category == IntentCategory.CHAT
        assert result.confidence >= 0.0

    def test_classify_workflow_request(self, classifier):
        """RED: Test classifying workflow request."""
        result = classifier._heuristic_classify("Run daily sales report")
        assert result.category == IntentCategory.WORKFLOW
        assert result.confidence >= 0.0

    def test_classify_complex_task(self, classifier):
        """RED: Test classifying complex unstructured task."""
        result = classifier._heuristic_classify("Research competitors and build Slack integration")
        assert result.category == IntentCategory.TASK
        assert result.confidence >= 0.0

    def test_classify_with_question_word(self, classifier):
        """RED: Test questions default to CHAT."""
        result = classifier._heuristic_classify("How do I create an agent?")
        assert result.category == IntentCategory.CHAT

    def test_classify_with_action_verb(self, classifier):
        """RED: Test action verbs indicate WORKFLOW."""
        result = classifier._heuristic_classify("Generate monthly report")
        assert result.category in [IntentCategory.WORKFLOW, IntentCategory.TASK]

    def test_classify_empty_string(self, classifier):
        """RED: Test classifying empty string."""
        result = classifier._heuristic_classify("")
        assert result.category == IntentCategory.CHAT  # Default fallback

    def test_classification_has_confidence(self, classifier):
        """RED: Test classification includes confidence score."""
        result = classifier._heuristic_classify("Test request")
        assert hasattr(result, 'confidence')
        assert 0.0 <= result.confidence <= 1.0


# =============================================================================
# Test Class: Intent Classification Result
# =============================================================================

class TestIntentClassification:
    """Tests for IntentClassification result structure."""

    def test_classification_attributes(self):
        """RED: Test IntentClassification has required attributes."""
        classification = IntentClassification(
            category=IntentCategory.CHAT,
            confidence=0.85,
            reasoning="Simple query detected",
            requires_execution=False,
            suggested_handler="llm_service"
        )

        assert classification.category == IntentCategory.CHAT
        assert classification.confidence == 0.85
        assert classification.reasoning == "Simple query detected"
        assert classification.suggested_handler == "llm_service"


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
