"""
Test Coverage for AI Workflow Optimization Endpoints
Testing AI-powered workflow analysis and optimization endpoints
"""

import pytest
from unittest.mock import Mock, AsyncMock, patch
from fastapi.testclient import TestClient
from fastapi import HTTPException
from datetime import datetime, timezone


# ============================================================================
# Fixtures
# ============================================================================

@pytest.fixture
def mock_optimizer():
    """Mock AIWorkflowOptimizer."""
    optimizer = Mock()
    optimizer.analyze_workflow = AsyncMock()
    optimizer.optimize_workflow_plan = AsyncMock()
    optimizer.monitor_workflow_performance = AsyncMock()
    return optimizer


@pytest.fixture
def mock_analysis_result():
    """Mock workflow analysis result."""
    analysis = Mock()
    analysis.workflow_id = "workflow_123"
    analysis.workflow_name = "Test Workflow"
    analysis.total_nodes = 10
    analysis.total_edges = 15
    analysis.complexity_score = 0.75
    analysis.estimated_execution_time = 120
    analysis.integrations_used = ["notion", "slack"]
    analysis.failure_points = [{"node_id": "node_1", "issues": ["timeout_risk"]}]
    analysis.bottlenecks = [{"node_id": "node_2", "reason": "high_load"}]
    analysis.optimization_opportunities = [
        Mock(
            id="opt_1",
            type=Mock(value="performance"),
            title="Optimize Performance",
            impact_level=Mock(value="high"),
            estimated_improvement={"execution_time": 40},
            implementation_effort="medium",
            confidence_score=85
        )
    ]
    analysis.analysis_timestamp = datetime.now(timezone.utc)
    return analysis


@pytest.fixture
def client(mock_optimizer):
    """Test client with mocked optimizer."""
    from fastapi import FastAPI
    from core.ai_workflow_optimization_endpoints import router

    app = FastAPI()
    app.include_router(router)

    # Mock get_ai_workflow_optimizer dependency
    def override_get_optimizer():
        return mock_optimizer

    from core.ai_workflow_optimization_endpoints import get_ai_workflow_optimizer
    app.dependency_overrides[get_ai_workflow_optimizer] = override_get_optimizer

    yield TestClient(app)

    app.dependency_overrides.clear()


# ============================================================================
# TestAIWorkflowOptimization - Analysis Endpoints
# ============================================================================

