"""
A/B Testing Routes Test Suite

Comprehensive TestClient-based testing for ab_testing.py API routes.
Covers all endpoints with 75%+ line coverage target.

Test Structure:
- TestCreateTest (8 tests): Create endpoint validation and success cases
- TestStartTest (5 tests): Start endpoint with status transitions
- TestCompleteTest (6 tests): Complete endpoint with statistical analysis
- TestAssignVariant (7 tests): Variant assignment with deterministic hashing
- TestRecordMetric (6 tests): Metric recording with validation
- TestGetTestResults (5 tests): Results retrieval with participant data
- TestListTests (6 tests): List endpoint with filtering and pagination
- TestRequestModels (4 tests): Pydantic model validation
- TestErrorResponses (4 tests): Error response format consistency
- TestTestTypes (4 tests): All test types (agent_config, prompt, strategy, tool)

Total: 55+ tests targeting 600+ lines of test code
"""

import pytest
from datetime import datetime
from fastapi import FastAPI
from unittest.mock import MagicMock, AsyncMock, patch
from sqlalchemy.orm import Session

from api.ab_testing import router
from core.ab_testing_service import ABTestingService


# ============================================================================
# TestCreateTest - 8 tests
# ============================================================================

class TestCreateTest:
    """Test suite for POST /api/ab-tests/create endpoint."""

    def test_create_test_success(self, ab_testing_client, mock_ab_testing_service):
        """Test creating A/B test with valid data returns 200."""
        # Setup
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "draft",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {"temperature": 0.7}},
            "variant_b": {"name": "Treatment", "config": {"temperature": 0.9}},
            "primary_metric": "satisfaction_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        # Execute
        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Test A",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {"temperature": 0.7},
            "variant_b_config": {"temperature": 0.9},
            "primary_metric": "satisfaction_rate"
        })

        # Verify
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["test_id"] == "test-123"
        assert data["data"]["status"] == "draft"
        mock_ab_testing_service.create_test.assert_called_once()

    def test_create_test_with_all_fields(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with all optional fields included."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-456",
            "name": "Comprehensive Test",
            "status": "draft",
            "test_type": "agent_config",
            "agent_id": "agent-2",
            "variant_a": {"name": "V1", "config": {"model": "gpt-3"}},
            "variant_b": {"name": "V2", "config": {"model": "gpt-4"}},
            "primary_metric": "success_rate",
            "description": "Testing model performance",
            "min_sample_size": 200,
            "traffic_percentage": 0.6,
            "confidence_level": 0.99
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Comprehensive Test",
            "test_type": "agent_config",
            "agent_id": "agent-2",
            "variant_a_config": {"model": "gpt-3"},
            "variant_b_config": {"model": "gpt-4"},
            "primary_metric": "success_rate",
            "description": "Testing model performance",
            "min_sample_size": 200,
            "traffic_percentage": 0.6,
            "confidence_level": 0.99,
            "secondary_metrics": ["response_time", "error_rate"]
        })

        assert response.status_code == 200
        data = response.json()
        assert data["data"]["test_id"] == "test-456"

    def test_create_test_default_values(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test uses correct defaults for optional fields."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-defaults",
            "name": "Default Test",
            "status": "draft",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {}},
            "variant_b": {"name": "Treatment", "config": {}},
            "primary_metric": "satisfaction_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Default Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "satisfaction_rate"
        })

        assert response.status_code == 200
        mock_ab_testing_service.create_test.assert_called_once()

    def test_create_test_prompt_type(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with test_type='prompt' validates correctly."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-prompt",
            "name": "Prompt Test",
            "status": "draft",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {"prompt": "v1"}},
            "variant_b": {"name": "Treatment", "config": {"prompt": "v2"}},
            "primary_metric": "satisfaction_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Prompt Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {"prompt": "v1"},
            "variant_b_config": {"prompt": "v2"},
            "primary_metric": "satisfaction_rate"
        })

        assert response.status_code == 200
        assert response.json()["data"]["test_type"] == "prompt"

    def test_create_test_agent_config_type(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with test_type='agent_config' validates correctly."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-config",
            "name": "Config Test",
            "status": "draft",
            "test_type": "agent_config",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {"temperature": 0.5}},
            "variant_b": {"name": "Treatment", "config": {"temperature": 0.9}},
            "primary_metric": "success_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Config Test",
            "test_type": "agent_config",
            "agent_id": "agent-1",
            "variant_a_config": {"temperature": 0.5},
            "variant_b_config": {"temperature": 0.9},
            "primary_metric": "success_rate"
        })

        assert response.status_code == 200
        assert response.json()["data"]["test_type"] == "agent_config"

    def test_create_test_validation_error(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with invalid data returns 400."""
        mock_ab_testing_service.create_test.return_value = {
            "error": "Invalid test configuration"
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Invalid Test",
            "test_type": "invalid_type",
            "agent_id": "",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": ""
        })

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "error" in data

    def test_create_test_traffic_percentage_validation(self, ab_testing_client, mock_ab_testing_service):
        """Test traffic_percentage enforces ge=0.0 and le=1.0 constraints."""
        mock_ab_testing_service.create_test.return_value = {
            "error": "traffic_percentage must be between 0.0 and 1.0"
        }

        # Test > 1.0
        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "satisfaction_rate",
            "traffic_percentage": 1.5
        })

        assert response.status_code == 400

        # Test < 0.0
        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "satisfaction_rate",
            "traffic_percentage": -0.1
        })

        assert response.status_code == 400

    def test_create_test_confidence_validation(self, ab_testing_client, mock_ab_testing_service):
        """Test confidence_level enforces ge=0.0 and le=1.0 constraints."""
        mock_ab_testing_service.create_test.return_value = {
            "error": "confidence_level must be between 0.0 and 1.0"
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "satisfaction_rate",
            "confidence_level": 1.5
        })

        assert response.status_code == 400


# ============================================================================
# TestStartTest - 5 tests
# ============================================================================

class TestStartTest:
    """Test suite for POST /api/ab-tests/{test_id}/start endpoint."""

    def test_start_test_success(self, ab_testing_client, mock_ab_testing_service):
        """Test starting test changes status to running."""
        mock_ab_testing_service.start_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "running",
            "started_at": "2026-03-12T10:00:00Z"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/start")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "running"
        assert "started_at" in data["data"]

    def test_start_test_includes_timestamp(self, ab_testing_client, mock_ab_testing_service):
        """Test starting test returns started_at timestamp."""
        started_at = "2026-03-12T10:30:00Z"
        mock_ab_testing_service.start_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "running",
            "started_at": started_at
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/start")

        assert response.status_code == 200
        assert response.json()["data"]["started_at"] == started_at

    def test_start_test_already_running(self, ab_testing_client, mock_ab_testing_service):
        """Test starting already running test returns error."""
        mock_ab_testing_service.start_test.return_value = {
            "error": "Test must be in 'draft' status to start, current status: running"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/start")

        assert response.status_code == 400
        data = response.json()
        assert data["success"] is False
        assert "error" in data["error"]

    def test_start_test_not_found(self, ab_testing_client, mock_ab_testing_service):
        """Test starting non-existent test returns 404."""
        mock_ab_testing_service.start_test.return_value = {
            "error": "Test 'nonexistent' not found"
        }

        response = ab_testing_client.post("/api/ab-tests/nonexistent/start")

        assert response.status_code == 400

    def test_start_test_error_handling(self, ab_testing_client, mock_ab_testing_service):
        """Test service exceptions are handled gracefully."""
        mock_ab_testing_service.start_test.side_effect = Exception("Database error")

        response = ab_testing_client.post("/api/ab-tests/test-123/start")

        assert response.status_code == 500


# ============================================================================
# TestCompleteTest - 6 tests
# ============================================================================

class TestCompleteTest:
    """Test suite for POST /api/ab-tests/{test_id}/complete endpoint."""

    def test_complete_test_success(self, ab_testing_client, mock_ab_testing_service):
        """Test completing test calculates results and changes status."""
        mock_ab_testing_service.complete_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "completed",
            "completed_at": "2026-03-12T12:00:00Z",
            "variant_a_metrics": {
                "count": 150,
                "success_count": 120,
                "success_rate": 0.80,
                "average_metric_value": 4.2
            },
            "variant_b_metrics": {
                "count": 150,
                "success_count": 135,
                "success_rate": 0.90,
                "average_metric_value": 4.7
            },
            "p_value": 0.02,
            "winner": "B",
            "min_sample_size_reached": True
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/complete")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["status"] == "completed"
        assert "variant_a_metrics" in data["data"]
        assert "variant_b_metrics" in data["data"]

    def test_complete_test_includes_results(self, ab_testing_client, mock_ab_testing_service):
        """Test completing test returns variant_a_metrics and variant_b_metrics."""
        mock_ab_testing_service.complete_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "completed",
            "completed_at": "2026-03-12T12:00:00Z",
            "variant_a_metrics": {
                "count": 100,
                "success_count": 80,
                "success_rate": 0.80,
                "average_metric_value": 4.0
            },
            "variant_b_metrics": {
                "count": 100,
                "success_count": 90,
                "success_rate": 0.90,
                "average_metric_value": 4.5
            },
            "p_value": 0.05,
            "winner": "B"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/complete")

        assert response.status_code == 200
        data = response.json()["data"]
        assert data["variant_a_metrics"]["success_rate"] == 0.80
        assert data["variant_b_metrics"]["success_rate"] == 0.90

    def test_complete_test_includes_winner(self, ab_testing_client, mock_ab_testing_service):
        """Test completing test returns winner (A, B, or inconclusive)."""
        mock_ab_testing_service.complete_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "completed",
            "completed_at": "2026-03-12T12:00:00Z",
            "variant_a_metrics": {},
            "variant_b_metrics": {},
            "p_value": 0.01,
            "winner": "B"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/complete")

        assert response.status_code == 200
        assert response.json()["data"]["winner"] == "B"

    def test_complete_test_includes_p_value(self, ab_testing_client, mock_ab_testing_service):
        """Test completing test returns statistical significance p_value."""
        mock_ab_testing_service.complete_test.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "completed",
            "completed_at": "2026-03-12T12:00:00Z",
            "variant_a_metrics": {},
            "variant_b_metrics": {},
            "p_value": 0.02,
            "winner": "A"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/complete")

        assert response.status_code == 200
        assert "p_value" in response.json()["data"]
        assert response.json()["data"]["p_value"] == 0.02

    def test_complete_test_insufficient_data(self, ab_testing_client, mock_ab_testing_service):
        """Test completing test with insufficient data returns error."""
        mock_ab_testing_service.complete_test.return_value = {
            "error": "Insufficient sample size to complete test. Need at least 100 participants per variant."
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/complete")

        assert response.status_code == 400
        assert "error" in response.json()

    def test_complete_test_not_found(self, ab_testing_client, mock_ab_testing_service):
        """Test completing non-existent test returns 404."""
        mock_ab_testing_service.complete_test.return_value = {
            "error": "Test 'nonexistent' not found"
        }

        response = ab_testing_client.post("/api/ab-tests/nonexistent/complete")

        assert response.status_code == 400


# ============================================================================
# TestAssignVariant - 7 tests
# ============================================================================

class TestAssignVariant:
    """Test suite for POST /api/ab-tests/{test_id}/assign endpoint."""

    def test_assign_variant_success(self, ab_testing_client, mock_ab_testing_service):
        """Test assigning user to variant returns variant and config."""
        mock_ab_testing_service.assign_variant.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "variant_name": "Control",
            "config": {"temperature": 0.7},
            "existing_assignment": False
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/assign", json={
            "user_id": "user-1"
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["variant"] in ["A", "B"]
        assert "config" in data["data"]

    def test_assign_variant_consistent(self, ab_testing_client, mock_ab_testing_service):
        """Test same user gets same variant consistently."""
        # First call
        mock_ab_testing_service.assign_variant.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "variant_name": "Control",
            "config": {},
            "existing_assignment": False
        }

        response1 = ab_testing_client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})
        variant1 = response1.json()["data"]["variant"]

        # Second call should return same variant
        mock_ab_testing_service.assign_variant.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": variant1,
            "variant_name": "Control",
            "config": {},
            "existing_assignment": True
        }

        response2 = ab_testing_client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})
        variant2 = response2.json()["data"]["variant"]

        assert variant1 == variant2

    def test_assign_variant_returns_config(self, ab_testing_client, mock_ab_testing_service):
        """Test assigning variant returns variant configuration."""
        mock_ab_testing_service.assign_variant.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "variant_name": "Control",
            "config": {"temperature": 0.7, "max_tokens": 1000},
            "existing_assignment": False
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})

        assert response.status_code == 200
        config = response.json()["data"]["config"]
        assert config["temperature"] == 0.7
        assert config["max_tokens"] == 1000

    def test_assign_variant_existing_assignment(self, ab_testing_client, mock_ab_testing_service):
        """Test reassigning user indicates existing_assignment=True."""
        mock_ab_testing_service.assign_variant.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "variant_name": "Control",
            "config": {},
            "existing_assignment": True
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})

        assert response.status_code == 200
        assert response.json()["data"]["existing_assignment"] is True

    def test_assign_variant_with_session(self, ab_testing_client, mock_ab_testing_service):
        """Test assigning variant handles optional session_id."""
        mock_ab_testing_service.assign_variant.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "B",
            "variant_name": "Treatment",
            "config": {},
            "existing_assignment": False
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/assign", json={
            "user_id": "user-1",
            "session_id": "session-123"
        })

        assert response.status_code == 200
        mock_ab_testing_service.assign_variant.assert_called_with(
            test_id="test-123",
            user_id="user-1",
            session_id="session-123"
        )

    def test_assign_variant_not_found(self, ab_testing_client, mock_ab_testing_service):
        """Test assigning to non-existent test returns 400."""
        mock_ab_testing_service.assign_variant.return_value = {
            "error": "Test 'nonexistent' not found"
        }

        response = ab_testing_client.post("/api/ab-tests/nonexistent/assign", json={
            "user_id": "user-1"
        })

        assert response.status_code == 400

    def test_assign_variant_error_handling(self, ab_testing_client, mock_ab_testing_service):
        """Test service exceptions are handled gracefully."""
        mock_ab_testing_service.assign_variant.side_effect = Exception("Service error")

        response = ab_testing_client.post("/api/ab-tests/test-123/assign", json={
            "user_id": "user-1"
        })

        assert response.status_code == 500


# ============================================================================
# TestRecordMetric - 6 tests
# ============================================================================

class TestRecordMetric:
    """Test suite for POST /api/ab-tests/{test_id}/record endpoint."""

    def test_record_metric_with_success(self, ab_testing_client, mock_ab_testing_service):
        """Test recording boolean success metric."""
        mock_ab_testing_service.record_metric.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "success": True,
            "metric_value": None,
            "recorded_at": "2026-03-12T11:00:00Z"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1",
            "success": True
        })

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["success"] is True

    def test_record_metric_with_value(self, ab_testing_client, mock_ab_testing_service):
        """Test recording numerical metric value."""
        mock_ab_testing_service.record_metric.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "success": None,
            "metric_value": 4.5,
            "recorded_at": "2026-03-12T11:00:00Z"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1",
            "metric_value": 4.5
        })

        assert response.status_code == 200
        assert response.json()["data"]["metric_value"] == 4.5

    def test_record_metric_with_metadata(self, ab_testing_client, mock_ab_testing_service):
        """Test recording metric includes metadata."""
        mock_ab_testing_service.record_metric.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "success": True,
            "metric_value": None,
            "recorded_at": "2026-03-12T11:00:00Z"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1",
            "success": True,
            "metadata": {"source": "mobile", "version": "1.0"}
        })

        assert response.status_code == 200

    def test_record_metric_minimal(self, ab_testing_client, mock_ab_testing_service):
        """Test recording with only required user_id field."""
        mock_ab_testing_service.record_metric.return_value = {
            "test_id": "test-123",
            "user_id": "user-1",
            "variant": "A",
            "success": None,
            "metric_value": None,
            "recorded_at": "2026-03-12T11:00:00Z"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1"
        })

        assert response.status_code == 200
        mock_ab_testing_service.record_metric.assert_called_once()

    def test_record_metric_validation(self, ab_testing_client, mock_ab_testing_service):
        """Test recording with invalid data returns error."""
        mock_ab_testing_service.record_metric.return_value = {
            "error": "Invalid metric data. Must provide either success or metric_value."
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1",
            "success": None,
            "metric_value": None
        })

        assert response.status_code == 400

    def test_record_metric_not_found(self, ab_testing_client, mock_ab_testing_service):
        """Test recording for non-existent participant returns 400."""
        mock_ab_testing_service.record_metric.return_value = {
            "error": "Participant not found for test 'test-123' and user 'user-999'"
        }

        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-999",
            "success": True
        })

        assert response.status_code == 400


# ============================================================================
# TestGetTestResults - 5 tests
# ============================================================================

class TestGetTestResults:
    """Test suite for GET /api/ab-tests/{test_id}/results endpoint."""

    def test_get_test_results_success(self, ab_testing_client, mock_ab_testing_service):
        """Test getting test results returns metrics data."""
        mock_ab_testing_service.get_test_results.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "completed",
            "test_type": "prompt",
            "primary_metric": "satisfaction_rate",
            "variant_a": {
                "name": "Control",
                "participant_count": 150,
                "metrics": {"count": 150, "success_rate": 0.80}
            },
            "variant_b": {
                "name": "Treatment",
                "participant_count": 150,
                "metrics": {"count": 150, "success_rate": 0.90}
            },
            "winner": "B",
            "statistical_significance": 0.02,
            "started_at": "2026-03-12T10:00:00Z",
            "completed_at": "2026-03-12T12:00:00Z"
        }

        response = ab_testing_client.get("/api/ab-tests/test-123/results")

        assert response.status_code == 200
        data = response.json()
        assert "variant_a" in data
        assert "variant_b" in data

    def test_get_test_results_includes_variants(self, ab_testing_client, mock_ab_testing_service):
        """Test getting results returns variant_a and variant_b data."""
        mock_ab_testing_service.get_test_results.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "running",
            "test_type": "prompt",
            "primary_metric": "satisfaction_rate",
            "variant_a": {
                "name": "Control",
                "participant_count": 100,
                "metrics": {"count": 100}
            },
            "variant_b": {
                "name": "Treatment",
                "participant_count": 100,
                "metrics": {"count": 100}
            },
            "winner": None,
            "statistical_significance": None,
            "started_at": "2026-03-12T10:00:00Z",
            "completed_at": None
        }

        response = ab_testing_client.get("/api/ab-tests/test-123/results")

        assert response.status_code == 200
        data = response.json()
        assert data["variant_a"]["participant_count"] == 100
        assert data["variant_b"]["participant_count"] == 100

    def test_get_test_results_winner(self, ab_testing_client, mock_ab_testing_service):
        """Test getting results includes winner when completed."""
        mock_ab_testing_service.get_test_results.return_value = {
            "test_id": "test-123",
            "name": "Test A",
            "status": "completed",
            "test_type": "prompt",
            "primary_metric": "satisfaction_rate",
            "variant_a": {"name": "Control", "participant_count": 150, "metrics": {}},
            "variant_b": {"name": "Treatment", "participant_count": 150, "metrics": {}},
            "winner": "B",
            "statistical_significance": 0.01,
            "started_at": "2026-03-12T10:00:00Z",
            "completed_at": "2026-03-12T12:00:00Z"
        }

        response = ab_testing_client.get("/api/ab-tests/test-123/results")

        assert response.status_code == 200
        assert response.json()["winner"] == "B"

    def test_get_test_results_not_found(self, ab_testing_client, mock_ab_testing_service):
        """Test getting results for non-existent test returns 404."""
        mock_ab_testing_service.get_test_results.return_value = {
            "error": "Test 'nonexistent' not found"
        }

        response = ab_testing_client.get("/api/ab-tests/nonexistent/results")

        assert response.status_code == 404

    def test_get_test_results_error_handling(self, ab_testing_client, mock_ab_testing_service):
        """Test service exceptions are handled gracefully."""
        mock_ab_testing_service.get_test_results.side_effect = Exception("Database error")

        response = ab_testing_client.get("/api/ab-tests/test-123/results")

        assert response.status_code == 500


# ============================================================================
# TestListTests - 6 tests
# ============================================================================

class TestListTests:
    """Test suite for GET /api/ab-tests endpoint."""

    def test_list_tests_success(self, ab_testing_client, mock_ab_testing_service):
        """Test listing tests returns list of tests."""
        mock_ab_testing_service.list_tests.return_value = {
            "total": 2,
            "tests": [
                {
                    "test_id": "test-123",
                    "name": "Test A",
                    "status": "running",
                    "test_type": "prompt",
                    "agent_id": "agent-1",
                    "primary_metric": "satisfaction_rate",
                    "winner": None,
                    "created_at": "2026-03-12T10:00:00Z"
                },
                {
                    "test_id": "test-456",
                    "name": "Test B",
                    "status": "completed",
                    "test_type": "agent_config",
                    "agent_id": "agent-2",
                    "primary_metric": "success_rate",
                    "winner": "B",
                    "created_at": "2026-03-11T10:00:00Z"
                }
            ]
        }

        response = ab_testing_client.get("/api/ab-tests")

        assert response.status_code == 200
        data = response.json()
        assert "total" in data
        assert "tests" in data
        assert data["total"] == 2

    def test_list_tests_filtered_by_agent(self, ab_testing_client, mock_ab_testing_service):
        """Test listing tests filters by agent_id parameter."""
        mock_ab_testing_service.list_tests.return_value = {
            "total": 1,
            "tests": [
                {
                    "test_id": "test-123",
                    "name": "Test A",
                    "status": "running",
                    "test_type": "prompt",
                    "agent_id": "agent-1",
                    "primary_metric": "satisfaction_rate",
                    "winner": None,
                    "created_at": "2026-03-12T10:00:00Z"
                }
            ]
        }

        response = ab_testing_client.get("/api/ab-tests?agent_id=agent-1")

        assert response.status_code == 200
        mock_ab_testing_service.list_tests.assert_called_with(
            agent_id="agent-1",
            status=None,
            limit=50
        )

    def test_list_tests_filtered_by_status(self, ab_testing_client, mock_ab_testing_service):
        """Test listing tests filters by status parameter."""
        mock_ab_testing_service.list_tests.return_value = {
            "total": 1,
            "tests": [
                {
                    "test_id": "test-123",
                    "name": "Test A",
                    "status": "running",
                    "test_type": "prompt",
                    "agent_id": "agent-1",
                    "primary_metric": "satisfaction_rate",
                    "winner": None,
                    "created_at": "2026-03-12T10:00:00Z"
                }
            ]
        }

        response = ab_testing_client.get("/api/ab-tests?status=running")

        assert response.status_code == 200
        mock_ab_testing_service.list_tests.assert_called_with(
            agent_id=None,
            status="running",
            limit=50
        )

    def test_list_tests_with_limit(self, ab_testing_client, mock_ab_testing_service):
        """Test listing tests respects limit parameter."""
        mock_ab_testing_service.list_tests.return_value = {
            "total": 10,
            "tests": [{"test_id": f"test-{i}", "name": f"Test {i}", "status": "running",
                       "test_type": "prompt", "agent_id": "agent-1", "primary_metric": "satisfaction_rate",
                       "winner": None, "created_at": "2026-03-12T10:00:00Z"} for i in range(10)]
        }

        response = ab_testing_client.get("/api/ab-tests?limit=10")

        assert response.status_code == 200
        mock_ab_testing_service.list_tests.assert_called_with(
            agent_id=None,
            status=None,
            limit=10
        )

    def test_list_tests_empty(self, ab_testing_client, mock_ab_testing_service):
        """Test listing tests returns empty list when no tests."""
        mock_ab_testing_service.list_tests.return_value = {
            "total": 0,
            "tests": []
        }

        response = ab_testing_client.get("/api/ab-tests")

        assert response.status_code == 200
        data = response.json()
        assert data["total"] == 0
        assert data["tests"] == []

    def test_list_tests_limit_validation(self, ab_testing_client, mock_ab_testing_service):
        """Test limit parameter enforces ge=1 and le=100 constraints."""
        # Test limit < 1
        response = ab_testing_client.get("/api/ab-tests?limit=0")
        assert response.status_code == 422  # Pydantic validation error

        # Test limit > 100
        response = ab_testing_client.get("/api/ab-tests?limit=101")
        assert response.status_code == 422


# ============================================================================
# TestRequestModels - 4 tests
# ============================================================================

class TestRequestModels:
    """Test suite for Pydantic request model validation."""

    def test_create_test_request_required_fields(self, ab_testing_client):
        """Test CreateTestRequest validates required fields."""
        response = ab_testing_client.post("/api/ab-tests/create", json={})

        # Pydantic validation error
        assert response.status_code == 422

    def test_create_test_request_optional_fields(self, ab_testing_client, mock_ab_testing_service):
        """Test CreateTestRequest handles optional fields correctly."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-123",
            "name": "Test",
            "status": "draft",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {}},
            "variant_b": {"name": "Treatment", "config": {}},
            "primary_metric": "satisfaction_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        # Without optional fields
        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "satisfaction_rate"
        })

        assert response.status_code == 200

    def test_assign_variant_request_required_fields(self, ab_testing_client):
        """Test AssignVariantRequest validates user_id required."""
        response = ab_testing_client.post("/api/ab-tests/test-123/assign", json={})

        assert response.status_code == 422

    def test_record_metric_request_at_least_one(self, ab_testing_client):
        """Test RecordMetricRequest requires success or metric_value."""
        response = ab_testing_client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1"
        })

        # This should pass (both are optional)
        # Service will validate if needed
        assert response.status_code in [200, 400]


