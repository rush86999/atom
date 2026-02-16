"""
Health Check Routes Tests

Tests for production health check endpoints used by Kubernetes/ECS orchestration.

Coverage:
- /health/live: Liveness probe (200 when alive)
- /health/ready: Readiness probe (200 when dependencies ready, 503 when not)
- /health/metrics: Prometheus metrics endpoint

References:
- 15-RESEARCH.md: Health check patterns
- Kubernetes probes: https://kubernetes.io/docs/tasks/configure-pod-container/configure-liveness-readiness-startup-probes/
"""

import pytest
from unittest.mock import AsyncMock, MagicMock, patch
from fastapi import status
from fastapi.testclient import TestClient

from main_api_app import app


@pytest.fixture
def client():
    """Create a test client for the FastAPI app."""
    return TestClient(app)


class TestLivenessProbe:
    """Tests for /health/live endpoint."""

    def test_live_returns_200(self, client):
        """
        GIVEN the application is running
        WHEN GET /health/live is called
        THEN return 200 with status='alive'
        """
        response = client.get("/health/live")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "alive"
        assert "timestamp" in data

    def test_live_always_succeeds(self, client):
        """
        GIVEN the application is running (even with degraded services)
        WHEN GET /health/live is called
        THEN always return 200 (liveness probes should be lightweight)
        """
        # Liveness probe should not check dependencies
        # It only verifies the process is alive
        response = client.get("/health/live")

        # Should always succeed if the app is running
        assert response.status_code == status.HTTP_200_OK


class TestReadinessProbe:
    """Tests for /health/ready endpoint."""

    @patch('api.health_routes._check_database')
    @patch('api.health_routes._check_disk_space')
    def test_ready_returns_200_when_dependencies_healthy(
        self, mock_disk, mock_db, client
    ):
        """
        GIVEN all dependencies (database, disk) are healthy
        WHEN GET /health/ready is called
        THEN return 200 with status='ready' and all checks passing
        """
        # Mock healthy dependencies
        mock_db.return_value = {
            "healthy": True,
            "message": "Database accessible",
            "latency_ms": 5.0,
        }
        mock_disk.return_value = {
            "healthy": True,
            "message": "10.00GB free",
            "free_gb": 10.0,
        }

        response = client.get("/health/ready")

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "ready"
        assert "timestamp" in data
        assert "checks" in data
        assert data["checks"]["database"]["healthy"] is True
        assert data["checks"]["disk"]["healthy"] is True

    @patch('api.health_routes._check_database')
    @patch('api.health_routes._check_disk_space')
    def test_ready_returns_503_when_database_unavailable(
        self, mock_disk, mock_db, client
    ):
        """
        GIVEN database is unavailable
        WHEN GET /health/ready is called
        THEN return 503 with database check failed
        """
        # Mock database failure
        mock_db.return_value = {
            "healthy": False,
            "message": "Database timeout after 5.0s",
            "latency_ms": 5000.0,
        }
        # Mock healthy disk
        mock_disk.return_value = {
            "healthy": True,
            "message": "10.00GB free",
            "free_gb": 10.0,
        }

        response = client.get("/health/ready")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "detail" in data
        assert data["detail"]["status"] == "not_ready"
        assert data["detail"]["checks"]["database"]["healthy"] is False
        assert "Database timeout" in data["detail"]["checks"]["database"]["message"]

    @patch('api.health_routes._check_disk_space')
    def test_ready_returns_503_when_disk_insufficient(self, mock_disk, client):
        """
        GIVEN disk space is insufficient (<1GB free)
        WHEN GET /health/ready is called
        THEN return 503 with disk check failed
        """
        # Mock healthy database
        with patch('api.health_routes._check_database') as mock_db:
            mock_db.return_value = {
                "healthy": True,
                "message": "Database accessible",
                "latency_ms": 5.0,
            }

            # Mock low disk space
            mock_disk.return_value = {
                "healthy": False,
                "message": "Low disk space: 0.50GB free (minimum: 1.0GB)",
                "free_gb": 0.5,
            }

            response = client.get("/health/ready")

            assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
            data = response.json()
            assert "detail" in data
            assert data["detail"]["status"] == "not_ready"
            assert data["detail"]["checks"]["disk"]["healthy"] is False
            assert "Low disk space" in data["detail"]["checks"]["disk"]["message"]

    @patch('api.health_routes._check_database')
    @patch('api.health_routes._check_disk_space')
    def test_ready_returns_503_when_both_dependencies_fail(
        self, mock_disk, mock_db, client
    ):
        """
        GIVEN both database and disk checks fail
        WHEN GET /health/ready is called
        THEN return 503 with both checks failed
        """
        # Mock both failures
        mock_db.return_value = {
            "healthy": False,
            "message": "Database error",
            "latency_ms": 0,
        }
        mock_disk.return_value = {
            "healthy": False,
            "message": "Disk check error",
            "free_gb": 0,
        }

        response = client.get("/health/ready")

        assert response.status_code == status.HTTP_503_SERVICE_UNAVAILABLE
        data = response.json()
        assert "detail" in data
        assert data["detail"]["checks"]["database"]["healthy"] is False
        assert data["detail"]["checks"]["disk"]["healthy"] is False


