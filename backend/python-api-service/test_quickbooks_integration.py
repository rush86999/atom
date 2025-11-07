"""
ATOM QuickBooks Integration Test Suite
Comprehensive testing for QuickBooks integration
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

from quickbooks_service import create_quickbooks_service, QuickBooksService, format_quickbooks_response
from db_oauth_quickbooks import create_quickbooks_db_handler, QuickBooksOAuthToken, QuickBooksUserData
from auth_handler_quickbooks import QuickBooksAuthHandler

class TestQuickBooksService:
    """Test QuickBooks service functionality"""
    
    @pytest.fixture
    def quickbooks_service(self):
        """Create QuickBooks service instance for testing"""
        return create_quickbooks_service()
    
    @pytest.fixture
    def mock_config(self):
        """Mock QuickBooks configuration"""
        from quickbooks_service import QuickBooksConfig
        return QuickBooksConfig(
            client_id="test-client-id",
            client_secret="test-client-secret",
            redirect_uri="http://localhost:5058/auth/quickbooks/callback",
            environment="sandbox"
        )
    
    def test_service_creation(self, quickbooks_service):
        """Test QuickBooks service creation"""
        assert quickbooks_service is not None
        assert isinstance(quickbooks_service, QuickBooksService)
        assert quickbooks_service.config.client_id is not None
    
    def test_config_from_env(self):
        """Test configuration loading from environment"""
        with patch.dict(os.environ, {
            'QUICKBOOKS_CLIENT_ID': 'test-client-id',
            'QUICKBOOKS_CLIENT_SECRET': 'test-client-secret',
            'QUICKBOOKS_REDIRECT_URI': 'http://localhost:5058/auth/quickbooks/callback'
        }):
            service = create_quickbooks_service()
            assert service.config.client_id == 'test-client-id'
            assert service.config.client_secret == 'test-client-secret'
            assert service.config.redirect_uri == 'http://localhost:5058/auth/quickbooks/callback'
    
    @pytest.mark.asyncio
    async def test_get_invoices_no_auth(self, quickbooks_service):
        """Test getting invoices without authentication should fail"""
        with pytest.raises(Exception):
            await quickbooks_service.get_invoices("test-token", "test-realm")
    
    @pytest.mark.asyncio
    async def test_get_invoices_with_mock(self, quickbooks_service):
        """Test getting invoices with mocked HTTP client"""
        # Mock HTTP response
        mock_response = {
            "QueryResponse": {
                "Invoice": [
                    {"Id": "1", "TotalAmt": 100.0},
                    {"Id": "2", "TotalAmt": 200.0}
                ]
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await quickbooks_service.get_invoices("test-token", "test-realm")
            
            assert "QueryResponse" in result
            assert len(result["QueryResponse"]["Invoice"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_invoice(self, quickbooks_service):
        """Test creating an invoice"""
        mock_response = {
            "Invoice": {
                "Id": "123",
                "TotalAmt": 500.0,
                "CustomerRef": {"value": "customer-1"}
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            line_items = [
                {
                    "Amount": 500.0,
                    "Description": "Test Service",
                    "DetailType": "SalesItemLineDetail",
                    "SalesItemLineDetail": {"ItemRef": {"value": "item-1"}}
                }
            ]
            
            result = await quickbooks_service.create_invoice(
                "test-token",
                "test-realm",
                "customer-1",
                line_items
            )
            
            assert "Invoice" in result
            assert result["Invoice"]["Id"] == "123"
            assert result["Invoice"]["TotalAmt"] == 500.0
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_customers(self, quickbooks_service):
        """Test getting customers"""
        mock_response = {
            "QueryResponse": {
                "Customer": [
                    {"Id": "1", "DisplayName": "Test Customer 1"},
                    {"Id": "2", "DisplayName": "Test Customer 2"}
                ]
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await quickbooks_service.get_customers("test-token", "test-realm")
            
            assert "QueryResponse" in result
            assert len(result["QueryResponse"]["Customer"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_customer(self, quickbooks_service):
        """Test creating a customer"""
        mock_response = {
            "Customer": {
                "Id": "456",
                "DisplayName": "New Customer",
                "PrimaryEmailAddr": {"Address": "test@example.com"}
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await quickbooks_service.create_customer(
                "test-token",
                "test-realm",
                "New Customer",
                "test@example.com"
            )
            
            assert "Customer" in result
            assert result["Customer"]["Id"] == "456"
            assert result["Customer"]["DisplayName"] == "New Customer"
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_expenses(self, quickbooks_service):
        """Test getting expenses"""
        mock_response = {
            "QueryResponse": {
                "Purchase": [
                    {"Id": "1", "TotalAmt": 50.0, "Desc": "Office Supplies"},
                    {"Id": "2", "TotalAmt": 75.0, "Desc": "Software License"}
                ]
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await quickbooks_service.get_expenses("test-token", "test-realm")
            
            assert "QueryResponse" in result
            assert len(result["QueryResponse"]["Purchase"]) == 2
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_create_expense(self, quickbooks_service):
        """Test creating an expense"""
        mock_response = {
            "Purchase": {
                "Id": "789",
                "TotalAmt": 150.0,
                "Desc": "Test Expense",
                "AccountRef": {"value": "account-1"}
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await quickbooks_service.create_expense(
                "test-token",
                "test-realm",
                "account-1",
                150.0,
                "Test Expense"
            )
            
            assert "Purchase" in result
            assert result["Purchase"]["Id"] == "789"
            assert result["Purchase"]["TotalAmt"] == 150.0
            mock_request.assert_called_once()
    
    @pytest.mark.asyncio
    async def test_get_profit_and_loss(self, quickbooks_service):
        """Test getting profit and loss report"""
        mock_response = {
            "ProfitAndLoss": {
                "Columns": [
                    {"ColType": "Account", "ColKey": "Account"},
                    {"ColType": "Total", "ColKey": "Total"}
                ],
                "Rows": [
                    {"Header": {"ColData": [{"value": "Income"}], "type": "Header"}},
                    {"ColData": [{"value": "Sales Revenue"}, {"value": 1000.0}]},
                    {"Header": {"ColData": [{"value": "Expenses"}], "type": "Header"}},
                    {"ColData": [{"value": "Operating Costs"}, {"value": 500.0}]}
                ]
            }
        }
        
        with patch.object(quickbooks_service, '_make_request') as mock_request:
            mock_request.return_value = mock_response
            
            result = await quickbooks_service.get_profit_and_loss("test-token", "test-realm")
            
            assert "ProfitAndLoss" in result
            assert "Columns" in result["ProfitAndLoss"]
            assert "Rows" in result["ProfitAndLoss"]
            mock_request.assert_called_once()
    
    def test_format_quickbooks_response(self):
        """Test response formatting"""
        data = {"id": 1, "total": 100.0}
        result = format_quickbooks_response(data)
        
        assert result["ok"] is True
        assert result["data"] == data
        assert result["service"] == "quickbooks"
        assert "timestamp" in result

class TestQuickBooksDBHandler:
    """Test QuickBooks database handler"""
    
    @pytest.fixture
    def db_handler_sqlite(self):
        """Create SQLite database handler for testing"""
        with patch.dict(os.environ, {'SQLITE_DB_PATH': ':memory:'}):
            return create_quickbooks_db_handler(db_type="sqlite")
    
    @pytest.mark.asyncio
    async def test_save_and_get_tokens(self, db_handler_sqlite):
        """Test saving and retrieving tokens"""
        tokens = QuickBooksOAuthToken(
            user_id="test-user",
            access_token="test-access-token",
            refresh_token="test-refresh-token",
            realm_id="test-realm-id"
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
        assert retrieved_tokens.realm_id == "test-realm-id"
    
    @pytest.mark.asyncio
    async def test_save_and_get_user_data(self, db_handler_sqlite):
        """Test saving and retrieving user data"""
        user_data = QuickBooksUserData(
            user_id="test-user",
            realm_id="test-realm-id",
            company_name="Test Company",
            legal_name="Test Company LLC",
            email="test@example.com"
        )
        
        # Save user data
        result = await db_handler_sqlite.save_user_data(user_data)
        assert result is True
        
        # Get user data
        retrieved_data = await db_handler_sqlite.get_user_data("test-user")
        assert retrieved_data is not None
        assert retrieved_data.user_id == "test-user"
        assert retrieved_data.realm_id == "test-realm-id"
        assert retrieved_data.company_name == "Test Company"
        assert retrieved_data.legal_name == "Test Company LLC"
        assert retrieved_data.email == "test@example.com"
    
    @pytest.mark.asyncio
    async def test_token_expiration(self, db_handler_sqlite):
        """Test token expiration checking"""
        # Create expired token
        expired_time = datetime.utcnow() - timedelta(hours=2)
        tokens = QuickBooksOAuthToken(
            user_id="expired-user",
            access_token="expired-token",
            realm_id="test-realm",
            updated_at=expired_time,
            expires_in=3600  # 1 hour
        )
        
        await db_handler_sqlite.save_tokens(tokens)
        
        # Check if expired
        is_expired = await db_handler_sqlite.is_token_expired("expired-user")
        assert is_expired is True
        
        # Create fresh token
        fresh_tokens = QuickBooksOAuthToken(
            user_id="fresh-user",
            access_token="fresh-token",
            realm_id="test-realm",
            expires_in=3600
        )
        
        await db_handler_sqlite.save_tokens(fresh_tokens)
        
        # Check if not expired
        is_not_expired = await db_handler_sqlite.is_token_expired("fresh-user")
        assert is_not_expired is False
    
    @pytest.mark.asyncio
    async def test_refresh_token_expiration(self, db_handler_sqlite):
        """Test refresh token expiration checking"""
        # Create expired refresh token
        expired_time = datetime.utcnow() - timedelta(days=101)  # More than 100 days
        tokens = QuickBooksOAuthToken(
            user_id="expired-refresh-user",
            access_token="test-token",
            realm_id="test-realm",
            created_at=expired_time,
            x_refresh_token_expires_in=864000  # 100 days
        )
        
        await db_handler_sqlite.save_tokens(tokens)
        
        # Check if refresh token is expired
        is_refresh_expired = await db_handler_sqlite.is_refresh_token_expired("expired-refresh-user")
        assert is_refresh_expired is True
    
    @pytest.mark.asyncio
    async def test_delete_tokens(self, db_handler_sqlite):
        """Test deleting tokens"""
        tokens = QuickBooksOAuthToken(
            user_id="delete-user",
            access_token="delete-token",
            realm_id="test-realm"
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

class TestQuickBooksAuthHandler:
    """Test QuickBooks authentication handler"""
    
    @pytest.fixture
    def auth_handler(self):
        """Create auth handler for testing"""
        with patch.dict(os.environ, {
            'QUICKBOOKS_CLIENT_ID': 'test-client-id',
            'QUICKBOOKS_CLIENT_SECRET': 'test-client-secret',
            'QUICKBOOKS_REDIRECT_URI': 'http://localhost:5058/auth/quickbooks/callback'
        }):
            return QuickBooksAuthHandler()
    
    def test_generate_auth_url(self, auth_handler):
        """Test authorization URL generation"""
        url, state = auth_handler.generate_auth_url("test-user")
        
        assert url is not None
        assert state is not None
        assert "appcenter.intuit.com/connect/oauth2" in url
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
            "x_refresh_token_expires_in": 864000
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
        """Test getting company info with mock HTTP response"""
        mock_company_data = {
            "CompanyInfo": [
                {
                    "Id": "123",
                    "CompanyName": "Test Company",
                    "LegalName": "Test Company LLC",
                    "CompanyType": "Corporation",
                    "Email": "test@example.com",
                    "Phone": "555-1234"
                }
            ]
        }
        
        with patch('aiohttp.ClientSession.get') as mock_get:
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = mock_company_data
            mock_get.return_value.__aenter__.return_value = mock_response
            
            result = await auth_handler.get_user_info("test-access-token", "test-realm")
            
            assert result["realm_id"] == "test-realm"
            assert result["company_name"] == "Test Company"
            assert result["legal_name"] == "Test Company LLC"
            assert result["company_type"] == "Corporation"
            assert result["email"] == "test@example.com"
            assert result["phone"] == "555-1234"

class TestQuickBooksIntegration:
    """Integration tests for QuickBooks service"""
    
    @pytest.fixture
    def mock_env(self):
        """Mock environment for integration tests"""
        env_vars = {
            'QUICKBOOKS_CLIENT_ID': 'test-client-id',
            'QUICKBOOKS_CLIENT_SECRET': 'test-client-secret',
            'QUICKBOOKS_REDIRECT_URI': 'http://localhost:5058/auth/quickbooks/callback',
            'QUICKBOOKS_ENVIRONMENT': 'sandbox'
        }
        with patch.dict(os.environ, env_vars):
            yield env_vars
    
    def test_integration_availability(self, mock_env):
        """Test integration availability check"""
        from quickbooks_integration_register import check_quickbooks_availability
        
        availability = check_quickbooks_availability()
        assert availability is True
    
    def test_integration_configuration(self, mock_env):
        """Test integration configuration check"""
        from quickbooks_integration_register import check_quickbooks_configuration
        
        config_status = check_quickbooks_configuration()
        assert config_status is True
    
    def test_service_initialization(self, mock_env):
        """Test service initialization"""
        from quickbooks_integration_register import init_quickbooks_services
        
        success = init_quickbooks_services()
        assert success is True
    
    def test_get_quickbooks_info(self, mock_env):
        """Test getting integration information"""
        from quickbooks_integration_register import get_quickbooks_info
        
        info = get_quickbooks_info()
        
        assert info['name'] == 'QuickBooks'
        assert info['available'] is True
        assert 'features' in info
        assert 'supported_operations' in info
        assert len(info['features']) > 0
        assert len(info['supported_operations']) > 0

class TestQuickBooksEndpoints:
    """Test QuickBooks API endpoints"""
    
    @pytest.fixture
    def mock_access_token_and_realm(self):
        """Mock access token and realm ID dependency"""
        with patch('quickbooks_routes.get_access_token_and_realm') as mock:
            mock.return_value = ("test-access-token", "test-realm-id")
            yield mock
    
    @pytest.mark.asyncio
    async def test_get_invoices_endpoint(self, mock_access_token_and_realm):
        """Test GET /invoices endpoint"""
        from quickbooks_routes import get_invoices
        
        # Mock service call
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.get_invoices.return_value = {"QueryResponse": {"Invoice": []}}
            
            result = await get_invoices(
                user_id="test-user",
                limit=10,
                customer_id="test-customer"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "quickbooks"
    
    @pytest.mark.asyncio
    async def test_create_invoice_endpoint(self, mock_access_token_and_realm):
        """Test POST /invoices endpoint"""
        from quickbooks_routes import create_invoice
        
        invoice_data = {
            "customer_id": "test-customer",
            "line_items": [
                {
                    "Amount": 500.0,
                    "Description": "Test Service",
                    "DetailType": "SalesItemLineDetail",
                    "SalesItemLineDetail": {"ItemRef": {"value": "item-1"}}
                }
            ],
            "due_date": "2024-12-31",
            "memo": "Test Invoice"
        }
        
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.create_invoice.return_value = {"Invoice": {"Id": "123"}}
            
            result = await create_invoice(
                invoice_data=invoice_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Invoice created successfully"
    
    @pytest.mark.asyncio
    async def test_get_customers_endpoint(self, mock_access_token_and_realm):
        """Test GET /customers endpoint"""
        from quickbooks_routes import get_customers
        
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.get_customers.return_value = {"QueryResponse": {"Customer": []}}
            
            result = await get_customers(
                user_id="test-user",
                limit=20,
                name="test"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "quickbooks"
    
    @pytest.mark.asyncio
    async def test_create_customer_endpoint(self, mock_access_token_and_realm):
        """Test POST /customers endpoint"""
        from quickbooks_routes import create_customer
        
        customer_data = {
            "name": "New Customer",
            "email": "newcustomer@example.com",
            "phone": "555-1234",
            "company_name": "Customer Corp"
        }
        
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.create_customer.return_value = {"Customer": {"Id": "456"}}
            
            result = await create_customer(
                customer_data=customer_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Customer created successfully"
    
    @pytest.mark.asyncio
    async def test_get_expenses_endpoint(self, mock_access_token_and_realm):
        """Test GET /expenses endpoint"""
        from quickbooks_routes import get_expenses
        
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.get_expenses.return_value = {"QueryResponse": {"Purchase": []}}
            
            result = await get_expenses(
                user_id="test-user",
                limit=15,
                date_from="2024-01-01"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "quickbooks"
    
    @pytest.mark.asyncio
    async def test_create_expense_endpoint(self, mock_access_token_and_realm):
        """Test POST /expenses endpoint"""
        from quickbooks_routes import create_expense
        
        expense_data = {
            "account_id": "test-account",
            "amount": 250.0,
            "description": "Test Expense",
            "vendor_id": "test-vendor",
            "date": "2024-12-15",
            "reference": "EXP-001"
        }
        
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.create_expense.return_value = {"Purchase": {"Id": "789"}}
            
            result = await create_expense(
                expense_data=expense_data,
                user_id="test-user"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["message"] == "Expense created successfully"
    
    @pytest.mark.asyncio
    async def test_get_profit_loss_report_endpoint(self, mock_access_token_and_realm):
        """Test GET /reports/profit-loss endpoint"""
        from quickbooks_routes import get_profit_loss_report
        
        with patch('quickbooks_routes.quickbooks_service') as mock_service:
            mock_service.get_profit_and_loss.return_value = {"ProfitAndLoss": {"Columns": [], "Rows": []}}
            
            result = await get_profit_loss_report(
                user_id="test-user",
                date_from="2024-01-01",
                date_to="2024-12-31"
            )
            
            assert result["ok"] is True
            assert "data" in result
            assert result["service"] == "quickbooks"
    
    @pytest.mark.asyncio
    async def test_health_check(self):
        """Test health check endpoint"""
        from quickbooks_routes import health_check
        
        result = await health_check()
        
        assert result["ok"] is True
        assert "data" in result
        assert result["data"]["service"] == "quickbooks"
        assert "status" in result["data"]

# Performance and stress tests
class TestQuickBooksPerformance:
    """Performance tests for QuickBooks integration"""
    
    @pytest.mark.asyncio
    async def test_concurrent_operations(self):
        """Test concurrent financial operations"""
        # Mock service to avoid HTTP calls
        with patch('quickbooks_service.create_quickbooks_service') as mock_create:
            mock_service = Mock()
            mock_service.get_invoices.return_value = {"QueryResponse": {"Invoice": []}}
            mock_service.get_customers.return_value = {"QueryResponse": {"Customer": []}}
            mock_service.get_expenses.return_value = {"QueryResponse": {"Purchase": []}}
            mock_create.return_value = mock_service
            
            # Run multiple operations concurrently
            tasks = []
            for i in range(10):
                service = create_quickbooks_service()
                task = service.get_invoices("test-token", "test-realm", limit=5)
                tasks.append(task)
                task = service.get_customers("test-token", "test-realm", limit=5)
                tasks.append(task)
                task = service.get_expenses("test-token", "test-realm", limit=5)
                tasks.append(task)
            
            results = await asyncio.gather(*tasks, return_exceptions=True)
            
            # All operations should complete successfully
            assert len(results) == 30
            assert all(isinstance(r, dict) or isinstance(r, Exception) for r in results)
            exceptions = [r for r in results if isinstance(r, Exception)]
            assert len(exceptions) == 0

# Error handling tests
class TestQuickBooksErrorHandling:
    """Test error handling in QuickBooks integration"""
    
    @pytest.mark.asyncio
    async def test_invalid_credentials(self):
        """Test handling of invalid credentials"""
        service = create_quickbooks_service()
        
        # Mock HTTP client to raise authentication error
        mock_service = Mock()
        mock_service._make_request.side_effect = Exception("Invalid or expired access token")
        service._make_request = mock_service._make_request
        
        with pytest.raises(Exception):
            await service.get_invoices("invalid-token", "test-realm")
    
    @pytest.mark.asyncio
    async def test_network_timeout(self):
        """Test handling of network timeouts"""
        handler = QuickBooksAuthHandler()
        
        with patch('aiohttp.ClientSession.post') as mock_post:
            mock_post.side_effect = asyncio.TimeoutError()
            
            with pytest.raises(Exception):
                await handler.exchange_code_for_tokens("test-code", "test-state")
    
    @pytest.mark.asyncio
    async def test_api_rate_limit(self):
        """Test handling of API rate limits"""
        service = create_quickbooks_service()
        
        # Mock HTTP response with rate limit
        mock_service = Mock()
        mock_service._make_request.side_effect = Exception("QuickBooks API error: 429 - Rate limit exceeded")
        service._make_request = mock_service._make_request
        
        with pytest.raises(Exception):
            await service.get_invoices("test-token", "test-realm")

if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])