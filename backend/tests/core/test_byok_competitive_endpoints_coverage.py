"""
Test Coverage for BYOK Competitive Endpoints
Testing cost optimization and competitive intelligence endpoints
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_byok_manager():
    """Mock BYOKManager."""
    manager = Mock()
    manager.get_provider_status = Mock()
    manager.usage_stats = {
        "openai": Mock(cost_accumulated=100.0),
        "anthropic": Mock(cost_accumulated=50.0)
    }
    manager.providers = {
        "openai": Mock(cost_per_token=0.00003),
        "anthropic": Mock(cost_per_token=0.00002),
        "deepseek": Mock(cost_per_token=0.000001)
    }
    return manager


@pytest.fixture
def mock_cost_optimizer(mock_byok_manager):
    """Mock BYOKCostOptimizer."""
    optimizer = Mock()
    optimizer.byok_manager = mock_byok_manager
    optimizer.get_competitive_analysis_report = Mock()
    optimizer.analyze_user_usage_pattern = Mock()
    optimizer.get_cost_optimization_recommendations = Mock()
    optimizer.simulate_cost_savings = Mock()
    optimizer.competitive_insights = {
        "openai": Mock(
            market_position="premium",
            best_for_tasks=["reasoning", "code"],
            market_trend="stable"
        ),
        "deepseek": Mock(
            market_position="budget",
            best_for_tasks=["simple_tasks"],
            market_trend="rising"
        )
    }
    optimizer.usage_patterns = {}
    return optimizer


@pytest.fixture
def mock_competitive_analysis():
    """Mock competitive analysis report."""
    return {
        "providers": {
            "openai": {
                "market_position": "premium",
                "quality_score": 90,
                "cost_efficiency_score": 70,
                "quality_ranking": 1,
                "cost_ranking": 5,
                "market_trend": "stable"
            },
            "deepseek": {
                "market_position": "budget",
                "quality_score": 75,
                "cost_efficiency_score": 95,
                "quality_ranking": 3,
                "cost_ranking": 1,
                "market_trend": "rising"
            }
        },
        "market_overview": {
            "providers_with_keys": 2,
            "average_quality_score": 82.5,
            "average_cost_efficiency": 82.5,
            "market_segments": {
                "premium": 1,
                "budget": 1
            }
        }
    }


@pytest.fixture
def client(mock_cost_optimizer):
    """Test client with mocked cost optimizer."""
    from fastapi import FastAPI
    from core.byok_competitive_endpoints import router

    app = FastAPI()
    app.include_router(router)

    # Mock get_cost_optimizer dependency
    def override_get_optimizer():
        return mock_cost_optimizer

    from core.byok_competitive_endpoints import get_cost_optimizer
    app.dependency_overrides[get_cost_optimizer] = override_get_optimizer

    yield TestClient(app)

    app.dependency_overrides.clear()


# ============================================================================
# TestBYOKCompetitiveEndpoints - Competitive Analysis
# ============================================================================

class TestBYOKCompetitiveEndpoints:
    """Test BYOK competitive analysis endpoints."""

    def test_get_competitive_analysis_success(self, client, mock_cost_optimizer, mock_competitive_analysis):
        """Test successful competitive analysis retrieval."""
        mock_cost_optimizer.get_competitive_analysis_report.return_value = mock_competitive_analysis

        response = client.get("/api/v1/byok/competitive-analysis")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "report" in data
        assert "generated_at" in data

    def test_get_competitive_analysis_service_error(self, client, mock_cost_optimizer):
        """Test competitive analysis with service error."""
        mock_cost_optimizer.get_competitive_analysis_report.side_effect = Exception("Analysis failed")

        response = client.get("/api/v1/byok/competitive-analysis")

        assert response.status_code == 500

    def test_get_market_insights_success(self, client, mock_cost_optimizer, mock_competitive_analysis):
        """Test successful market insights retrieval."""
        mock_cost_optimizer.get_competitive_analysis_report.return_value = mock_competitive_analysis

        response = client.get("/api/v1/byok/market-insights")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "insights" in data
        assert "provider_trends" in data["insights"]
        assert "cost_trends" in data["insights"]

    def test_get_market_insights_includes_recommendations(self, client, mock_cost_optimizer, mock_competitive_analysis):
        """Test that market insights include strategic recommendations."""
        mock_cost_optimizer.get_competitive_analysis_report.return_value = mock_competitive_analysis

        response = client.get("/api/v1/byok/market-insights")

        assert response.status_code == 200
        data = response.json()
        insights = data["insights"]
        assert "strategic_recommendations" in insights

    def test_get_value_proposition_success(self, client, mock_cost_optimizer, mock_competitive_analysis):
        """Test successful value proposition retrieval."""
        mock_cost_optimizer.get_competitive_analysis_report.return_value = mock_competitive_analysis

        response = client.get("/api/v1/byok/value-proposition")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "value_proposition" in data
        assert "byok_advantages" in data["value_proposition"]

    def test_get_value_proposition_includes_metrics(self, client, mock_cost_optimizer, mock_competitive_analysis):
        """Test that value proposition includes metrics."""
        mock_cost_optimizer.get_competitive_analysis_report.return_value = mock_competitive_analysis

        response = client.get("/api/v1/byok/value-proposition")

        assert response.status_code == 200
        data = response.json()
        metrics = data["value_proposition"]["metrics"]
        assert "active_providers" in metrics
        assert "estimated_monthly_savings" in metrics


# ============================================================================
# TestBYOKPricing - Cost Optimization
# ============================================================================

class TestBYOKPricing:
    """Test BYOK pricing and cost optimization endpoints."""

    def test_optimize_costs_success(self, client, mock_cost_optimizer):
        """Test successful cost optimization."""
        mock_recommendation = Mock(
            recommended_provider="deepseek",
            confidence=90,
            reasoning="Cost-effective for this task type"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation
        mock_cost_optimizer.analyze_user_usage_pattern.return_value = None

        response = client.post(
            "/api/v1/byok/optimize-costs",
            json={
                "user_id": "user_123",
                "task_type": "simple_query",
                "context": {}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recommendation" in data

    def test_optimize_costs_default_user(self, client, mock_cost_optimizer):
        """Test cost optimization with default user."""
        mock_recommendation = Mock(
            recommended_provider="openai",
            confidence=85,
            reasoning="High quality required"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation

        response = client.post(
            "/api/v1/byok/optimize-costs",
            json={"task_type": "complex_reasoning"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_optimize_costs_with_context(self, client, mock_cost_optimizer):
        """Test cost optimization with context."""
        mock_recommendation = Mock(
            recommended_provider="anthropic",
            confidence=88,
            reasoning="Balanced cost and quality"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation

        response = client.post(
            "/api/v1/byok/optimize-costs",
            json={
                "user_id": "user_123",
                "task_type": "code_generation",
                "context": {"language": "python", "complexity": "high"}
            }
        )

        assert response.status_code == 200

    def test_simulate_cost_savings_success(self, client, mock_cost_optimizer):
        """Test successful cost savings simulation."""
        mock_simulation = {
            "current_cost": 100.0,
            "optimized_cost": 70.0,
            "savings": 30.0,
            "savings_percentage": 30.0
        }
        mock_cost_optimizer.simulate_cost_savings.return_value = mock_simulation

        response = client.post(
            "/api/v1/byok/simulate-savings",
            json={
                "user_id": "user_123",
                "months": 6,
                "adoption_rate": 0.8
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "simulation" in data

    def test_simulate_cost_savings_default_params(self, client, mock_cost_optimizer):
        """Test cost savings simulation with default parameters."""
        mock_simulation = {"savings": 15.0}
        mock_cost_optimizer.simulate_cost_savings.return_value = mock_simulation

        response = client.post(
            "/api/v1/byok/simulate-savings",
            json={"user_id": "user_123"}
        )

        assert response.status_code == 200

    def test_simulate_cost_savings_custom_months(self, client, mock_cost_optimizer):
        """Test cost savings simulation with custom month range."""
        mock_simulation = {"savings": 60.0}
        mock_cost_optimizer.simulate_cost_savings.return_value = mock_simulation

        response = client.post(
            "/api/v1/byok/simulate-savings",
            json={
                "user_id": "user_123",
                "months": 12,
                "adoption_rate": 1.0
            }
        )

        assert response.status_code == 200

    def test_optimize_workflow_costs_success(self, client, mock_cost_optimizer):
        """Test successful workflow cost optimization."""
        mock_recommendation = Mock(
            recommended_provider="deepseek",
            confidence=92,
            reasoning="High volume simple tasks"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation

        response = client.post(
            "/api/v1/byok/workflow-optimization",
            json={
                "id": "workflow_123",
                "user_id": "user_123",
                "steps": [
                    {
                        "name": "step1",
                        "task_type": "simple_query",
                        "estimated_tokens": 1000,
                        "current_provider": "openai"
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "summary" in data
        assert "optimizations" in data

    def test_optimize_workflow_costs_multiple_steps(self, client, mock_cost_optimizer):
        """Test workflow optimization with multiple steps."""
        mock_recommendation = Mock(
            recommended_provider="anthropic",
            confidence=88,
            reasoning="Balanced performance"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation

        response = client.post(
            "/api/v1/byok/workflow-optimization",
            json={
                "id": "workflow_123",
                "user_id": "user_123",
                "steps": [
                    {"name": "step1", "task_type": "query", "estimated_tokens": 500},
                    {"name": "step2", "task_type": "analysis", "estimated_tokens": 1000},
                    {"name": "step3", "task_type": "summary", "estimated_tokens": 300}
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert len(data["optimizations"]) == 3

    def test_optimize_workflow_costs_empty_steps(self, client, mock_cost_optimizer):
        """Test workflow optimization with no steps."""
        response = client.post(
            "/api/v1/byok/workflow-optimization",
            json={"id": "workflow_123", "steps": []}
        )

        assert response.status_code == 400

    def test_optimize_workflow_costs_calculates_savings(self, client, mock_cost_optimizer):
        """Test that workflow optimization calculates savings correctly."""
        mock_recommendation = Mock(
            recommended_provider="deepseek",
            confidence=95,
            reasoning="Significant cost savings"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation

        response = client.post(
            "/api/v1/byok/workflow-optimization",
            json={
                "id": "workflow_123",
                "user_id": "user_123",
                "steps": [
                    {
                        "name": "step1",
                        "task_type": "query",
                        "estimated_tokens": 1000,
                        "current_provider": "openai"
                    }
                ]
            }
        )

        assert response.status_code == 200
        data = response.json()
        summary = data["summary"]
        assert "total_savings" in summary
        assert "total_savings_percentage" in summary


# ============================================================================
# TestBYOKComparison - Provider Intelligence
# ============================================================================

class TestBYOKComparison:
    """Test BYOK provider comparison and intelligence endpoints."""

    def test_get_provider_intelligence_success(self, client, mock_cost_optimizer, mock_byok_manager):
        """Test successful provider intelligence retrieval."""
        mock_status = {
            "provider": {
                "provider_id": "openai",
                "cost_per_token": 0.00003
            }
        }
        mock_byok_manager.get_provider_status.return_value = mock_status

        response = client.get("/api/v1/byok/provider-intelligence/openai")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "intelligence" in data

    def test_get_provider_intelligence_budget_provider(self, client, mock_cost_optimizer, mock_byok_manager):
        """Test provider intelligence for budget provider."""
        mock_status = {
            "provider": {
                "provider_id": "deepseek",
                "cost_per_token": 0.000001
            }
        }
        mock_byok_manager.get_provider_status.return_value = mock_status
        mock_cost_optimizer.competitive_insights = {
            "deepseek": Mock(
                market_position="budget",
                best_for_tasks=["simple_tasks", "batch_operations"],
                market_trend="rising"
            )
        }

        response = client.get("/api/v1/byok/provider-intelligence/deepseek")

        assert response.status_code == 200
        data = response.json()
        intelligence = data["intelligence"]
        assert "recommendations" in intelligence
        assert "best_use_cases" in intelligence

    def test_get_provider_intelligence_premium_provider(self, client, mock_cost_optimizer, mock_byok_manager):
        """Test provider intelligence for premium provider."""
        mock_status = {
            "provider": {
                "provider_id": "anthropic",
                "cost_per_token": 0.00002
            }
        }
        mock_byok_manager.get_provider_status.return_value = mock_status
        mock_cost_optimizer.competitive_insights = {
            "anthropic": Mock(
                market_position="premium",
                best_for_tasks=["reasoning", "code_generation"],
                market_trend="stable"
            )
        }

        response = client.get("/api/v1/byok/provider-intelligence/anthropic")

        assert response.status_code == 200
        data = response.json()
        intelligence = data["intelligence"]
        assert "cost_analysis" in intelligence

    def test_get_provider_intelligence_not_found(self, client, mock_cost_optimizer, mock_byok_manager):
        """Test provider intelligence for non-existent provider."""
        mock_byok_manager.get_provider_status.side_effect = ValueError("Provider not found")

        response = client.get("/api/v1/byok/provider-intelligence/nonexistent")

        assert response.status_code == 404

    def test_get_provider_intelligence_includes_cost_analysis(self, client, mock_cost_optimizer, mock_byok_manager):
        """Test that provider intelligence includes cost analysis."""
        mock_status = {
            "provider": {
                "provider_id": "openai",
                "cost_per_token": 0.00003
            }
        }
        mock_byok_manager.get_provider_status.return_value = mock_status

        response = client.get("/api/v1/byok/provider-intelligence/openai")

        assert response.status_code == 200
        data = response.json()
        intelligence = data["intelligence"]
        assert "cost_analysis" in intelligence
        assert "cost_per_token" in intelligence["cost_analysis"]
        assert "relative_cost" in intelligence["cost_analysis"]


# ============================================================================
# TestBYOKErrors - Error Handling
# ============================================================================

class TestBYOKErrors:
    """Test error handling in BYOK competitive endpoints."""

    def test_optimize_costs_service_error(self, client, mock_cost_optimizer):
        """Test cost optimization with service error."""
        mock_cost_optimizer.get_cost_optimization_recommendations.side_effect = Exception("Optimization failed")

        response = client.post(
            "/api/v1/byok/optimize-costs",
            json={"task_type": "query"}
        )

        assert response.status_code == 500

    def test_simulate_cost_savings_service_error(self, client, mock_cost_optimizer):
        """Test cost savings simulation with service error."""
        mock_cost_optimizer.simulate_cost_savings.side_effect = Exception("Simulation failed")

        response = client.post(
            "/api/v1/byok/simulate-savings",
            json={"user_id": "user_123"}
        )

        assert response.status_code == 500

    def test_get_value_proposition_service_error(self, client, mock_cost_optimizer):
        """Test value proposition with service error."""
        mock_cost_optimizer.get_competitive_analysis_report.side_effect = Exception("Analysis failed")

        response = client.get("/api/v1/byok/value-proposition")

        assert response.status_code == 500

    def test_optimize_workflow_costs_service_error(self, client, mock_cost_optimizer):
        """Test workflow optimization with service error."""
        mock_cost_optimizer.get_cost_optimization_recommendations.side_effect = Exception("Optimization failed")

        response = client.post(
            "/api/v1/byok/workflow-optimization",
            json={
                "id": "workflow_123",
                "steps": [{"name": "step1", "task_type": "query"}]
            }
        )

        assert response.status_code == 500

    def test_get_market_insights_service_error(self, client, mock_cost_optimizer):
        """Test market insights with service error."""
        mock_cost_optimizer.get_competitive_analysis_report.side_effect = Exception("Insights failed")

        response = client.get("/api/v1/byok/market-insights")

        assert response.status_code == 500

    def test_get_provider_intelligence_service_error(self, client, mock_cost_optimizer, mock_byok_manager):
        """Test provider intelligence with service error."""
        mock_byok_manager.get_provider_status.side_effect = Exception("Provider lookup failed")

        response = client.get("/api/v1/byok/provider-intelligence/openai")

        assert response.status_code == 500

    def test_optimize_costs_missing_task_type(self, client, mock_cost_optimizer):
        """Test cost optimization without task type."""
        mock_recommendation = Mock(
            recommended_provider="openai",
            confidence=80,
            reasoning="Default provider"
        )
        mock_cost_optimizer.get_cost_optimization_recommendations.return_value = mock_recommendation

        response = client.post(
            "/api/v1/byok/optimize-costs",
            json={}
        )

        # Should use default task_type
        assert response.status_code == 200

    def test_simulate_savings_negative_adoption(self, client, mock_cost_optimizer):
        """Test cost savings with negative adoption rate (edge case)."""
        mock_simulation = {"savings": 0}
        mock_cost_optimizer.simulate_cost_savings.return_value = mock_simulation

        response = client.post(
            "/api/v1/byok/simulate-savings",
            json={
                "user_id": "user_123",
                "adoption_rate": -0.5
            }
        )

        assert response.status_code == 200
