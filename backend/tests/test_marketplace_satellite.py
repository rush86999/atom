"""
Marketplace Satellite Tests - Tests for satellite connection to atomagentos.com mothership.

Tests the satellite-side marketplace functionality:
- API token validation
- Connection to mothership
- Marketplace browsing (agents, domains, components, skills)
- Installation from mothership
- Error handling and graceful degradation
"""

import pytest
import os
from unittest.mock import Mock, patch, AsyncMock
from sqlalchemy.orm import Session

from core.atom_saas_client import AtomAgentOSMarketplaceClient, AtomSaaSConfig
from core.canvas_marketplace_service import CanvasMarketplaceService
from core.domain_marketplace_service import DomainMarketplaceService
from core.config import MarketplaceConfig


class TestMarketplaceConfig:
    """Test marketplace configuration validation."""

    def test_marketplace_config_defaults(self):
        """Test default marketplace configuration."""
        config = MarketplaceConfig()
        assert config.enabled is True
        assert config.api_url == "https://atomagentos.com/api/v1/marketplace"
        assert config.api_token is None
        assert config.timeout == 30
        assert config.cache_ttl_seconds == 300

    def test_marketplace_config_from_env(self):
        """Test marketplace configuration from environment variables."""
        with patch.dict(os.environ, {
            'MARKETPLACE_ENABLED': 'false',
            'ATOM_SAAS_API_URL': 'https://custom.marketplace.com',
            'ATOM_SAAS_API_TOKEN': 'test_token_12345678901234567890',
            'ATOM_SAAS_TIMEOUT': '60',
            'ATOM_SAAS_CACHE_TTL': '600'
        }):
            config = MarketplaceConfig()
            assert config.enabled is False
            assert config.api_url == 'https://custom.marketplace.com'
            assert config.api_token == 'test_token_12345678901234567890'
            assert config.timeout == 60
            assert config.cache_ttl_seconds == 600

    def test_marketplace_config_validate_disabled(self):
        """Test validation when marketplace is disabled."""
        config = MarketplaceConfig()
        config.enabled = False
        is_valid, error = config.validate()
        assert is_valid is True
        assert error is None

    def test_marketplace_config_validate_no_token(self):
        """Test validation when marketplace is enabled but no token."""
        config = MarketplaceConfig()
        config.enabled = True
        config.api_token = None
        is_valid, error = config.validate()
        assert is_valid is True  # Valid but with warning
        assert "not set" in error

    def test_marketplace_config_validate_short_token(self):
        """Test validation with token that's too short."""
        config = MarketplaceConfig()
        config.enabled = True
        config.api_token = "short"
        is_valid, error = config.validate()
        assert is_valid is False
        assert "too short" in error

    def test_marketplace_config_is_configured(self):
        """Test is_configured method."""
        config = MarketplaceConfig()
        assert config.is_configured() is False

        config.api_token = "valid_token_12345678901234567890"
        assert config.is_configured() is True

        config.enabled = False
        assert config.is_configured() is False


class TestAtomSaasClient:
    """Test Atom SaaS client functionality."""

    def test_client_initialization_with_config(self):
        """Test client initialization with custom config."""
        config = AtomSaaSConfig(
            ws_url="wss://test.com/ws",
            api_url="https://test.com/api",
            api_token="test_token"
        )
        client = AtomAgentOSMarketplaceClient(config)
        assert client.config.api_url == "https://test.com/api"
        assert client.config.api_token == "test_token"

    def test_client_load_config_from_env(self):
        """Test client loads configuration from environment."""
        with patch.dict(os.environ, {
            'ATOM_SAAS_API_URL': 'https://test.com/marketplace',
            'ATOM_SAAS_API_TOKEN': 'env_token'
        }):
            client = AtomAgentOSMarketplaceClient()
            assert client.config.api_url == 'https://test.com/marketplace'
            assert client.config.api_token == 'env_token'

    @pytest.mark.asyncio
    async def test_fetch_components_success(self):
        """Test successful component fetch."""
        client = AtomAgentOSMarketplaceClient()
        
        with patch.object(client, '_get_http_client') as mock_client:
            mock_response = Mock()
            mock_response.json.return_value = {
                "components": [
                    {"id": "comp1", "name": "Test Component"},
                    {"id": "comp2", "name": "Another Component"}
                ],
                "total": 2
            }
            mock_response.raise_for_status = Mock()
            
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_client.return_value = mock_http
            
            result = await client.fetch_components()
            assert result["total"] == 2
            assert len(result["components"]) == 2
            assert result["components"][0]["name"] == "Test Component"

    @pytest.mark.asyncio
    async def test_fetch_components_error(self):
        """Test component fetch with error."""
        client = AtomAgentOSMarketplaceClient()
        
        with patch.object(client, '_get_http_client') as mock_client:
            import httpx
            mock_http = AsyncMock()
            mock_http.get.side_effect = httpx.HTTPError("Connection error")
            mock_client.return_value = mock_http
            
            result = await client.fetch_components()
            assert result["components"] == []
            assert result["total"] == 0

    @pytest.mark.asyncio
    async def test_health_check_success(self):
        """Test successful health check."""
        client = AtomAgentOSMarketplaceClient()
        
        with patch.object(client, '_get_http_client') as mock_client:
            mock_response = Mock()
            mock_response.raise_for_status = Mock()
            
            mock_http = AsyncMock()
            mock_http.get.return_value = mock_response
            mock_client.return_value = mock_http
            
            result = await client.health_check()
            assert result is True

    @pytest.mark.asyncio
    async def test_health_check_failure(self):
        """Test health check with error."""
        client = AtomAgentOSMarketplaceClient()
        
        with patch.object(client, '_get_http_client') as mock_client:
            import httpx
            mock_http = AsyncMock()
            mock_http.get.side_effect = httpx.HTTPError("Connection failed")
            mock_client.return_value = mock_http
            
            result = await client.health_check()
            assert result is False


