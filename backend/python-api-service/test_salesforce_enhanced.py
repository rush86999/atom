#!/usr/bin/env python3
"""
🧪 Test script for Enhanced Salesforce Services
"""

import sys
import os
import asyncio
import requests
import json
from datetime import datetime, timezone, timedelta

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

async def test_salesforce_oauth_api():
    """Test Salesforce OAuth API endpoints"""
    print("🧪 Testing Salesforce OAuth API...")
    
    base_url = "http://localhost:8000"
    test_user_id = "test_salesforce_user_123"
    
    try:
        # Test OAuth URL generation
        print("\n🔐 Testing Salesforce OAuth URL generation...")
        response = requests.get(
            f"{base_url}/api/oauth/salesforce/url",
            params={"user_id": test_user_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce OAuth URL generation: {result.get('ok', False)}")
            if result.get("authorization_url"):
                print(f"📄 Authorization URL generated successfully")
            else:
                print("⚠️ Authorization URL not found in response")
        else:
            print(f"❌ Salesforce OAuth URL generation failed: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Salesforce OAuth API test error: {e}")

async def test_salesforce_enhanced_api():
    """Test Enhanced Salesforce API endpoints"""
    print("\n🧪 Testing Enhanced Salesforce API...")
    
    base_url = "http://localhost:8000"
    test_user_id = "test_salesforce_user_123"
    
    try:
        # Test health endpoint
        print("\n📊 Testing Salesforce health endpoint...")
        response = requests.get(f"{base_url}/api/salesforce/enhanced/health")
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce enhanced API health check: {result.get('ok', False)}")
        else:
            print(f"❌ Salesforce health endpoint failed: {response.status_code}")
            
        # Test accounts list endpoint
        print("\n📋 Testing Salesforce accounts list endpoint...")
        response = requests.post(
            f"{base_url}/api/salesforce/enhanced/accounts/list",
            json={
                "user_id": test_user_id,
                "limit": 10,
                "fields": ["Id", "Name", "Type", "Industry"]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce accounts list response: {result.get('ok', False)}")
        else:
            print(f"⚠️ Salesforce accounts list: {response.status_code} (Expected if no OAuth token)")
            
        # Test opportunities list endpoint
        print("\n💰 Testing Salesforce opportunities list endpoint...")
        response = requests.post(
            f"{base_url}/api/salesforce/enhanced/opportunities/list",
            json={
                "user_id": test_user_id,
                "limit": 10,
                "fields": ["Id", "Name", "Amount", "StageName", "CloseDate"]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce opportunities list response: {result.get('ok', False)}")
            if result.get("pipeline_statistics"):
                stats = result["pipeline_statistics"]
                print(f"📈 Pipeline stats - Total: ${stats.get('total_pipeline_value', 0):,}, Weighted: ${stats.get('weighted_pipeline_value', 0):,}")
        else:
            print(f"⚠️ Salesforce opportunities list: {response.status_code} (Expected if no OAuth token)")
            
        # Test leads list endpoint
        print("\n🎯 Testing Salesforce leads list endpoint...")
        response = requests.post(
            f"{base_url}/api/salesforce/enhanced/leads/list",
            json={
                "user_id": test_user_id,
                "limit": 10,
                "fields": ["Id", "FirstName", "LastName", "Company", "Status", "LeadSource"]
            }
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce leads list response: {result.get('ok', False)}")
            if result.get("lead_statistics"):
                stats = result["lead_statistics"]
                print(f"🎯 Lead stats - Total: {stats.get('total_leads', 0)}, Converted: {stats.get('converted_leads', 0)}, Rate: {stats.get('conversion_rate', 0)}%")
        else:
            print(f"⚠️ Salesforce leads list: {response.status_code} (Expected if no OAuth token)")
            
        # Test analytics endpoints
        print("\n📈 Testing Salesforce pipeline analytics...")
        response = requests.post(
            f"{base_url}/api/salesforce/enhanced/analytics/pipeline",
            json={"user_id": test_user_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce pipeline analytics response: {result.get('ok', False)}")
        else:
            print(f"⚠️ Salesforce pipeline analytics: {response.status_code}")
            
        print("\n📈 Testing Salesforce leads analytics...")
        response = requests.post(
            f"{base_url}/api/salesforce/enhanced/analytics/leads",
            json={"user_id": test_user_id}
        )
        
        if response.status_code == 200:
            result = response.json()
            print(f"✅ Salesforce leads analytics response: {result.get('ok', False)}")
        else:
            print(f"⚠️ Salesforce leads analytics: {response.status_code}")
            
    except Exception as e:
        print(f"❌ Salesforce enhanced API test error: {e}")

async def test_database_imports():
    """Test database imports and table creation"""
    print("\n🧪 Testing Database Imports...")
    
    try:
        # Test Salesforce OAuth database module
        print("\n🗃️ Testing Salesforce OAuth database module...")
        from db_oauth_salesforce import init_salesforce_oauth_table, get_user_salesforce_tokens
        
        print("✅ Salesforce OAuth database module imported successfully")
        
        # Test Salesforce core service
        print("\n🚀 Testing Salesforce core service module...")
        from salesforce_core_service import SalesforceCoreService, get_salesforce_core_service
        
        print("✅ Salesforce core service module imported successfully")
        
        # Test Salesforce enhanced API
        print("\n📦 Testing Salesforce enhanced API module...")
        from salesforce_enhanced_api import salesforce_enhanced_bp
        
        print("✅ Salesforce enhanced API module imported successfully")
        
    except ImportError as e:
        print(f"❌ Module import error: {e}")
    except Exception as e:
        print(f"❌ Database test error: {e}")

async def test_main_app_imports():
    """Test main app imports"""
    print("\n🧪 Testing Main App Imports...")
    
    try:
        # Test that main app can import all modules
        print("\n🚀 Testing main app Salesforce imports...")
        
        # These should be importable by main_api_app.py
        from db_oauth_salesforce import init_salesforce_oauth_table
        from auth_handler_salesforce import init_salesforce_oauth_handler, salesforce_auth_bp
        from salesforce_enhanced_api import salesforce_enhanced_bp
        
        print("✅ All Salesforce service modules importable by main app")
        
    except ImportError as e:
        print(f"❌ Main app import error: {e}")
    except Exception as e:
        print(f"❌ Main app test error: {e}")

async def test_oauth_database():
    """Test OAuth database functionality (if database is available)"""
    print("\n🧪 Testing OAuth Database...")
    
    try:
        import asyncpg
        from db_oauth_salesforce import init_salesforce_oauth_table
        
        # Test database connection (if configured)
        db_host = os.getenv('DB_HOST', 'localhost')
        db_port = int(os.getenv('DB_PORT', 5432))
        db_name = os.getenv('DB_NAME', 'atom')
        db_user = os.getenv('DB_USER', 'postgres')
        db_password = os.getenv('DB_PASSWORD', '')
        
        if db_password:
            print("\n🔗 Testing database connection...")
            conn = await asyncpg.connect(
                host=db_host,
                port=db_port,
                database=db_name,
                user=db_user,
                password=db_password
            )
            
            # Test table creation
            await init_salesforce_oauth_table(conn)
            print("✅ Salesforce OAuth table initialization successful")
            
            await conn.close()
        else:
            print("⚠️ Database password not configured, skipping database test")
            
    except Exception as e:
        print(f"⚠️ Database test failed (expected if database not running): {e}")

async def test_configuration():
    """Test Salesforce configuration"""
    print("\n🧪 Testing Salesforce Configuration...")
    
    # Check required environment variables
    required_vars = [
        'SALESFORCE_CLIENT_ID',
        'SALESFORCE_CLIENT_SECRET',
        'SALESFORCE_REDIRECT_URI'
    ]
    
    config_status = []
    missing_vars = []
    
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Don't show actual values for security
            if value.startswith(('your_', 'mock_', 'test_')):
                config_status.append(f"⚠️ {var}: Configured with placeholder value")
            else:
                config_status.append(f"✅ {var}: Configured")
        else:
            config_status.append(f"❌ {var}: Not configured")
            missing_vars.append(var)
    
    print("\n📋 Configuration Status:")
    for status in config_status:
        print(f"  {status}")
    
    if missing_vars:
        print(f"\n⚠️ Missing required variables: {', '.join(missing_vars)}")
        print("📄 Use .env.salesforce.template as reference")
    else:
        print("\n✅ All required Salesforce variables configured")
    
    # Check optional configuration
    optional_vars = [
        'SALESFORCE_ENVIRONMENT',
        'SALESFORCE_API_VERSION',
        'DB_HOST',
        'DB_NAME'
    ]
    
    print("\n📋 Optional Configuration:")
    for var in optional_vars:
        value = os.getenv(var)
        if value:
            print(f"  ✅ {var}: {value}")
        else:
            print(f"  ⚪ {var}: Not set (using default)")

async def test_service_availability():
    """Test Salesforce service availability"""
    print("\n🧪 Testing Service Availability...")
    
    base_url = "http://localhost:8000"
    services_to_test = [
        {
            "name": "Salesforce OAuth Handler",
            "url": f"{base_url}/api/auth/salesforce/health",
            "method": "GET"
        },
        {
            "name": "Salesforce Enhanced API",
            "url": f"{base_url}/api/salesforce/enhanced/health",
            "method": "GET"
        },
        {
            "name": "Main App Health",
            "url": f"{base_url}/healthz",
            "method": "GET"
        }
    ]
    
    for service in services_to_test:
        try:
            print(f"\n🔍 Testing {service['name']}...")
            if service['method'] == 'GET':
                response = requests.get(service['url'], timeout=5)
            else:
                response = requests.post(service['url'], timeout=5)
            
            if response.status_code == 200:
                print(f"  ✅ {service['name']}: Available")
            else:
                print(f"  ⚠️ {service['name']}: HTTP {response.status_code}")
        except requests.exceptions.ConnectionError:
            print(f"  ❌ {service['name']}: Connection refused")
        except requests.exceptions.Timeout:
            print(f"  ⚠️ {service['name']}: Timeout")
        except Exception as e:
            print(f"  ❌ {service['name']}: Error - {e}")

async def test_oauth_flow_simulation():
    """Simulate OAuth flow (without actual Salesforce)"""
    print("\n🧪 Testing OAuth Flow Simulation...")
    
    try:
        # Test OAuth URL generation
        print("\n📄 Step 1: Generate OAuth URL")
        
        base_url = "http://localhost:8000"
        test_user_id = "test_user_123"
        test_state = "test_state_456"
        
        response = requests.get(
            f"{base_url}/api/oauth/salesforce/url",
            params={"user_id": test_user_id, "state": test_state}
        )
        
        if response.status_code == 200:
            result = response.json()
            if result.get("ok"):
                print("  ✅ OAuth URL generation successful")
                print(f"  🔗 URL: {result.get('authorization_url', 'N/A')[:50]}...")
                print(f"  🏷️ State: {result.get('state', 'N/A')}")
            else:
                print("  ❌ OAuth URL generation failed")
        else:
            print(f"  ❌ OAuth URL generation: HTTP {response.status_code}")
        
        # Note: We can't test the full OAuth flow without actual Salesforce credentials
        print("\n📄 Step 2: OAuth Callback (requires actual Salesforce)")
        print("  ⚠️ Full OAuth flow requires valid Salesforce credentials")
        print("  📝 Configure SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET")
        
    except Exception as e:
        print(f"  ❌ OAuth flow simulation error: {e}")

async def test_api_endpoints_validation():
    """Test API endpoint validation"""
    print("\n🧪 Testing API Endpoints Validation...")
    
    base_url = "http://localhost:8000"
    test_user_id = "test_user_123"
    
    # Test validation endpoints
    validation_tests = [
        {
            "name": "Accounts List - No user_id",
            "url": f"{base_url}/api/salesforce/enhanced/accounts/list",
            "data": {},
            "expected_error": "validation_error"
        },
        {
            "name": "Account Create - No data",
            "url": f"{base_url}/api/salesforce/enhanced/accounts/create",
            "data": {"user_id": test_user_id},
            "expected_error": "validation_error"
        },
        {
            "name": "Account Get - No account_id",
            "url": f"{base_url}/api/salesforce/enhanced/accounts/get",
            "data": {"user_id": test_user_id},
            "expected_error": "validation_error"
        },
        {
            "name": "SOQL Query - No query",
            "url": f"{base_url}/api/salesforce/enhanced/query",
            "data": {"user_id": test_user_id},
            "expected_error": "validation_error"
        }
    ]
    
    for test in validation_tests:
        try:
            print(f"\n🔍 Testing: {test['name']}")
            response = requests.post(
                test['url'],
                json=test['data'],
                timeout=5
            )
            
            if response.status_code == 400:
                result = response.json()
                error = result.get("error")
                if error == test['expected_error']:
                    print(f"  ✅ Validation error correctly returned: {error}")
                else:
                    print(f"  ⚠️ Unexpected error: {error} (expected: {test['expected_error']})")
            elif response.status_code == 404:
                print(f"  ⚠️ Endpoint not found (may not be implemented)")
            else:
                print(f"  ⚠️ Unexpected response: HTTP {response.status_code}")
                
        except Exception as e:
            print(f"  ❌ Validation test error: {e}")

async def main():
    """Main test function"""
    print("=" * 60)
    print("🔬 ENHANCED SALESFORCE SERVICES TEST SUITE")
    print("=" * 60)
    print(f"⏰ Test started at: {datetime.now().isoformat()}")
    
    # Run all tests
    await test_configuration()
    await test_database_imports()
    await test_main_app_imports()
    await test_oauth_database()
    await test_service_availability()
    await test_salesforce_oauth_api()
    await test_salesforce_enhanced_api()
    await test_oauth_flow_simulation()
    await test_api_endpoints_validation()
    
    print("\n" + "=" * 60)
    print("✅ TEST SUITE COMPLETED")
    print("=" * 60)
    print("💡 Notes:")
    print("- OAuth token errors are expected if not authenticated with Salesforce")
    print("- Database errors are expected if database is not running")
    print("- Import errors should be investigated if they occur")
    print("- Health endpoints should return 200 if modules load correctly")
    print("- Configure environment variables for full functionality")
    print("\n📋 Next Steps:")
    print("1. Configure Salesforce Connected App")
    print("2. Set SALESFORCE_CLIENT_ID and SALESFORCE_CLIENT_SECRET")
    print("3. Test OAuth flow with valid credentials")
    print("4. Verify database connection and tables")
    print("5. Test API endpoints with authenticated requests")

if __name__ == "__main__":
    asyncio.run(main())