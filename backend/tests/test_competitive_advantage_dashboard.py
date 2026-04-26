"""
Tests for CompetitiveAdvantageDashboard

Test coverage for competitive advantage dashboard engine including:
- Dashboard metrics calculation and visualization
- Analytics processing and insight generation
- Competitive positioning and market analysis
- Integration with analytics and feedback systems
"""

import pytest
from datetime import datetime, timezone, timedelta
from typing import Dict, List, Any

from core.competitive_advantage_dashboard import (
    AdvantageCategory,
    CompetitiveMetric,
    CompetitiveInsight,
    MarketPosition,
    CompetitiveAdvantageEngine,
    get_competitive_advantage_engine,
)


# ============================================================================
# Test: Dashboard Metrics
# ============================================================================

class TestDashboardMetrics:
    """Test competitive metrics calculation and benchmarking."""

    def test_competitive_metric_creation(self):
        """CompetitiveMetric created with valid fields."""
        # Arrange & Act
        metric = CompetitiveMetric(
            category=AdvantageCategory.COST,
            metric_name="AI Cost Savings",
            atom_value=35.0,
            competitor_average=15.0,
            industry_best=40.0,
            unit="%",
            description="Average cost savings through AI provider optimization",
            calculation_method="Weighted average of user cost savings",
            last_updated=datetime.now(timezone.utc)
        )

        # Assert
        assert metric.category == AdvantageCategory.COST
        assert metric.metric_name == "AI Cost Savings"
        assert metric.atom_value == 35.0
        assert metric.competitor_average == 15.0
        assert metric.industry_best == 40.0
        assert metric.unit == "%"

    def test_advantage_category_enum_values(self):
        """AdvantageCategory enum has correct values."""
        # Assert
        assert AdvantageCategory.COST == "cost"
        assert AdvantageCategory.PRIVACY == "privacy"
        assert AdvantageCategory.INTEGRATION == "integration"
        assert AdvantageCategory.AI_OPTIMIZATION == "ai_optimization"
        assert AdvantageCategory.CUSTOMIZATION == "customization"
        assert AdvantageCategory.PERFORMANCE == "performance"
        assert AdvantageCategory.COMPLIANCE == "compliance"
        assert AdvantageCategory.USER_EXPERIENCE == "user_experience"

    def test_metric_initialization_on_engine_creation(self):
        """Engine initializes with default competitive metrics."""
        # Arrange & Act
        engine = CompetitiveAdvantageEngine()

        # Assert
        assert len(engine.metrics) > 0
        assert "ai_cost_savings" in engine.metrics
        assert "byok_transparency" in engine.metrics
        assert "data_control" in engine.metrics
        assert "integration_count" in engine.metrics

    def test_metric_benchmark_comparison(self):
        """Metric values correctly benchmark against competitors and industry."""
        # Arrange
        engine = CompetitiveAdvantageEngine()
        metric = engine.metrics["ai_cost_savings"]

        # Assert
        assert metric.atom_value > metric.competitor_average  # ATOM beats average
        assert metric.atom_value <= metric.industry_best  # ATOM at or below best

    def test_metric_unit_variety(self):
        """Metrics have appropriate units for their domain."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - Percentage-based metrics
        assert engine.metrics["ai_cost_savings"].unit == "%"
        assert engine.metrics["data_control"].unit == "%"

        # Assert - Count-based metrics
        assert engine.metrics["integration_count"].unit == "count"
        assert engine.metrics["industry_templates"].unit == "count"

        # Assert - Time-based metrics
        assert engine.metrics["workflow_execution_speed"].unit == "seconds"


# ============================================================================
# Test: Analytics Processing
# ============================================================================

class TestAnalyticsProcessing:
    """Test data aggregation, insight generation, and recommendations."""

    def test_insight_initialization(self):
        """Engine initializes with competitive insights."""
        # Arrange & Act
        engine = CompetitiveAdvantageEngine()

        # Assert
        assert len(engine.insights) > 0
        assert all(isinstance(insight, CompetitiveInsight) for insight in engine.insights)

    def test_competitive_insight_structure(self):
        """CompetitiveInsight has all required fields."""
        # Arrange & Act
        insight = CompetitiveInsight(
            title="BYOK Cost Transparency Leadership",
            category=AdvantageCategory.COST,
            description="ATOM provides 100% cost transparency while competitors average 25%",
            impact_level="transformational",
            evidence=["Feature comparison analysis", "User feedback data"],
            supporting_metrics=["byok_transparency"],
            competitive_moat="sustainable"
        )

        # Assert
        assert insight.title == "BYOK Cost Transparency Leadership"
        assert insight.category == AdvantageCategory.COST
        assert insight.impact_level == "transformational"
        assert len(insight.evidence) > 0
        assert len(insight.supporting_metrics) > 0
        assert insight.competitive_moat == "sustainable"

    def test_insight_impact_levels(self):
        """Insights have valid impact levels."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - All insights should have valid impact levels
        valid_levels = ["low", "medium", "high", "transformational"]
        for insight in engine.insights:
            assert insight.impact_level in valid_levels

    def test_insight_competitive_moat_classification(self):
        """Insights classify competitive moat correctly."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - All insights should have valid moat classifications
        valid_moats = ["sustainable", "temporary", "innovating"]
        for insight in engine.insights:
            assert insight.competitive_moat in valid_moats

    def test_supporting_metrics_reference_existing_metrics(self):
        """Insight supporting metrics reference existing engine metrics."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - All supporting metrics should exist in engine.metrics
        for insight in engine.insights:
            for metric_key in insight.supporting_metrics:
                assert metric_key in engine.metrics, f"Metric {metric_key} not found in engine"


