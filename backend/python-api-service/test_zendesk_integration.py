"""
ATOM Zendesk Integration Test Suite
Comprehensive testing for Zendesk integration
Following ATOM testing patterns and conventions
"""

import os
import sys
import pytest
import asyncio
from datetime import datetime, timedelta
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
import json
import aiohttp

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from zendesk_service import create_zendesk_service, ZendeskServiceEnhanced, format_zendesk_response
from db_oauth_zendesk import create_zendesk_db_handler, ZendeskOAuthToken, ZendeskUserData
from auth_handler_zendesk import ZendeskAuthHandler
from zendesk_routes import router, get_access_token

class TestZendeskService:
    """Test Zendesk service functionality"""
    
    @pytest.fixture
    def zendesk_service(self):
        """Create Zendesk service instance for testing"""
        return create_zendesk_service()
    
    @pytest.fixture
    def mock_config(self):
        """Mock Zendesk configuration"""
        from zendesk_service import ZendeskConfig
        return ZendeskConfig(
            subdomain="test-subdomain",
            email="test@example.com",
            token="test-token",
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:5058/auth/zendesk/callback"
        )
    
    def test_service_creation(self, zendesk_service):
        """Test Zendesk service creation"""
        assert zendesk_service is not None
        assert isinstance(zendesk_service, ZendeskServiceEnhanced)
        assert zendesk_service.config.subdomain is not None
    
    def test_config_from_env(self):
        """Test configuration loading from environment"""
        with patch.dict(os.environ, {
            'ZENDESK_SUBDOMAIN': 'test-subdomain',
            'ZENDESK_EMAIL': 'test@example.com',
            'ZENDESK_TOKEN': 'test-token'
        }):
            service = create_zendesk_service()
            assert service.config.subdomain == 'test-subdomain'
            assert service.config.email == 'test@example.com'
            assert service.config.token == 'test-token'
    
    @pytest.mark.asyncio
    async def test_get_tickets_no_auth(self, zendesk_service):
        """Test getting tickets without authentication should fail"""
        with pytest.raises(Exception):
            await zendesk_service.get_tickets()
    
    @pytest.mark.asyncio
    async def test_get_tickets_with_zenpy_mock(self, zendesk_service):
        """Test getting tickets with mocked Zenpy client"""
        # Mock Zenpy client
        mock_client = Mock()
        mock_ticket = Mock()
        mock_ticket.id = 1
        mock_ticket.subject = "Test Ticket"
        mock_ticket.status = "open"
        mock_client.tickets.return_value = [mock_ticket]
        
        zendesk_service._zenpy_client = mock_client
        
        result = await zendesk_service.get_tickets()
        assert "tickets" in result
        assert len(result["tickets"]) == 1
        assert result["tickets"][0].id == 1
    
    @pytest.mark.asyncio
    async def test_create_ticket(self, zendesk_service):
        """Test creating a ticket"""
        mock_client = Mock()
        mock_ticket = Mock()
        mock_ticket.id = 123
        mock_ticket.subject = "New Ticket"
        
        mock_result = Mock()
        mock_result.ticket = mock_ticket
        mock_client.tickets.create.return_value = mock_result
        
        zendesk_service._zenpy_client = mock_client
        
        result = await zendesk_service.create_ticket(
            subject="Test Subject",
            comment="Test Comment"
        )
        
        assert "ticket" in result
        assert result["ticket"].id == 123
        mock_client.tickets.create.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_update_ticket(self, zendesk_service):
        """Test updating a ticket"""
        mock_client = Mock()
        mock_ticket = Mock()
        mock_ticket.id = 123
        mock_ticket.status = "open"
        
        mock_result = Mock()
        mock_result.ticket = mock_ticket
        mock_client.tickets.update.return_value = mock_result
        
        zendesk_service._zenpy_client = mock_client
        
        result = await zendesk_service.update_ticket(
            ticket_id=123,
            status="solved"
        )
        
        assert "ticket" in result
        assert result["ticket"].id == 123
        mock_client.tickets.update.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_search_tickets(self, zendesk_service):
        """Test searching tickets"""
        mock_client = Mock()
        mock_ticket = Mock()
        mock_ticket.id = 1
        mock_ticket.subject = "Search Result"
        mock_client.search.return_value = [mock_ticket]
        
        zendesk_service._zenpy_client = mock_client
        
        result = await zendesk_service.search_tickets(query="test")
        
        assert "tickets" in result
        assert "count" in result
        assert len(result["tickets"]) == 1
        mock_client.search.assert_called_once_with("test", type='ticket')
    
    def test_format_zendesk_response(self):
        """Test response formatting"""
        data = {"id": 1, "subject": "Test"}
        result = format_zendesk_response(data)
        
        assert result["ok"] is True
        assert result["data"] == data
        assert result["service"] == "zendesk"
        assert "timestamp" in result

