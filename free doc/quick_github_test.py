#!/usr/bin/env python3
"""
Quick GitHub OAuth Test
"""

import requests
import os

def quick_github_test():
    """Quick test of GitHub OAuth"""
    
    print("🔍 Quick GitHub OAuth Test")
    print("=" * 40)
    
    # Check if credentials exist in environment
    github_client_id = os.getenv('GITHUB_CLIENT_ID')
    github_client_secret = os.getenv('GITHUB_CLIENT_SECRET')
    
    print(f"GITHUB_CLIENT_ID: {github_client_id[:10] if github_client_id else 'NOT_FOUND'}...")
    print(f"GITHUB_CLIENT_SECRET: {github_client_secret[:10] if github_client_secret else 'NOT_FOUND'}...")
    
    try:
        # Test GitHub status endpoint
        response = requests.get("http://localhost:5058/api/auth/github/status?user_id=test_user", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ GitHub Status Response: {data.get('status')}")
            print(f"   Credentials: {data.get('credentials')}")
            print(f"   Client ID in Response: {data.get('client_id', 'N/A')[:10]}...")
            
            # Test authorization endpoint
            auth_response = requests.get("http://localhost:5058/api/auth/github/authorize?user_id=test_user", timeout=5)
            auth_data = auth_response.json()
            
            print(f"✅ GitHub Auth Response: {auth_data.get('ok', False)}")
            print(f"   Credentials: {auth_data.get('credentials', 'N/A')}")
            
            return auth_data.get('ok', False)
        else:
            print(f"❌ GitHub Status Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub OAuth Test Failed: {e}")
        return False

if __name__ == "__main__":
    success = quick_github_test()
    
    print("\n" + "=" * 40)
    if success:
        print("🎉 GITHUB OAUTH IS WORKING!")
        print("✅ Ready for Microsoft OAuth setup")
    else:
        print("⚠️  GitHub OAuth needs debugging")
    
    return success