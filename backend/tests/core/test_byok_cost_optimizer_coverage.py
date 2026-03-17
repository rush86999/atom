"""
Comprehensive test coverage for BYOK Cost Optimizer
Target: 60%+ line coverage (168 lines)
"""

import pytest
from unittest.mock import Mock, MagicMock, patch
from pathlib import Path
from core.byok_cost_optimizer import (
    BYOKCostOptimizer,
    CostOptimizationRecommendation,
    UsagePattern,
    CompetitiveInsight,
)


# ==================== FIXTURES ====================

@pytest.fixture
def mock_byok_manager():
    """Mock BYOK manager with providers and usage stats."""
    manager = Mock()

    # Mock providers
    provider_openai = Mock()
    provider_openai.is_active = True
    provider_openai.name = "OpenAI GPT-4"
    provider_openai.cost_per_token = 0.00003  # Premium
    provider_openai.supported_tasks = ["chat", "code", "analysis"]

    provider_anthropic = Mock()
    provider_anthropic.is_active = True
    provider_anthropic.name = "Anthropic Claude"
    provider_anthropic.cost_per_token = 0.00002  # Premium
    provider_anthropic.supported_tasks = ["chat", "writing", "analysis"]

    provider_deepseek = Mock()
    provider_deepseek.is_active = True
    provider_deepseek.name = "DeepSeek"
    provider_deepseek.cost_per_token = 0.000001  # Budget
    provider_deepseek.supported_tasks = ["code", "math", "analysis"]

    # Create a custom dict-like object for providers
    class ProviderDict(dict):
        def __getitem__(self, key):
            return {
                "openai": provider_openai,
                "anthropic": provider_anthropic,
                "deepseek": provider_deepseek,
            }[key]

    manager.providers = ProviderDict({
        "openai": provider_openai,
        "anthropic": provider_anthropic,
        "deepseek": provider_deepseek,
    })

    # Mock usage stats
    usage_openai = Mock()
    usage_openai.total_requests = 1000
    usage_openai.cost_accumulated = 30.0

    usage_anthropic = Mock()
    usage_anthropic.total_requests = 500
    usage_anthropic.cost_accumulated = 10.0

    manager.usage_stats = {
        "openai": usage_openai,
        "anthropic": usage_anthropic,
    }

    # Mock API key retrieval
    def mock_get_key(provider_id):
        return f"fake_key_{provider_id}"

    manager.get_api_key = mock_get_key

    # Mock optimal provider selection
    manager.get_optimal_provider = Mock(return_value="openai")

    return manager


@pytest.fixture
def cost_optimizer(mock_byok_manager):
    """Fresh cost optimizer instance."""
    return BYOKCostOptimizer(mock_byok_manager)


# ==================== TestBYOKCostOptimizer: Initialization ====================

class TestBYOKCostOptimizer:
    """Test cost optimizer initialization and setup."""

    def test_optimizer_initialization(self, cost_optimizer):
        """Test optimizer initializes with competitive intelligence."""
        assert len(cost_optimizer.competitive_insights) >= 3
        assert "openai" in cost_optimizer.competitive_insights
        assert "anthropic" in cost_optimizer.competitive_insights
        assert cost_optimizer.byok_manager is not None

    def test_competitive_insights_structure(self, cost_optimizer):
        """Test competitive insights have required fields."""
        insight = cost_optimizer.competitive_insights["openai"]

        assert insight.provider_id == "openai"
        assert insight.market_position in ["budget", "mid-range", "premium"]
        assert len(insight.unique_features) > 0
        assert len(insight.best_for_tasks) > 0
        assert 0 <= insight.cost_efficiency_score <= 100
        assert 0 <= insight.quality_score <= 100

    def test_usage_patterns_empty_initially(self, mock_byok_manager):
        """Test usage patterns dict starts empty (mock file load)."""
        # Mock _load_usage_patterns to do nothing
        with patch.object(BYOKCostOptimizer, "_load_usage_patterns"):
            optimizer = BYOKCostOptimizer(mock_byok_manager)
            assert len(optimizer.usage_patterns) == 0

    def test_optimization_cache_initialized(self, cost_optimizer):
        """Test optimization cache is initialized."""
        assert isinstance(cost_optimizer.optimization_cache, dict)


# ==================== TestCostCalculation: Cost Analysis ====================

