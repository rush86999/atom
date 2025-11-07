"""
ATOM HubSpot Integration Test Suite
Comprehensive testing for HubSpot marketing integration
Following ATOM testing patterns and conventions
"""

import os
import sys
import pytest
import asyncio
from datetime import datetime, timedelta, date
from typing import Dict, Any, Optional
from unittest.mock import Mock, patch, AsyncMock
import json
import aiohttp

# Add project root to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from hubspot_service import create_hubspot_service, HubSpotService, format_hubspot_response
from db_oauth_hubspot import create_hubspot_db_handler, HubSpotOAuthToken, HubSpotUserData, HubSpotPortalData
from auth_handler_hubspot import HubSpotAuthHandler

class TestHubSpotService:
    """Test HubSpot service functionality"""
    
    @pytest.fixture
    def hubspot_service(self):
        """Create HubSpot service instance for testing"""
        return create_hubspot_service()
    
    @pytest.fixture
    def mock_config(self):
        """Mock HubSpot configuration"""
        from hubspot_service import HubSpotConfig
        return HubSpotConfig(
            access_token="test-access-token",
            private_app_token="test-private-token",
            environment="qa"
        )
    
    def test_service_creation(self, hubspot_service):
        """Test HubSpot service creation"""
        assert hubspot_service is not None
        assert isinstance(hubspot_service, HubSpotService)
        assert hubspot_service.config.access_token is not None
    
    def test_config_from_env(self):
        """Test configuration loading from environment"""
        with patch.dict(os.environ, {
            'HUBSPOT_ACCESS_TOKEN': 'test-access-token',
            'HUBSPOT_CLIENT_ID': 'test-client-id',
            'HUBSPOT_CLIENT_SECRET': 'test-client-secret',
            'HUBSPOT_REDIRECT_URI': 'http://localhost:5058/auth/hubspot/callback'
        }):
            service = create_hubspot_service()
            assert service.config.access_token == 'test-access-token'
    
    @pytest.mark.asyncio
    async def test_get_contacts_no_auth(self, hubspot_service):
        """Test getting contacts without authentication should fail"""
        with pytest.raises(Exception):
            await hubspot_service.get_contacts("test-token", limit=10)
    
    @pytest.mark.asyncio
    async def test_get_contacts_with_mock(self, hubspot_service):
        """Test getting contacts with mocked HTTP client"""
        # Mock HTTP response
        mock_response = {
            "results": [
                {"id": "1", "properties": {"email": "test1@example.com"}},
                {"id": "2", "properties": {"email": "test2@example.com"}}
            ],
            "total": 2,
            "paging": None
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.get_contacts("test-token", limit=10)
            
            assert "results" in result
            assert len(result["results"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_contact(self, hubspot_service):
        """Test creating a contact"""
        mock_response = {
            "id": "123",
            "properties": {
                "email": "newcontact@example.com",
                "firstname": "John",
                "lastname": "Doe"
            }
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.create_contact(
                "test-token",
                email="newcontact@example.com",
                first_name="John",
                last_name="Doe"
            )
            
            assert result["id"] == "123"
            assert result["properties"]["email"] == "newcontact@example.com"
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_companies(self, hubspot_service):
        """Test getting companies"""
        mock_response = {
            "results": [
                {"id": "1", "properties": {"name": "Company 1", "domain": "company1.com"}},
                {"id": "2", "properties": {"name": "Company 2", "domain": "company2.com"}}
            ],
            "total": 2,
            "paging": None
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.get_companies("test-token", limit=10)
            
            assert "results" in result
            assert len(result["results"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_company(self, hubspot_service):
        """Test creating a company"""
        mock_response = {
            "id": "456",
            "properties": {
                "name": "New Company",
                "domain": "newcompany.com",
                "industry": "Technology"
            }
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.create_company(
                "test-token",
                name="New Company",
                domain="newcompany.com",
                industry="Technology"
            )
            
            assert result["id"] == "456"
            assert result["properties"]["name"] == "New Company"
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_deals(self, hubspot_service):
        """Test getting deals"""
        mock_response = {
            "results": [
                {"id": "1", "properties": {"dealname": "Deal 1", "amount": "1000.0"}},
                {"id": "2", "properties": {"dealname": "Deal 2", "amount": "2000.0"}}
            ],
            "total": 2,
            "paging": None
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.get_deals("test-token", limit=10)
            
            assert "results" in result
            assert len(result["results"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_deal(self, hubspot_service):
        """Test creating a deal"""
        mock_response = {
            "id": "789",
            "properties": {
                "dealname": "New Deal",
                "amount": "5000.0",
                "dealstage": "appointmentscheduled"
            }
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.create_deal(
                "test-token",
                deal_name="New Deal",
                amount=5000.0
            )
            
            assert result["id"] == "789"
            assert result["properties"]["dealname"] == "New Deal"
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_campaigns(self, hubspot_service):
        """Test getting campaigns"""
        mock_response = {
            "results": [
                {"id": "1", "campaignName": "Campaign 1", "status": "DRAFT"},
                {"id": "2", "campaignName": "Campaign 2", "status": "ACTIVE"}
            ],
            "total": 2,
            "paging": None
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.get_campaigns("test-token", limit=10)
            
            assert "results" in result
            assert len(result["results"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_campaign(self, hubspot_service):
        """Test creating a campaign"""
        mock_response = {
            "id": "101",
            "campaignName": "New Campaign",
            "status": "DRAFT",
            "campaignType": "EMAIL"
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.create_campaign(
                "test-token",
                campaign_name="New Campaign",
                campaign_type="EMAIL"
            )
            
            assert result["id"] == "101"
            assert result["campaignName"] == "New Campaign"
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_pipelines(self, hubspot_service):
        """Test getting pipelines"""
        mock_response = {
            "results": [
                {"id": "1", "label": "Sales Pipeline", "displayOrder": 1},
                {"id": "2", "label": "Support Pipeline", "displayOrder": 2}
            ]
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.get_pipelines("test-token")
            
            assert "results" in result
            assert len(result["results"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_deal_analytics(self, hubspot_service):
        """Test getting deal analytics"""
        mock_response = {
            "total": 100,
            "closed_won": 30,
            "closed_lost": 20,
            "open_deals": 50,
            "total_amount": 500000.0
        }
        
        with patch.object(hubspot_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await hubspot_service.get_deal_analytics("test-token")
            
            assert result["total"] == 100
            assert result["closed_won"] == 30
            assert result["total_amount"] == 500000.0
            mock_request.assert_called_once()
    
    def test_format_hubspot_response(self):
        """Test response formatting"""
        data = {"id": 1, "name": "Test"}
        result = format_hubspot_response(data)
        
        assert result["ok"] is True
        assert result["data"] == data
        assert result["service"] == "hubspot"
        assert "timestamp" in result

class TestHubSpotDBHandler:
    """Test HubSpot database handler"""
    
    @pytest.fixture
    def db_handler_sqlite(self):
        """Create SQLite database handler for testing"""
        with patch.dict(os.environ, {'SQLITE_DB_PATH': ':memory:'}):
            return create_hubspot_db_handler(db_type="sqlite")
    
    @pytest.mark.asyncio
    async def test_save_and_get_tokens(self, db_handler_sqlite):
        """Test saving and retrieving tokens"""
        tokens = HubSpotOAuthToken(
            user_id="test-user",
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            hub_id="12345",
            scopes=["contacts", "companies"]
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
        assert retrieved_tokens.hub_id == "12345"
        assert "contacts" in retrieved_tokens.scopes
        assert "companies" in retrieved_tokens.scopes
    
    @pytest.mark.asyncio
    async def test_save_and_get_user_data(self, db_handler_sqlite):
        """Test saving and retrieving user data"""
        user_data = HubSpotUserData(
            user_id="test-user",
            hub_id="12345",
            user_email="test@example.com",
            user_name="Test User",
            first_name="Test",
            last_name="User",
            is_super_admin=True,
            permissions={"contacts": "read", "deals": "write"}
        )
        
        # Save user data
        result = await db_handler_sqlite.save_user_data(user_data)
        assert result is True
        
        # Get user data
        retrieved_data = await db_handler_sqlite.get_user_data("test-user")
        assert retrieved_data is not None
        assert retrieved_data.user_id == "test-user"
        assert retrieved_data.hub_id == "12345"
        assert retrieved_data.user_email == "test@example.com"
        assert retrieved_data.user_name == "Test User"
        assert retrieved_data.is_super_admin is True
        assert retrieved_data.permissions["contacts"] == "read"
        assert retrieved_data.permissions["deals"] == "write"
    
    @pytest.mark.asyncio
    async def test_save_and_get_portal_data(self, db_handler_sqlite):
        """Test saving and retrieving portal data"""
        portal_data = HubSpotPortalData(
            user_id="test-user",
            portal_id="12345",
            company_name="Test Company",
            domain="testcompany.com",
            currency="USD",
            time_zone="America/New_York"
        )
        
        # Save portal data
        result = await db_handler_sqlite.save_portal_data(portal_data)
        assert result is True
        
        # Get portal data
        retrieved_data = await db_handler_sqlite.get_portal_data("test-user")
        assert retrieved_data is not None
        assert retrieved_data.user_id == "test-user"
        assert retrieved_data.portal_id == "12345"
        assert retrieved_data.company_name == "Test Company"
        assert retrieved_data.domain == "testcompany.com"
        assert retrieved_data.currency == "USD"
        assert retrieved_data.time_zone == "America/New_York"
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, db_handler_sqlite):
        """Test token expiration checking"""
        # Create expired token
        expired_time = datetime.utcnow() - timedelta(hours=2)
        tokens = HubSpotOAuthToken(
            user_id="expired-user",
            access_token="expired-token",
            hub_id="12345",
            updated_at=expired_time,
            expires_in=3600  # 1 hour
        )
        
        await db_handler_sqlite.save_tokens(tokens)
        
        # Check if expired
        is_expired = await db_handler_sqlite.is_token_expired("expired-user")
        assert is_expired is True
        
        # Create fresh token
        fresh_tokens = HubSpotOAuthToken(
            user_id="fresh-user",
            access_token="fresh-token",
            hub_id="12345",
            expires_in=3600
        )
        
        await db_handler_sqlite.save_tokens(fresh_tokens)
        
        # Check if not expired
        is_not_expired = await db_handler_sqlite.is_token_expired("fresh-user")
        assert is_not_expired is False
    
    @pytest.mark.asyncio
    async def test_delete_tokens(self, db_handler_sqlite):
        """Test deleting tokens"""
        tokens = HubSpotOAuthToken(
            user_id="delete-user",
            access_token="delete-token",
            hub_id="12345"
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

class TestHubSpotAuthHandler:
    """Test HubSpot authentication handler"""
    
    @pytest.fixture
    def auth_handler(self):
        """Create auth handler for testing"""
        with patch.dict(os.environ, {
            'HUBSPOT_CLIENT_ID': 'test-client-id',
            'HUBSPOT_CLIENT_SECRET': 'test-client-secret',
            'HUBSPOT_REDIRECT_URI': 'http://localhost:5058/auth/hubspot/callback'
        }):
            return HubSpotAuthHandler()
    
    def test_generate_auth_url(self, auth_handler):
        """Test authorization URL generation"""
        url, state = auth_handler.generate_auth_url("test-user")
        
        assert url is not None
        assert state is not None
        assert "app.hubspot.com/oauth/authorize" in url
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
            "hub_id": "12345",
            "scope": "contacts companies deals"
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await auth_handler.exchange_code_for_tokens("test-code", "test-user:state")
            
            assert result["access_token"] == "test-access-token"
            assert result["refresh_token"] == "test-refresh-token"
            assert result["hub_id"] == "12345"
            assert result["user_id"] == "test-user"
            assert "created_at" in result
    
    @pytest.mark.asyncio
    async def test_get_user_info_mock(self, auth_handler):
        """Test getting user info with mock HTTP response"""
        mock_user_data = {
            "userId": "12345",
            "email": "test@example.com",
            "firstName": "Test",
            "lastName": "User",
            "portalId": "12345",
            "accountType": "STANDARD",
            "timeZone": "America/New_York",
            "currency": "USD",
            "superAdmin": True
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_user_data
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await auth_handler.get_user_info("test-access-token", "12345")
            
            assert result["hub_id"] == "12345"
            assert result["user_email"] == "test@example.com"
            assert result["first_name"] == "Test"
            assert result["last_name"] == "User"
            assert result["super_admin"] is True
    
    @pytest.mark.asyncio
    async def test_refresh_token_mock(self, auth_handler):
        """Test token refresh with mock HTTP response"""
        mock_response_data = {
            "access_token": "new-access-token",
            "refresh_token": "new-refresh-token",
            "token_type": "Bearer",
            "expires_in": 3600,
            "hub_id": "12345"
        }
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_response_data
            mock_post.return_value.__aenter__.return_value = mock_response
            
            result = await auth_handler.refresh_access_token("test-refresh-token")
            
            assert result["access_token"] == "new-access-token"
            assert result["refresh_token"] == "new-refresh-token"
            assert result["hub_id"] == "12345"
            assert "created_at" in result

class TestHubSpotIntegration:
    """Integration tests for HubSpot service"""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment for integration tests"""
        env_vars = {
            'HUBSPOT_CLIENT_ID': 'test-client-id',
            'HUBSPOT_CLIENT_SECRET': 'test-client-secret',
            'HUBSPOT_REDIRECT_URI': 'http://localhost:5058/auth/hubspot/callback',
            'HUBSPOT_ENVIRONMENT': 'qa'
        }
        with patch.dict(os.environ, env_vars):
            yield env_vars
    
    def test_integration_availability(self, mock_env):
        """Test integration availability check"""
        from hubspot_integration_register import check_hubspot_availability
        
        availability = check_hubspot_availability()
        assert availability is True
    
    def test_integration_configuration(self, mock_env):
        """Test integration configuration check"""
        from hubspot_integration_register import check_hubspot_configuration
        
        config_status = check_hubspot_configuration()
        assert config_status is True
    
    def test_service_initialization(self, mock_env):
        """Test service initialization"""
        from hubspot_integration_register import init_hubspot_services
        
        success = init_hubspot_services()
        assert success is True
    
    def test_get_hubspot_info(self, mock_env):
        """Test getting integration information"""
        from hubspot_integration_register import get_hubspot_info
        
        info = get_hubspot_info()
        
        assert info['name'] == 'HubSpot'
        assert info['available'] is True
        assert 'features' in info
        assert 'supported_operations' in info
        assert len(info['features']) > 0
        assert len(info['supported_operations']) > 0

class TestHubSpotEndpoints:
    """Test HubSpot API endpoints"""
    
    @pytest.fixture
    def mock_access_token_and_hub_id(self):
        """Mock access token and hub ID dependency"""
        with patch('hubspot_routes.get_access_token_and_hub_id') as mock:
            mock.return_value = ("test-access-token", "test-hub-id")
            yield mock
    
    @pytest.mark.asyncio
    async def test_get_contacts_endpoint(self, mock_access_token_and_hub_id):
        """Test GET /contacts endpoint"""
        from hubspot_routes import get_contacts
        
        # Mock service call
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.get_contacts.return_value = {"results": []}
            
            result = await get_contacts(
                user_id="test-user",
                limit=10,
                email="test@example.com"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_create_contact_endpoint(self, mock_access_token_and_hub_id):
        """Test POST /contacts endpoint"""
        from hubspot_routes import create_contact
        
        contact_data = {
            "email": "newcontact@example.com",
            "first_name": "John",
            "last_name": "Doe",
            "company": "Test Company",
            "lifecycle_stage": "lead"
        }
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.create_contact.return_value = {"id": "123"}
            
            result = await create_contact(
                contact_data=contact_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Contact created successfully"
    
    @pytest.mark.asyncio
    async def test_get_companies_endpoint(self, mock_access_token_and_hub_id):
        """Test GET /companies endpoint"""
        from hubspot_routes import get_companies
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.get_companies.return_value = {"results": []}
            
            result = await get_companies(
                user_id="test-user",
                limit=10,
                domain="example.com"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_create_company_endpoint(self, mock_access_token_and_hub_id):
        """Test POST /companies endpoint"""
        from hubspot_routes import create_company
        
        company_data = {
            "name": "New Company",
            "domain": "newcompany.com",
            "industry": "Technology",
            "employee_count": 100,
            "annual_revenue": 1000000.0
        }
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.create_company.return_value = {"id": "456"}
            
            result = await create_company(
                company_data=company_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Company created successfully"
    
    @pytest.mark.asyncio
    async def test_get_deals_endpoint(self, mock_access_token_and_hub_id):
        """Test GET /deals endpoint"""
        from hubspot_routes import get_deals
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.get_deals.return_value = {"results": []}
            
            result = await get_deals(
                user_id="test-user",
                limit=10,
                deal_stage="appointmentscheduled"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_create_deal_endpoint(self, mock_access_token_and_hub_id):
        """Test POST /deals endpoint"""
        from hubspot_routes import create_deal
        
        deal_data = {
            "deal_name": "New Deal",
            "amount": 5000.0,
            "pipeline": "default",
            "deal_stage": "appointmentscheduled",
            "contact_id": "123",
            "company_id": "456"
        }
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.create_deal.return_value = {"id": "789"}
            
            result = await create_deal(
                deal_data=deal_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Deal created successfully"
    
    @pytest.mark.asyncio
    async def test_get_campaigns_endpoint(self, mock_access_token_and_hub_id):
        """Test GET /campaigns endpoint"""
        from hubspot_routes import get_campaigns
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.get_campaigns.return_value = {"results": []}
            
            result = await get_campaigns(
                user_id="test-user",
                limit=10,
                status="ACTIVE"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_create_campaign_endpoint(self, mock_access_token_and_hub_id):
        """Test POST /campaigns endpoint"""
        from hubspot_routes import create_campaign
        
        campaign_data = {
            "campaign_name": "New Campaign",
            "subject": "Test Subject",
            "content": "Test Content",
            "status": "DRAFT",
            "campaign_type": "EMAIL"
        }
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.create_campaign.return_value = {"id": "101"}
            
            result = await create_campaign(
                campaign_data=campaign_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Campaign created successfully"
    
    @pytest.mark.asyncio
    async def test_get_pipelines_endpoint(self, mock_access_token_and_hub_id):
        """Test GET /pipelines endpoint"""
        from hubspot_routes import get_pipelines
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.get_pipelines.return_value = {"results": []}
            
            result = await get_pipelines(user_id="test-user")
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_get_deal_analytics_endpoint(self, mock_access_token_and_hub_id):
        """Test GET /analytics/deals endpoint"""
        from hubspot_routes import get_deal_analytics
        
        with patch('hubspot_routes.hubspot_service') as mock_service:
            mock_service.get_deal_analytics.return_value = {"total": 100}
            
            result = await get_deal_analytics(
                user_id="test-user",
                date_from="2024-01-01",
                date_to="2024-12-31"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_save_auth_data_endpoint(self, mock_access_token_and_hub_id):
        """Test POST /auth/save endpoint"""
        from hubspot_routes import save_auth_data
        
        auth_data = {
            "tokens": {
                "access_token": "test-access-token",
                "refresh_token": "test-refresh-token",
                "hub_id": "12345"
            },
            "account_info": {
                "email": "test@example.com",
                "user_name": "Test User"
            },
            "portal_info": {
                "portal_id": "12345",
                "company_name": "Test Company"
            }
        }
        
        with patch('hubspot_routes.db_handler') as mock_db:
            mock_db.save_tokens.return_value = True
            mock_db.save_user_data.return_value = True
            mock_db.save_portal_data.return_value = True
            
            result = await save_auth_data(
                auth_data=auth_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert result["message"] == "Authentication data saved successfully"
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_get_auth_status_endpoint(self):
        """Test GET /auth/status endpoint"""
        from hubspot_routes import get_auth_status
        
        with patch('hubspot_routes.db_handler') as mock_db:
            mock_db.get_tokens.return_value = None
            mock_db.get_user_data.return_value = None
            mock_db.get_portal_data.return_value = None
            mock_db.is_token_expired.return_value = True
            
            result = await get_auth_status(user_id="test-user")
            
            assert result["ok"] is True
            assert "data" in result
            assert result["data"]["authenticated"] is False
            assert result["service"] == "hubspot"
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint"""
        from hubspot_routes import health_check
        
        result = await health_check()
        
        assert result["ok"] is True
        assert "data" in result
        assert result["data"]["service"] == "hubspot"
        assert "status" in result["data"]

# Performance and stress tests
class TestHubSpotPerformance:
    """Performance tests for HubSpot integration"""
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent marketing operations"""
        # Mock service to avoid HTTP calls
        with patch('hubspot_service.create_hubspot_service') as mock_create:
            mock_service = Mock()
            mock_service.get_contacts.return_value = {"results": []}
            mock_service.get_companies.return_value = {"results": []}
            mock_service.get_deals.return_value = {"results": []}
            mock_create.return_value = mock_service
            
            # Run multiple operations concurrently
            tasks = []
            for i in range(10):
                service = create_hubspot_service()
                task = service.get_contacts("test-token", limit=5)
                tasks.append(task)
                task = service.get_companies("test-token", limit=5)
                tasks.append(task)
                task = service.get_deals("test-token", limit=5)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All operations should complete successfully
            assert len(results) == 30
            assert all(isinstance(r, dict) or isinstance(r, Exception) for r in results)
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0

# Error handling tests
class TestHubSpotErrorHandling:
    """Test error handling in HubSpot integration"""
    
    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        """Test handling of invalid credentials"""
        service = create_hubspot_service()
        
        # Mock HTTP client to raise authentication error
        mock_service = Mock()
        mock_service._make_request.side_effect = Exception("Invalid access token")
        service._make_request = mock_service._make_request
        
        with pytest.raises(Exception):
            await service.get_contacts("invalid-token", limit=10)
    
    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeouts"""
        handler = HubSpotAuthHandler()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(Exception):
                await handler.exchange_code_for_tokens("test-code", "test-state")
    
    @pytest.mark.asyncio
    async def test_api_rate_limit(self):
        """Test handling of API rate limits"""
        service = create_hubspot_service()
        
        # Mock HTTP response with rate limit
        mock_service = Mock()
        mock_service._make_request.side_effect = Exception("HubSpot API error: 429 - Rate limit exceeded")
        service._make_request = mock_service._make_request
        
        with pytest.raises(Exception):
            await service.get_contacts("test-token", limit=10)

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])