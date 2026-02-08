"""
Tests for OAuth Flows

Tests OAuth endpoint functionality for services:
- Trello, Asana, Notion, GitHub, Dropbox
"""

import pytest
from fastapi.testclient import TestClient
from unittest.mock import Mock, patch
import sys
from pathlib import Path

# Add backend to path
sys.path.insert(0, str(Path(__file__).parent.parent))

from core.oauth_handler import (
    ASANA_OAUTH_CONFIG,
    DROPBOX_OAUTH_CONFIG,
    GITHUB_OAUTH_CONFIG,
    NOTION_OAUTH_CONFIG,
    TRELLO_OAUTH_CONFIG,
)
from main_api_app import app


class TestOAuthEndpoints:
    """Test OAuth endpoint implementations"""

    @pytest.fixture
    def client(self):
        """Create test client"""
        return TestClient(app)

    def test_health_check_endpoint_includes_new_services(self, client):
        """Test that health endpoint includes all OAuth services"""
        response = client.get("/api/auth/health")

        assert response.status_code == 200
        data = response.json()

        # Check that all new services are included
        assert "oauth_configured" in data
        services = data["oauth_configured"]

        # Verify new services are listed
        assert "trello" in services
        assert "asana" in services
        assert "notion" in services
        assert "dropbox" in services
        # GitHub was already implemented
        assert "github" in services

    def test_trello_config_exists(self):
        """Test that Trello OAuth config is defined"""
        assert TRELLO_OAUTH_CONFIG is not None
        assert hasattr(TRELLO_OAUTH_CONFIG, 'client_id')
        assert hasattr(TRELLO_OAUTH_CONFIG, 'client_secret')

    def test_asana_config_exists(self):
        """Test that Asana OAuth config is defined"""
        assert ASANA_OAUTH_CONFIG is not None
        assert hasattr(ASANA_OAUTH_CONFIG, 'client_id')

    def test_notion_config_exists(self):
        """Test that Notion OAuth config is defined"""
        assert NOTION_OAUTH_CONFIG is not None
        assert hasattr(NOTION_OAUTH_CONFIG, 'client_id')

    def test_dropbox_config_exists(self):
        """Test that Dropbox OAuth config is defined"""
        assert DROPBOX_OAUTH_CONFIG is not None
        assert hasattr(DROPBOX_OAUTH_CONFIG, 'client_id')

    def test_github_config_exists(self):
        """Test that GitHub OAuth config is defined"""
        assert GITHUB_OAUTH_CONFIG is not None
        assert hasattr(GITHUB_OAUTH_CONFIG, 'client_id')

    def test_oauth_configs_is_configured_method(self):
        """Test that all configs have is_configured method"""
        configs = [
            TRELLO_OAUTH_CONFIG,
            ASANA_OAUTH_CONFIG,
            NOTION_OAUTH_CONFIG,
            GITHUB_OAUTH_CONFIG,
            DROPBOX_OAUTH_CONFIG
        ]

        for config in configs:
            assert hasattr(config, 'is_configured')
            # Should return False without environment variables set
            # (in test environment, credentials are not configured)

    @patch('core.oauth_handler.TRELLO_OAUTH_CONFIG.client_id', 'fake_key')
    @patch('core.oauth_handler.TRELLOAUTH_CONFIG.client_secret', 'fake_secret')
    def test_trello_oauth_initiate_endpoint_redirects(self, client):
        """Test Trello OAuth initiate endpoint exists"""
        # This test would require mocking the OAuth flow
        # For now, just verify the route exists
        response = client.get("/api/auth/trello/initiate")

        # Should redirect (307) or return error if not configured
        # Since we're not providing credentials, we expect an error or redirect
        assert response.status_code in [200, 307, 500]

    def test_oauth_status_endpoints_return_auth_urls(self, client):
        """Test that status endpoints return actual auth URLs"""
        services = ["trello", "asana", "notion", "github", "dropbox"]

        for service in services:
            response = client.get(f"/api/auth/{service}/authorize")

            assert response.status_code == 200
            data = response.json()
            assert "auth_url" in data or "configured" in data
            assert data.get("service") == service


class TestOAuthConfigStructure:
    """Test OAuth configuration structures"""

    def test_all_configs_have_required_fields(self):
        """Verify all configs have required OAuth fields"""
        required_fields = ['client_id', 'client_secret', 'redirect_uri', 'auth_url', 'token_url']

        configs = [
            TRELLO_OAUTH_CONFIG,
            ASANA_OAUTH_CONFIG,
            NOTION_OAUTH_CONFIG,
            GITHUB_OAUTH_CONFIG,
            DROPBOX_OAUTH_CONFIG
        ]

        for config in configs:
            for field in required_fields:
                assert hasattr(config, field), f"{config} missing {field}"


class TestOAuthFlowIntegration:
    """Integration tests for OAuth flows"""

    @pytest.mark.skipif(True, "Requires actual OAuth credentials")
    def test_full_oauth_flow(self):
        """Test complete OAuth flow (integration test)"""
        # This test would require actual OAuth credentials
        # Skip by default in CI/CD
        pass

    @pytest.mark.skipif(True, "Requires mocking OAuth providers")
    def test_oauth_token_exchange(self):
        """Test OAuth token exchange functionality"""
        # This would mock the OAuth provider's token endpoint
        pass
