"""
Feedback Analytics Routes API Tests

Tests for feedback analytics endpoints:
- GET /api/feedback/analytics - Overall feedback analytics
- GET /api/feedback/agent/{agent_id}/analytics - Per-agent analytics
- GET /api/feedback/trends - Feedback trends over time

Coverage target: 75%+ line coverage on feedback_analytics.py
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch, MagicMock


# ============================================================================
# Test Feedback Analytics Dashboard
# ============================================================================

class TestFeedbackAnalyticsDashboard:
    """Test overall feedback analytics dashboard endpoint."""

    def test_get_feedback_dashboard_success(self, feedback_analytics_client: TestClient):
        """Test complete dashboard returns all sections."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "period_days" in data["data"]
        assert "summary" in data["data"]
        assert "top_performing_agents" in data["data"]
        assert "most_corrected_agents" in data["data"]
        assert "feedback_by_type" in data["data"]
        assert "trends" in data["data"]

    def test_get_feedback_dashboard_with_days(self, feedback_analytics_client: TestClient):
        """Test dashboard respects days parameter (1-365)."""
        response = feedback_analytics_client.get("/api/feedback/analytics?days=7")

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["period_days"] == 7

    def test_get_feedback_dashboard_with_limit(self, feedback_analytics_client: TestClient):
        """Test dashboard respects limit parameter."""
        response = feedback_analytics_client.get("/api/feedback/analytics?limit=5")

        assert response.status_code == 200
        data = response.json()

        # Should return top/bottom agents limited to 5
        assert len(data["data"]["top_performing_agents"]) <= 5

    def test_get_feedback_dashboard_summary(self, feedback_analytics_client: TestClient):
        """Test dashboard includes summary section."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        summary = data["data"]["summary"]
        assert "total_feedback" in summary
        assert "positive_count" in summary
        assert "negative_count" in summary
        assert "thumbs_up_count" in summary
        assert "thumbs_down_count" in summary
        assert "average_rating" in summary

    def test_get_feedback_dashboard_top_agents(self, feedback_analytics_client: TestClient):
        """Test dashboard includes top_performing_agents."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        top_agents = data["data"]["top_performing_agents"]
        assert isinstance(top_agents, list)
        assert len(top_agents) > 0

        # Check agent structure
        agent = top_agents[0]
        assert "agent_id" in agent
        assert "agent_name" in agent
        assert "total_feedback" in agent
        assert "average_rating" in agent

    def test_get_feedback_dashboard_most_corrected(self, feedback_analytics_client: TestClient):
        """Test dashboard includes most_corrected_agents."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        most_corrected = data["data"]["most_corrected_agents"]
        assert isinstance(most_corrected, list)
        assert len(most_corrected) > 0

        # Check agent structure
        agent = most_corrected[0]
        assert "agent_id" in agent
        assert "total_corrections" in agent
        assert "correction_rate" in agent

    def test_get_feedback_dashboard_breakdown(self, feedback_analytics_client: TestClient):
        """Test dashboard includes feedback_by_type breakdown."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        breakdown = data["data"]["feedback_by_type"]
        assert "thumbs_up" in breakdown
        assert "thumbs_down" in breakdown
        assert "rating" in breakdown

    def test_get_feedback_dashboard_trends(self, feedback_analytics_client: TestClient):
        """Test dashboard includes trends section."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        trends = data["data"]["trends"]
        assert isinstance(trends, list)
        assert len(trends) > 0

        # Check trend structure
        trend = trends[0]
        assert "date" in trend
        assert "total_feedback" in trend
        assert "positive_count" in trend
        assert "negative_count" in trend
        assert "average_rating" in trend


# ============================================================================
# Test Feedback Analytics Validation
# ============================================================================

class TestFeedbackAnalyticsValidation:
    """Test query parameter validation for feedback analytics."""

    def test_get_feedback_dashboard_days_validation(self, feedback_analytics_client: TestClient):
        """Test enforces ge=1, le=365 for days parameter."""
        # Test days < 1 (should fail)
        response = feedback_analytics_client.get("/api/feedback/analytics?days=0")
        assert response.status_code == 422  # Validation error

        # Test days > 365 (should fail)
        response = feedback_analytics_client.get("/api/feedback/analytics?days=400")
        assert response.status_code == 422  # Validation error

    def test_get_feedback_dashboard_limit_validation(self, feedback_analytics_client: TestClient):
        """Test enforces ge=1, le=100 for limit parameter."""
        # Test limit < 1 (should fail)
        response = feedback_analytics_client.get("/api/feedback/analytics?limit=0")
        assert response.status_code == 422  # Validation error

        # Test limit > 100 (should fail)
        response = feedback_analytics_client.get("/api/feedback/analytics?limit=150")
        assert response.status_code == 422  # Validation error

    def test_get_feedback_dashboard_default_values(self, feedback_analytics_client: TestClient):
        """Test uses defaults (days=30, limit=10) when not specified."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        # Default values should be applied
        assert data["data"]["period_days"] == 30