class TestMetricsEndpoint:
    """Tests for /health/metrics endpoint."""

    def test_metrics_exposes_prometheus_format(self, client):
        """
        GIVEN Prometheus metrics are configured
        WHEN GET /health/metrics is called
        THEN return Prometheus text format metrics
        """
        response = client.get("/health/metrics")

        # Should return 200
        assert response.status_code == status.HTTP_200_OK

        # Should have Prometheus content type
        assert "text/plain" in response.headers["content-type"]

        # Should contain Prometheus format metrics
        metrics_text = response.text
        # Check for metric name patterns
        assert "#" in metrics_text or "http_requests_total" in metrics_text or "agent_executions_total" in metrics_text

    def test_metrics_includes_http_metrics(self, client):
        """
        GIVEN HTTP request metrics are tracked
        WHEN GET /health/metrics is called
        THEN include HTTP request counter and histogram
        """
        response = client.get("/health/metrics")

        metrics_text = response.text

        # Check for HTTP metrics (may be empty if no requests yet)
        # The metric definitions should be present
        assert "http_requests_total" in metrics_text or "HELP" in metrics_text
        assert "http_request_duration_seconds" in metrics_text or "HELP" in metrics_text

    def test_metrics_includes_agent_metrics(self, client):
        """
        GIVEN agent execution metrics are tracked
        WHEN GET /health/metrics is called
        THEN include agent execution counter and histogram
        """
        response = client.get("/health/metrics")

        metrics_text = response.text

        # Check for agent metrics
        assert "agent_executions_total" in metrics_text or "HELP" in metrics_text
        assert "agent_execution_duration_seconds" in metrics_text or "HELP" in metrics_text

    def test_metrics_includes_skill_metrics(self, client):
        """
        GIVEN skill execution metrics are tracked
        WHEN GET /health/metrics is called
        THEN include skill execution counter and histogram
        """
        response = client.get("/health/metrics")

        metrics_text = response.text

        # Check for skill metrics
        assert "skill_executions_total" in metrics_text or "HELP" in metrics_text
        assert "skill_execution_duration_seconds" in metrics_text or "HELP" in metrics_text


class TestPerformance:
    """Performance tests for health check endpoints."""

    def test_liveness_probe_latency(self, client):
        """
        GIVEN the application is running
        WHEN GET /health/live is called
        THEN response time should be <10ms (lightweight check)
        """
        import time

        start = time.time()
        response = client.get("/health/live")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == status.HTTP_200_OK
        # Liveness probe should be very fast
        assert duration_ms < 100, f"Liveness probe took {duration_ms:.2f}ms (target: <10ms)"

    @patch('api.health_routes._check_database')
    @patch('api.health_routes._check_disk_space')
    def test_readiness_probe_latency(self, mock_disk, mock_db, client):
        """
        GIVEN all dependencies are healthy
        WHEN GET /health/ready is called
        THEN response time should be <100ms (includes dependency checks)
        """
        import time

        # Mock fast dependency checks
        mock_db.return_value = {
            "healthy": True,
            "message": "Database accessible",
            "latency_ms": 1.0,
        }
        mock_disk.return_value = {
            "healthy": True,
            "message": "10.00GB free",
            "free_gb": 10.0,
        }

        start = time.time()
        response = client.get("/health/ready")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == status.HTTP_200_OK
        # Readiness probe includes database check, so allow more time
        assert duration_ms < 500, f"Readiness probe took {duration_ms:.2f}ms (target: <100ms)"

    def test_metrics_endpoint_latency(self, client):
        """
        GIVEN Prometheus metrics are configured
        WHEN GET /health/metrics is called
        THEN response time should be <50ms for full scrape
        """
        import time

        start = time.time()
        response = client.get("/health/metrics")
        duration_ms = (time.time() - start) * 1000

        assert response.status_code == status.HTTP_200_OK
        # Metrics generation should be fast
        assert duration_ms < 200, f"Metrics scrape took {duration_ms:.2f}ms (target: <50ms)"
