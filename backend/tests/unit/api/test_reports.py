"""
Unit Tests for Reports API Routes

Tests report generation endpoints:
- GET /api/reports - Reports API root endpoint

Target Coverage: 95%
Target Branch Coverage: 60%+
"""

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from api.reports import router as reports_router


@pytest.fixture(scope="function")
def client() -> TestClient:
    """
    Create TestClient with reports router for testing.
    """
    app = FastAPI()
    app.include_router(reports_router)
    return TestClient(app)


class TestReportsRoot:
    """Tests for GET /api/reports endpoint."""

    def test_reports_root_success(self, client: TestClient):
        """Test GET /api/reports returns success response."""
        # Act: Get reports root
        response = client.get("/api/reports")

        # Assert: Verify success response structure
        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert data["data"]["message"] == "Reports API"
        assert "message" in data
        assert data["message"] == "Reports API root endpoint"
        assert "timestamp" in data

    def test_reports_root_response_structure(self, client: TestClient):
        """Test GET /api/reports returns correct response structure."""
        # Act: Get reports root
        response = client.get("/api/reports")

        # Assert: Verify all expected fields present
        data = response.json()
        expected_keys = {"success", "data", "message", "timestamp"}
        assert set(data.keys()) == expected_keys
        assert isinstance(data["success"], bool)
        assert isinstance(data["data"], dict)
        assert isinstance(data["message"], str)
        assert isinstance(data["timestamp"], str)

    def test_reports_root_data_field(self, client: TestClient):
        """Test GET /api/reports data field contains message."""
        # Act: Get reports root
        response = client.get("/api/reports")

        # Assert: Verify data field structure
        data = response.json()
        assert "message" in data["data"]
        assert data["data"]["message"] == "Reports API"

    def test_reports_root_timestamp_format(self, client: TestClient):
        """Test GET /api/reports returns ISO format timestamp."""
        # Act: Get reports root
        response = client.get("/api/reports")

        # Assert: Verify timestamp is ISO format
        data = response.json()
        timestamp = data["timestamp"]
        assert isinstance(timestamp, str)
        # Verify ISO format: YYYY-MM-DDTHH:MM:SS.mmmmmm
        assert "T" in timestamp
        assert len(timestamp) >= 20

    def test_reports_root_no_auth_required(self, client: TestClient):
        """Test GET /api/reports does not require authentication."""
        # Act: Get reports root without auth headers
        response = client.get("/api/reports")

        # Assert: Verify request succeeds without auth
        assert response.status_code == 200
        assert response.json()["success"] is True

    def test_reports_root_content_type(self, client: TestClient):
        """Test GET /api/reports returns JSON content type."""
        # Act: Get reports root
        response = client.get("/api/reports")

        # Assert: Verify content type is JSON
        assert response.status_code == 200
        assert "application/json" in response.headers["content-type"]