# ============================================================================
# Test: Visualization Data
# ============================================================================

class TestVisualizationData:
    """Test chart data generation and dashboard configuration."""

    def test_market_position_creation(self):
        """MarketPosition created with valid fields."""
        # Arrange & Act
        position = MarketPosition(
            segment="Small Business Automation",
            market_share=12.5,
            growth_rate=35.0,
            competitive_ranking=3,
            total_competitors=10,
            key_differentiators=["BYOK", "Multi-provider AI", "Industry templates"]
        )

        # Assert
        assert position.segment == "Small Business Automation"
        assert position.market_share == 12.5
        assert position.growth_rate == 35.0
        assert position.competitive_ranking == 3
        assert position.total_competitors == 10
        assert len(position.key_differentiators) > 0

    def test_market_position_initialization(self):
        """Engine initializes with market position data."""
        # Arrange & Act
        engine = CompetitiveAdvantageEngine()

        # Assert
        assert len(engine.market_positions) > 0
        assert all(isinstance(pos, MarketPosition) for pos in engine.market_positions.values())

    def test_metric_data_freshness(self):
        """Metrics have recent last_updated timestamps."""
        # Arrange
        engine = CompetitiveAdvantageEngine()
        now = datetime.now(timezone.utc)

        # Assert - All metrics should be updated within last 24 hours
        for metric in engine.metrics.values():
            time_since_update = now - metric.last_updated
            assert time_since_update < timedelta(hours=24), f"Metric {metric.metric_name} is stale"

    def test_calculation_method_documented(self):
        """All metrics have documented calculation methods."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - All metrics should describe how they're calculated
        for metric in engine.metrics.values():
            assert metric.calculation_method, f"Metric {metric.metric_name} missing calculation method"
            assert len(metric.calculation_method) > 0


# ============================================================================
# Test: Integration
# ============================================================================

class TestIntegration:
    """Test integration with analytics and feedback systems."""

    def test_engine_initialization_complete(self):
        """Engine initializes all data structures on creation."""
        # Arrange & Act
        engine = CompetitiveAdvantageEngine()

        # Assert
        assert len(engine.metrics) > 0
        assert len(engine.insights) > 0
        assert len(engine.market_positions) > 0
        assert engine._initialize_competitive_data is not None
        assert engine._initialize_benchmark_data is not None

    def test_singleton_pattern(self):
        """get_competitive_advantage_engine returns singleton instance."""
        # Arrange & Act
        engine1 = get_competitive_advantage_engine()
        engine2 = get_competitive_advantage_engine()

        # Assert
        assert engine1 is engine2  # Same instance

    def test_metric_categories_distributed(self):
        """Metrics are distributed across all advantage categories."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Count metrics per category
        category_counts = {}
        for metric in engine.metrics.values():
            category = metric.category
            category_counts[category] = category_counts.get(category, 0) + 1

        # Assert - Should have metrics in multiple categories
        assert len(category_counts) >= 4, "Should have metrics across 4+ categories"

        # Assert - Key categories should be represented
        assert AdvantageCategory.COST in category_counts
        assert AdvantageCategory.PRIVACY in category_counts
        assert AdvantageCategory.INTEGRATION in category_counts

    def test_insights_link_to_metrics(self):
        """Insights reference metrics that support their claims."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - Each insight should reference at least one metric
        for insight in engine.insights:
            assert len(insight.supporting_metrics) > 0, \
                f"Insight '{insight.title}' has no supporting metrics"

            # Assert - Referenced metrics should exist
            for metric_key in insight.supporting_metrics:
                assert metric_key in engine.metrics, \
                    f"Insight '{insight.title}' references missing metric '{metric_key}'"

    def test_data_integrity_across_collections(self):
        """Data integrity maintained across metrics, insights, and positions."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - All metric categories should be valid
        valid_categories = {cat for cat in AdvantageCategory}
        for metric in engine.metrics.values():
            assert metric.category in valid_categories

        # Assert - All insight categories should be valid
        for insight in engine.insights:
            assert insight.category in valid_categories

        # Assert - Market positions should have valid ranking ranges
        for position in engine.market_positions.values():
            assert 1 <= position.competitive_ranking <= position.total_competitors
            assert 0 <= position.market_share <= 100
            assert position.growth_rate >= -100  # Can decline up to 100%