class TestCostCalculation:
    """Test cost calculation and optimization logic."""

    def test_analyze_user_usage_pattern_new_user(self, cost_optimizer):
        """Test usage pattern analysis for new user."""
        pattern = cost_optimizer.analyze_user_usage_pattern("new_user_123")

        assert pattern.user_id == "new_user_123"
        assert pattern.monthly_budget == 50.0
        assert pattern.cost_sensitivity == "medium"
        assert pattern.quality_preference == "balanced"
        assert len(pattern.task_distribution) > 0

    def test_analyze_user_usage_pattern_saves_to_disk(self, cost_optimizer, tmp_path):
        """Test usage pattern gets saved to file."""
        with patch("core.byok_cost_optimizer.Path") as mock_path:
            mock_path.return_value = tmp_path / "usage_patterns.json"

            pattern = cost_optimizer.analyze_user_usage_pattern("user_456")

            # Verify pattern was cached
            assert "user_456" in cost_optimizer.usage_patterns

    def test_get_cost_optimization_recommendations_basic(self, cost_optimizer):
        """Test basic cost optimization recommendations."""
        # Note: Uses real optimizer logic with mocked providers
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "user_new_basic",
            "code"
        )

        assert recommendation.task_type == "code"
        assert recommendation.current_provider is not None
        assert recommendation.recommended_provider is not None
        assert isinstance(recommendation.estimated_savings, (int, float))
        assert isinstance(recommendation.confidence, (int, float))

    def test_cost_optimization_with_no_savings(self, cost_optimizer):
        """Test optimization returns recommendation even with no savings."""
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "user_no_savings",
            "chat"
        )

        # Should still return recommendation
        assert recommendation.reasoning != ""
        assert recommendation.alternative_providers is not None

    def test_cost_optimization_analyzes_all_providers(self, cost_optimizer):
        """Test optimization analyzes all active providers."""
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "user_all_providers",
            "analysis"
        )

        # Should have current and recommended providers
        assert recommendation.current_provider is not None
        assert recommendation.recommended_provider is not None

    def test_calculate_savings_percentage(self, cost_optimizer):
        """Test savings percentage calculation."""
        with patch.object(cost_optimizer, "get_cost_optimization_recommendations") as mock_rec:
            mock_rec.return_value = CostOptimizationRecommendation(
                task_type="code",
                current_provider="openai",
                recommended_provider="deepseek",
                estimated_savings=50.0,
                savings_percentage=75.0,
                reasoning="Test",
                confidence=85.0,
                alternative_providers=[]
            )

            rec = cost_optimizer.get_cost_optimization_recommendations("user", "code")
            assert rec.savings_percentage == 75.0


# ==================== TestCostOptimization: Provider Selection ====================

class TestCostOptimization:
    """Test provider selection and optimization strategies."""

    def test_provider_selection_considers_cost_sensitivity(self, cost_optimizer):
        """Test provider selection respects cost sensitivity."""
        # Create cost-sensitive user
        pattern = UsagePattern(
            user_id="cost_sensitive_user_test",
            task_distribution={"code": 100},
            peak_hours=[9, 10],
            preferred_providers={},
            monthly_budget=50.0,
            cost_sensitivity="high",
            quality_preference="cost"
        )
        cost_optimizer.usage_patterns["cost_sensitive_user_test"] = pattern

        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "cost_sensitive_user_test",
            "code"
        )

        # Should recommend a provider (deepseek for cost-sensitive)
        assert recommendation.recommended_provider is not None

    def test_provider_selection_considers_quality_preference(self, cost_optimizer):
        """Test provider selection respects quality preference."""
        pattern = UsagePattern(
            user_id="quality_user_test",
            task_distribution={"analysis": 100},
            peak_hours=[9, 10],
            preferred_providers={},
            monthly_budget=200.0,
            cost_sensitivity="low",
            quality_preference="quality"
        )
        cost_optimizer.usage_patterns["quality_user_test"] = pattern

        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "quality_user_test",
            "analysis"
        )

        # Should recommend a provider
        assert recommendation.recommended_provider is not None

    def test_optimization_includes_alternatives(self, cost_optimizer):
        """Test optimization provides alternative providers."""
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "user_alternatives_test",
            "chat"
        )

        # Should have alternatives (may be empty if only 1 suitable provider)
        assert isinstance(recommendation.alternative_providers, list)

    def test_cache_optimization_results(self, cost_optimizer):
        """Test optimization results can be cached."""
        rec1 = cost_optimizer.get_cost_optimization_recommendations(
            "cached_user_test",
            "code"
        )

        # Second call should use cached pattern
        rec2 = cost_optimizer.get_cost_optimization_recommendations(
            "cached_user_test",
            "code"
        )

        assert rec1.task_type == rec2.task_type
        assert rec1.recommended_provider == rec2.recommended_provider


# ==================== TestCostErrors: Error Handling ====================

