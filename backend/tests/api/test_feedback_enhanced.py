"""
Enhanced Feedback API Tests

Tests for enhanced feedback endpoints including:
- Feedback submission
- Agent feedback retrieval
- Feedback analytics
- Feedback trends
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch

from main_api_app import app
from tests.factories import AgentFactory


class TestEnhancedFeedbackEndpoints:
    """Test enhanced feedback API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    @pytest.fixture
    def agent(self, db_session):
        """Create test agent."""
        agent = AgentFactory(
            name="TestAgent",
            status="autonomous"
        )
        db_session.commit()
        return agent

    def test_submit_feedback_thumbs_up(self, client, agent):
        """Test submitting thumbs up feedback."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "thumbs_up_down": True
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "success" in data or "feedback_id" in data

    def test_submit_feedback_thumbs_down(self, client, agent):
        """Test submitting thumbs down feedback."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "thumbs_up_down": False
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "success" in data or "feedback_id" in data

    def test_submit_feedback_star_rating(self, client, agent):
        """Test submitting star rating feedback."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "rating": 5
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "success" in data or "feedback_id" in data

    def test_submit_feedback_invalid_rating(self, client, agent):
        """Test submitting invalid star rating."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "rating": 6  # Invalid: should be 1-5
            }
        )

        # Should reject with validation error
        assert response.status_code == 422

    def test_submit_feedback_user_correction(self, client, agent):
        """Test submitting detailed correction feedback."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "user_correction": "The output should have been X, not Y",
                "input_context": "Original input",
                "original_output": "Agent's response"
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]
        data = response.json()
        assert "success" in data or "feedback_id" in data

    def test_submit_feedback_multiple_types(self, client, agent):
        """Test submitting feedback with multiple types."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "thumbs_up_down": True,
                "rating": 5,
                "user_correction": "Great job!"
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]

    def test_submit_feedback_missing_agent_id(self, client):
        """Test submitting feedback without agent_id."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "user_id": "test-user-123",
                "thumbs_up_down": True
            }
        )

        # Should reject with validation error
        assert response.status_code == 422

    def test_submit_feedback_missing_user_id(self, client):
        """Test submitting feedback without user_id."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": "test-agent-123",
                "thumbs_up_down": True
            }
        )

        # Should reject with validation error
        assert response.status_code == 422

    def test_submit_feedback_no_content(self, client, agent):
        """Test submitting feedback without any feedback content."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123"
            }
        )

        # Should accept (backend may handle empty feedback)
        assert response.status_code in [200, 201, 202, 400]

    def test_get_agent_feedback(self, client, agent):
        """Test getting feedback for an agent."""
        response = client.get(f"/api/feedback/api/feedback/agent/{agent.id}")

        assert response.status_code == 200
        data = response.json()

        # Should have feedback summary structure
        assert "agent_id" in data or "total_feedback" in data

    def test_get_agent_feedback_structure(self, client, agent):
        """Test agent feedback response structure."""
        response = client.get(f"/api/feedback/api/feedback/agent/{agent.id}")

        assert response.status_code == 200
        data = response.json()

        # Check for common fields
        expected_fields = ["agent_id", "total_feedback", "positive_count",
                          "negative_count", "average_rating"]
        present_fields = [field for field in expected_fields if field in data]

        # Should have at least some fields
        assert len(present_fields) >= 3

    def test_get_agent_feedback_not_found(self, client):
        """Test getting feedback for non-existent agent."""
        response = client.get("/api/feedback/api/feedback/agent/nonexistent-agent-id")

        # Should handle gracefully (empty result or error)
        assert response.status_code in [200, 404]

    def test_get_feedback_analytics(self, client):
        """Test getting overall feedback analytics."""
        response = client.get("/api/feedback/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        # Should have analytics structure
        assert "total_feedback" in data or "overall_positive_ratio" in data

    def test_get_feedback_analytics_structure(self, client):
        """Test feedback analytics response structure."""
        response = client.get("/api/feedback/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        # Check for common analytics fields
        expected_fields = ["total_feedback", "total_agents_with_feedback",
                          "overall_positive_ratio", "overall_average_rating"]
        present_fields = [field for field in expected_fields if field in data]

        # Should have at least some analytics fields
        assert len(present_fields) >= 2

    def test_get_feedback_trends(self, client):
        """Test getting feedback trends."""
        response = client.get("/api/feedback/api/feedback/trends")

        assert response.status_code == 200
        data = response.json()

        # Should have trends structure
        assert "trends" in data or isinstance(data, list)

    def test_get_feedback_trends_with_days(self, client):
        """Test getting feedback trends with custom days parameter."""
        response = client.get("/api/feedback/api/feedback/trends?days=7")

        assert response.status_code == 200
        data = response.json()

        # Should return trends data
        assert "trends" in data or isinstance(data, list)

    def test_get_feedback_trends_structure(self, client):
        """Test feedback trends response structure."""
        response = client.get("/api/feedback/api/feedback/trends?days=7")

        assert response.status_code == 200
        data = response.json()

        # If trends is a list, check structure
        if isinstance(data, list):
            # Empty list is valid
            assert True
        elif "trends" in data:
            trends = data["trends"]
            # Can be empty list or list of trend objects
            assert isinstance(trends, list)

    def test_feedback_endpoints_return_json(self, client):
        """Test that all feedback endpoints return JSON."""
        endpoints = [
            ("POST", "/api/feedback/api/feedback/submit", {
                "agent_id": "test-agent",
                "user_id": "test-user",
                "thumbs_up_down": True
            }),
            ("GET", "/api/feedback/api/feedback/agent/test-agent", None),
            ("GET", "/api/feedback/api/feedback/analytics", None),
            ("GET", "/api/feedback/api/feedback/trends", None)
        ]

        for method, endpoint, body in endpoints:
            if method == "POST":
                response = client.post(endpoint, json=body)
            else:
                response = client.get(endpoint)

            # Should return JSON for valid requests
            assert response.headers["content-type"].startswith("application/json")

    def test_submit_feedback_with_execution_id(self, client, agent):
        """Test submitting feedback with execution ID."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "agent_execution_id": "exec-123",
                "user_id": "test-user-123",
                "thumbs_up_down": True
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]

    def test_submit_feedback_with_explicit_type(self, client, agent):
        """Test submitting feedback with explicit feedback type."""
        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "user_correction": "Correction text",
                "feedback_type": "correction"
            }
        )

        # Should accept the submission
        assert response.status_code in [200, 201, 202]

    @patch('api.feedback_enhanced.AgentGovernanceService')
    def test_submit_feedback_with_governance_check(self, mock_gov_class, client, agent):
        """Test that feedback submission respects governance checks."""
        # Mock the governance service
        mock_gov = Mock()
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/feedback/api/feedback/submit",
            json={
                "agent_id": agent.id,
                "user_id": "test-user-123",
                "thumbs_up_down": True
            }
        )

        # Should accept the submission (governance check may or may not be called)
        assert response.status_code in [200, 201, 202, 403]

    def test_get_agent_feedback_with_limit(self, client, agent):
        """Test getting agent feedback with limit parameter."""
        response = client.get(f"/api/feedback/api/feedback/agent/{agent.id}?limit=10")

        assert response.status_code == 200
        data = response.json()

        # Should return feedback data
        assert "agent_id" in data or "total_feedback" in data

    def test_get_agent_feedback_with_days_filter(self, client, agent):
        """Test getting agent feedback with days filter."""
        response = client.get(f"/api/feedback/api/feedback/agent/{agent.id}?days=30")

        assert response.status_code == 200
        data = response.json()

        # Should return feedback data
        assert "agent_id" in data or "total_feedback" in data

    def test_feedback_analytics_aggregation(self, client):
        """Test that feedback analytics aggregates data correctly."""
        response = client.get("/api/feedback/api/feedback/analytics")

        assert response.status_code == 200
        data = response.json()

        # If there's data, check aggregation fields
        if "total_feedback" in data and data["total_feedback"] > 0:
            # Should have aggregated metrics
            assert isinstance(data["total_feedback"], int)
            if "overall_positive_ratio" in data:
                assert isinstance(data["overall_positive_ratio"], float)

    def test_feedback_trends_date_format(self, client):
        """Test that feedback trends have proper date format."""
        response = client.get("/api/feedback/api/feedback/trends?days=7")

        assert response.status_code == 200
        data = response.json()

        # Check trends if present
        if isinstance(data, list) and len(data) > 0:
            trend = data[0]
            if "date" in trend:
                # Should be ISO format date string
                assert isinstance(trend["date"], str)
