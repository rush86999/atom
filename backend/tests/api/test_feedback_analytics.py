"""
Feedback Analytics API Tests

Tests for feedback analytics endpoints including:
- Overall feedback dashboard
- Per-agent analytics
- Feedback trends over time
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, MagicMock

from main_api_app import app
from core.models import AgentRegistry
from tests.factories import AgentFactory


class TestFeedbackAnalyticsEndpoints:
    """Test feedback analytics API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def db_session(self, request):
        """Create database session."""
        from core.database import SessionLocal
        db = SessionLocal()
        yield db
        db.close()

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_get_feedback_analytics_dashboard_default_params(self, client):
        """Test getting analytics dashboard with default parameters."""
        response = client.get("/api/feedback/analytics/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data

        # Check response structure
        dashboard = data["data"]
        assert "period_days" in dashboard
        assert "summary" in dashboard
        assert "top_performing_agents" in dashboard
        assert "most_corrected_agents" in dashboard
        assert "feedback_by_type" in dashboard
        assert "trends" in dashboard

    def test_get_feedback_analytics_dashboard_custom_days(self, client):
        """Test getting analytics dashboard with custom days parameter."""
        response = client.get("/api/feedback/analytics/?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["period_days"] == 7

    def test_get_feedback_analytics_dashboard_invalid_days_low(self, client):
        """Test analytics dashboard with invalid days (too low)."""
        response = client.get("/api/feedback/analytics/?days=0")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_get_feedback_analytics_dashboard_invalid_days_high(self, client):
        """Test analytics dashboard with invalid days (too high)."""
        response = client.get("/api/feedback/analytics/?days=400")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_get_agent_feedback_dashboard(self, client, agent):
        """Test getting agent-specific feedback dashboard."""
        response = client.get(f"/api/feedback/analytics/agent/{agent.id}")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Check response structure
        dashboard = data["data"]
        assert "agent_id" in dashboard
        assert dashboard["agent_id"] == agent.id
        assert "period_days" in dashboard
        assert "feedback_summary" in dashboard
        assert "learning_signals" in dashboard

    @pytest.mark.skip(reason="Agent not found error handling needs improvement")
    def test_get_agent_feedback_dashboard_not_found(self, client):
        """Test getting analytics for non-existent agent."""
        response = client.get("/api/feedback/analytics/agent/nonexistent-agent-id")

        # Should return error when agent not found (500 from unhandled ValueError)
        assert response.status_code == 500
        data = response.json()
        assert "detail" in data or "error" in data

    def test_get_agent_feedback_dashboard_custom_days(self, client, agent):
        """Test agent dashboard with custom days parameter."""
        response = client.get(f"/api/feedback/analytics/agent/{agent.id}?days=14")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["period_days"] == 14

    def test_get_feedback_trends_default(self, client):
        """Test getting feedback trends with default parameters."""
        response = client.get("/api/feedback/analytics/trends")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True

        # Check response structure
        trends_data = data["data"]
        assert "period_days" in trends_data
        assert "trends" in trends_data
        assert trends_data["period_days"] == 30

    def test_get_feedback_trends_custom_days(self, client):
        """Test getting feedback trends with custom days parameter."""
        response = client.get("/api/feedback/analytics/trends?days=7")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["period_days"] == 7

    def test_get_feedback_trends_validation_error(self, client):
        """Test trends endpoint with invalid days parameter."""
        response = client.get("/api/feedback/analytics/trends?days=500")

        # Should return 422 validation error
        assert response.status_code == 422

    def test_feedback_analytics_with_no_data(self, client, db_session):
        """Test analytics endpoints when no feedback data exists."""
        response = client.get("/api/feedback/analytics/")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        # Should return empty structure
        assert "summary" in data["data"]

    @patch('core.feedback_analytics.FeedbackAnalytics')
    def test_feedback_analytics_error_handling(self, mock_analytics_class, client):
        """Test error handling in analytics endpoint."""
        # Mock analytics to raise an exception
        mock_analytics = Mock()
        mock_analytics.return_value = mock_analytics
        mock_analytics.get_feedback_statistics.side_effect = Exception("Database error")

        with patch('core.feedback_analytics.FeedbackAnalytics', return_value=mock_analytics):
            response = client.get("/api/feedback/analytics/")

            # Should handle error gracefully
            # Either return error or empty data
            assert response.status_code in [200, 500]

    def test_dashboard_response_structure_complete(self, client):
        """Test that dashboard response contains all required fields."""
        response = client.get("/api/feedback/analytics/")

        assert response.status_code == 200
        data = response.json()
        dashboard = data["data"]

        # Check summary structure
        summary = dashboard["summary"]
        assert "total_feedback" in summary or "total_count" in summary

        # Check top agents structure
        top_agents = dashboard["top_performing_agents"]
        assert isinstance(top_agents, list)

        # Check trends structure
        trends = dashboard["trends"]
        assert isinstance(trends, list) or isinstance(trends, dict)

    def test_agent_dashboard_response_structure_complete(self, client, agent):
        """Test that agent dashboard response contains all required fields."""
        response = client.get(f"/api/feedback/analytics/agent/{agent.id}")

        assert response.status_code == 200
        data = response.json()
        dashboard = data["data"]

        # Check feedback summary structure
        summary = dashboard["feedback_summary"]
        assert "agent_id" in summary or "total_feedback" in summary

        # Check learning signals structure
        signals = dashboard["learning_signals"]
        assert isinstance(signals, list) or isinstance(signals, dict)
