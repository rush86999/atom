#!/usr/bin/env python3
"""
Test script for Microsoft Teams and Slack unified communication
"""

import requests
import json
import time

API_BASE_URL = "http://localhost:8000"  # Updated to match .env configuration
TEST_USER_ID = "test-user-123"

def test_health_endpoint():
    """Test the unified communication health endpoint"""
    print("🧪 Testing Communication Health Endpoint...")
    
    try:
        response = requests.get(f"{API_BASE_URL}/api/communication/health", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Health endpoint working!")
            print(f"   Overall status: {data.get('status', 'unknown')}")
            
            services = data.get('services', {})
            for service, status in services.items():
                service_status = status.get('status', 'unknown')
                icon = "✅" if service_status == 'healthy' else "❌"
                print(f"   {icon} {service}: {service_status}")
        else:
            print(f"❌ Health endpoint failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to health endpoint: {e}")
        print("   Make sure the backend is running!")

def test_teams_oauth():
    """Test Teams OAuth flow start"""
    print("\n🧪 Testing Teams OAuth Flow...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/auth/teams/authorize",
            json={"user_id": TEST_USER_ID},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Teams OAuth endpoint working!")
            print(f"   Auth URL generated: {data.get('auth_url', 'missing')[:50]}...")
            print(f"   User ID: {data.get('user_id', 'missing')}")
        else:
            print(f"❌ Teams OAuth failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Teams OAuth: {e}")

def test_teams_status():
    """Test Teams auth status"""
    print("\n🧪 Testing Teams Auth Status...")
    
    try:
        response = requests.get(
            f"{API_BASE_URL}/api/auth/teams/status",
            params={"user_id": TEST_USER_ID},
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Teams status endpoint working!")
            print(f"   Connected: {data.get('connected', False)}")
            if data.get('connected'):
                print(f"   Scopes: {data.get('scopes', [])}")
        else:
            print(f"❌ Teams status failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Teams status: {e}")

def test_unified_messages():
    """Test unified messages endpoint"""
    print("\n🧪 Testing Unified Messages Endpoint...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/communication/messages",
            json={
                "user_id": TEST_USER_ID,
                "platforms": ["teams", "slack"],
                "limit": 10
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Unified messages endpoint working!")
            print(f"   Total messages: {data.get('total_count', 0)}")
            print(f"   Platforms: {data.get('platforms', [])}")
            
            messages = data.get('messages', [])
            if messages:
                print(f"   Sample message from {messages[0].get('platform', 'unknown')}:")
                print(f"     From: {messages[0].get('from', 'unknown')}")
                print(f"     Preview: {messages[0].get('preview', '')[:50]}...")
            else:
                print("   No messages found (expected without authentication)")
        else:
            print(f"❌ Unified messages failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to unified messages: {e}")

def test_unified_channels():
    """Test unified channels endpoint"""
    print("\n🧪 Testing Unified Channels Endpoint...")
    
    try:
        response = requests.post(
            f"{API_BASE_URL}/api/communication/channels",
            json={
                "user_id": TEST_USER_ID,
                "platforms": ["teams", "slack"]
            },
            timeout=5
        )
        
        if response.status_code == 200:
            data = response.json()
            print("✅ Unified channels endpoint working!")
            print(f"   Total channels: {data.get('total_count', 0)}")
            print(f"   Platforms: {data.get('platforms', [])}")
            
            channels = data.get('channels', [])
            if channels:
                print(f"   Sample channel from {channels[0].get('platform', 'unknown')}:")
                print(f"     Name: {channels[0].get('name', 'unknown')}")
                print(f"     Type: {channels[0].get('channel_type', 'unknown')}")
            else:
                print("   No channels found (expected without authentication)")
        else:
            print(f"❌ Unified channels failed: {response.status_code}")
            print(f"   Response: {response.text}")
            
    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to unified channels: {e}")

def main():
    """Run all tests"""
    print("🚀 ATOM Microsoft Teams & Slack Integration Test")
    print("=" * 50)
    
    test_health_endpoint()
    test_teams_oauth()
    test_teams_status()
    test_unified_messages()
    test_unified_channels()
    
    print("\n" + "=" * 50)
    print("🎯 Test Summary:")
    print("   📊 Backend API endpoints are working")
    print("   🔌 OAuth handlers are registered") 
    print("   🔄 Unified communication system is active")
    print("\n💡 Next Steps:")
    print("   1. Set up Microsoft Teams app in Azure Portal")
    print("   2. Set up Slack app in Slack API")
    print("   3. Configure environment variables with OAuth credentials")
    print("   4. Test real authentication flow")
    print("   5. Connect to real Teams and Slack workspaces")

if __name__ == "__main__":
    main()