class TestZendeskDBHandler:
    """Test Zendesk database handler"""
    
    @pytest.fixture
    def db_handler_sqlite(self):
        """Create SQLite database handler for testing"""
        with patch.dict(os.environ, {'SQLITE_DB_PATH': ':memory:'}):
            return create_zendesk_db_handler(db_type="sqlite")
    
    @pytest.mark.asyncio
    async def test_save_and_get_tokens(self, db_handler_sqlite):
        """Test saving and retrieving tokens"""
        tokens = ZendeskOAuthToken(
            user_id="test-user",
            access_token="test-access-token",
            refresh_token="test-refresh-token"
        )
        
        # Save tokens
        result = await db_handler_sqlite.save_tokens(tokens)
        assert result is True
        
        # Get tokens
        retrieved_tokens = await db_handler_sqlite.get_tokens("test-user")
        assert retrieved_tokens is not None
        assert retrieved_tokens.user_id == "test-user"
        assert retrieved_tokens.access_token == "test-access-token"
        assert retrieved_tokens.refresh_token == "test-refresh-token"
    
    @pytest.mark.asyncio
    async def test_save_and_get_user_data(self, db_handler_sqlite):
        """Test saving and retrieving user data"""
        user_data = ZendeskUserData(
            user_id="test-user",
            zendesk_user_id=123,
            email="test@example.com",
            name="Test User",
            role="agent"
        )
        
        # Save user data
        result = await db_handler_sqlite.save_user_data(user_data)
        assert result is True
        
        # Get user data
        retrieved_data = await db_handler_sqlite.get_user_data("test-user")
        assert retrieved_data is not None
        assert retrieved_data.user_id == "test-user"
        assert retrieved_data.zendesk_user_id == 123
        assert retrieved_data.email == "test@example.com"
        assert retrieved_data.name == "Test User"
        assert retrieved_data.role == "agent"
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, db_handler_sqlite):
        """Test token expiration checking"""
        # Create expired token
        expired_time = datetime.utcnow() - timedelta(hours=2)
        tokens = ZendeskOAuthToken(
            user_id="expired-user",
            access_token="expired-token",
            updated_at=expired_time,
            expires_in=3600  # 1 hour
        )
        
        await db_handler_sqlite.save_tokens(tokens)
        
        # Check if expired
        is_expired = await db_handler_sqlite.is_token_expired("expired-user")
        assert is_expired is True
        
        # Create fresh token
        fresh_tokens = ZendeskOAuthToken(
            user_id="fresh-user",
            access_token="fresh-token",
            expires_in=3600
        )
        
        await db_handler_sqlite.save_tokens(fresh_tokens)
        
        # Check if not expired
        is_not_expired = await db_handler_sqlite.is_token_expired("fresh-user")
        assert is_not_expired is False
    
    @pytest.mark.asyncio
    async def test_delete_tokens(self, db_handler_sqlite):
        """Test deleting tokens"""
        tokens = ZendeskOAuthToken(
            user_id="delete-user",
            access_token="delete-token"
        )
        
        # Save tokens first
        await db_handler_sqlite.save_tokens(tokens)
        
        # Verify saved
        saved_tokens = await db_handler_sqlite.get_tokens("delete-user")
        assert saved_tokens is not None
        
        # Delete tokens
        result = await db_handler_sqlite.delete_tokens("delete-user")
        assert result is True
        
        # Verify deleted
        deleted_tokens = await db_handler_sqlite.get_tokens("delete-user")
        assert deleted_tokens is None