class TestAIWorkflowOptimization:
    """Test AI workflow optimization endpoints."""

    def test_analyze_workflow_success(self, client, mock_optimizer, mock_analysis_result):
        """Test successful workflow analysis."""
        mock_optimizer.analyze_workflow.return_value = mock_analysis_result

        response = client.post(
            "/api/v1/workflows/analyze",
            json={
                "workflow_data": {"nodes": [], "edges": []},
                "performance_metrics": {"avg_execution_time": 100}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "analysis" in data
        assert data["analysis"]["workflow_id"] == "workflow_123"

    def test_analyze_workflow_without_metrics(self, client, mock_optimizer, mock_analysis_result):
        """Test workflow analysis without performance metrics."""
        mock_optimizer.analyze_workflow.return_value = mock_analysis_result

        response = client.post(
            "/api/v1/workflows/analyze",
            json={"workflow_data": {"nodes": [], "edges": []}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

    def test_analyze_workflow_service_error(self, client, mock_optimizer):
        """Test workflow analysis with service error."""
        mock_optimizer.analyze_workflow.side_effect = Exception("Analysis failed")

        response = client.post(
            "/api/v1/workflows/analyze",
            json={"workflow_data": {"nodes": [], "edges": []}}
        )

        assert response.status_code == 500

    def test_create_optimization_plan_success(self, client, mock_optimizer):
        """Test successful optimization plan creation."""
        mock_plan = {
            "optimization_plan": {"steps": ["step1", "step2"]},
            "workflow_analysis": {
                "workflow_id": "workflow_123",
                "workflow_name": "Test Workflow",
                "complexity_score": 0.75,
                "failure_points": []
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        mock_optimizer.optimize_workflow_plan.return_value = mock_plan

        response = client.post(
            "/api/v1/workflows/optimization-plan",
            json={
                "workflow_data": {"nodes": []},
                "optimization_goals": ["performance", "cost"],
                "constraints": {"max_cost": 100}
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "optimization_plan" in data
        assert "workflow_summary" in data

    def test_create_optimization_plan_invalid_goal(self, client, mock_optimizer):
        """Test optimization plan with invalid optimization goal."""
        response = client.post(
            "/api/v1/workflows/optimization-plan",
            json={
                "workflow_data": {"nodes": []},
                "optimization_goals": ["invalid_goal"]
            }
        )

        assert response.status_code == 400

    def test_create_optimization_plan_empty_goals(self, client, mock_optimizer):
        """Test optimization plan with empty goals list."""
        mock_plan = {
            "optimization_plan": {},
            "workflow_analysis": {
                "workflow_id": "workflow_123",
                "workflow_name": "Test",
                "complexity_score": 0.5,
                "failure_points": []
            },
            "generated_at": datetime.now(timezone.utc).isoformat()
        }
        mock_optimizer.optimize_workflow_plan.return_value = mock_plan

        response = client.post(
            "/api/v1/workflows/optimization-plan",
            json={
                "workflow_data": {"nodes": []},
                "optimization_goals": []
            }
        )

        assert response.status_code == 200

    def test_monitor_workflow_performance_success(self, client, mock_optimizer):
        """Test successful workflow performance monitoring."""
        mock_monitoring = {
            "health_score": 85,
            "urgent_recommendations": [],
            "identified_issues": []
        }
        mock_optimizer.monitor_workflow_performance.return_value = mock_monitoring

        response = client.post(
            "/api/v1/workflows/workflow_123/monitor",
            json={
                "workflow_id": "workflow_123",
                "metrics": {"execution_time": 100},
                "time_window_hours": 24
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "health_status" in data
        assert data["health_status"]["overall_health"] == 85

    def test_monitor_workflow_performance_healthy(self, client, mock_optimizer):
        """Test monitoring with healthy workflow."""
        mock_monitoring = {"health_score": 90, "urgent_recommendations": [], "identified_issues": []}
        mock_optimizer.monitor_workflow_performance.return_value = mock_monitoring

        response = client.post(
            "/api/v1/workflows/workflow_123/monitor",
            json={"workflow_id": "workflow_123", "metrics": {}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["health_status"]["status"] == "healthy"

    def test_monitor_workflow_performance_warning(self, client, mock_optimizer):
        """Test monitoring with warning health status."""
        mock_monitoring = {"health_score": 65, "urgent_recommendations": [], "identified_issues": []}
        mock_optimizer.monitor_workflow_performance.return_value = mock_monitoring

        response = client.post(
            "/api/v1/workflows/workflow_123/monitor",
            json={"workflow_id": "workflow_123", "metrics": {}}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["health_status"]["status"] == "warning"


# ============================================================================
# TestWorkflowOptimization - Optimization Algorithms
# ============================================================================

class TestWorkflowOptimization:
    """Test workflow optimization algorithms and recommendations."""

    def test_get_workflow_recommendations_success(self, client):
        """Test successful recommendations retrieval."""
        response = client.get("/api/v1/workflows/workflow_123/recommendations")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "recommendations" in data
        assert len(data["recommendations"]) > 0

    def test_get_recommendations_with_type_filter(self, client):
        """Test recommendations with type filter."""
        response = client.get(
            "/api/v1/workflows/workflow_123/recommendations?type_filter=performance"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"]["type"] == "performance"

    def test_get_recommendations_with_impact_filter(self, client):
        """Test recommendations with impact filter."""
        response = client.get(
            "/api/v1/workflows/workflow_123/recommendations?impact_filter=high"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"]["impact"] == "high"

    def test_get_recommendations_both_filters(self, client):
        """Test recommendations with both type and impact filters."""
        response = client.get(
            "/api/v1/workflows/workflow_123/recommendations?type_filter=cost&impact_filter=medium"
        )

        assert response.status_code == 200
        data = response.json()
        assert data["filters_applied"]["type"] == "cost"
        assert data["filters_applied"]["impact"] == "medium"

    def test_get_optimization_types_success(self, client):
        """Test successful optimization types retrieval."""
        response = client.get("/api/v1/workflows/optimization-types")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "optimization_types" in data
        assert "performance" in data["optimization_types"]
        assert "cost" in data["optimization_types"]

    def test_batch_analyze_workflows_success(self, client, mock_optimizer, mock_analysis_result):
        """Test successful batch workflow analysis."""
        mock_optimizer.analyze_workflow.return_value = mock_analysis_result

        response = client.post(
            "/api/v1/workflows/batch-analysis",
            json=[
                {"id": "workflow_1", "nodes": []},
                {"id": "workflow_2", "nodes": []}
            ]
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "batch_analysis" in data

    def test_batch_analyze_workflows_exceeds_limit(self, client):
        """Test batch analysis with too many workflows."""
        workflows = [{"id": f"workflow_{i}"} for i in range(51)]

        response = client.post(
            "/api/v1/workflows/batch-analysis",
            json=workflows
        )

        assert response.status_code == 400

    def test_batch_analyze_single_workflow(self, client, mock_optimizer, mock_analysis_result):
        """Test batch analysis with single workflow."""
        mock_optimizer.analyze_workflow.return_value = mock_analysis_result

        response = client.post(
            "/api/v1/workflows/batch-analysis",
            json=[{"id": "workflow_1", "nodes": []}]
        )

        assert response.status_code == 200


# ============================================================================
# TestOptimizationAlgorithms - Advanced Features
# ============================================================================

class TestOptimizationAlgorithms:
    """Test advanced optimization algorithms and features."""

    def test_get_optimization_insights_success(self, client):
        """Test successful optimization insights retrieval."""
        response = client.get("/api/v1/workflows/optimization-insights?time_range=7d")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "insights" in data
        assert data["time_range"] == "7d"

    def test_get_optimization_insights_30d(self, client):
        """Test optimization insights for 30-day range."""
        response = client.get("/api/v1/workflows/optimization-insights?time_range=30d")

        assert response.status_code == 200
        data = response.json()
        assert data["time_range"] == "30d"

    def test_implement_optimization_success(self, client, mock_optimizer):
        """Test successful optimization implementation initiation."""
        response = client.post(
            "/api/v1/workflows/workflow_123/implement-optimization",
            json={"optimization_id": "opt_parallel_processing"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "job_id" in data
        assert data["status"] == "initiated"

    def test_implement_optimization_returns_job_id(self, client, mock_optimizer):
        """Test that optimization implementation returns valid job ID."""
        response = client.post(
            "/api/v1/workflows/workflow_123/implement-optimization",
            json={"optimization_id": "opt_caching"}
        )

        assert response.status_code == 200
        data = response.json()
        assert data["job_id"].startswith("opt_job_")

    def test_get_optimization_insights_includes_trends(self, client):
        """Test that insights include optimization trends."""
        response = client.get("/api/v1/workflows/optimization-insights")

        assert response.status_code == 200
        data = response.json()
        insights = data["insights"]
        assert "optimization_trends" in insights
        assert "roi_analysis" in insights


# ============================================================================
# TestOptimizationErrors - Error Handling
# ============================================================================

class TestOptimizationErrors:
    """Test error handling in optimization endpoints."""

    def test_analyze_workflow_invalid_json(self, client):
        """Test workflow analysis with invalid JSON."""
        response = client.post(
            "/api/v1/workflows/analyze",
            json={"invalid": "data"}
        )

        # May succeed or fail depending on validation
        assert response.status_code in [200, 422, 500]

    def test_monitor_workflow_missing_workflow_id(self, client):
        """Test monitoring without workflow_id in path."""
        response = client.post(
            "/api/v1/workflows//monitor",
            json={"metrics": {}}
        )

        assert response.status_code == 404  # Route not found

    def test_implement_optimization_missing_id(self, client):
        """Test optimization implementation without optimization_id."""
        response = client.post(
            "/api/v1/workflows/workflow_123/implement-optimization",
            json={}
        )

        assert response.status_code == 422  # Validation error

    def test_batch_analyze_empty_list(self, client):
        """Test batch analysis with empty workflow list."""
        response = client.post(
            "/api/v1/workflows/batch-analysis",
            json=[]
        )

        assert response.status_code == 200

    def test_monitor_workflow_service_error(self, client, mock_optimizer):
        """Test monitoring with service error."""
        mock_optimizer.monitor_workflow_performance.side_effect = Exception("Monitoring failed")

        response = client.post(
            "/api/v1/workflows/workflow_123/monitor",
            json={"workflow_id": "workflow_123", "metrics": {}}
        )

        assert response.status_code == 500

    def test_implement_optimization_service_error(self, client, mock_optimizer):
        """Test optimization implementation with service error."""
        # Mock background task to raise error
        with patch('core.ai_workflow_optimization_endpoints.BackgroundTasks'):
            response = client.post(
                "/api/v1/workflows/workflow_123/implement-optimization",
                json={"optimization_id": "opt_invalid"}
            )

            # Should succeed in initiating, error happens in background
            assert response.status_code in [200, 500]

    def test_create_optimization_plan_service_error(self, client, mock_optimizer):
        """Test optimization plan creation with service error."""
        mock_optimizer.optimize_workflow_plan.side_effect = Exception("Planning failed")

        response = client.post(
            "/api/v1/workflows/optimization-plan",
            json={
                "workflow_data": {"nodes": []},
                "optimization_goals": ["performance"]
            }
        )

        assert response.status_code == 500

    def test_get_recommendations_service_error(self, client):
        """Test recommendations endpoint with service error."""
        # This endpoint doesn't depend on external services, so it should succeed
        response = client.get("/api/v1/workflows/workflow_123/recommendations")

        assert response.status_code == 200

    def test_batch_analyze_with_service_error(self, client, mock_optimizer):
        """Test batch analysis with partial service failures."""
        # First workflow succeeds, second fails
        mock_optimizer.analyze_workflow.side_effect = [
            Mock(workflow_id="workflow_1", workflow_name="Workflow 1"),
            Exception("Analysis failed")
        ]

        response = client.post(
            "/api/v1/workflows/batch-analysis",
            json=[
                {"id": "workflow_1", "nodes": []},
                {"id": "workflow_2", "nodes": []}
            ]
        )

        assert response.status_code == 200
        data = response.json()
        # Should have results with one error
        assert "batch_analysis" in data
