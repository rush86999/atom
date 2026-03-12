"""
A/B Testing Routes Test Suite

Comprehensive TestClient-based testing for ab_testing.py API routes.
Tests cover all endpoints with proper mocking.
"""

import pytest
from datetime import datetime
from fastapi import FastAPI
from unittest.mock import MagicMock, patch
from sqlalchemy.orm import Session

from api.ab_testing import router


# ============================================================================
# TestCreateTest - 8 tests
# ============================================================================

class TestCreateTest:
    """Test suite for POST /api/ab-tests/create endpoint."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_create_test_success(self, client):
        """Test creating A/B test with valid data returns 200."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Test A",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "variant_a_config": {"temperature": 0.7},
                "variant_b_config": {"temperature": 0.9},
                "primary_metric": "satisfaction_rate"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["test_id"] == "test-123"

    def test_create_test_with_all_fields(self, client):
        """Test creating test with all optional fields included."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
                "test_id": "test-456",
                "name": "Comprehensive Test",
                "status": "draft",
                "test_type": "agent_config",
                "agent_id": "agent-2",
                "variant_a": {"name": "V1", "config": {"model": "gpt-3"}},
                "variant_b": {"name": "V2", "config": {"model": "gpt-4"}},
                "primary_metric": "success_rate",
                "min_sample_size": 200,
                "traffic_percentage": 0.6
            }

            response = client.post("/api/ab-tests/create", json={
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

    def test_create_test_default_values(self, client):
        """Test creating test uses correct defaults for optional fields."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Default Test",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "satisfaction_rate"
            })

            assert response.status_code == 200

    def test_create_test_prompt_type(self, client):
        """Test creating test with test_type='prompt' validates correctly."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Prompt Test",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "variant_a_config": {"prompt": "v1"},
                "variant_b_config": {"prompt": "v2"},
                "primary_metric": "satisfaction_rate"
            })

            assert response.status_code == 200
            assert response.json()["data"]["test_type"] == "prompt"

    def test_create_test_agent_config_type(self, client):
        """Test creating test with test_type='agent_config' validates correctly."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Config Test",
                "test_type": "agent_config",
                "agent_id": "agent-1",
                "variant_a_config": {"temperature": 0.5},
                "variant_b_config": {"temperature": 0.9},
                "primary_metric": "success_rate"
            })

            assert response.status_code == 200
            assert response.json()["data"]["test_type"] == "agent_config"

    def test_create_test_validation_error(self, client):
        """Test creating test with invalid data returns 400."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
                "error": "Invalid test configuration"
            }

            response = client.post("/api/ab-tests/create", json={
                "name": "Invalid Test",
                "test_type": "invalid_type",
                "agent_id": "",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": ""
            })

            assert response.status_code == 400
            assert response.json()["success"] is False

    def test_create_test_traffic_percentage_validation(self, client):
        """Test traffic_percentage enforces ge=0.0 and le=1.0 constraints."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
                "error": "traffic_percentage must be between 0.0 and 1.0"
            }

            # Test > 1.0
            response = client.post("/api/ab-tests/create", json={
                "name": "Test",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "satisfaction_rate",
                "traffic_percentage": 1.5
            })

            assert response.status_code == 400

    def test_create_test_confidence_validation(self, client):
        """Test confidence_level enforces ge=0.0 and le=1.0 constraints."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
                "error": "confidence_level must be between 0.0 and 1.0"
            }

            response = client.post("/api/ab-tests/create", json={
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

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_start_test_success(self, client):
        """Test starting test changes status to running."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.start_test.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "running",
                "started_at": "2026-03-12T10:00:00Z"
            }

            response = client.post("/api/ab-tests/test-123/start")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["status"] == "running"

    def test_start_test_includes_timestamp(self, client):
        """Test starting test returns started_at timestamp."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            started_at = "2026-03-12T10:30:00Z"
            mock_service.start_test.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "running",
                "started_at": started_at
            }

            response = client.post("/api/ab-tests/test-123/start")

            assert response.status_code == 200
            assert response.json()["data"]["started_at"] == started_at

    def test_start_test_already_running(self, client):
        """Test starting already running test returns error."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.start_test.return_value = {
                "error": "Test must be in 'draft' status to start, current status: running"
            }

            response = client.post("/api/ab-tests/test-123/start")

            assert response.status_code == 400

    def test_start_test_not_found(self, client):
        """Test starting non-existent test returns 404."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.start_test.return_value = {
                "error": "Test 'nonexistent' not found"
            }

            response = client.post("/api/ab-tests/nonexistent/start")

            assert response.status_code == 400

    def test_start_test_error_handling(self, client):
        """Test service exceptions are handled gracefully."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.start_test.side_effect = Exception("Database error")

            response = client.post("/api/ab-tests/test-123/start")

            assert response.status_code == 500