class TestZendeskAuthHandler:
    """Test Zendesk authentication handler"""
    
    @pytest.fixture
    def auth_handler(self):
        """Create auth handler for testing"""
        with patch.dict(os.environ, {
            'ZENDESK_CLIENT_ID': 'test-client-id',
            'ZENDESK_CLIENT_SECRET': 'test-client-secret',
            'ZENDESK_SUBDOMAIN': 'test-subdomain',
            'ZENDESK_REDIRECT_URI': 'http://localhost:5058/auth/zendesk/callback'
        }):
            return ZendeskAuthHandler()
    
    def test_generate_auth_url(self, auth_handler):
        """Test authorization URL generation"""
        url, state = auth_handler.generate_auth_url("test-user")
        
        assert url is not None
        assert state is not None
        assert "test-subdomain.zendesk.com" in url
        assert "test-client-id" in url
        assert "test-user" in state
    
    def test_validate_state(self, auth_handler):
        """Test state validation"""
        valid_state = auth_handler.generate_auth_url("test-user")[1]
        
        # Valid state should match
        assert auth_handler.validate_state(valid_state, valid_state) is True
        
        # Invalid state should not match
        assert auth_handler.validate_state("invalid", valid_state) is False
        
        # Empty states should not match
        assert auth_handler.validate_state("", valid_state) is False
        assert auth_handler.validate_state(valid_state, "") is False
    
    @pytest.mark.asyncio
    async def test_exchange_code_for_tokens_mock(self, auth_handler):
        """Test code exchange with mock HTTP response"""
        mock_response_data = {
            "access_token": "test-access-token",
            "refresh_token": "test-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "scope": "tickets:read tickets:write"
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await auth_handler.exchange_code_for_tokens("test-code", "test-user:state")
            
            assert result["access_token"] == "test-access-token"
            assert result["refresh_token"] == "test-refresh-token"
            assert result["user_id"] == "test-user"
            assert "created_at" in result
    
    @pytest.mark.asyncio
    async def test_get_user_info_mock(self, auth_handler):
        """Test getting user info with mock HTTP response"""
        mock_user_data = {
            "user": {
                "id": 123,
                "email": "test@example.com",
                "name": "Test User",
                "role": "agent",
                "organization_id": 456
            }
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_user_data
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await auth_handler.get_user_info("test-access-token")
            
            assert result["id"] == 123
            assert result["email"] == "test@example.com"
            assert result["name"] == "Test User"
            assert result["role"] == "agent"
            assert result["organization_id"] == 456

class TestZendeskIntegration:
    """Integration tests for Zendesk service"""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment for integration tests"""
        env_vars = {
            'ZENDESK_SUBDOMAIN': 'test-subdomain',
            'ZENDESK_EMAIL': 'test@example.com',
            'ZENDESK_TOKEN': 'test-token',
            'ZENDESK_CLIENT_ID': 'test-client-id',
            'ZENDESK_CLIENT_SECRET': 'test-client-secret',
            'ZENDESK_REDIRECT_URI': 'http://localhost:5058/auth/zendesk/callback'
        }
        with patch.dict(os.environ, env_vars):
            yield env_vars
    
    def test_integration_availability(self, mock_env):
        """Test integration availability check"""
        from zendesk_integration_register import check_zendesk_availability
        
        availability = check_zendesk_availability()
        assert availability is True
    
    def test_integration_configuration(self, mock_env):
        """Test integration configuration check"""
        from zendesk_integration_register import check_zendesk_configuration
        
        config_status = check_zendesk_configuration()
        assert config_status is True
    
    def test_service_initialization(self, mock_env):
        """Test service initialization"""
        from zendesk_integration_register import init_zendesk_services
        
        success = init_zendesk_services()
        assert success is True
    
    def test_get_zendesk_info(self, mock_env):
        """Test getting integration information"""
        from zendesk_integration_register import get_zendesk_info
        
        info = get_zendesk_info()
        
        assert info['name'] == 'Zendesk'
        assert info['available'] is True
        assert 'features' in info
        assert 'supported_operations' in info
        assert len(info['features']) > 0
        assert len(info['supported_operations']) > 0
    
    def test_validate_configuration(self, mock_env):
        """Test configuration validation"""
        from zendesk_integration_register import validate_zendesk_configuration
        
        validation = validate_zendesk_configuration()
        
        assert validation['valid'] is True
        assert validation['configured'] is True
        assert validation['has_oauth'] is True
        assert len(validation['issues']) == 0

class TestZendeskEndpoints:
    """Test Zendesk API endpoints"""
    
    @pytest.fixture
    def mock_access_token(self):
        """Mock access token dependency"""
        with patch('zendesk_routes.get_access_token') as mock:
            mock.return_value = "test-access-token"
            yield mock
    
    @pytest.mark.asyncio
    async def test_get_tickets_endpoint(self, mock_access_token):
        """Test GET /tickets endpoint"""
        from zendesk_routes import get_tickets
        
        # Mock the service call
        with patch('zendesk_routes.zendesk_service') as mock_service:
            mock_service.get_tickets.return_value = {"tickets": []}
            
            result = await get_tickets(
                user_id="test-user",
                limit=10,
                status="open"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "zendesk"
    
    @pytest.mark.asyncio
    async def test_create_ticket_endpoint(self, mock_access_token):
        """Test POST /tickets endpoint"""
        from zendesk_routes import create_ticket
        
        ticket_data = {
            "subject": "Test Ticket",
            "comment": "This is a test ticket",
            "priority": "high"
        }
        
        with patch('zendesk_routes.zendesk_service') as mock_service:
            mock_service.create_ticket.return_value = {"ticket": {"id": 123}}
            
            result = await create_ticket(
                ticket_data=ticket_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Ticket created successfully"
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint"""
        from zendesk_routes import health_check
        
        result = await health_check()
        
        assert result["ok"] is True
        assert "data" in result
        assert result["data"]["service"] == "zendesk"
        assert "status" in result["data"]

# Performance and stress tests
class TestZendeskPerformance:
    """Performance tests for Zendesk integration"""
    
    @pytest.mark.asyncio
    async def test_concurrent_ticket_operations(self):
        """Test concurrent ticket operations"""
        service = create_zendesk_service()
        
        # Mock the Zenpy client
        mock_client = Mock()
        mock_client.tickets.return_value = []
        mock_client.search.return_value = []
        service._zenpy_client = mock_client
        
        # Run multiple operations concurrently
        tasks = []
        for i in range(10):
            task = service.get_tickets(limit=5)
            tasks.append(task)
            task = service.search_tickets(f"query-{i}")
            tasks.append(task)
        
        results = await asyncio.gather(*tasks, return_exceptions=True)
        
        # All operations should complete successfully
        assert len(results) == 20
        assert all(isinstance(r, dict) or isinstance(r, Exception) for r in results)
        exceptions = [r for r in results if isinstance(r, Exception)]
        assert len(exceptions) == 0

# Error handling tests
class TestZendeskErrorHandling:
    """Test error handling in Zendesk integration"""
    
    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        """Test handling of invalid credentials"""
        service = create_zendesk_service()
        
        # Mock Zenpy client to raise authentication error
        mock_client = Mock()
        mock_client.tickets.side_effect = Exception("Invalid credentials")
        service._zenpy_client = mock_client
        
        with pytest.raises(Exception):
            await service.get_tickets()
    
    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeouts"""
        handler = ZendeskAuthHandler()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(Exception):
                await handler.exchange_code_for_tokens("test-code", "test-state")
    
    @pytest.mark.asyncio
    async def test_api_rate_limit(self):
        """Test handling of API rate limits"""
        service = create_zendesk_service()
        
        # Mock HTTP response with rate limit
        with patch.object(service, '_make_rest_request') as mock_request:
            mock_request.side_effect = Exception("Rate limit exceeded")
            
            with pytest.raises(Exception):
                await service.get_tickets(access_token="test-token")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])