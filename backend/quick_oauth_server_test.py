#!/usr/bin/env python3
"""
Quick OAuth Server Test
"""

import requests

def quick_oauth_server_test():
    """Quick test if OAuth server is accessible"""
    
    print("🔍 Quick OAuth Server Accessibility Test")
    print("=" * 50)
    
    try:
        # Test health endpoint
        response = requests.get("http://localhost:5058/healthz", timeout=5)
        
        if response.status_code == 200:
            data = response.json()
            print(f"✅ OAuth Server Health: {data.get('status', 'unknown')}")
            print(f"   Service: {data.get('service', 'unknown')}")
            print(f"   Version: {data.get('version', 'unknown')}")
            
            # Test root endpoint
            root_response = requests.get("http://localhost:5058/", timeout=5)
            root_data = root_response.json()
            print(f"✅ Root Endpoint: Working")
            print(f"   Services Available: {root_data.get('services', 0)}")
            
            return True
        else:
            print(f"❌ OAuth Server Health Error: {response.status_code}")
            return False
            
    except Exception as e:
        print(f"❌ OAuth Server Test Failed: {e}")
        return False

if __name__ == "__main__":
    success = quick_oauth_server_test()
    
    print("\n" + "=" * 50)
    if success:
        print("🎉 OAUTH SERVER IS ACCESSIBLE!")
        print("✅ Ready for full OAuth system test")
        
        # Test one service
        print("\n🔍 Testing One Service (GitHub):")
        try:
            github_status = requests.get("http://localhost:5058/api/auth/github/status?user_id=test_user", timeout=5)
            github_data = github_status.json()
            print(f"   Status: {github_data.get('status')}")
            print(f"   Credentials: {github_data.get('credentials')}")
            
            github_auth = requests.get("http://localhost:5058/api/auth/github/authorize?user_id=test_user", timeout=5)
            github_auth_data = github_auth.json()
            print(f"   Authorization: {github_auth_data.get('ok', False)}")
            
        except Exception as e:
            print(f"   GitHub Test Error: {e}")
            
    else:
        print("❌ OAUTH SERVER NOT ACCESSIBLE")
        print("🔧 Check if server is running on port 5058")
        print("🔧 Try: python fixed_oauth_server.py")