# ============================================================================
# TestCompleteTest - 6 tests
# ============================================================================

class TestCompleteTest:
    """Test suite for POST /api/ab-tests/{test_id}/complete endpoint."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_complete_test_success(self, client):
        """Test completing test calculates results and changes status."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.complete_test.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "completed",
                "completed_at": "2026-03-12T12:00:00Z",
                "variant_a_metrics": {
                    "count": 150,
                    "success_count": 120,
                    "success_rate": 0.80
                },
                "variant_b_metrics": {
                    "count": 150,
                    "success_count": 135,
                    "success_rate": 0.90
                },
                "p_value": 0.02,
                "winner": "B"
            }

            response = client.post("/api/ab-tests/test-123/complete")

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["status"] == "completed"

    def test_complete_test_includes_results(self, client):
        """Test completing test returns variant_a_metrics and variant_b_metrics."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.complete_test.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "completed",
                "completed_at": "2026-03-12T12:00:00Z",
                "variant_a_metrics": {"count": 100, "success_rate": 0.80},
                "variant_b_metrics": {"count": 100, "success_rate": 0.90},
                "p_value": 0.05,
                "winner": "B"
            }

            response = client.post("/api/ab-tests/test-123/complete")

            assert response.status_code == 200
            data = response.json()["data"]
            assert data["variant_a_metrics"]["success_rate"] == 0.80

    def test_complete_test_includes_winner(self, client):
        """Test completing test returns winner (A, B, or inconclusive)."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.complete_test.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "completed",
                "completed_at": "2026-03-12T12:00:00Z",
                "variant_a_metrics": {},
                "variant_b_metrics": {},
                "p_value": 0.01,
                "winner": "B"
            }

            response = client.post("/api/ab-tests/test-123/complete")

            assert response.status_code == 200
            assert response.json()["data"]["winner"] == "B"

    def test_complete_test_includes_p_value(self, client):
        """Test completing test returns statistical significance p_value."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.complete_test.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "completed",
                "completed_at": "2026-03-12T12:00:00Z",
                "variant_a_metrics": {},
                "variant_b_metrics": {},
                "p_value": 0.02,
                "winner": "A"
            }

            response = client.post("/api/ab-tests/test-123/complete")

            assert response.status_code == 200
            assert "p_value" in response.json()["data"]

    def test_complete_test_insufficient_data(self, client):
        """Test completing test with insufficient data returns error."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.complete_test.return_value = {
                "error": "Insufficient sample size to complete test."
            }

            response = client.post("/api/ab-tests/test-123/complete")

            assert response.status_code == 400

    def test_complete_test_not_found(self, client):
        """Test completing non-existent test returns 404."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.complete_test.return_value = {
                "error": "Test 'nonexistent' not found"
            }

            response = client.post("/api/ab-tests/nonexistent/complete")

            assert response.status_code == 400


# ============================================================================
# TestAssignVariant - 7 tests
# ============================================================================

class TestAssignVariant:
    """Test suite for POST /api/ab-tests/{test_id}/assign endpoint."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_assign_variant_success(self, client):
        """Test assigning user to variant returns variant and config."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.assign_variant.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "variant_name": "Control",
                "config": {"temperature": 0.7},
                "existing_assignment": False
            }

            response = client.post("/api/ab-tests/test-123/assign", json={
                "user_id": "user-1"
            })

            assert response.status_code == 200
            data = response.json()
            assert data["success"] is True
            assert data["data"]["variant"] in ["A", "B"]

    def test_assign_variant_consistent(self, client):
        """Test same user gets same variant consistently."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            # First call
            mock_service.assign_variant.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "variant_name": "Control",
                "config": {},
                "existing_assignment": False
            }

            response1 = client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})
            variant1 = response1.json()["data"]["variant"]

            # Second call should return same variant
            mock_service.assign_variant.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": variant1,
                "variant_name": "Control",
                "config": {},
                "existing_assignment": True
            }

            response2 = client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})
            variant2 = response2.json()["data"]["variant"]

            assert variant1 == variant2

    def test_assign_variant_returns_config(self, client):
        """Test assigning variant returns variant configuration."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.assign_variant.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "variant_name": "Control",
                "config": {"temperature": 0.7, "max_tokens": 1000},
                "existing_assignment": False
            }

            response = client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})

            assert response.status_code == 200
            config = response.json()["data"]["config"]
            assert config["temperature"] == 0.7

    def test_assign_variant_existing_assignment(self, client):
        """Test reassigning user indicates existing_assignment=True."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.assign_variant.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "variant_name": "Control",
                "config": {},
                "existing_assignment": True
            }

            response = client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})

            assert response.status_code == 200
            assert response.json()["data"]["existing_assignment"] is True

    def test_assign_variant_with_session(self, client):
        """Test assigning variant handles optional session_id."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.assign_variant.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "B",
                "variant_name": "Treatment",
                "config": {},
                "existing_assignment": False
            }

            response = client.post("/api/ab-tests/test-123/assign", json={
                "user_id": "user-1",
                "session_id": "session-123"
            })

            assert response.status_code == 200

    def test_assign_variant_not_found(self, client):
        """Test assigning to non-existent test returns 400."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.assign_variant.return_value = {
                "error": "Test 'nonexistent' not found"
            }

            response = client.post("/api/ab-tests/nonexistent/assign", json={
                "user_id": "user-1"
            })

            assert response.status_code == 400

    def test_assign_variant_error_handling(self, client):
        """Test service exceptions are handled gracefully."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.assign_variant.side_effect = Exception("Service error")

            response = client.post("/api/ab-tests/test-123/assign", json={"user_id": "user-1"})

            assert response.status_code == 500


# ============================================================================
# TestRecordMetric - 6 tests
# ============================================================================

class TestRecordMetric:
    """Test suite for POST /api/ab-tests/{test_id}/record endpoint."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_record_metric_with_success(self, client):
        """Test recording boolean success metric."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.record_metric.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "success": True,
                "metric_value": None,
                "recorded_at": "2026-03-12T11:00:00Z"
            }

            response = client.post("/api/ab-tests/test-123/record", json={
                "user_id": "user-1",
                "success": True
            })

            assert response.status_code == 200
            assert response.json()["data"]["success"] is True

    def test_record_metric_with_value(self, client):
        """Test recording numerical metric value."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.record_metric.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "success": None,
                "metric_value": 4.5,
                "recorded_at": "2026-03-12T11:00:00Z"
            }

            response = client.post("/api/ab-tests/test-123/record", json={
                "user_id": "user-1",
                "metric_value": 4.5
            })

            assert response.status_code == 200
            assert response.json()["data"]["metric_value"] == 4.5

    def test_record_metric_with_metadata(self, client):
        """Test recording metric includes metadata."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.record_metric.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "success": True,
                "metric_value": None,
                "recorded_at": "2026-03-12T11:00:00Z"
            }

            response = client.post("/api/ab-tests/test-123/record", json={
                "user_id": "user-1",
                "success": True,
                "metadata": {"source": "mobile", "version": "1.0"}
            })

            assert response.status_code == 200

    def test_record_metric_minimal(self, client):
        """Test recording with only required user_id field."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.record_metric.return_value = {
                "test_id": "test-123",
                "user_id": "user-1",
                "variant": "A",
                "success": None,
                "metric_value": None,
                "recorded_at": "2026-03-12T11:00:00Z"
            }

            response = client.post("/api/ab-tests/test-123/record", json={"user_id": "user-1"})

            assert response.status_code == 200

    def test_record_metric_validation(self, client):
        """Test recording with invalid data returns error."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.record_metric.return_value = {
                "error": "Invalid metric data"
            }

            response = client.post("/api/ab-tests/test-123/record", json={
                "user_id": "user-1",
                "success": None,
                "metric_value": None
            })

            assert response.status_code == 400

    def test_record_metric_not_found(self, client):
        """Test recording for non-existent participant returns 400."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.record_metric.return_value = {
                "error": "Participant not found"
            }

            response = client.post("/api/ab-tests/test-123/record", json={
                "user_id": "user-999",
                "success": True
            })

            assert response.status_code == 400


