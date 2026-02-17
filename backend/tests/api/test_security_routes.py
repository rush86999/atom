"""
Security Routes API Tests

Tests for security configuration and health check endpoints including:
- Security configuration check
- Secrets security status
- Webhook security status
- Security health check
"""

import pytest
import os
from fastapi.testclient import TestClient
from unittest.mock import patch, Mock

from main_api_app import app


class TestSecurityRoutes:
    """Test security API endpoints."""

    @pytest.fixture
    def client(self):
        """Create test client."""
        return TestClient(app)

    def test_security_configuration_check_default_env(self, client):
        """Test security configuration check in default environment."""
        response = client.get("/api/security/configuration")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "issues" in data
        assert "config" in data
        assert isinstance(data["issues"], list)
        assert isinstance(data["config"], dict)

    def test_security_configuration_config_structure(self, client):
        """Test security configuration response structure."""
        response = client.get("/api/security/configuration")

        assert response.status_code == 200
        data = response.json()

        # Check config has required fields
        config = data["config"]
        assert "environment" in config
        assert "cors_origins" in config
        assert "jwt_expiration" in config
        assert "allow_dev_temp_users" in config

    def test_security_configuration_issues_severity(self, client):
        """Test that security issues have proper severity levels."""
        response = client.get("/api/security/configuration")

        assert response.status_code == 200
        data = response.json()

        # Check that issues have valid severity
        for issue in data["issues"]:
            assert "severity" in issue
            assert issue["severity"] in ["critical", "warning", "info"]
            assert "issue" in issue
            assert "message" in issue
            assert "recommendation" in issue

    def test_security_configuration_status_values(self, client):
        """Test that status field has valid values."""
        response = client.get("/api/security/configuration")

        assert response.status_code == 200
        data = response.json()

        # Status should be one of these values
        assert data["status"] in ["healthy", "warning", "critical"]

    def test_secrets_security_status(self, client):
        """Test secrets security status endpoint."""
        response = client.get("/api/security/secrets")

        assert response.status_code == 200
        data = response.json()
        assert "encryption_enabled" in data
        assert "storage_type" in data
        assert "secrets_count" in data
        assert "environment" in data

    def test_secrets_security_status_types(self, client):
        """Test secrets security status response types."""
        response = client.get("/api/security/secrets")

        assert response.status_code == 200
        data = response.json()

        # Check field types
        assert isinstance(data["encryption_enabled"], bool)
        assert isinstance(data["storage_type"], str)
        assert isinstance(data["secrets_count"], int)
        assert isinstance(data["environment"], str)

    def test_webhook_security_status(self, client):
        """Test webhook security status endpoint."""
        response = client.get("/api/security/webhooks")

        assert response.status_code == 200
        data = response.json()
        assert "slack_configured" in data
        assert "teams_configured" in data
        assert "gmail_configured" in data
        assert "environment" in data
        assert "warnings" in data

    def test_webhook_security_status_types(self, client):
        """Test webhook security status response types."""
        response = client.get("/api/security/webhooks")

        assert response.status_code == 200
        data = response.json()

        # Check field types
        assert isinstance(data["slack_configured"], bool)
        assert isinstance(data["teams_configured"], bool)
        assert isinstance(data["gmail_configured"], bool)
        assert isinstance(data["environment"], str)
        assert isinstance(data["warnings"], list)

    def test_webhook_security_warnings_content(self, client):
        """Test that webhook warnings are strings."""
        response = client.get("/api/security/webhooks")

        assert response.status_code == 200
        data = response.json()

        # All warnings should be strings
        for warning in data["warnings"]:
            assert isinstance(warning, str)

    def test_security_health_check(self, client):
        """Test security health check endpoint."""
        response = client.get("/api/security/health")

        assert response.status_code == 200
        data = response.json()
        assert "status" in data
        assert "environment" in data
        assert "encryption_enabled" in data

    def test_security_health_check_status_values(self, client):
        """Test security health check status values."""
        response = client.get("/api/security/health")

        assert response.status_code == 200
        data = response.json()

        # Status should be healthy or unhealthy
        assert data["status"] in ["healthy", "unhealthy"]

    def test_security_health_check_encryption_field(self, client):
        """Test security health check encryption field."""
        response = client.get("/api/security/health")

        assert response.status_code == 200
        data = response.json()

        # Encryption enabled should be boolean
        assert isinstance(data["encryption_enabled"], bool)

    @patch.dict(os.environ, {'ENVIRONMENT': 'production'}, clear=False)
    def test_security_configuration_production_env(self, client):
        """Test security configuration in production environment."""
        # Temporarily set production environment
        original_env = os.environ.get('ENVIRONMENT')
        os.environ['ENVIRONMENT'] = 'production'

        try:
            response = client.get("/api/security/configuration")
            assert response.status_code == 200
            data = response.json()
            assert data["config"]["environment"] == "production"
        finally:
            # Restore original environment
            if original_env is not None:
                os.environ['ENVIRONMENT'] = original_env
            else:
                os.environ.pop('ENVIRONMENT', None)

    @patch.dict(os.environ, {'ENVIRONMENT': 'development'}, clear=False)
    def test_security_configuration_development_env(self, client):
        """Test security configuration in development environment."""
        original_env = os.environ.get('ENVIRONMENT')
        os.environ['ENVIRONMENT'] = 'development'

        try:
            response = client.get("/api/security/configuration")
            assert response.status_code == 200
            data = response.json()
            assert data["config"]["environment"] == "development"
        finally:
            if original_env is not None:
                os.environ['ENVIRONMENT'] = original_env
            else:
                os.environ.pop('ENVIRONMENT', None)

    @patch('api.security_routes.get_secret_manager')
    def test_secrets_security_status_mocked(self, mock_get_secret_manager, client):
        """Test secrets security status with mocked secret manager."""
        # Mock the secret manager
        mock_manager = Mock()
        mock_manager.get_security_status.return_value = {
            "encryption_enabled": True,
            "storage_type": "encrypted",
            "secrets_count": 5,
            "environment": "development"
        }
        mock_get_secret_manager.return_value = mock_manager

        response = client.get("/api/security/secrets")

        assert response.status_code == 200
        data = response.json()
        assert data["encryption_enabled"] is True
        assert data["storage_type"] == "encrypted"
        assert data["secrets_count"] == 5

    @patch.dict(os.environ, {
        'SLACK_SIGNING_SECRET': 'test-secret',
        'TEAMS_APP_ID': 'test-app-id',
        'GMAIL_API_KEY': 'test-api-key'
    }, clear=False)
    def test_webhook_security_all_configured(self, client):
        """Test webhook security when all webhooks are configured."""
        original_slack = os.environ.get('SLACK_SIGNING_SECRET')
        original_teams = os.environ.get('TEAMS_APP_ID')
        original_gmail = os.environ.get('GMAIL_API_KEY')

        os.environ['SLACK_SIGNING_SECRET'] = 'test-secret'
        os.environ['TEAMS_APP_ID'] = 'test-app-id'
        os.environ['GMAIL_API_KEY'] = 'test-api-key'

        try:
            response = client.get("/api/security/webhooks")
            assert response.status_code == 200
            data = response.json()
            assert data["slack_configured"] is True
            assert data["teams_configured"] is True
            assert data["gmail_configured"] is True
        finally:
            # Restore original values
            if original_slack is not None:
                os.environ['SLACK_SIGNING_SECRET'] = original_slack
            else:
                os.environ.pop('SLACK_SIGNING_SECRET', None)

            if original_teams is not None:
                os.environ['TEAMS_APP_ID'] = original_teams
            else:
                os.environ.pop('TEAMS_APP_ID', None)

            if original_gmail is not None:
                os.environ['GMAIL_API_KEY'] = original_gmail
            else:
                os.environ.pop('GMAIL_API_KEY', None)

    def test_security_configuration_no_critical_issues(self, client):
        """Test that development environment doesn't have critical issues by default."""
        response = client.get("/api/security/configuration")

        assert response.status_code == 200
        data = response.json()

        # In development, should not have critical issues (only warnings/info)
        # (unless there's a serious misconfiguration)
        if data["config"]["environment"] == "development":
            for issue in data["issues"]:
                if issue["severity"] == "critical":
                    # If there are critical issues in dev, verify they're justified
                    assert issue["issue"] in ["dev_temp_users_enabled"]

    def test_security_endpoints_return_json(self, client):
        """Test that all security endpoints return JSON."""
        endpoints = [
            "/api/security/configuration",
            "/api/security/secrets",
            "/api/security/webhooks",
            "/api/security/health"
        ]

        for endpoint in endpoints:
            response = client.get(endpoint)
            assert response.status_code == 200
            assert response.headers["content-type"].startswith("application/json")

    def test_security_configuration_issues_ordering(self, client):
        """Test that security issues are returned in a consistent order."""
        response1 = client.get("/api/security/configuration")
        response2 = client.get("/api/security/configuration")

        assert response1.status_code == 200
        assert response2.status_code == 200

        data1 = response1.json()
        data2 = response2.json()

        # Issues should be in the same order
        issues1 = [issue["issue"] for issue in data1["issues"]]
        issues2 = [issue["issue"] for issue in data2["issues"]]

        assert issues1 == issues2