# ============================================================================
# Test Agent Feedback Dashboard
# ============================================================================

class TestAgentFeedbackDashboard:
    """Test agent-specific feedback analytics dashboard."""

    def test_get_agent_dashboard_success(self, feedback_analytics_client: TestClient):
        """Test returns agent-specific dashboard."""
        agent_id = "agent-sales-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "agent_id" in data["data"]
        assert data["data"]["agent_id"] == agent_id

    def test_get_agent_dashboard_with_agent_id(self, feedback_analytics_client: TestClient):
        """Test routes to correct agent."""
        agent_id = "agent-support-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["agent_id"] == agent_id

    def test_get_agent_dashboard_with_days(self, feedback_analytics_client: TestClient):
        """Test respects days parameter."""
        agent_id = "agent-sales-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics?days=7")

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["period_days"] == 7

    def test_get_agent_dashboard_feedback_summary(self, feedback_analytics_client: TestClient):
        """Test includes feedback_summary section."""
        agent_id = "agent-sales-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

        assert response.status_code == 200
        data = response.json()

        summary = data["data"]["feedback_summary"]
        assert "total_feedback" in summary
        assert "positive_count" in summary
        assert "negative_count" in summary
        assert "average_rating" in summary

    def test_get_agent_dashboard_learning_signals(self, feedback_analytics_client: TestClient):
        """Test includes learning_signals section."""
        agent_id = "agent-sales-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

        assert response.status_code == 200
        data = response.json()

        signals = data["data"]["learning_signals"]
        assert "improvement_suggestions" in signals
        assert "common_corrections" in signals
        assert "performance_trends" in signals

    def test_get_agent_dashboard_improvements(self, feedback_analytics_client: TestClient):
        """Test includes improvement_suggestions."""
        agent_id = "agent-sales-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

        assert response.status_code == 200
        data = response.json()

        improvements = data["data"]["learning_signals"]["improvement_suggestions"]
        assert isinstance(improvements, list)
        assert len(improvements) > 0

    def test_get_agent_dashboard_corrections(self, feedback_analytics_client: TestClient):
        """Test includes common_corrections."""
        agent_id = "agent-sales-001"
        response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

        assert response.status_code == 200
        data = response.json()

        corrections = data["data"]["learning_signals"]["common_corrections"]
        assert isinstance(corrections, list)
        assert len(corrections) > 0

    def test_get_agent_dashboard_error_handling(self, feedback_analytics_client: TestClient):
        """Test handles service errors gracefully."""
        agent_id = "nonexistent-agent"

        # Mock service to raise ValueError for nonexistent agent
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_agent_feedback_summary.side_effect = ValueError(f"Agent '{agent_id}' not found")
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

            # Should handle error gracefully
            assert response.status_code in [404, 500]


# ============================================================================
# Test Feedback Trends
# ============================================================================

