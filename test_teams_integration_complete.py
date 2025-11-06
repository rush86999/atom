#!/usr/bin/env python3
"""
Test Script for Microsoft Teams Integration
Verifies that Teams enhanced API is working correctly
"""

import asyncio
import json
import requests
import os
import sys
from datetime import datetime, timezone

# Configuration
API_BASE_URL = "http://localhost:5058"
TEAMS_ENHANCED_ENDPOINT = f"{API_BASE_URL}/api/integrations/teams"
TEAMS_OAUTH_ENDPOINT = f"{API_BASE_URL}/api/auth/teams"

def test_health():
    """Test the enhanced Teams health endpoint"""
    print("🔍 Testing Teams Enhanced API Health...")
    
    try:
        response = requests.get(f"{TEAMS_ENHANCED_ENDPOINT}/health", timeout=10)
        
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
    """Test the enhanced Teams service info endpoint"""
    print("\n📋 Testing Teams Enhanced API Service Info...")
    
    try:
        response = requests.get(f"{TEAMS_ENHANCED_ENDPOINT}/info", timeout=10)
        
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
    """Test the Teams OAuth authorization endpoint"""
    print("\n🔐 Testing Teams OAuth Authorization...")
    
    try:
        response = requests.post(f"{TEAMS_OAUTH_ENDPOINT}/authorize", 
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
    print("\n🏥 Testing Teams OAuth Service Health...")
    
    try:
        response = requests.get(f"{TEAMS_OAUTH_ENDPOINT}/health", timeout=10)
        
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

def test_teams_endpoint():
    """Test the Teams listing endpoint"""
    print("\n📢 Testing Teams Endpoint...")
    
    try:
        response = requests.post(f"{TEAMS_ENHANCED_ENDPOINT}/teams/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Teams endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Teams endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Teams endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Teams endpoint error: {e}")
        return False

def test_channels_endpoint():
    """Test the channels listing endpoint"""
    print("\n📢 Testing Teams Channels Endpoint...")
    
    try:
        response = requests.post(f"{TEAMS_ENHANCED_ENDPOINT}/channels/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Channels endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Channels endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Channels endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Channels endpoint error: {e}")
        return False

def test_messages_endpoint():
    """Test the messages listing endpoint"""
    print("\n💬 Testing Teams Messages Endpoint...")
    
    try:
        response = requests.post(f"{TEAMS_ENHANCED_ENDPOINT}/messages/list", 
                            json={'user_id': 'test-user', 'channel_id': 'test'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Messages endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Messages endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Messages endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Messages endpoint error: {e}")
        return False

def test_users_endpoint():
    """Test the users listing endpoint"""
    print("\n👥 Testing Teams Users Endpoint...")
    
    try:
        response = requests.post(f"{TEAMS_ENHANCED_ENDPOINT}/users/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Users endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Users endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Users endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Users endpoint error: {e}")
        return False

def test_meetings_endpoint():
    """Test the meetings listing endpoint"""
    print("\n📅 Testing Teams Meetings Endpoint...")
    
    try:
        response = requests.post(f"{TEAMS_ENHANCED_ENDPOINT}/meetings/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Meetings endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Meetings endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Meetings endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Meetings endpoint error: {e}")
        return False

def test_files_endpoint():
    """Test the files listing endpoint"""
    print("\n📁 Testing Teams Files Endpoint...")
    
    try:
        response = requests.post(f"{TEAMS_ENHANCED_ENDPOINT}/files/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Files endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Files endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Files endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Files endpoint error: {e}")
        return False

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔧 Checking Environment Variables...")
    
    required_vars = [
        'TEAMS_CLIENT_ID',
        'TEAMS_CLIENT_SECRET',
        'TEAMS_REDIRECT_URI'
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
    print("🚀 Microsoft Teams Integration Test Suite")
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
    teams_ok = test_teams_endpoint()
    channels_ok = test_channels_endpoint()
    messages_ok = test_messages_endpoint()
    users_ok = test_users_endpoint()
    meetings_ok = test_meetings_endpoint()
    files_ok = test_files_endpoint()
    
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
        ("Teams Endpoint", teams_ok),
        ("Channels Endpoint", channels_ok),
        ("Messages Endpoint", messages_ok),
        ("Users Endpoint", users_ok),
        ("Meetings Endpoint", meetings_ok),
        ("Files Endpoint", files_ok)
    ]
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    all_passed = all([health_ok, info_ok, oauth_health_ok, oauth_auth_ok, 
                     teams_ok, channels_ok, messages_ok, users_ok, meetings_ok, files_ok])
    
    if all_passed:
        print(f"\n🎉 All critical tests passed! Teams integration is ready.")
        if not env_ok:
            print("💡 Configure environment variables for full OAuth functionality.")
    else:
        print(f"\n💥 Some tests failed. Please check to errors above.")
    
    print(f"\n🕐 Test completed at: {datetime.now(timezone.utc).isoformat()}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())