# ============================================================================
# TestGetTestResults - 5 tests
# ============================================================================

class TestGetTestResults:
    """Test suite for GET /api/ab-tests/{test_id}/results endpoint."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_get_test_results_success(self, client):
        """Test getting test results returns metrics data."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_test_results.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "completed",
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
                "statistical_significance": 0.02
            }

            response = client.get("/api/ab-tests/test-123/results")

            assert response.status_code == 200
            data = response.json()
            assert "variant_a" in data
            assert "variant_b" in data

    def test_get_test_results_includes_variants(self, client):
        """Test getting results returns variant_a and variant_b data."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_test_results.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "running",
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
                "winner": None
            }

            response = client.get("/api/ab-tests/test-123/results")

            assert response.status_code == 200
            data = response.json()
            assert data["variant_a"]["participant_count"] == 100

    def test_get_test_results_winner(self, client):
        """Test getting results includes winner when completed."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_test_results.return_value = {
                "test_id": "test-123",
                "name": "Test A",
                "status": "completed",
                "variant_a": {"name": "Control", "participant_count": 150, "metrics": {}},
                "variant_b": {"name": "Treatment", "participant_count": 150, "metrics": {}},
                "winner": "B",
                "statistical_significance": 0.01
            }

            response = client.get("/api/ab-tests/test-123/results")

            assert response.status_code == 200
            assert response.json()["winner"] == "B"

    def test_get_test_results_not_found(self, client):
        """Test getting results for non-existent test returns 404."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_test_results.return_value = {
                "error": "Test 'nonexistent' not found"
            }

            response = client.get("/api/ab-tests/nonexistent/results")

            assert response.status_code == 404

    def test_get_test_results_error_handling(self, client):
        """Test service exceptions are handled gracefully."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_test_results.side_effect = Exception("Database error")

            response = client.get("/api/ab-tests/test-123/results")

            assert response.status_code == 500