class TestFeedbackTrends:
    """Test feedback trends endpoint."""

    def test_get_feedback_trends_success(self, feedback_analytics_client: TestClient):
        """Test returns trends data."""
        response = feedback_analytics_client.get("/api/feedback/trends")

        assert response.status_code == 200
        data = response.json()

        assert data["success"] is True
        assert "data" in data
        assert "trends" in data["data"]

    def test_get_feedback_trends_with_days(self, feedback_analytics_client: TestClient):
        """Test respects days parameter."""
        response = feedback_analytics_client.get("/api/feedback/trends?days=7")

        assert response.status_code == 200
        data = response.json()

        assert data["data"]["period_days"] == 7

    def test_get_feedback_trends_period_days(self, feedback_analytics_client: TestClient):
        """Test includes period_days in response."""
        response = feedback_analytics_client.get("/api/feedback/trends")

        assert response.status_code == 200
        data = response.json()

        assert "period_days" in data["data"]
        assert isinstance(data["data"]["period_days"], int)

    def test_get_feedback_trends_daily_data(self, feedback_analytics_client: TestClient):
        """Test returns array of daily trends."""
        response = feedback_analytics_client.get("/api/feedback/trends")

        assert response.status_code == 200
        data = response.json()

        trends = data["data"]["trends"]
        assert isinstance(trends, list)
        assert len(trends) > 0

        # Verify daily trend structure
        trend = trends[0]
        assert "date" in trend
        assert "total_feedback" in trend
        assert "positive_count" in trend
        assert "negative_count" in trend

    def test_get_feedback_trends_empty(self, feedback_analytics_client: TestClient):
        """Test returns empty trends for no data."""
        # Mock service to return empty trends
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_feedback_trends.return_value = []
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get("/api/feedback/trends")

            assert response.status_code == 200
            data = response.json()

            assert data["data"]["trends"] == []

    def test_get_feedback_trends_error_handling(self, feedback_analytics_client: TestClient):
        """Test handles service exceptions gracefully."""
        # Mock service to raise exception
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_feedback_trends.side_effect = Exception("Database error")
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get("/api/feedback/trends")

            # Should handle error gracefully
            assert response.status_code in [500, 503]


# ============================================================================
# Test Feedback Statistics Content
# ============================================================================