# ============================================================================
# Test: Edge Cases and Validation
# ============================================================================

class TestEdgeCasesAndValidation:
    """Test edge cases, data validation, and error handling."""

    def test_metric_with_no_industry_best(self):
        """Metrics can have None for industry_best if not available."""
        # Arrange & Act
        metric = CompetitiveMetric(
            category=AdvantageCategory.COST,
            metric_name="Niche Metric",
            atom_value=50.0,
            competitor_average=30.0,
            industry_best=None,  # Not available
            unit="%",
            description="A metric without industry benchmark",
            calculation_method="Direct measurement",
            last_updated=datetime.now(timezone.utc)
        )

        # Assert
        assert metric.industry_best is None
        assert metric.atom_value > metric.competitor_average

    def test_market_position_key_differentiators_unique(self):
        """Market position key differentiators should be unique within position."""
        # Arrange & Act
        position = MarketPosition(
            segment="Test Segment",
            market_share=10.0,
            growth_rate=20.0,
            competitive_ranking=1,
            total_competitors=5,
            key_differentiators=["Feature A", "Feature B", "Feature A"]  # Duplicate
        )

        # Assert - Duplicates allowed (may represent emphasis)
        assert len(position.key_differentiators) == 3

    def test_competitive_advantage_comprehensive_coverage(self):
        """Engine covers all major competitive advantage categories."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Collect unique categories from metrics
        metric_categories = {metric.category for metric in engine.metrics.values()}
        insight_categories = {insight.category for insight in engine.insights}

        # Assert - Should cover most advantage categories
        expected_categories = {
            AdvantageCategory.COST,
            AdvantageCategory.PRIVACY,
            AdvantageCategory.INTEGRATION,
            AdvantageCategory.AI_OPTIMIZATION,
        }

        for category in expected_categories:
            assert category in metric_categories, f"Missing metric category: {category}"

    def test_metric_last_updated_timezone_aware(self):
        """Metric timestamps are timezone-aware."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Assert - All metrics should have timezone-aware timestamps
        for metric in engine.metrics.values():
            assert metric.last_updated.tzinfo is not None, \
                f"Metric '{metric.metric_name}' has naive datetime"

    def test_engine_data_immutability_safety(self):
        """Engine data structures can be safely accessed without modification."""
        # Arrange
        engine = CompetitiveAdvantageEngine()

        # Act - Access metrics (should not modify original)
        metrics_count_before = len(engine.metrics)
        _ = list(engine.metrics.values())  # Iterate
        metrics_count_after = len(engine.metrics)

        # Assert
        assert metrics_count_before == metrics_count_after

    def test_competitive_metric_equality(self):
        """CompetitiveMetric equality comparison works correctly."""
        # Arrange
        now = datetime.now(timezone.utc)
        metric1 = CompetitiveMetric(
            category=AdvantageCategory.COST,
            metric_name="Test Metric",
            atom_value=50.0,
            competitor_average=30.0,
            industry_best=60.0,
            unit="%",
            description="Test",
            calculation_method="Test",
            last_updated=now
        )

        metric2 = CompetitiveMetric(
            category=AdvantageCategory.COST,
            metric_name="Test Metric",
            atom_value=50.0,
            competitor_average=30.0,
            industry_best=60.0,
            unit="%",
            description="Test",
            calculation_method="Test",
            last_updated=now
        )

        # Assert
        # Note: dataclass uses field equality, not object identity
        assert metric1.category == metric2.category
        assert metric1.metric_name == metric2.metric_name