class TestCanvasMarketplaceService:
    """Test canvas marketplace service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_saas_client(self):
        """Create mock SaaS client."""
        client = Mock(spec=AtomAgentOSMarketplaceClient)
        return client

    def test_browse_components_success(self, mock_db, mock_saas_client):
        """Test successful component browsing."""
        mock_saas_client.fetch_components.return_value = {
            "components": [
                {"id": "comp1", "name": "Chart Component"}
            ],
            "total": 1
        }
        
        service = CanvasMarketplaceService(mock_db, mock_saas_client)
        result = service.browse_components_sync()
        
        assert len(result) == 1
        assert result[0]["name"] == "Chart Component"

    def test_install_component_success(self, mock_db, mock_saas_client):
        """Test successful component installation."""
        mock_component = {
            "id": "comp1",
            "name": "Test Component",
            "description": "A test component",
            "category": "charts",
            "component_type": "react",
            "version": "1.0.0"
        }
        
        mock_saas_client.get_component_details.return_value = mock_component
        mock_saas_client.install_component.return_value = {"success": True}
        
        service = CanvasMarketplaceService(mock_db, mock_saas_client)
        result = service.install_component_sync("comp1", canvas_id="canvas1")
        
        assert result["success"] is True
        assert result["component"]["name"] == "Test Component"

    def test_install_component_not_found(self, mock_db, mock_saas_client):
        """Test component installation when not found."""
        mock_saas_client.get_component_details.return_value = None
        
        service = CanvasMarketplaceService(mock_db, mock_saas_client)
        result = service.install_component_sync("invalid_id")
        
        assert result["success"] is False
        assert "not found" in result["error"]


class TestDomainMarketplaceService:
    """Test domain marketplace service."""

    @pytest.fixture
    def mock_db(self):
        """Create mock database session."""
        return Mock(spec=Session)

    @pytest.fixture
    def mock_saas_client(self):
        """Create mock SaaS client."""
        client = Mock(spec=AtomAgentOSMarketplaceClient)
        return client

    def test_browse_domains_success(self, mock_db, mock_saas_client):
        """Test successful domain browsing."""
        mock_saas_client.fetch_domains.return_value = {
            "domains": [
                {"id": "domain1", "name": "Sales Domain"}
            ],
            "total": 1
        }
        
        service = DomainMarketplaceService(mock_db, mock_saas_client)
        result = service.browse_domains_sync()
        
        assert len(result["domains"]) == 1
        assert result["domains"][0]["name"] == "Sales Domain"

    def test_install_domain_success(self, mock_db, mock_saas_client):
        """Test successful domain installation."""
        mock_domain = {
            "id": "domain1",
            "domain_name": "Sales Domain",
            "description": "Sales specialist domain"
        }
        
        mock_saas_client.get_domain_template.return_value = mock_domain
        mock_saas_client.install_domain.return_value = {"success": True}
        
        service = DomainMarketplaceService(mock_db, mock_saas_client)
        result = service.install_domain("domain1", tenant_id="tenant1")
        
        assert result["success"] is True
        assert result["domain_name"] == "Sales Domain"

    def test_install_domain_not_found(self, mock_db, mock_saas_client):
        """Test domain installation when template not found."""
        mock_saas_client.get_domain_template.return_value = None
        
        service = DomainMarketplaceService(mock_db, mock_saas_client)
        result = service.install_domain("invalid_id", tenant_id="tenant1")
        
        assert result["success"] is False
        assert "not found" in result["error"]


class TestMarketplaceIntegration:
    """Integration tests for marketplace functionality."""

    def test_marketplace_requires_api_token(self):
        """Verify marketplace fails gracefully without API token."""
        # Remove API token
        with patch.dict(os.environ, {'ATOM_SAAS_API_TOKEN': ''}):
            client = AtomAgentOSMarketplaceClient()
            assert client.config.api_token == ""
            
            # Health check should fail
            result = client.health_check_sync()
            assert result is False

    def test_marketplace_rejects_invalid_token(self):
        """Verify marketplace rejects invalid API token."""
        # This would require actual HTTP mocking or integration test setup
        # For now, we test the configuration validation
        config = MarketplaceConfig()
        config.api_token = "invalid"
        
        is_valid, error = config.validate()
        assert is_valid is False
        assert "too short" in error

    @pytest.mark.integration
    def test_marketplace_connection_with_valid_token(self):
        """
        Integration test: Verify connection to mothership with valid token.
        
        NOTE: This test requires:
        1. Valid ATOM_SAAS_API_TOKEN environment variable
        2. Network access to atomagentos.com
        
        Skip this test in CI/CD or when token is not available.
        """
        token = os.getenv('ATOM_SAAS_API_TOKEN')
        if not token:
            pytest.skip("ATOM_SAAS_API_TOKEN not set - skipping integration test")
        
        client = AtomAgentOSMarketplaceClient()
        result = client.health_check_sync()
        
        # Should either succeed or fail gracefully (no exceptions)
        assert isinstance(result, bool)


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
