"""
Unit Tests for AI Trigger Coordinator

Tests AI-driven specialty agent triggering:
- Data category classification
- Trigger decision logic
- Agent template mapping
- User preference integration

Target Coverage: 80%
Target Branch Coverage: 50%+
Pass Rate Target: 95%+
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from core.ai_trigger_coordinator import (
    AITriggerCoordinator,
    DataCategory,
    TriggerDecision
)


# =============================================================================
# Test Class: Data Category Enum
# =============================================================================

class TestDataCategory:
    """Tests for DataCategory enumeration."""

    def test_finance_category_exists(self):
        """RED: Test FINANCE category exists."""
        assert DataCategory.FINANCE.value == "finance"

    def test_sales_category_exists(self):
        """RED: Test SALES category exists."""
        assert DataCategory.SALES.value == "sales"

    def test_general_category_exists(self):
        """RED: Test GENERAL category exists."""
        assert DataCategory.GENERAL.value == "general"


# =============================================================================
# Test Class: Trigger Decision Enum
# =============================================================================

class TestTriggerDecision:
    """Tests for TriggerDecision enumeration."""

    def test_trigger_agent_decision_exists(self):
        """RED: Test TRIGGER_AGENT decision exists."""
        assert TriggerDecision.TRIGGER_AGENT.value == "trigger_agent"

    def test_no_action_decision_exists(self):
        """RED: Test NO_ACTION decision exists."""
        assert TriggerDecision.NO_ACTION.value == "no_action"

    def test_queue_for_review_decision_exists(self):
        """RED: Test QUEUE_FOR_REVIEW decision exists."""
        assert TriggerDecision.QUEUE_FOR_REVIEW.value == "queue_for_review"


# =============================================================================
# Test Class: AI Trigger Coordinator - Initialization
# =============================================================================

class TestAITriggerCoordinatorInit:
    """Tests for AITriggerCoordinator initialization."""

    def test_initialization_with_defaults(self):
        """RED: Test coordinator initialization with defaults."""
        coordinator = AITriggerCoordinator()
        assert coordinator.workspace_id == "default"
        assert coordinator.user_id is None
        assert coordinator._enabled is None

    def test_initialization_with_parameters(self):
        """RED: Test coordinator initialization with parameters."""
        coordinator = AITriggerCoordinator(
            workspace_id="test-workspace",
            user_id="user-123"
        )
        assert coordinator.workspace_id == "test-workspace"
        assert coordinator.user_id == "user-123"


# =============================================================================
# Test Class: Is Enabled Check
# =============================================================================

class TestIsEnabled:
    """Tests for is_enabled method."""

    @pytest.mark.asyncio
    async def test_returns_true_when_no_preference_set(self):
        """RED: Test default to enabled when no preference exists."""
        coordinator = AITriggerCoordinator(user_id="test-user")

        with patch('core.ai_trigger_coordinator.get_db_session') as mock_get_db, \
             patch('core.ai_trigger_coordinator.UserPreferenceService') as mock_pref_service:

            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_instance = mock_pref_service.return_value
            mock_instance.get_preference.side_effect = Exception("No preference")

            result = await coordinator.is_enabled()

            # Should default to True on error
            assert result is True

    @pytest.mark.asyncio
    async def test_caches_result_after_first_call(self):
        """RED: Test that result is cached."""
        coordinator = AITriggerCoordinator(user_id="test-user")

        with patch('core.ai_trigger_coordinator.get_db_session') as mock_get_db, \
             patch('core.ai_trigger_coordinator.UserPreferenceService') as mock_pref_service:

            mock_db = Mock()
            mock_get_db.return_value.__enter__.return_value = mock_db

            mock_instance = mock_pref_service.return_value
            mock_instance.get_preference.return_value = True

            # First call
            result1 = await coordinator.is_enabled()
            # Second call (should use cache)
            result2 = await coordinator.is_enabled()

            assert result1 == result2
            # Should only call get_preference once due to caching
            mock_instance.get_preference.assert_called_once()


# =============================================================================
# Test Class: Evaluate Data
# =============================================================================

class TestEvaluateData:
    """Tests for evaluate_data method."""

    @pytest.mark.asyncio
    async def test_returns_no_action_when_disabled(self):
        """RED: Test evaluation when feature is disabled."""
        coordinator = AITriggerCoordinator(user_id="test-user")

        with patch.object(coordinator, 'is_enabled', return_value=False):
            result = await coordinator.evaluate_data(
                data={"text": "invoice data"},
                source="gmail"
            )

            assert result["decision"] == TriggerDecision.NO_ACTION.value
            assert "disabled" in result["reasoning"].lower()

    @pytest.mark.asyncio
    async def test_classifies_finance_category(self):
        """RED: Test classification of finance data."""
        coordinator = AITriggerCoordinator()

        result = await coordinator.evaluate_data(
            data={"text": "Please process the invoice payment"},
            source="document_upload"
        )

        # Should detect finance category
        assert result["category"] == DataCategory.FINANCE.value

    @pytest.mark.asyncio
    async def test_classifies_sales_category(self):
        """RED: Test classification of sales data."""
        coordinator = AITriggerCoordinator()

        result = await coordinator.evaluate_data(
            data={"text": "New lead from the website"},
            source="webhook"
        )

        # Should detect sales category
        assert result["category"] == DataCategory.SALES.value

    @pytest.mark.asyncio
    async def test_maps_finance_to_finance_analyst(self):
        """RED: Test agent template mapping for finance."""
        coordinator = AITriggerCoordinator()

        result = await coordinator.evaluate_data(
            data={"text": "Budget report for Q4"},
            source="upload"
        )

        # Should map to finance_analyst
        assert result["agent_template"] == "finance_analyst"

    @pytest.mark.asyncio
    async def test_maps_sales_to_sales_assistant(self):
        """RED: Test agent template mapping for sales."""
        coordinator = AITriggerCoordinator()

        result = await coordinator.evaluate_data(
            data={"text": "New opportunity in pipeline"},
            source="crm"
        )

        # Should map to sales_assistant
        assert result["agent_template"] == "sales_assistant"

    @pytest.mark.asyncio
    async def test_returns_confidence_score(self):
        """RED: Test that confidence score is included."""
        coordinator = AITriggerCoordinator()

        result = await coordinator.evaluate_data(
            data={"text": "Invoice payment received"},
            source="email"
        )

        # Should have confidence score
        assert "confidence" in result
        assert isinstance(result["confidence"], float)
        assert 0 <= result["confidence"] <= 1

    @pytest.mark.asyncio
    async def test_includes_reasoning_in_response(self):
        """RED: Test that reasoning is included."""
        coordinator = AITriggerCoordinator()

        result = await coordinator.evaluate_data(
            data={"text": "Process the payroll"},
            source="hr_system"
        )

        # Should have reasoning
        assert "reasoning" in result
        assert isinstance(result["reasoning"], str)
        assert len(result["reasoning"]) > 0


# =============================================================================
# Test Class: Category Keywords
# =============================================================================

class TestCategoryKeywords:
    """Tests for category keyword detection."""

    def test_finance_keywords_detected(self):
        """RED: Test finance keyword detection."""
        coordinator = AITriggerCoordinator()

        text = "We need to process the invoice and payment"
        category = coordinator._classify_category(text)

        assert category == DataCategory.FINANCE

    def test_sales_keywords_detected(self):
        """RED: Test sales keyword detection."""
        coordinator = AITriggerCoordinator()

        text = "New lead in the pipeline, follow up with the prospect"
        category = coordinator._classify_category(text)

        assert category == DataCategory.SALES

    def test_operations_keywords_detected(self):
        """RED: Test operations keyword detection."""
        coordinator = AITriggerCoordinator()

        text = "Check inventory and shipping status"
        category = coordinator._classify_category(text)

        assert category == DataCategory.OPERATIONS

    def test_hr_keywords_detected(self):
        """RED: Test HR keyword detection."""
        coordinator = AITriggerCoordinator()

        text = "Employee onboarding and benefits enrollment"
        category = coordinator._classify_category(text)

        assert category == DataCategory.HR

    def test_marketing_keywords_detected(self):
        """RED: Test marketing keyword detection."""
        coordinator = AITriggerCoordinator()

        text = "Campaign analytics and engagement metrics"
        category = coordinator._classify_category(text)

        assert category == DataCategory.MARKETING

    def test_general_category_for_unknown_keywords(self):
        """RED: Test general category for unknown text."""
        coordinator = AITriggerCoordinator()

        text = "This is some random text without specific keywords"
        category = coordinator._classify_category(text)

        assert category == DataCategory.GENERAL


# =============================================================================
# Test Class: Agent Template Mapping
# =============================================================================

class TestAgentTemplateMapping:
    """Tests for agent template mapping."""

    def test_finance_maps_to_finance_analyst(self):
        """RED: Test finance category mapping."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.FINANCE)
        assert template == "finance_analyst"

    def test_sales_maps_to_sales_assistant(self):
        """RED: Test sales category mapping."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.SALES)
        assert template == "sales_assistant"

    def test_operations_maps_to_ops_coordinator(self):
        """RED: Test operations category mapping."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.OPERATIONS)
        assert template == "ops_coordinator"

    def test_hr_maps_to_hr_assistant(self):
        """RED: Test HR category mapping."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.HR)
        assert template == "hr_assistant"

    def test_marketing_maps_to_marketing_analyst(self):
        """RED: Test marketing category mapping."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.MARKETING)
        assert template == "marketing_analyst"

    def test_legal_maps_to_none(self):
        """RED: Test legal category has no default agent."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.LEGAL)
        assert template is None

    def test_general_maps_to_none(self):
        """RED: Test general category has no agent."""
        coordinator = AITriggerCoordinator()
        template = coordinator.CATEGORY_TO_AGENT.get(DataCategory.GENERAL)
        assert template is None


# =============================================================================
# Test Class: Text Extraction
# =============================================================================

class TestExtractText:
    """Tests for text extraction from data."""

    def test_extracts_text_from_string_field(self):
        """RED: Test text extraction from string field."""
        coordinator = AITriggerCoordinator()
        data = {"text": "Sample text content"}

        text = coordinator._extract_text(data)

        assert text == "Sample text content"

    def test_extracts_text_from_content_field(self):
        """RED: Test text extraction from content field."""
        coordinator = AITriggerCoordinator()
        data = {"content": "Sample content"}

        text = coordinator._extract_text(data)

        assert text == "Sample content"

    def test_handles_missing_text_fields(self):
        """RED: Test handling when no text field exists."""
        coordinator = AITriggerCoordinator()
        data = {"other_field": "value"}

        text = coordinator._extract_text(data)

        # Should return empty string or handle gracefully
        assert text == ""


# =============================================================================
# Run Tests
# =============================================================================

if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
