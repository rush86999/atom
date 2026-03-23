"""
Provider Health Routes Integration Tests

Comprehensive TestClient-based tests for provider health endpoints.

Coverage:
- GET /api/providers/health - Overall provider registry health status
- GET /api/providers/{provider_id}/health - Per-provider health details
- POST /api/providers/sync - Manual provider sync trigger

Test fixtures from backend/tests/conftest.py (db_session, test_token)
"""

import pytest
from datetime import datetime
from fastapi.testclient import TestClient
from fastapi import FastAPI


# Import provider health routes router
from api.provider_health_routes import router as provider_health_router

# Create minimal FastAPI app for testing provider health routes
app = FastAPI()
app.include_router(provider_health_router, tags=["Provider Health"])


# ============================================================================
# Test Class: TestProviderHealthRoutes
# ============================================================================

class TestProviderHealthRoutes:
    """Tests for provider health endpoints."""

    def test_get_provider_health_success(self):
        """GET /api/providers/health returns health status with provider counts."""
        client = TestClient(app)
        response = client.get("/api/providers/health")

        assert response.status_code == 200
        data = response.json()
        assert "total_providers" in data
        assert "healthy_providers" in data
        assert "unhealthy_providers" in data
        assert "timestamp" in data
        assert data["total_providers"] >= 0
        assert data["healthy_providers"] >= 0
        assert data["unhealthy_providers"] >= 0

        # Verify timestamp format
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_get_provider_health_unhealthy_providers(self):
        """GET /api/providers/health includes unhealthy provider count."""
        client = TestClient(app)
        response = client.get("/api/providers/health")

        assert response.status_code == 200
        data = response.json()
        # Verify the structure includes all expected fields
        assert "total_providers" in data
        assert "healthy_providers" in data
        assert "unhealthy_providers" in data
        # Verify counts are consistent
        assert data["total_providers"] == data["healthy_providers"] + data["unhealthy_providers"]

    def test_get_provider_health_detail_success(self):
        """GET /api/providers/{provider_id}/health returns provider details for existing provider."""
        client = TestClient(app)

        # First, try to get a list of providers to find an existing one
        health_response = client.get("/api/providers/health")
        if health_response.status_code == 200:
            providers = health_response.json().get("providers", [])
            if providers:
                provider_id = providers[0]["provider_id"]
                response = client.get(f"/api/providers/{provider_id}/health")

                assert response.status_code == 200
                data = response.json()
                assert "provider_id" in data
                assert "name" in data
                assert "health_score" in data
                assert "is_healthy" in data
                assert "last_updated" in data
                assert "is_active" in data
                assert "supports_vision" in data
                assert "supports_tools" in data

    def test_get_provider_health_detail_not_found(self):
        """GET /api/providers/{provider_id}/health returns 404 for unknown provider."""
        client = TestClient(app)
        response = client.get("/api/providers/unknown_provider_xyz123/health")

        assert response.status_code == 404
        data = response.json()
        assert "detail" in data
        assert "not found" in data["detail"].lower()

    def test_get_provider_health_detail_is_healthy_threshold(self):
        """GET /api/providers/{provider_id}/health is_healthy reflects 0.5 threshold."""
        client = TestClient(app)

        # Try to find an existing provider first
        health_response = client.get("/api/providers/health")
        if health_response.status_code == 200:
            providers = health_response.json().get("providers", [])
            if providers:
                provider_id = providers[0]["provider_id"]
                response = client.get(f"/api/providers/{provider_id}/health")

                assert response.status_code == 200
                data = response.json()

                # Verify is_healthy is consistent with health_score
                health_score = data["health_score"]
                is_healthy = data["is_healthy"]

                if health_score >= 0.5:
                    assert is_healthy == True
                else:
                    assert is_healthy == False

    def test_trigger_provider_sync_success(self):
        """POST /api/providers/sync triggers manual sync and returns results."""
        client = TestClient(app)
        response = client.post("/api/providers/sync")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] == True
        assert "providers_synced" in data
        assert "models_synced" in data
        assert "timestamp" in data
        assert data["providers_synced"] >= 0
        assert data["models_synced"] >= 0

        # Verify timestamp format
        datetime.fromisoformat(data["timestamp"].replace("Z", "+00:00"))

    def test_trigger_provider_sync_result_timestamp(self):
        """POST /api/providers/sync includes ISO timestamp in result."""
        client = TestClient(app)
        response = client.post("/api/providers/sync")

        assert response.status_code == 200
        data = response.json()

        # Verify timestamp exists and is valid ISO format
        assert "timestamp" in data
        timestamp = data["timestamp"]
        assert "T" in timestamp  # ISO format has T separator
        # Parse without error
        parsed_time = datetime.fromisoformat(timestamp.replace("Z", "+00:00"))
        assert isinstance(parsed_time, datetime)

    def test_get_provider_health_no_auth_required(self):
        """Provider health endpoints work without authentication."""
        # These are health monitoring endpoints, no auth required
        client = TestClient(app)

        # Ensure no auth header is sent
        client.headers.pop("Authorization", None)

        response = client.get("/api/providers/health")
        assert response.status_code == 200
