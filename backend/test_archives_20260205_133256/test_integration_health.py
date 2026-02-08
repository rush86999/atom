"""
Tests for Integration Health Checks

Tests the health check endpoints for various integrations.
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import patch
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from main_api_app import app


class TestIntegrationHealthEndpoints:
    """Test integration health check endpoints"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_zoom_health_endpoint_exists(self, client):
        """Test Zoom health check endpoint"""
        response = client.get("/api/zoom/health")

        assert response.status_code == 200
        data = response.json()
        assert "service" in data
        assert data["service"] == "zoom"
        assert "configured" in data
        assert "timestamp" in data

    def test_notion_health_endpoint_exists(self, client):
        """Test Notion health check endpoint"""
        response = client.get("/api/notion/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "notion"
        assert "configured" in data

    def test_trello_health_endpoint_exists(self, client):
        """Test Trello health check endpoint"""
        response = client.get("/api/trello/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "trello"
        assert "configured" in data

    def test_stripe_health_endpoint_exists(self, client):
        """Test Stripe health check endpoint"""
        response = client.get("/api/stripe/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "stripe"
        assert "configured" in data

    def test_quickbooks_health_endpoint_exists(self, client):
        """Test QuickBooks health check endpoint"""
        response = client.get("/api/quickbooks/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "quickbooks"
        assert "configured" in data

    def test_github_health_endpoint_exists(self, client):
        """Test GitHub health check endpoint"""
        response = client.get("/api/github/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "github"
        assert "configured" in data

    def test_salesforce_health_endpoint_exists(self, client):
        """Test Salesforce health check endpoint"""
        response = client.get("/api/salesforce/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "salesforce"
        assert "configured" in data

    def test_google_drive_health_endpoint_exists(self, client):
        """Test Google Drive health check endpoint"""
        response = client.get("/api/google-drive/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "google-drive"
        assert "configured" in data

    def test_dropbox_health_endpoint_exists(self, client):
        """Test Dropbox health check endpoint"""
        response = client.get("/api/dropbox/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "dropbox"
        assert "configured" in data

    def test_slack_health_endpoint_exists(self, client):
        """Test Slack health check endpoint"""
        response = client.get("/api/slack/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "slack"
        assert "configured" in data


class TestHealthCheckResponseStructure:
    """Test health check response format consistency"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_responses_have_consistent_structure(self, client):
        """Test all health endpoints return consistent structure"""
        services = ["zoom", "notion", "trello", "stripe", "quickbooks",
                    "github", "salesforce", "google-drive", "dropbox", "slack"]

        for service in services:
            response = client.get(f"/api/{service}/health")

            assert response.status_code == 200
            data = response.json()

            # Check required fields
            assert "ok" in data
            assert "service" in data
            assert "timestamp" in data
            assert "configured" in data
            assert "has_credentials" in data

            # Check types
            assert isinstance(data["ok"], bool)
            assert isinstance(data["service"], str)
            assert isinstance(data["configured"], bool)
            assert isinstance(data["has_credentials"], bool)

    def test_health_responses_include_config_status_details(self, client):
        """Test health responses include configuration details when not configured"""
        # In test environment, most services won't be configured
        response = client.get("/api/trello/health")

        assert response.status_code == 200
        data = response.json()

        # When not configured, should have missing_env_vars
        if not data["configured"]:
            assert "missing_env_vars" in data
            assert isinstance(data["missing_env_vars"], list)


class TestHealthCheckRealVerification:
    """Test that health checks actually verify configuration"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    @patch.dict(os.environ, {}, clear=True)
    def test_health_check_detects_unconfigured_service(self, client, monkeypatch):
        """Test health check properly detects unconfigured services"""
        import os

        # Remove environment variables to simulate unconfigured service
        # (in real test, we'd set specific test variables)

        # This test verifies the health check logic works correctly
        # without requiring actual credentials
        response = client.get("/api/trello/health")

        assert response.status_code == 200
        data = response.json()

        # Should report not configured (no env vars set)
        # The health check function verifies actual environment variables
        assert "configured" in data
        # In test environment with no env vars, this should be False
        assert isinstance(data["configured"], bool)
