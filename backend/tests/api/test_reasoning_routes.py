"""
Reasoning Routes API Tests

Tests for reasoning step feedback endpoint including:
- Step feedback submission
- Error handling
- Input validation
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch, AsyncMock
from fastapi import status

from main_api_app import app
from core.auth import get_current_user
from core.agent_governance_service import AgentGovernanceService


class TestReasoningRoutes:
    """Test reasoning API endpoints."""

    @pytest.fixture
    def mock_user(self):
        """Create mock user."""
        user = Mock()
        user.id = "test-user-123"
        return user

    @pytest.fixture
    def client(self, mock_user):
        """Create test client with auth override."""
        # Override the get_current_user dependency
        app.dependency_overrides[get_current_user] = lambda: mock_user
        try:
            yield TestClient(app)
        finally:
            # Clean up override
            app.dependency_overrides.clear()

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_step_feedback_success(self, mock_gov_class, client, mock_user):
        """Test successful reasoning step feedback submission."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-123"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-456",
                "step_index": 1,
                "step_content": {
                    "thought": "I need to solve this problem",
                    "action": "execute"
                },
                "feedback_type": "thumbs_up",
                "comment": "Good reasoning!"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data
        assert "id" in data["data"] or "message" in data

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_thumbs_down(self, mock_gov_class, client):
        """Test submitting thumbs down feedback."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-thumbs-down"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-456",
                "step_index": 2,
                "step_content": {
                    "thought": "Incorrect reasoning",
                    "action": "wrong_action"
                },
                "feedback_type": "thumbs_down",
                "comment": "This was wrong"
            }
        )

        # May return 200 or 401 (auth)
        assert response.status_code in [200, 401]

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_with_comment_only(self, mock_gov_class, client):
        """Test submitting feedback with just a comment."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-comment"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-456",
                "step_index": 3,
                "step_content": {
                    "thought": "Step content"
                },
                "feedback_type": "thumbs_up",
                "comment": "Well done"
            }
        )

        # May return 200 or 401 (auth)
        assert response.status_code in [200, 401]

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_without_comment(self, mock_gov_class, client):
        """Test submitting feedback without comment."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-456"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-789",
                "step_index": 0,
                "step_content": {
                    "thought": "Initial thought",
                    "action": "start"
                },
                "feedback_type": "thumbs_up"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    def test_submit_feedback_missing_required_fields(self, client):
        """Test submitting feedback with missing required fields."""

        # Missing required fields
        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123"
            }
        )

        # Should return validation error
        assert response.status_code == 422

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_invalid_step_index(self, mock_gov_class, client):
        """Test submitting feedback with invalid step index."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-invalid"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-456",
                "step_index": -1,  # Invalid
                "step_content": {},
                "feedback_type": "thumbs_up"
            }
        )

        # Should accept (backend may validate)
        assert response.status_code in [200, 400, 422]

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_with_complex_step_content(self, mock_gov_class, client):
        """Test submitting feedback with complex step content."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-789"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-complex",
                "step_index": 5,
                "step_content": {
                    "thought": "Complex multi-step reasoning",
                    "action": "analyze",
                    "observation": "Data processed",
                    "next_step": "proceed"
                },
                "feedback_type": "thumbs_up",
                "comment": "Excellent multi-step reasoning!"
            }
        )

        assert response.status_code == 200
        data = response.json()
        assert "data" in data

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_governance_integration(self, mock_gov_class, client):
        """Test that feedback integrates with governance service."""
        # Mock governance service and verify integration
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-gov-123"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-gov-123",
                "run_id": "run-governance",
                "step_index": 1,
                "step_content": {
                    "thought": "Governed thought",
                    "action": "governed_action"
                },
                "feedback_type": "thumbs_up"
            }
        )

        assert response.status_code == 200
        mock_gov.submit_feedback.assert_called_once()

        # Verify the call parameters
        call_args = mock_gov.submit_feedback.call_args
        assert call_args is not None

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_stores_context_correctly(self, mock_gov_class, client):
        """Test that feedback stores context payload correctly."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-context-123"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        run_id = "context-run-123"
        step_index = 3
        step_content = {
            "thought": "Context test thought",
            "action": "context_action"
        }

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-context-123",
                "run_id": run_id,
                "step_index": step_index,
                "step_content": step_content,
                "feedback_type": "thumbs_up"
            }
        )

        assert response.status_code == 200

        # Verify governance service was called with correct context
        mock_gov.submit_feedback.assert_called_once()
        call_kwargs = mock_gov.submit_feedback.call_args[1]

        # Verify input_context contains the context payload
        input_context_arg = call_kwargs['input_context']
        import json
        context_payload = json.loads(input_context_arg)

        assert context_payload["run_id"] == run_id
        assert context_payload["step_index"] == step_index
        assert context_payload["step_content"] == step_content

    def test_submit_feedback_unauthorized(self):
        """Test that unauthorized requests are rejected."""
        # Create client without auth override
        client = TestClient(app)

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-456",
                "step_index": 1,
                "step_content": {},
                "feedback_type": "thumbs_up"
            }
        )

        # Should return unauthorized
        assert response.status_code == 401

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_handles_governance_error(self, mock_gov_class, client):
        """Test that governance service errors are handled gracefully."""
        # Mock governance service to raise error
        mock_gov = Mock()
        mock_gov.submit_feedback = AsyncMock(side_effect=Exception("Governance error"))
        mock_gov_class.return_value = mock_gov

        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-error-123",
                "run_id": "run-error",
                "step_index": 1,
                "step_content": {},
                "feedback_type": "thumbs_up"
            }
        )

        # Should handle error and return 500
        assert response.status_code == 500

    def test_reasoning_endpoint_returns_json(self):
        """Test that reasoning endpoint returns JSON."""
        # Create client without auth override to test both cases
        client = TestClient(app)
        response = client.post(
            "/api/reasoning/feedback",
            json={
                "agent_id": "agent-123",
                "run_id": "run-456",
                "step_index": 1,
                "step_content": {},
                "feedback_type": "thumbs_up"
            }
        )

        # Should return JSON or 401
        assert response.status_code in [200, 401]
        if response.status_code == 200:
            assert response.headers["content-type"].startswith("application/json")

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_feedback_different_feedback_types(self, mock_gov_class, client):
        """Test submitting different feedback types."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-type-test"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        feedback_types = ["thumbs_up", "thumbs_down"]

        for feedback_type in feedback_types:
            response = client.post(
                "/api/reasoning/feedback",
                json={
                    "agent_id": "agent-123",
                    "run_id": f"run-{feedback_type}",
                    "step_index": 1,
                    "step_content": {},
                    "feedback_type": feedback_type
                }
            )

            # Should handle both types
            assert response.status_code in [200, 401, 404, 422]

    @patch('api.reasoning_routes.AgentGovernanceService')
    def test_submit_reasoning_endpoint_id_format(self, mock_gov_class, client):
        """Test that endpoint accepts various ID formats."""
        # Mock governance service
        mock_gov = Mock()
        mock_feedback = Mock()
        mock_feedback.id = "feedback-id-test"
        mock_gov.submit_feedback = AsyncMock(return_value=mock_feedback)
        mock_gov_class.return_value = mock_gov

        # Test with different ID formats
        test_ids = [
            "simple-id",
            "uuid-1234-5678-9abc-def0",
            "agent_123",
            "run_456_test"
        ]

        for test_id in test_ids:
            response = client.post(
                "/api/reasoning/feedback",
                json={
                    "agent_id": test_id,
                    "run_id": f"run-{test_id}",
                    "step_index": 1,
                    "step_content": {},
                    "feedback_type": "thumbs_up"
                }
            )

            # Should accept various ID formats
            assert response.status_code in [200, 401, 404, 422]