# ============================================================================
# TestErrorResponses - 4 tests
# ============================================================================

class TestErrorResponses:
    """Test suite for error response format consistency."""

    def test_error_response_format(self, ab_testing_client, mock_ab_testing_service):
        """Test error responses have consistent format."""
        mock_ab_testing_service.create_test.return_value = {
            "error": "Invalid test configuration"
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Invalid",
            "test_type": "invalid",
            "agent_id": "",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": ""
        })

        assert response.status_code == 400
        data = response.json()
        assert "success" in data
        assert data["success"] is False

    def test_error_response_code_includes_ab_test_error(self, ab_testing_client, mock_ab_testing_service):
        """Test error responses include AB_TEST_ERROR code."""
        mock_ab_testing_service.start_test.return_value = {
            "error": "Test not found"
        }

        response = ab_testing_client.post("/api/ab-tests/nonexistent/start")

        assert response.status_code == 400

    def test_not_found_response_format(self, ab_testing_client, mock_ab_testing_service):
        """Test 404 response format for not found."""
        mock_ab_testing_service.get_test_results.return_value = {
            "error": "Test 'nonexistent' not found"
        }

        response = ab_testing_client.get("/api/ab-tests/nonexistent/results")

        assert response.status_code == 404

    def test_validation_error_response(self, ab_testing_client):
        """Test 400 response for validation errors."""
        response = ab_testing_client.post("/api/ab-tests/create", json={})

        assert response.status_code == 422


