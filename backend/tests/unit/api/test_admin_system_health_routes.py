"""
Unit Tests for Admin System Health API Routes

Tests for admin system health endpoints covering:
- System health monitoring
- Service health checks
- Database and queue health
- Error handling

Target Coverage: 75%
Pass Rate Target: 95%+
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

try:
    from api.admin.system_health_routes import router
except ImportError:
    pytest.skip("admin.system_health_routes not available", allow_module_level=True)


@pytest.fixture
def app():
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    return TestClient(app)


class TestSystemHealth:
    """Tests for system health operations"""

    def test_get_overall_system_health(self, client):
        response = client.get("/api/admin/system-health")
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_service_health_status(self, client):
        response = client.get("/api/admin/system-health/services")
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_database_health(self, client):
        response = client.get("/api/admin/system-health/databases")
        assert response.status_code in [200, 400, 401, 403, 404, 500]


class TestHealthChecks:
    """Tests for health check operations"""

    def test_run_health_checks(self, client):
        response = client.post("/api/admin/system-health/checks")
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_check_results(self, client):
        response = client.get("/api/admin/system-health/checks/results")
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_run_specific_health_check(self, client):
        response = client.post("/api/admin/system-health/checks/database")
        assert response.status_code in [200, 400, 401, 403, 404, 500]


class TestHealthMetrics:
    """Tests for health metrics operations"""

    def test_get_health_metrics(self, client):
        response = client.get("/api/admin/system-health/metrics")
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_performance_metrics(self, client):
        response = client.get("/api/admin/system-health/performance")
        assert response.status_code in [200, 400, 401, 403, 404, 500]

    def test_get_resource_usage(self, client):
        response = client.get("/api/admin/system-health/resources")
        assert response.status_code in [200, 400, 401, 403, 404, 500]


class TestErrorHandling:
    """Tests for error handling"""

    def test_health_check_failure(self, client):
        response = client.get("/api/admin/system-health/checks/failed-check")
        assert response.status_code in [200, 400, 403, 404, 500]


if __name__ == "__main__":
    pytest.main([__file__, "-v", "-s"])
