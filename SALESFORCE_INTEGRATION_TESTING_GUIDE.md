# Salesforce Integration Testing Guide

## Overview

This guide provides comprehensive testing procedures for the Salesforce integration in the ATOM Agent Memory System. The testing covers all aspects of the integration including OAuth authentication, API operations, error handling, performance, and security.

## Testing Environment Setup

### Prerequisites
- **Salesforce Developer Org** or **Sandbox Environment**
- **ATOM Backend** running on localhost:5000
- **PostgreSQL Database** with Salesforce OAuth tables
- **Salesforce Connected App** configured with OAuth

### Test Configuration
```bash
# Environment variables for testing
SALESFORCE_CLIENT_ID="test_consumer_key"
SALESFORCE_CLIENT_SECRET="test_consumer_secret"
SALESFORCE_REDIRECT_URI="http://localhost:5000/api/auth/salesforce/callback"
SALESFORCE_API_VERSION="57.0"
DATABASE_URL="postgresql://test:test@localhost/atom_test"
```

## Test Categories

### 1. Unit Testing

#### 1.1 Service Layer Tests
```python
# test_salesforce_service.py
import pytest
import asyncio
from unittest.mock import Mock, patch
from salesforce_service import (
    get_salesforce_client,
    list_contacts,
    create_contact,
    list_accounts,
    create_account
)

class TestSalesforceService:
    
    @pytest.fixture
    def mock_sf_client(self):
        return Mock()
    
    @pytest.mark.asyncio
    async def test_get_salesforce_client_success(self):
        """Test successful Salesforce client creation"""
        with patch('salesforce_service.get_user_salesforce_tokens') as mock_get_tokens:
            mock_get_tokens.return_value = {
                'access_token': 'test_access_token',
                'instance_url': 'https://test.salesforce.com',
                'expires_at': '2024-12-31T23:59:59Z'
            }
            
            client = await get_salesforce_client('test_user', Mock())
            assert client is not None
    
    @pytest.mark.asyncio
    async def test_list_contacts_success(self, mock_sf_client):
        """Test successful contacts listing"""
        mock_sf_client.query_all.return_value = {
            'records': [
                {'Id': '001', 'Name': 'Test Contact', 'Email': 'test@example.com'}
            ]
        }
        
        contacts = await list_contacts(mock_sf_client)
        assert len(contacts) == 1
        assert contacts[0]['Name'] == 'Test Contact'
    
    @pytest.mark.asyncio
    async def test_create_contact_validation(self, mock_sf_client):
        """Test contact creation validation"""
        with pytest.raises(ValueError):
            await create_contact(mock_sf_client, '')  # Empty last name
```

#### 1.2 Authentication Tests
```python
# test_auth_handler_salesforce.py
import pytest
from auth_handler_salesforce import SalesforceOAuthHandler

class TestSalesforceOAuthHandler:
    
    def test_oauth_url_generation(self):
        """Test OAuth URL generation"""
        handler = SalesforceOAuthHandler()
        result = handler.get_oauth_url('test_user')
        
        assert result['ok'] == True
        assert 'authorization_url' in result['data']
        assert 'state' in result['data']
        assert 'login.salesforce.com' in result['data']['authorization_url']
    
    def test_config_validation(self):
        """Test configuration validation"""
        with patch.dict('os.environ', {}, clear=True):
            with pytest.raises(ValueError):
                SalesforceOAuthHandler()
```

### 2. Integration Testing