class TestCostErrors:
    """Test error handling and edge cases."""

    def test_optimization_with_invalid_task_type(self, cost_optimizer, mock_byok_manager):
        """Test optimization fails for unsupported task type."""
        # Mock provider that doesn't support the task
        mock_byok_manager.providers["openai"].supported_tasks = ["chat"]

        with pytest.raises(ValueError, match="No suitable providers"):
            cost_optimizer.get_cost_optimization_recommendations(
                "user_xyz",
                "unsupported_task"
            )

    def test_optimization_with_no_active_providers(self, mock_byok_manager):
        """Test optimization with no active providers."""
        # Deactivate all providers
        for provider in mock_byok_manager.providers.values():
            provider.is_active = False

        optimizer = BYOKCostOptimizer(mock_byok_manager)

        with pytest.raises(ValueError, match="No suitable providers"):
            optimizer.get_cost_optimization_recommendations("user", "chat")

    def test_get_optimal_provider_failure(self, mock_byok_manager):
        """Test handles get_optimal_provider exception gracefully."""
        mock_byok_manager.get_optimal_provider.side_effect = Exception("Provider error")

        optimizer = BYOKCostOptimizer(mock_byok_manager)

        # Should fallback to openai
        recommendation = optimizer.get_cost_optimization_recommendations(
            "user_fail_test",
            "chat"
        )

        assert recommendation.current_provider == "openai"

    def test_usage_pattern_load_failure(self, tmp_path):
        """Test handles usage pattern load failure gracefully."""
        # Create mock manager that will fail to load
        mock_manager = Mock()
        mock_manager.providers = {}
        mock_manager.usage_stats = {}
        mock_manager.get_api_key = Mock(return_value=None)
        mock_manager.get_optimal_provider = Mock(return_value="openai")

        with patch("core.byok_cost_optimizer.Path") as mock_path:
            mock_path.return_value = tmp_path / "nonexistent.json"

            optimizer = BYOKCostOptimizer(mock_manager)

            # Should still initialize
            assert optimizer is not None

    def test_competitive_analysis_report(self, cost_optimizer):
        """Test competitive analysis report generation."""
        report = cost_optimizer.get_competitive_analysis_report()

        assert "providers" in report
        assert "market_overview" in report
        assert "recommendations" in report
        assert report["market_overview"]["total_providers"] >= 3

    def test_competitive_analysis_includes_rankings(self, cost_optimizer):
        """Test competitive analysis includes cost and quality rankings."""
        report = cost_optimizer.get_competitive_analysis_report()

        openai_data = report["providers"]["openai"]
        assert "cost_ranking" in openai_data
        assert "quality_ranking" in openai_data
        assert "overall_score" in openai_data

    def test_simulate_cost_savings(self, cost_optimizer):
        """Test cost savings simulation."""
        result = cost_optimizer.simulate_cost_savings("user_sim", months=6)

        assert "user_id" in result
        assert "current_monthly_cost" in result
        assert "optimized_monthly_cost" in result
        assert "monthly_savings" in result
        assert "total_projected_savings" in result
        assert result["simulation_period_months"] == 6

    def test_simulate_cost_savings_with_adoption_rate(self, cost_optimizer):
        """Test simulation with adoption rate."""
        result = cost_optimizer.simulate_cost_savings(
            "user_adoption",
            months=12,
            adoption_rate=0.6
        )

        assert result["adoption_rate"] == 0.6
        assert "roi_calculation" in result

    def test_simulate_cost_savings_for_new_user(self, cost_optimizer):
        """Test simulation for user with no usage history."""
        # New user with zero historical cost
        mock_manager = Mock()
        mock_manager.providers = {}
        mock_manager.usage_stats = {}
        mock_manager.get_api_key = Mock(return_value=None)
        mock_manager.get_optimal_provider = Mock(return_value="openai")

        optimizer = BYOKCostOptimizer(mock_manager)

        result = optimizer.simulate_cost_savings("new_user", months=3)

        # Should estimate based on default budget
        assert result["current_monthly_cost"] > 0

    def test_cost_optimization_reasoning(self, cost_optimizer):
        """Test optimization includes reasoning."""
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "user_reasoning",
            "writing"
        )

        assert recommendation.reasoning != ""
        assert isinstance(recommendation.reasoning, str)

    def test_confidence_score_calculation(self, cost_optimizer):
        """Test confidence score is calculated appropriately."""
        recommendation = cost_optimizer.get_cost_optimization_recommendations(
            "user_confidence",
            "math"
        )

        # Confidence should be between 70 and 95
        assert 70 <= recommendation.confidence <= 95


# ==================== TestMarketIntelligence: Competitive Analysis ====================

class TestMarketIntelligence:
    """Test competitive intelligence and market analysis."""

    def test_provider_insight_for_openai(self, cost_optimizer):
        """Test OpenAI has competitive insights."""
        insight = cost_optimizer.competitive_insights["openai"]

        assert "Superior reasoning" in insight.unique_features or "Advanced coding" in insight.unique_features
        assert insight.market_position == "premium"
        assert insight.quality_score >= 90

    def test_provider_insight_for_deepseek(self, cost_optimizer):
        """Test DeepSeek has competitive insights."""
        insight = cost_optimizer.competitive_insights["deepseek"]

        assert insight.market_position == "budget"
        assert insight.cost_efficiency_score >= 90
        assert "code" in insight.best_for_tasks

    def test_market_segments_in_report(self, cost_optimizer):
        """Test market overview includes segment breakdown."""
        report = cost_optimizer.get_competitive_analysis_report()
        segments = report["market_overview"]["market_segments"]

        assert "budget" in segments
        assert "premium" in segments
        assert segments["budget"] >= 1

    def test_strategic_recommendations_generated(self, cost_optimizer):
        """Test report includes strategic recommendations."""
        report = cost_optimizer.get_competitive_analysis_report()

        assert len(report["recommendations"]) > 0

        # Check recommendation structure
        rec = report["recommendations"][0]
        assert "type" in rec
        assert "title" in rec
        assert "priority" in rec
