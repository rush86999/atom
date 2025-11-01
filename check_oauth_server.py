#!/usr/bin/env python3
"""
Quick OAuth Server Check
"""

import requests

def check_oauth_server():
    """Quick check if OAuth server is working"""
    
    print("🔍 Quick OAuth Server Check")
    print("=" * 50)
    
    try:
        response = requests.get("http://127.0.0.1:5058/healthz", timeout=3)
        if response.status_code == 200:
            data = response.json()
            print(f"✅ OAuth Server: {data.get('status')}")
            print(f"   Service: {data.get('service')}")
            return True
        else:
            print(f"❌ OAuth Server: HTTP {response.status_code}")
            return False
    except Exception as e:
        print(f"❌ OAuth Server: {e}")
        return False

if __name__ == "__main__":
    success = check_oauth_server()
    
    if success:
        print("🎉 OAuth server is accessible!")
    else:
        print("❌ OAuth server is not accessible")
        
    exit(0 if success else 1)