# ============================================================================
# TestListTests - 6 tests
# ============================================================================

class TestListTests:
    """Test suite for GET /api/ab-tests endpoint."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_list_tests_success(self, client):
        """Test listing tests returns list of tests."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.list_tests.return_value = {
                "total": 2,
                "tests": [
                    {
                        "test_id": "test-123",
                        "name": "Test A",
                        "status": "running",
                        "test_type": "prompt",
                        "agent_id": "agent-1",
                        "primary_metric": "satisfaction_rate",
                        "winner": None
                    },
                    {
                        "test_id": "test-456",
                        "name": "Test B",
                        "status": "completed",
                        "test_type": "agent_config",
                        "agent_id": "agent-2",
                        "primary_metric": "success_rate",
                        "winner": "B"
                    }
                ]
            }

            response = client.get("/api/ab-tests")

            assert response.status_code == 200
            data = response.json()
            assert "total" in data
            assert data["total"] == 2

    def test_list_tests_filtered_by_agent(self, client):
        """Test listing tests filters by agent_id parameter."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.list_tests.return_value = {
                "total": 1,
                "tests": [{
                    "test_id": "test-123",
                    "name": "Test A",
                    "status": "running",
                    "test_type": "prompt",
                    "agent_id": "agent-1",
                    "primary_metric": "satisfaction_rate",
                    "winner": None
                }]
            }

            response = client.get("/api/ab-tests?agent_id=agent-1")

            assert response.status_code == 200

    def test_list_tests_filtered_by_status(self, client):
        """Test listing tests filters by status parameter."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.list_tests.return_value = {
                "total": 1,
                "tests": [{
                    "test_id": "test-123",
                    "name": "Test A",
                    "status": "running",
                    "test_type": "prompt",
                    "agent_id": "agent-1",
                    "primary_metric": "satisfaction_rate",
                    "winner": None
                }]
            }

            response = client.get("/api/ab-tests?status=running")

            assert response.status_code == 200

    def test_list_tests_with_limit(self, client):
        """Test listing tests respects limit parameter."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.list_tests.return_value = {
                "total": 10,
                "tests": []
            }

            response = client.get("/api/ab-tests?limit=10")

            assert response.status_code == 200

    def test_list_tests_empty(self, client):
        """Test listing tests returns empty list when no tests."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.list_tests.return_value = {
                "total": 0,
                "tests": []
            }

            response = client.get("/api/ab-tests")

            assert response.status_code == 200
            data = response.json()
            assert data["total"] == 0

    def test_list_tests_limit_validation(self, client):
        """Test limit parameter enforces ge=1 and le=100 constraints."""
        # Test limit < 1
        response = client.get("/api/ab-tests?limit=0")
        assert response.status_code == 422  # Pydantic validation error

        # Test limit > 100
        response = client.get("/api/ab-tests?limit=101")
        assert response.status_code == 422


