#!/usr/bin/env python3
"""
Test Script for Notion Integration
Verifies that Notion enhanced API is working correctly
"""

import asyncio
import json
import requests
import os
import sys
from datetime import datetime, timezone

# Configuration
API_BASE_URL = "http://localhost:5058"
NOTION_ENHANCED_ENDPOINT = f"{API_BASE_URL}/api/integrations/notion"
NOTION_OAUTH_ENDPOINT = f"{API_BASE_URL}/api/auth/notion"

def test_health():
    """Test the enhanced Notion health endpoint"""
    print("🔍 Testing Notion Enhanced API Health...")
    
    try:
        response = requests.get(f"{NOTION_ENHANCED_ENDPOINT}/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print("✅ Health check successful")
            print(f"   Service Status: {health_data.get('status')}")
            print(f"   Components: {list(health_data.get('components', {}).keys())}")
            
            # Check configuration
            config = health_data.get('components', {}).get('configuration', {})
            if config.get('status') == 'configured':
                print("   ✅ OAuth configuration complete")
            else:
                print("   ⚠️  OAuth configuration incomplete")
                print(f"   Client ID: {config.get('client_id_configured')}")
                print(f"   Client Secret: {config.get('client_secret_configured')}")
            
            return True
        else:
            print(f"❌ Health check failed with status {response.status_code}")
            print(f"Response: {response.text}")
            return False
            
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to API server - make sure it's running")
        return False
    except Exception as e:
        print(f"❌ Health check error: {e}")
        return False

def test_service_info():
    """Test the enhanced Notion service info endpoint"""
    print("\n📋 Testing Notion Enhanced API Service Info...")
    
    try:
        response = requests.get(f"{NOTION_ENHANCED_ENDPOINT}/info", timeout=10)
        
        if response.status_code == 200:
            info_data = response.json()
            
            if info_data.get('ok'):
                service_data = info_data.get('data', {})
                print("✅ Service info retrieved successfully")
                print(f"   Service: {service_data.get('service')}")
                print(f"   Version: {service_data.get('version')}")
                print(f"   Status: {service_data.get('status')}")
                
                capabilities = service_data.get('capabilities', [])
                print(f"   Capabilities ({len(capabilities)}): {', '.join(capabilities[:5])}")
                if len(capabilities) > 5:
                    print(f"                     ... and {len(capabilities) - 5} more")
                
                endpoints = service_data.get('api_endpoints', [])
                print(f"   API Endpoints: {len(endpoints)} available")
                
                return True
            else:
                print(f"❌ Service info failed: {info_data.get('error')}")
                return False
        else:
            print(f"❌ Service info failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Service info error: {e}")
        return False

def test_oauth_flow():
    """Test the Notion OAuth authorization endpoint"""
    print("\n🔐 Testing Notion OAuth Authorization...")
    
    try:
        response = requests.post(f"{NOTION_OAUTH_ENDPOINT}/authorize", 
                           json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            auth_data = response.json()
            
            if auth_data.get('success'):
                print("✅ OAuth authorization URL generated")
                print(f"   State: {auth_data.get('state')}")
                return True
            else:
                print(f"❌ OAuth authorization failed: {auth_data.get('error')}")
                return False
        else:
            print(f"❌ OAuth authorization failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ OAuth authorization error: {e}")
        return False

def test_oauth_health():
    """Test the OAuth health endpoint"""
    print("\n🏥 Testing Notion OAuth Service Health...")
    
    try:
        response = requests.get(f"{NOTION_OAUTH_ENDPOINT}/health", timeout=10)
        
        if response.status_code == 200:
            health_data = response.json()
            print("✅ OAuth service health check successful")
            print(f"   Service: {health_data.get('service')}")
            print(f"   Status: {health_data.get('status')}")
            
            components = health_data.get('components', {})
            oauth_comp = components.get('oauth', {})
            api_comp = components.get('api', {})
            
            print(f"   OAuth: {oauth_comp.get('status')}")
            print(f"   API: {api_comp.get('status')}")
            
            return True
        else:
            print(f"❌ OAuth health check failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ OAuth health check error: {e}")
        return False

def test_workspaces_endpoint():
    """Test the workspace listing endpoint"""
    print("\n📂 Testing Notion Workspaces Endpoint...")
    
    try:
        response = requests.post(f"{NOTION_ENHANCED_ENDPOINT}/workspaces/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                workspaces = data.get('data', {}).get('workspaces', [])
                print("✅ Workspaces endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Workspaces endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Workspaces endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Workspaces endpoint error: {e}")
        return False

def test_databases_endpoint():
    """Test the database listing endpoint"""
    print("\n💾 Testing Notion Databases Endpoint...")
    
    try:
        response = requests.post(f"{NOTION_ENHANCED_ENDPOINT}/databases/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Databases endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Databases endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Databases endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Databases endpoint error: {e}")
        return False

def test_pages_endpoint():
    """Test the pages search endpoint"""
    print("\n📄 Testing Notion Pages Endpoint...")
    
    try:
        response = requests.post(f"{NOTION_ENHANCED_ENDPOINT}/pages/search", 
                            json={'user_id': 'test-user', 'query': 'test'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Pages endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Pages endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Pages endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Pages endpoint error: {e}")
        return False

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔧 Checking Environment Variables...")
    
    required_vars = [
        'NOTION_CLIENT_ID',
        'NOTION_CLIENT_SECRET',
        'NOTION_REDIRECT_URI'
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Show partial value for sensitive variables
            if 'SECRET' in var:
                display_value = f"{value[:10]}..." if len(value) > 10 else "SET"
            else:
                display_value = value
            print(f"   ✅ {var}: {display_value}")
        else:
            print(f"   ❌ {var}: NOT SET")
            all_set = False
    
    return all_set

def main():
    """Run all tests"""
    print("🚀 Notion Integration Test Suite")
    print("=" * 50)
    
    # Check environment first
    env_ok = check_environment_variables()
    
    if not env_ok:
        print("\n⚠️  Some environment variables are missing.")
        print("   Please set them in your .env file for full functionality.")
        print("   The API may still work with limited functionality.")
    
    # Run API tests
    health_ok = test_health()
    info_ok = test_service_info()
    oauth_health_ok = test_oauth_health()
    oauth_auth_ok = test_oauth_flow()
    workspaces_ok = test_workspaces_endpoint()
    databases_ok = test_databases_endpoint()
    pages_ok = test_pages_endpoint()
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    results = [
        ("Environment Variables", env_ok),
        ("Enhanced API Health", health_ok),
        ("Service Info", info_ok),
        ("OAuth Health", oauth_health_ok),
        ("OAuth Authorization", oauth_auth_ok),
        ("Workspaces Endpoint", workspaces_ok),
        ("Databases Endpoint", databases_ok),
        ("Pages Endpoint", pages_ok)
    ]
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    all_passed = all([health_ok, info_ok, oauth_health_ok, oauth_auth_ok, 
                     workspaces_ok, databases_ok, pages_ok])
    
    if all_passed:
        print(f"\n🎉 All critical tests passed! Notion integration is ready.")
        if not env_ok:
            print("💡 Configure environment variables for full OAuth functionality.")
    else:
        print(f"\n💥 Some tests failed. Please check the errors above.")
    
    print(f"\n🕐 Test completed at: {datetime.now(timezone.utc).isoformat()}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())