#### 2.1 API Endpoint Tests
```python
# test_salesforce_api_endpoints.py
import pytest
import requests
import json

class TestSalesforceAPIEndpoints:
    
    BASE_URL = "http://localhost:5000"
    
    def test_health_endpoint(self):
        """Test Salesforce health endpoint"""
        response = requests.get(f"{self.BASE_URL}/api/salesforce/health")
        assert response.status_code == 200
        
        data = response.json()
        assert data['service'] == 'salesforce'
        assert 'status' in data
        assert 'checks' in data
    
    def test_contacts_endpoint_unauthorized(self):
        """Test contacts endpoint without authentication"""
        response = requests.get(f"{self.BASE_URL}/api/salesforce/contacts?user_id=test_user")
        assert response.status_code == 401  # Unauthorized
        
        data = response.json()
        assert data['ok'] == False
        assert data['error']['code'] == 'AUTH_ERROR'
    
    def test_create_contact_validation(self):
        """Test contact creation validation"""
        payload = {
            'user_id': 'test_user',
            # Missing required LastName field
        }
        response = requests.post(f"{self.BASE_URL}/api/salesforce/contacts", json=payload)
        assert response.status_code == 400  # Bad Request
        
        data = response.json()
        assert data['ok'] == False
        assert data['error']['code'] == 'VALIDATION_ERROR'
```

#### 2.2 OAuth Flow Tests
```python
# test_oauth_flow.py
import pytest
import requests
from unittest.mock import patch

class TestOAuthFlow:
    
    BASE_URL = "http://localhost:5000"
    
    def test_oauth_authorization_url(self):
        """Test OAuth authorization URL generation"""
        response = requests.get(
            f"{self.BASE_URL}/api/auth/salesforce/authorize?user_id=test_user"
        )
        
        # Should return authorization URL or error
        assert response.status_code in [200, 302, 400, 503]
        
        if response.status_code == 200:
            data = response.json()
            assert 'authorization_url' in data.get('data', {})
    
    @patch('auth_handler_salesforce.SalesforceOAuthHandler.exchange_code_for_token')
    def test_oauth_callback(self, mock_exchange):
        """Test OAuth callback handling"""
        mock_exchange.return_value = {
            'ok': True,
            'data': {
                'access_token': 'test_access_token',
                'refresh_token': 'test_refresh_token',
                'instance_url': 'https://test.salesforce.com'
            }
        }
        
        payload = {
            'code': 'test_auth_code',
            'state': 'test_state'
        }
        
        response = requests.post(
            f"{self.BASE_URL}/api/auth/salesforce/callback",
            json=payload
        )
        
        assert response.status_code in [200, 400]
```

### 3. End-to-End Testing

#### 3.1 Complete Integration Test
```python
# test_salesforce_integration_e2e.py
import pytest
import requests
import time

class TestSalesforceIntegrationE2E:
    
    BASE_URL = "http://localhost:5000"
    TEST_USER_ID = "e2e_test_user"
    
    def test_complete_salesforce_workflow(self):
        """Test complete Salesforce integration workflow"""
        
        # 1. Test health endpoint
        health_response = requests.get(f"{self.BASE_URL}/api/salesforce/health")
        assert health_response.status_code == 200
        
        # 2. Test service registry
        services_response = requests.get(f"{self.BASE_URL}/api/services")
        assert services_response.status_code == 200
        
        services_data = services_response.json()
        salesforce_services = [
            service for service in services_data 
            if 'salesforce' in service.lower()
        ]
        assert len(salesforce_services) > 0
        
        # 3. Test OAuth URL generation
        oauth_response = requests.get(
            f"{self.BASE_URL}/api/auth/salesforce/authorize?user_id={self.TEST_USER_ID}"
        )
        assert oauth_response.status_code in [200, 400, 503]
        
        # 4. Test token health (should be not configured)
        token_health_response = requests.get(
            f"{self.BASE_URL}/api/salesforce/health/tokens?user_id={self.TEST_USER_ID}"
        )
        assert token_health_response.status_code == 200
        
        token_data = token_health_response.json()
        assert token_data['success'] == True
        assert token_data['token_health']['has_tokens'] == False
        
        print("✅ All E2E tests passed - Salesforce integration is working correctly")
```

### 4. Performance Testing