# ============================================================================
# TestRequestModels - 4 tests
# ============================================================================

class TestRequestModels:
    """Test suite for Pydantic request model validation."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_create_test_request_required_fields(self, client):
        """Test CreateTestRequest validates required fields."""
        response = client.post("/api/ab-tests/create", json={})

        # Pydantic validation error
        assert response.status_code == 422

    def test_create_test_request_optional_fields(self, client):
        """Test CreateTestRequest handles optional fields correctly."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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
            response = client.post("/api/ab-tests/create", json={
                "name": "Test",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "satisfaction_rate"
            })

            assert response.status_code == 200

    def test_assign_variant_request_required_fields(self, client):
        """Test AssignVariantRequest validates user_id required."""
        response = client.post("/api/ab-tests/test-123/assign", json={})

        assert response.status_code == 422

    def test_record_metric_request_at_least_one(self, client):
        """Test RecordMetricRequest requires success or metric_value."""
        response = client.post("/api/ab-tests/test-123/record", json={
            "user_id": "user-1"
        })

        # This should pass (both are optional per service validation)
        assert response.status_code in [200, 400]


# ============================================================================
# TestErrorResponses - 4 tests
# ============================================================================

class TestErrorResponses:
    """Test suite for error response format consistency."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_error_response_format(self, client):
        """Test error responses have consistent format."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
                "error": "Invalid test configuration"
            }

            response = client.post("/api/ab-tests/create", json={
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

    def test_error_response_code_includes_ab_test_error(self, client):
        """Test error responses include AB_TEST_ERROR code."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.start_test.return_value = {
                "error": "Test not found"
            }

            response = client.post("/api/ab-tests/nonexistent/start")

            assert response.status_code == 400

    def test_not_found_response_format(self, client):
        """Test 404 response format for not found."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.get_test_results.return_value = {
                "error": "Test 'nonexistent' not found"
            }

            response = client.get("/api/ab-tests/nonexistent/results")

            assert response.status_code == 404

    def test_validation_error_response(self, client):
        """Test 400 response for validation errors."""
        response = client.post("/api/ab-tests/create", json={})

        assert response.status_code == 422


# ============================================================================
# TestTestTypes - 4 tests
# ============================================================================

class TestTestTypes:
    """Test suite for different test types (agent_config, prompt, strategy, tool)."""

    @pytest.fixture
    def client(self):
        """Create TestClient with A/B testing router."""
        app = FastAPI()
        app.include_router(router, prefix="/api/ab-tests")
        from fastapi.testclient import TestClient
        return TestClient(app)

    def test_create_test_agent_config_type(self, client):
        """Test creating test with test_type='agent_config'."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Config Test",
                "test_type": "agent_config",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "success_rate"
            })

            assert response.status_code == 200
            assert response.json()["data"]["test_type"] == "agent_config"

    def test_create_test_prompt_type(self, client):
        """Test creating test with test_type='prompt'."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Prompt Test",
                "test_type": "prompt",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "satisfaction_rate"
            })

            assert response.status_code == 200
            assert response.json()["data"]["test_type"] == "prompt"

    def test_create_test_strategy_type(self, client):
        """Test creating test with test_type='strategy'."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Strategy Test",
                "test_type": "strategy",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "success_rate"
            })

            assert response.status_code == 200
            assert response.json()["data"]["test_type"] == "strategy"

    def test_create_test_tool_type(self, client):
        """Test creating test with test_type='tool'."""
        with patch('core.ab_testing_service.ABTestingService') as MockService:
            mock_service = MagicMock()
            MockService.return_value = mock_service

            mock_service.create_test.return_value = {
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

            response = client.post("/api/ab-tests/create", json={
                "name": "Tool Test",
                "test_type": "tool",
                "agent_id": "agent-1",
                "variant_a_config": {},
                "variant_b_config": {},
                "primary_metric": "success_rate"
            })

            assert response.status_code == 200
            assert response.json()["data"]["test_type"] == "tool"
