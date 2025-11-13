#!/usr/bin/env python3
"""
Test GitHub OAuth Only
"""

import requests
import json
from datetime import datetime

def test_github_oauth_only():
    """Test GitHub OAuth specifically"""
    
    print("🔍 Testing GitHub OAuth Only")
    print("=" * 50)
    
    BASE_URL = "http://localhost:5058"
    TEST_USER = "test_user"
    
    try:
        # Test GitHub status
        status_response = requests.get(f"{BASE_URL}/api/auth/github/status?user_id={TEST_USER}", timeout=10)
        status_data = status_response.json()
        
        print(f"✅ GitHub Status: {status_data.get('status')}")
        print(f"   Credentials: {status_data.get('credentials')}")
        print(f"   Client ID: {status_data.get('client_id', 'N/A')[:20]}...")
        
        # Test GitHub authorization
        auth_response = requests.get(f"{BASE_URL}/api/auth/github/authorize?user_id={TEST_USER}", timeout=10)
        auth_data = auth_response.json()
        
        if auth_data.get('ok'):
            print(f"✅ GitHub Authorization: Working")
            print(f"   Auth URL Generated: Yes")
            print(f"   Credentials: {auth_data.get('credentials')}")
            
            return True
        else:
            print(f"❌ GitHub Authorization: {auth_data.get('message', 'Unknown error')}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub OAuth Test Failed: {e}")
        return False

if __name__ == "__main__":
    success = test_github_oauth_only()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 GITHUB OAUTH CONFIGURATION SUCCESS!")
        print("✅ Ready to proceed to Microsoft OAuth setup")
    else:
        print("⚠️  GitHub OAuth needs attention")
        print("🔧 Check .env file and try again")
    
    print("\n📋 Next Steps:")
    if success:
        print("   1. Proceed to Microsoft Azure setup (Outlook/Teams)")
        print("   2. Add Microsoft credentials to .env")
        print("   3. Test complete OAuth system")
    else:
        print("   1. Verify GitHub credentials in .env")
        print("   2. Restart OAuth server")
        print("   3. Test GitHub OAuth again")