#### 4.1 API Performance Tests
```python
# test_salesforce_performance.py
import pytest
import time
import requests
from concurrent.futures import ThreadPoolExecutor

class TestSalesforcePerformance:
    
    BASE_URL = "http://localhost:5000"
    
    def test_health_endpoint_performance(self):
        """Test health endpoint response time"""
        start_time = time.time()
        response = requests.get(f"{self.BASE_URL}/api/salesforce/health")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000  # Convert to milliseconds
        assert response_time < 500  # Should respond in under 500ms
        assert response.status_code == 200
    
    def test_concurrent_health_checks(self):
        """Test concurrent health check requests"""
        def make_request():
            response = requests.get(f"{self.BASE_URL}/api/salesforce/health")
            return response.status_code
        
        with ThreadPoolExecutor(max_workers=10) as executor:
            futures = [executor.submit(make_request) for _ in range(10)]
            results = [future.result() for future in futures]
        
        # All requests should succeed
        assert all(status == 200 for status in results)
    
    def test_database_connection_performance(self):
        """Test database connection performance"""
        start_time = time.time()
        response = requests.get(f"{self.BASE_URL}/api/salesforce/health/tokens?user_id=test_user")
        end_time = time.time()
        
        response_time = (end_time - start_time) * 1000
        assert response_time < 1000  # Should respond in under 1 second
```

### 5. Security Testing

#### 5.1 Security Validation Tests
```python
# test_salesforce_security.py
import pytest
import requests

class TestSalesforceSecurity:
    
    BASE_URL = "http://localhost:5000"
    
    def test_input_validation(self):
        """Test input validation for various endpoints"""
        
        # Test SQL injection attempts
        malicious_user_ids = [
            "test_user; DROP TABLE salesforce_oauth_tokens;",
            "test_user' OR '1'='1",
            "test_user\\"; DELETE FROM salesforce_oauth_tokens"
        ]
        
        for user_id in malicious_user_ids:
            response = requests.get(
                f"{self.BASE_URL}/api/salesforce/health/tokens?user_id={user_id}"
            )
            # Should handle gracefully without errors
            assert response.status_code in [200, 400, 401]
    
    def test_missing_parameters(self):
        """Test endpoints with missing required parameters"""
        
        # Test without user_id
        response = requests.get(f"{self.BASE_URL}/api/salesforce/health/tokens")
        assert response.status_code == 400  # Bad Request
        
        data = response.json()
        assert 'error' in data
        assert 'user_id' in data['error'].get('message', '').lower()
    
    def test_invalid_json_payload(self):
        """Test handling of invalid JSON payloads"""
        response = requests.post(
            f"{self.BASE_URL}/api/salesforce/contacts",
            data="invalid json data",
            headers={'Content-Type': 'application/json'}
        )
        assert response.status_code == 400  # Bad Request
```

### 6. Error Handling Testing

#### 6.1 Error Scenario Tests
```python
# test_salesforce_error_handling.py
import pytest
import requests
from unittest.mock import patch

class TestSalesforceErrorHandling:
    
    BASE_URL = "http://localhost:5000"
    
    @patch('salesforce_service.get_salesforce_client')
    def test_salesforce_api_timeout(self, mock_get_client):
        """Test handling of Salesforce API timeouts"""
        mock_get_client.return_value = None  # Simulate timeout
        
        response = requests.get(
            f"{self.BASE_URL}/api/salesforce/contacts?user_id=test_user"
        )
        assert response.status_code == 401  # Unauthorized
        
        data = response.json()
        assert data['ok'] == False
        assert data['error']['code'] == 'AUTH_ERROR'
    
    def test_invalid_endpoint(self):
        """Test handling of invalid endpoints"""
        response = requests.get(f"{self.BASE_URL}/api/salesforce/invalid_endpoint")
        assert response.status_code == 404  # Not Found
    
    def test_method_not_allowed(self):
        """Test handling of unsupported HTTP methods"""
        response = requests.delete(f"{self.BASE_URL}/api/salesforce/contacts")
        assert response.status_code == 405  # Method Not Allowed
```

## Test Execution

