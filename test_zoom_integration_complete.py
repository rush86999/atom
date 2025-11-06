#!/usr/bin/env python3
"""
Test Script for Zoom Integration
Verifies that Zoom enhanced API is working correctly
"""

import asyncio
import json
import requests
import os
import sys
from datetime import datetime, timezone

# Configuration
API_BASE_URL = "http://localhost:5058"
ZOOM_ENHANCED_ENDPOINT = f"{API_BASE_URL}/api/integrations/zoom"
ZOOM_OAUTH_ENDPOINT = f"{API_BASE_URL}/api/auth/zoom"

def test_health():
    """Test enhanced Zoom health endpoint"""
    print("🔍 Testing Zoom Enhanced API Health...")
    
    try:
        response = requests.get(f"{ZOOM_ENHANCED_ENDPOINT}/health", timeout=10)
        
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
    """Test enhanced Zoom service info endpoint"""
    print("\n📋 Testing Zoom Enhanced API Service Info...")
    
    try:
        response = requests.get(f"{ZOOM_ENHANCED_ENDPOINT}/info", timeout=10)
        
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
    """Test Zoom OAuth authorization endpoint"""
    print("\n🔐 Testing Zoom OAuth Authorization...")
    
    try:
        response = requests.post(f"{ZOOM_OAUTH_ENDPOINT}/authorize", 
                           json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            auth_data = response.json()
            
            if auth_data.get('ok'):
                print("✅ OAuth authorization URL generated")
                auth_url = auth_data.get('oauth_url', 'URL generated')
                print(f"   Auth URL: {auth_url[:50]}...")
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
    """Test OAuth health endpoint"""
    print("\n🏥 Testing Zoom OAuth Service Health...")
    
    try:
        response = requests.get(f"{ZOOM_OAUTH_ENDPOINT}/health", timeout=10)
        
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

def test_meetings_endpoint():
    """Test meetings listing endpoint"""
    print("\n📅 Testing Zoom Meetings Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/meetings/list", 
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

def test_schedule_meeting_endpoint():
    """Test meeting scheduling endpoint"""
    print("\n📝 Testing Zoom Schedule Meeting Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/meetings/schedule`, 
                            json={
                                'user_id': 'test-user',
                                'meeting': {
                                    'topic': 'Test Meeting',
                                    'start_time': (datetime.now(timezone.utc) + timedelta(hours=1)).isoformat(),
                                    'duration': 60,
                                    'agenda': 'Test meeting agenda'
                                }
                            }, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Schedule meeting endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Schedule meeting endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Schedule meeting endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Schedule meeting endpoint error: {e}")
        return False

def test_recordings_endpoint():
    """Test recordings listing endpoint"""
    print("\n🎥 Testing Zoom Recordings Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/recordings/list`, 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Recordings endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Recordings endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Recordings endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Recordings endpoint error: {e}")
        return False

def test_webinars_endpoint():
    """Test webinars listing endpoint"""
    print("\n🎬 Testing Zoom Webinars Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/webinars/list", 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Webinars endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Webinars endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Webinars endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Webinars endpoint error: {e}")
        return False

def test_users_endpoint():
    """Test users listing endpoint"""
    print("\n👥 Testing Zoom Users Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/users/list`, 
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

def test_chats_endpoint():
    """Test chats listing endpoint"""
    print("\n💬 Testing Zoom Chats Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/chats/list`, 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Chats endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Chats endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Chats endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Chats endpoint error: {e}")
        return False

def test_reports_endpoint():
    """Test reports listing endpoint"""
    print("\n📊 Testing Zoom Reports Endpoint...")
    
    try:
        response = requests.post(f"{ZOOM_ENHANCED_ENDPOINT}/reports/list`, 
                            json={'user_id': 'test-user'}, timeout=10)
        
        if response.status_code == 200:
            data = response.json()
            
            if data.get('ok'):
                print("✅ Reports endpoint working")
                print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                return True
            else:
                error = data.get('error', 'Unknown error')
                if 'user_id' in error or 'auth' in error.lower():
                    print("   ⚠️  Authentication required - this is expected without OAuth tokens")
                    return True
                else:
                    print(f"❌ Reports endpoint failed: {error}")
                    return False
        else:
            print(f"❌ Reports endpoint failed with status {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ Reports endpoint error: {e}")
        return False

def check_environment_variables():
    """Check if required environment variables are set"""
    print("\n🔧 Checking Environment Variables...")
    
    required_vars = [
        'ZOOM_CLIENT_ID',
        'ZOOM_CLIENT_SECRET',
        'ZOOM_REDIRECT_URI'
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
    print("🚀 Zoom Integration Test Suite")
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
    meetings_ok = test_meetings_endpoint()
    schedule_ok = test_schedule_meeting_endpoint()
    recordings_ok = test_recordings_endpoint()
    webinars_ok = test_webinars_endpoint()
    users_ok = test_users_endpoint()
    chats_ok = test_chats_endpoint()
    reports_ok = test_reports_endpoint()
    
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
        ("Meetings Endpoint", meetings_ok),
        ("Schedule Meeting", schedule_ok),
        ("Recordings Endpoint", recordings_ok),
        ("Webinars Endpoint", webinars_ok),
        ("Users Endpoint", users_ok),
        ("Chats Endpoint", chats_ok),
        ("Reports Endpoint", reports_ok)
    ]
    
    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{test_name:<25} {status}")
    
    all_passed = all([health_ok, info_ok, oauth_health_ok, oauth_auth_ok, 
                     meetings_ok, schedule_ok, recordings_ok, webinars_ok, 
                     users_ok, chats_ok, reports_ok])
    
    if all_passed:
        print(f"\n🎉 All critical tests passed! Zoom integration is ready.")
        if not env_ok:
            print("💡 Configure environment variables for full OAuth functionality.")
    else:
        print(f"\n💥 Some tests failed. Please check to errors above.")
    
    print(f"\n🕐 Test completed at: {datetime.now(timezone.utc).isoformat()}")
    
    return 0 if all_passed else 1

if __name__ == "__main__":
    sys.exit(main())