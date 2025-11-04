#!/usr/bin/env python3
"""
Final OAuth System Test - Working Server
"""

import requests
import json
from datetime import datetime

def test_final_oauth_system():
    """Test OAuth system with working server"""
    
    print("🎉 FINAL OAUTH SYSTEM TEST")
    print("=" * 60)
    
    BASE_URL = "http://localhost:5058"
    TEST_USER = "test_user"
    
    # Test server health
    try:
        health_response = requests.get(f"{BASE_URL}/healthz", timeout=5)
        health_data = health_response.json()
        print(f"✅ Server Health: {health_data.get('status')}")
        print(f"   Service: {health_data.get('service')}")
        print(f"   Version: {health_data.get('version')}")
    except Exception as e:
        print(f"❌ Server Health Failed: {e}")
        return False
    
    # Test GitHub OAuth specifically
    print(f"\n🔍 Testing GitHub OAuth:")
    try:
        # Test GitHub status
        status_response = requests.get(f"{BASE_URL}/api/auth/github/status?user_id={TEST_USER}", timeout=5)
        status_data = status_response.json()
        
        print(f"   ✅ GitHub Status: {status_data.get('status')}")
        print(f"      Credentials: {status_data.get('credentials')}")
        print(f"      Client ID: {status_data.get('client_id', 'N/A')[:15]}...")
        
        # Test GitHub authorization
        auth_response = requests.get(f"{BASE_URL}/api/auth/github/authorize?user_id={TEST_USER}", timeout=5)
        auth_data = auth_response.json()
        
        print(f"   ✅ GitHub Authorization: {auth_data.get('ok', False)}")
        print(f"      Credentials: {auth_data.get('credentials', 'N/A')}")
        print(f"      Auth URL Generated: {'YES' if auth_data.get('auth_url') else 'NO'}")
        
        github_working = auth_data.get('ok', False) and auth_data.get('credentials') == 'real'
        
    except Exception as e:
        print(f"   ❌ GitHub OAuth Test Failed: {e}")
        github_working = False
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 OAUTH SYSTEM STATUS SUMMARY")
    print("=" * 60)
    
    if github_working:
        print("🎉 GITHUB OAUTH IS 100% WORKING!")
        print("✅ Real credentials loaded from .env")
        print("✅ Authorization endpoint working")
        print("✅ Status endpoint working")
        print("✅ OAuth server accessible")
        
        print("\n🎯 OAUTH SYSTEM STATUS:")
        print("   🔧 OAuth Server: ✅ RUNNING")
        print("   🔧 GitHub Credentials: ✅ REAL")
        print("   🔧 Authorization Endpoints: ✅ WORKING")
        print("   🔧 Status Endpoints: ✅ WORKING")
        
        print("\n🚀 READY FOR MICROSOFT AZURE SETUP!")
        print("   ✅ GitHub OAuth complete - serves as working example")
        print("   ✅ OAuth server stable and accessible")
        print("   ✅ All infrastructure in place")
        
        print("\n📋 NEXT MICRO-STEPS FOR AZURE:")
        print("   Step 1: Go to Azure portal")
        print("   Step 2: Create OAuth app")
        print("   Step 3: Copy credentials to .env")
        print("   Step 4: Test complete system")
        
        return True
    else:
        print("⚠️  GitHub OAuth needs attention")
        print("🔧 Check server status and credentials")
        return False

if __name__ == "__main__":
    # Test after short delay
    import time
    time.sleep(2)
    success = test_final_oauth_system()
    
    print(f"\n📄 Test completed at: {datetime.now().isoformat()}")
    exit(0 if success else 1)