class TestFeedbackStatisticsContent:
    """Test feedback statistics data content."""

    def test_feedback_stats_includes_total_count(self, feedback_analytics_client: TestClient):
        """Test total feedback count is included."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        summary = data["data"]["summary"]
        assert "total_feedback" in summary
        assert isinstance(summary["total_feedback"], int)

    def test_feedback_stats_includes_ratio(self, feedback_analytics_client: TestClient):
        """Test positive/negative ratio is included."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        summary = data["data"]["summary"]
        assert "positive_count" in summary
        assert "negative_count" in summary

    def test_feedback_stats_includes_average_rating(self, feedback_analytics_client: TestClient):
        """Test average rating is included."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        summary = data["data"]["summary"]
        assert "average_rating" in summary
        assert isinstance(summary["average_rating"], (int, float))

    def test_feedback_stats_includes_thumbs_counts(self, feedback_analytics_client: TestClient):
        """Test thumbs up/down counts are included."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        summary = data["data"]["summary"]
        assert "thumbs_up_count" in summary
        assert "thumbs_down_count" in summary

    def test_feedback_stats_breakdown_by_type(self, feedback_analytics_client: TestClient):
        """Test feedback type breakdown is included."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        breakdown = data["data"]["feedback_by_type"]
        assert isinstance(breakdown, dict)
        assert len(breakdown) > 0


# ============================================================================
# Test Top Performing Agents
# ============================================================================

class TestTopPerformingAgents:
    """Test top performing agents data."""

    def test_top_performing_agents_returns_list(self, feedback_analytics_client: TestClient):
        """Test returns list of agents."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        top_agents = data["data"]["top_performing_agents"]
        assert isinstance(top_agents, list)

    def test_top_performing_agents_sorted(self, feedback_analytics_client: TestClient):
        """Test agents are sorted by performance metric."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        top_agents = data["data"]["top_performing_agents"]
        # Verify sorting (highest rating first)
        if len(top_agents) > 1:
            assert top_agents[0]["average_rating"] >= top_agents[1]["average_rating"]

    def test_top_performing_agents_limit(self, feedback_analytics_client: TestClient):
        """Test respects limit parameter."""
        response = feedback_analytics_client.get("/api/feedback/analytics?limit=5")

        assert response.status_code == 200
        data = response.json()

        top_agents = data["data"]["top_performing_agents"]
        assert len(top_agents) <= 5

    def test_top_performing_agents_empty(self, feedback_analytics_client: TestClient):
        """Test returns empty list when no agents."""
        # Mock service to return empty list
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_top_performing_agents.return_value = []
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get("/api/feedback/analytics")

            assert response.status_code == 200
            data = response.json()

            assert data["data"]["top_performing_agents"] == []


# ============================================================================
# Test Most Corrected Agents
# ============================================================================

class TestMostCorrectedAgents:
    """Test most corrected agents data."""

    def test_most_corrected_agents_returns_list(self, feedback_analytics_client: TestClient):
        """Test returns list of agents."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        most_corrected = data["data"]["most_corrected_agents"]
        assert isinstance(most_corrected, list)

    def test_most_corrected_agents_sorted(self, feedback_analytics_client: TestClient):
        """Test agents are sorted by correction count."""
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        most_corrected = data["data"]["most_corrected_agents"]
        # Verify sorting (highest correction rate first)
        if len(most_corrected) > 1:
            assert most_corrected[0]["correction_rate"] >= most_corrected[1]["correction_rate"]

    def test_most_corrected_agents_limit(self, feedback_analytics_client: TestClient):
        """Test respects limit parameter."""
        response = feedback_analytics_client.get("/api/feedback/analytics?limit=5")

        assert response.status_code == 200
        data = response.json()

        most_corrected = data["data"]["most_corrected_agents"]
        assert len(most_corrected) <= 5

    def test_most_corrected_agents_empty(self, feedback_analytics_client: TestClient):
        """Test returns empty list when no corrections."""
        # Mock service to return empty list
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_most_corrected_agents.return_value = []
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get("/api/feedback/analytics")

            assert response.status_code == 200
            data = response.json()

            assert data["data"]["most_corrected_agents"] == []


# ============================================================================
# Test Error Handling
# ============================================================================

class TestErrorHandling:
    """Test error handling in feedback analytics routes."""

    def test_feedback_dashboard_service_exception(self, feedback_analytics_client: TestClient):
        """Test handles FeedbackAnalytics exceptions."""
        # Mock service to raise exception
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_feedback_statistics.side_effect = Exception("Service unavailable")
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get("/api/feedback/analytics")

            # Should handle error gracefully
            assert response.status_code in [500, 503]

    def test_agent_dashboard_service_exception(self, feedback_analytics_client: TestClient):
        """Test handles AgentLearningEnhanced exceptions."""
        agent_id = "agent-sales-001"

        # Mock service to raise exception
        with patch('api.feedback_analytics.AgentLearningEnhanced') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_learning_signals.side_effect = Exception("Learning service unavailable")
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get(f"/api/feedback/agent/{agent_id}/analytics")

            # Should handle error gracefully
            assert response.status_code in [500, 503]

    def test_trends_service_exception(self, feedback_analytics_client: TestClient):
        """Test handles FeedbackAnalytics exceptions in trends."""
        # Mock service to raise exception
        with patch('api.feedback_analytics.FeedbackAnalytics') as mock_service_class:
            mock_service = MagicMock()
            mock_service.get_feedback_trends.side_effect = Exception("Database error")
            mock_service_class.return_value = mock_service

            response = feedback_analytics_client.get("/api/feedback/trends")

            # Should handle error gracefully
            assert response.status_code in [500, 503]

    def test_database_session_handling(self, feedback_analytics_client: TestClient):
        """Test handles get_db dependency correctly."""
        # Test should pass without database session errors
        response = feedback_analytics_client.get("/api/feedback/analytics")

        assert response.status_code == 200
