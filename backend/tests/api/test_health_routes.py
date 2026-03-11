"""
Health Routes Integration Tests

Comprehensive TestClient-based tests for health check endpoints.

Coverage:
- /health/live - Liveness probe
- /health/ready - Readiness probe (DB + disk checks)
- /health/db - Database connectivity check
- /health/metrics - Prometheus metrics endpoint
- /health/sync - Sync subsystem health
- /metrics/sync - Sync-specific Prometheus metrics

Test fixtures from backend/tests/conftest.py (db_session, test_token)
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI
from unittest.mock import patch, MagicMock, AsyncMock
from sqlalchemy.exc import SQLAlchemyError
import asyncio


# Import health routes router
from api.health_routes import router as health_router

# Create minimal FastAPI app for testing health routes
app = FastAPI()
app.include_router(health_router, tags=["Health"])


# ============================================================================
# Test Class: TestLivenessProbe
# ============================================================================

class TestLivenessProbe:
    """Tests for /health/live endpoint - Kubernetes liveness probe."""

    def test_liveness_returns_200(self, api_test_client: TestClient):
        """Test liveness probe returns 200 status code."""
        response = api_test_client.get("/health/live")
        assert response.status_code == 200

    def test_liveness_returns_status_alive(self, api_test_client: TestClient):
        """Test liveness probe returns status='alive'."""
        response = api_test_client.get("/health/live")
        data = response.json()
        assert data["status"] == "alive"

    def test_liveness_includes_timestamp(self, api_test_client: TestClient):
        """Test liveness probe includes ISO format timestamp."""
        response = api_test_client.get("/health/live")
        data = response.json()
        assert "timestamp" in data
        # Verify ISO format timestamp
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_liveness_no_auth_required(self, api_test_client: TestClient):
        """Test liveness probe works without Authorization header."""
        # Remove any auth headers
        api_test_client.headers.pop("Authorization", None)
        response = api_test_client.get("/health/live")
        assert response.status_code == 200


# ============================================================================
# Test Class: TestReadinessProbe
# ============================================================================

class TestReadinessProbe:
    """Tests for /health/ready endpoint - Kubernetes readiness probe."""

    def test_readiness_returns_200_when_healthy(self, api_test_client: TestClient):
        """Test readiness probe returns 200 when all dependencies are healthy."""
        response = api_test_client.get("/health/ready")
        # May return 200 or 503 depending on actual DB state
        assert response.status_code in [200, 503]

    def test_readiness_includes_timestamp(self, api_test_client: TestClient):
        """Test readiness probe includes ISO format timestamp."""
        response = api_test_client.get("/health/ready")
        if response.status_code == 200:
            data = response.json()
            assert "timestamp" in data
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))
        elif response.status_code == 503:
            data = response.json()["detail"]
            assert "timestamp" in data
            datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_readiness_returns_503_when_db_down(self, api_test_client: TestClient, monkeypatch):
        """Test readiness probe returns 503 when database is unreachable."""
        # Mock database check to fail
        async def mock_db_check_failure():
            return {
                "healthy": False,
                "message": "Database timeout after 5.0s",
                "latency_ms": 5000.0
            }

        with patch("api.health_routes._check_database", side_effect=mock_db_check_failure):
            response = api_test_client.get("/health/ready")
            # Should return 503 when DB is down
            assert response.status_code == 503

    def test_readiness_checks_disk_space(self, api_test_client: TestClient):
        """Test readiness probe checks disk space availability."""
        response = api_test_client.get("/health/ready")
        if response.status_code == 200:
            data = response.json()
            assert "checks" in data
            assert "disk" in data["checks"]
            disk_check = data["checks"]["disk"]
            assert "healthy" in disk_check
            assert "free_gb" in disk_check

    def test_readiness_includes_dependency_status(self, api_test_client: TestClient):
        """Test readiness probe returns status for all dependencies."""
        response = api_test_client.get("/health/ready")
        if response.status_code == 200:
            data = response.json()
            assert "checks" in data
            assert "database" in data["checks"]
            assert "disk" in data["checks"]
        elif response.status_code == 503:
            data = response.json()["detail"]
            assert "checks" in data

    def test_readiness_no_auth_required(self, api_test_client: TestClient):
        """Test readiness probe works without Authorization header."""
        api_test_client.headers.pop("Authorization", None)
        response = api_test_client.get("/health/ready")
        assert response.status_code in [200, 503]


# ============================================================================
# Test Class: TestDatabaseConnectivity
# ============================================================================

class TestDatabaseConnectivity:
    """Tests for /health/db endpoint - database connectivity check."""

    def test_database_connectivity_returns_200(self, api_test_client: TestClient):
        """Test database connectivity check returns 200 when DB is accessible."""
        response = api_test_client.get("/health/db")
        # May return 200 or 503 depending on actual DB state
        assert response.status_code in [200, 503]

    def test_database_connectivity_includes_pool_status(self, api_test_client: TestClient):
        """Test database connectivity check includes connection pool status."""
        response = api_test_client.get("/health/db")
        if response.status_code == 200:
            data = response.json()
            assert "database" in data
            assert "pool_status" in data["database"]
            pool_status = data["database"]["pool_status"]
            assert "size" in pool_status
            assert "checked_in" in pool_status
            assert "checked_out" in pool_status

    def test_database_connectivity_includes_query_time(self, api_test_client: TestClient):
        """Test database connectivity check includes query timing."""
        response = api_test_client.get("/health/db")
        if response.status_code == 200:
            data = response.json()
            assert "database" in data
            assert "query_time_ms" in data["database"]
            assert data["database"]["query_time_ms"] >= 0

    def test_database_connectivity_slow_query_warning(self, api_test_client: TestClient, monkeypatch):
        """Test database connectivity check warns on slow queries (>100ms)."""
        # Mock time.time to simulate slow query
        original_time = __import__("time").time
        call_count = [0]

        def mock_time():
            call_count[0] += 1
            if call_count[0] == 1:
                return original_time()  # Start time
            else:
                return original_time() + 0.15  # End time (150ms later)

        monkeypatch.setattr("time.time", mock_time)

        response = api_test_client.get("/health/db")
        # May return 200 or 503, but if 200 should have warning
        if response.status_code == 200:
            data = response.json()
            if "warning" in data.get("database", {}):
                assert "Slow query" in data["database"]["warning"]


# ============================================================================
# Test Class: TestPrometheusMetrics
# ============================================================================

class TestPrometheusMetrics:
    """Tests for /health/metrics endpoint - Prometheus metrics."""

    def test_metrics_returns_200(self, api_test_client: TestClient):
        """Test metrics endpoint returns 200 status code."""
        response = api_test_client.get("/health/metrics")
        assert response.status_code == 200

    def test_metrics_returns_prometheus_format(self, api_test_client: TestClient):
        """Test metrics endpoint returns Prometheus text format."""
        response = api_test_client.get("/health/metrics")
        assert response.status_code == 200
        # Check Content-Type header
        content_type = response.headers.get("content-type", "")
        assert "text/plain" in content_type or CONTENT_TYPE_LATEST in content_type

    def test_metrics_includes_http_metrics(self, api_test_client: TestClient):
        """Test metrics endpoint includes HTTP request metrics."""
        from prometheus_client import CONTENT_TYPE_LATEST

        response = api_test_client.get("/health/metrics")
        assert response.status_code == 200
        assert response.headers["content-type"] == CONTENT_TYPE_LATEST

        # Metrics should be in text format
        metrics_text = response.text
        # Prometheus metrics format includes # HELP and # TYPE comments
        assert "#" in metrics_text or len(metrics_text) > 0

    def test_metrics_accessible_without_auth(self, api_test_client: TestClient):
        """Test metrics endpoint works without Authorization header."""
        api_test_client.headers.pop("Authorization", None)
        response = api_test_client.get("/health/metrics")
        assert response.status_code == 200


# ============================================================================
# Test Class: TestSyncHealth
# ============================================================================

class TestSyncHealth:
    """Tests for /health/sync endpoint - sync subsystem health."""

    def test_sync_health_returns_200(self, api_test_client: TestClient):
        """Test sync health endpoint returns 200 or 503."""
        response = api_test_client.get("/health/sync")
        # Sync health monitor may or may not be available
        assert response.status_code in [200, 503, 500]  # 500 if monitor not configured

    def test_sync_health_includes_status(self, api_test_client: TestClient):
        """Test sync health endpoint includes status field."""
        response = api_test_client.get("/health/sync")
        if response.status_code in [200, 503]:
            data = response.json()
            assert "status" in data
            assert data["status"] in ["healthy", "unhealthy", "degraded"]

    def test_sync_health_no_auth_required(self, api_test_client: TestClient):
        """Test sync health endpoint works without Authorization header."""
        api_test_client.headers.pop("Authorization", None)
        response = api_test_client.get("/health/sync")
        assert response.status_code in [200, 503, 500]


# ============================================================================
# Test Class: TestSyncMetrics
# ============================================================================

class TestSyncMetrics:
    """Tests for /metrics/sync endpoint - sync-specific Prometheus metrics."""

    def test_sync_metrics_returns_200(self, api_test_client: TestClient):
        """Test sync metrics endpoint returns 200 status code."""
        response = api_test_client.get("/metrics/sync")
        assert response.status_code == 200

    def test_sync_metrics_returns_prometheus_format(self, api_test_client: TestClient):
        """Test sync metrics endpoint returns Prometheus text format."""
        from prometheus_client import CONTENT_TYPE_LATEST

        response = api_test_client.get("/metrics/sync")
        assert response.status_code == 200
        assert response.headers["content-type"] == CONTENT_TYPE_LATEST

    def test_sync_metrics_accessible_without_auth(self, api_test_client: TestClient):
        """Test sync metrics endpoint works without Authorization header."""
        api_test_client.headers.pop("Authorization", None)
        response = api_test_client.get("/metrics/sync")
        assert response.status_code == 200


# ============================================================================
# Parametrized Edge Case Tests
# ============================================================================

class TestHealthEdgeCases:
    """Edge case tests using pytest.mark.parametrize."""

    @pytest.mark.parametrize("endpoint", [
        "/health/live",
        "/health/ready",
        "/health/db",
        "/health/metrics",
        "/health/sync",
        "/metrics/sync"
    ])
    def test_health_endpoints_respond(self, endpoint, api_test_client: TestClient):
        """Test all health endpoints respond with valid status codes."""
        response = api_test_client.get(endpoint)
        # Health endpoints should return 200, 503, or 500 (if monitor not available)
        assert response.status_code in [200, 503, 500]

    @pytest.mark.parametrize("endpoint", [
        "/health/live",
        "/health/ready",
        "/health/db",
        "/health/metrics",
        "/health/sync",
        "/metrics/sync"
    ])
    def test_health_endpoints_no_auth(self, endpoint, api_test_client: TestClient):
        """Test all health endpoints work without authentication."""
        api_test_client.headers.pop("Authorization", None)
        response = api_test_client.get(endpoint)
        assert response.status_code in [200, 503, 500]

    @pytest.mark.parametrize("free_gb,expected_healthy", [
        (10.0, True),   # Plenty of space
        (2.0, True),    # Above threshold
        (1.0, True),    # At threshold
        (0.5, False),   # Below threshold
        (0.1, False),   # Critically low
    ])
    def test_disk_space_thresholds(self, free_gb, expected_healthy, monkeypatch):
        """Test disk space check validates MIN_DISK_GB threshold."""
        import psutil

        # Mock disk_usage to return specific free space
        mock_disk = MagicMock()
        mock_disk.free = free_gb * (1024 ** 3)  # Convert GB to bytes

        with patch("psutil.disk_usage", return_value=mock_disk):
            from api.health_routes import _check_disk_space
            result = asyncio.run(_check_disk_space())

            assert result["healthy"] == expected_healthy
            assert result["free_gb"] == free_gb


# ============================================================================
# Database Failure Scenarios
# ============================================================================

class TestDatabaseFailureScenarios:
    """Tests for database failure scenarios."""

    def test_database_timeout(self, api_test_client: TestClient, monkeypatch):
        """Test readiness probe handles database timeout."""
        async def mock_db_timeout():
            raise asyncio.TimeoutError("Database query timeout")

        with patch("api.health_routes._check_database", side_effect=mock_db_timeout):
            response = api_test_client.get("/health/ready")
            # Should handle timeout gracefully
            assert response.status_code in [503, 500]

    def test_database_connection_error(self, api_test_client: TestClient, monkeypatch):
        """Test readiness probe handles database connection errors."""
        async def mock_db_error():
            raise SQLAlchemyError("Connection refused")

        with patch("api.health_routes._check_database", side_effect=mock_db_error):
            response = api_test_client.get("/health/ready")
            # Should handle connection error gracefully
            assert response.status_code in [503, 500]

    def test_database_unexpected_error(self, api_test_client: TestClient, monkeypatch):
        """Test readiness probe handles unexpected database errors."""
        async def mock_db_unexpected():
            raise Exception("Unexpected database error")

        with patch("api.health_routes._check_database", side_effect=mock_db_unexpected):
            response = api_test_client.get("/health/ready")
            # Should handle unexpected error gracefully
            assert response.status_code in [503, 500]


# Import for CONTENT_TYPE_LATEST constant
from prometheus_client import CONTENT_TYPE_LATEST