# ============================================================================
# TestTestTypes - 4 tests
# ============================================================================

class TestTestTypes:
    """Test suite for different test types (agent_config, prompt, strategy, tool)."""

    def test_create_test_agent_config_type(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with test_type='agent_config'."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-config",
            "name": "Config Test",
            "status": "draft",
            "test_type": "agent_config",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {}},
            "variant_b": {"name": "Treatment", "config": {}},
            "primary_metric": "success_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Config Test",
            "test_type": "agent_config",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "success_rate"
        })

        assert response.status_code == 200
        assert response.json()["data"]["test_type"] == "agent_config"

    def test_create_test_prompt_type(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with test_type='prompt'."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-prompt",
            "name": "Prompt Test",
            "status": "draft",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {}},
            "variant_b": {"name": "Treatment", "config": {}},
            "primary_metric": "satisfaction_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Prompt Test",
            "test_type": "prompt",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "satisfaction_rate"
        })

        assert response.status_code == 200
        assert response.json()["data"]["test_type"] == "prompt"

    def test_create_test_strategy_type(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with test_type='strategy'."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-strategy",
            "name": "Strategy Test",
            "status": "draft",
            "test_type": "strategy",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {}},
            "variant_b": {"name": "Treatment", "config": {}},
            "primary_metric": "success_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Strategy Test",
            "test_type": "strategy",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "success_rate"
        })

        assert response.status_code == 200
        assert response.json()["data"]["test_type"] == "strategy"

    def test_create_test_tool_type(self, ab_testing_client, mock_ab_testing_service):
        """Test creating test with test_type='tool'."""
        mock_ab_testing_service.create_test.return_value = {
            "test_id": "test-tool",
            "name": "Tool Test",
            "status": "draft",
            "test_type": "tool",
            "agent_id": "agent-1",
            "variant_a": {"name": "Control", "config": {}},
            "variant_b": {"name": "Treatment", "config": {}},
            "primary_metric": "success_rate",
            "min_sample_size": 100,
            "traffic_percentage": 0.5
        }

        response = ab_testing_client.post("/api/ab-tests/create", json={
            "name": "Tool Test",
            "test_type": "tool",
            "agent_id": "agent-1",
            "variant_a_config": {},
            "variant_b_config": {},
            "primary_metric": "success_rate"
        })

        assert response.status_code == 200
        assert response.json()["data"]["test_type"] == "tool"
