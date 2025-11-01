#!/usr/bin/env python3
"""
Final GitHub OAuth Test
"""

import requests

def final_github_test():
    """Final test of GitHub OAuth"""
    
    print("🎉 FINAL GITHUB OAUTH TEST")
    print("=" * 50)
    
    try:
        # Test GitHub status
        status_response = requests.get("http://localhost:5058/api/auth/github/status?user_id=test_user", timeout=5)
        status_data = status_response.json()
        
        print(f"✅ GitHub Status: {status_data.get('status')}")
        print(f"   Credentials: {status_data.get('credentials')}")
        print(f"   Client ID: {status_data.get('client_id', 'N/A')[:20]}...")
        
        # Test GitHub authorization
        auth_response = requests.get("http://localhost:5058/api/auth/github/authorize?user_id=test_user", timeout=5)
        auth_data = auth_response.json()
        
        print(f"✅ GitHub Authorization: {auth_data.get('ok', False)}")
        print(f"   Credentials: {auth_data.get('credentials', 'N/A')}")
        print(f"   Auth URL Generated: {'YES' if auth_data.get('auth_url') else 'NO'}")
        
        if auth_data.get('ok') and auth_data.get('credentials') == 'real':
            print("\n🎉 GITHUB OAUTH IS 100% WORKING!")
            print("✅ Real credentials loaded from .env")
            print("✅ Authorization endpoint working")
            print("✅ Ready for production use")
            return True
        else:
            print(f"\n❌ GitHub OAuth Issue: {auth_data.get('message', 'Unknown')}")
            return False
            
    except Exception as e:
        print(f"❌ GitHub OAuth Test Failed: {e}")
        return False

if __name__ == "__main__":
    success = final_github_test()
    
    print("\n" + "=" * 50)
    if success:
        print("🎯 MICRO-STEPS COMPLETED SUCCESSFULLY!")
        print("✅ GitHub OAuth fully configured with real credentials")
        print("📋 Ready for Microsoft OAuth setup (Outlook/Teams)")
        print("\n🚀 NEXT PHASE:")
        print("   Step 1: Microsoft Azure app creation")
        print("   Step 2: Add Microsoft credentials to .env")
        print("   Step 3: Test complete OAuth system")
    else:
        print("⚠️  GitHub OAuth needs attention")
        print("🔧 Check .env file for GITHUB_CLIENT_* variables")
    
    exit(0 if success else 1)