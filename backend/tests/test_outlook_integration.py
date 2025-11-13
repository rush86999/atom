#!/usr/bin/env python3
"""
Test Script for Outlook Integration
Verifies that the Outlook enhanced API is working correctly
"""

import asyncio
import json
import requests
import os
import sys
from datetime import datetime, timezone

# Configuration
API_BASE_URL = "http://localhost:5058"
OUTLOOK_ENHANCED_ENDPOINT = f"{API_BASE_URL}/api/outlook/enhanced"

def test_health():
    """Test the enhanced Outlook health endpoint"""
    print("🔍 Testing Outlook Enhanced API Health...")
    
    try:
        response = requests.get(f"{OUTLOOK_ENHANCED_ENDPOINT}/health", timeout=10)
        
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
                print(f"   Tenant ID: {config.get('tenant_id_configured')}")
            
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
    """Test the enhanced Outlook service info endpoint"""
    print("\n📋 Testing Outlook Enhanced API Service Info...")
    
    try:
        response = requests.get(f"{OUTLOOK_ENHANCED_ENDPOINT}/info", timeout=10)
        
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
    """Test the OAuth authorization endpoint"""
    print("\n🔐 Testing Outlook OAuth Authorization...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/auth/outlook-new/authorize", 
                           params={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            auth_data = response.json()
            
            if auth_data.get('success'):
                print("✅ OAuth authorization URL generated")
                print(f"   State: {auth_data.get('state')}")
                print(f"   Tenant ID: {auth_data.get('tenant_id')}")
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
    print("\n🏥 Testing Outlook OAuth Service Health...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/auth/outlook-new/health", timeout=10)
        
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

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔧 Checking Environment Variables...")
    
    required_vars = [
        'OUTLOOK_CLIENT_ID',
        'OUTLOOK_CLIENT_SECRET', 
        'OUTLOOK_TENANT_ID',
        'OUTLOOK_REDIRECT_URI'
    ]
    
    all_set = True
    for var in required_vars:
        value = os.getenv(var)
        if value:
            # Show partial value for sensitive variables
            if 'SECRET' in var or 'TOKEN' in var:
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
    print("🚀 Outlook Integration Test Suite")
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
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    results = [
        ("Environment Variables", env_ok),
        ("Enhanced API Health", health_ok),
        ("Service Info", info_ok),
        ("OAuth Health", oauth_health_ok),
        ("OAuth Authorization", oauth_auth_ok)
    ]
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    all_passed = all([health_ok, info_ok, oauth_health_ok])
    
    if all_passed:
        print(f"\n🎉 All critical tests passed! Outlook integration is ready.")
        if not env_ok:
            print("💡 Configure environment variables for full OAuth functionality.")
    else:
        print(f"\n💥 Some tests failed. Please check the errors above.")
    
    print(f"\n🕐 Test completed at: {datetime.now(timezone.utc).isoformat()}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())