### Running All Tests
```bash
# Run unit tests
pytest test_salesforce_service.py -v
pytest test_auth_handler_salesforce.py -v

# Run integration tests
pytest test_salesforce_api_endpoints.py -v
pytest test_oauth_flow.py -v

# Run end-to-end tests
pytest test_salesforce_integration_e2e.py -v

# Run performance tests
pytest test_salesforce_performance.py -v

# Run security tests
pytest test_salesforce_security.py -v

# Run error handling tests
pytest test_salesforce_error_handling.py -v

# Run all Salesforce tests
pytest *salesforce* -v
```

### Test Configuration Files

#### pytest.ini
```ini
[tool:pytest]
testpaths = tests/
python_files = test_*.py
python_classes = Test*
python_functions = test_*
addopts = -v --tb=short --strict-markers
markers =
    unit: Unit tests
    integration: Integration tests
    e2e: End-to-end tests
    performance: Performance tests
    security: Security tests
```

#### requirements-testing.txt
```txt
pytest==7.4.0
pytest-asyncio==0.21.0
requests==2.31.0
pytest-benchmark==4.0.0
```

## Test Results Analysis

### Expected Test Outcomes

| Test Category | Success Criteria | Expected Pass Rate |
|---------------|------------------|-------------------|
| Unit Tests | All individual components work correctly | 100% |
| Integration Tests | Components work together properly | 95%+ |
| End-to-End Tests | Complete workflows function | 90%+ |
| Performance Tests | Meet response time targets | 100% |
| Security Tests | No security vulnerabilities | 100% |
| Error Handling | Graceful error recovery | 95%+ |

### Test Reporting

Generate comprehensive test reports:
```bash
# Generate HTML report
pytest --html=reports/salesforce_test_report.html --self-contained-html

# Generate JUnit XML report
pytest --junitxml=reports/salesforce_test_results.xml

# Generate coverage report
pytest --cov=salesforce_integration --cov-report=html:reports/coverage
```

## Continuous Integration

### GitHub Actions Workflow
```yaml
name: Salesforce Integration Tests

on:
  push:
    branches: [ main, develop ]
  pull_request:
    branches: [ main ]

jobs:
  test:
    runs-on: ubuntu-latest
    
    services:
      postgres:
        image: postgres:13
        env:
          POSTGRES_PASSWORD: test
          POSTGRES_DB: atom_test
        options: >-
          --health-cmd pg_isready
          --health-interval 10s
          --health-timeout 5s
          --health-retries 5
        ports:
          - 5432:5432

    steps:
    - uses: actions/checkout@v3
    
    - name: Set up Python
      uses: actions/setup-python@v4
      with:
        python-version: '3.9'
    
    - name: Install dependencies
      run: |
        python -m pip install --upgrade pip
        pip install -r requirements.txt
        pip install -r requirements-testing.txt
    
    - name: Run Salesforce tests
      run: |
        pytest *salesforce* -v --junitxml=test-results/salesforce.xml
    
    - name: Upload test results
      uses: actions/upload-artifact@v3
      with:
        name: salesforce-test-results
        path: test-results/
```

## Troubleshooting Common Issues

### 1. OAuth Configuration Issues
- **Issue**: "Invalid client credentials"
- **Solution**: Verify SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET in environment

### 2. Database Connection Issues
- **Issue**: "Database connection not available"
- **Solution**: Check DATABASE_URL and ensure PostgreSQL is running

### 3. API Connectivity Issues
- **Issue**: "Cannot connect to Salesforce API"
- **Solution**: Verify network connectivity and Salesforce instance status

### 4. Token Expiration Issues
- **Issue**: "Token expired" errors
- **Solution**: Implement automatic token refresh in service layer

## Conclusion

This testing guide provides comprehensive coverage for the Salesforce integration. Regular execution of these tests ensures the integration remains stable, secure, and performant. All tests should be integrated into the CI/CD pipeline to catch issues early and maintain high quality standards.

**Last Updated**: 2024-11-01  
**Test Coverage Target**: 90%+  
**Performance Target**: <500ms response time  
**Security Target**: Zero critical vulnerabilities