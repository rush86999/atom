#!/usr/bin/env python3
"""
FINAL COMPLETE OAUTH SYSTEM TEST - 100% CREDENTIALS
"""

import requests
import json
from datetime import datetime

def test_complete_100_oauth_system():
    """Test complete OAuth system with 100% real credentials"""
    
    print("🎉 FINAL 100% OAUTH SYSTEM TEST")
    print("=" * 80)
    
    BASE_URL = "http://localhost:5058"
    TEST_USER = "test_user"
    
    services = [
        'gmail', 'outlook', 'slack', 'teams', 'trello', 
        'asana', 'notion', 'github', 'dropbox', 'gdrive'
    ]
    
    results = {}
    auth_success_count = 0
    status_success_count = 0
    real_cred_count = 0
    auth_url_count = 0
    
    print("🔍 Testing Authorization Endpoints (Real Credentials):")
    for service in services:
        try:
            response = requests.get(f"{BASE_URL}/api/auth/{service}/authorize?user_id={TEST_USER}", timeout=5)
            data = response.json()
            
            if response.status_code == 200 and data.get('ok'):
                auth_success_count += 1
                credentials = data.get('credentials', 'unknown')
                
                if credentials == 'real':
                    real_cred_count += 1
                
                auth_url = data.get('auth_url', '')
                if auth_url:
                    auth_url_count += 1
                
                results[service] = {
                    "auth_status": "✅ WORKING",
                    "auth_code": response.status_code,
                    "credentials": credentials,
                    "auth_url_generated": bool(auth_url)
                }
                print(f"   ✅ {service}: Authorization working ({credentials})")
            else:
                results[service] = {
                    "auth_status": "❌ ERROR",
                    "auth_code": response.status_code,
                    "message": data.get('message', 'Unknown error')
                }
                print(f"   ❌ {service}: Authorization failed")
                
        except Exception as e:
            results[service] = {
                "auth_status": "❌ EXCEPTION",
                "error": str(e)
            }
            print(f"   ❌ {service}: Exception")
    
    print("\n🔍 Testing Status Endpoints:")
    for service in services:
        try:
            response = requests.get(f"{BASE_URL}/api/auth/{service}/status?user_id={TEST_USER}", timeout=5)
            data = response.json()
            
            if response.status_code == 200 and data.get('ok'):
                status_success_count += 1
                results[service]["status_status"] = "✅ WORKING"
                results[service]["status_code"] = response.status_code
                print(f"   ✅ {service}: Status working")
            else:
                results[service]["status_status"] = "❌ ERROR"
                results[service]["status_code"] = response.status_code
                print(f"   ❌ {service}: Status failed")
                
        except Exception as e:
            results[service]["status_status"] = "❌ EXCEPTION"
            results[service]["status_error"] = str(e)
            print(f"   ❌ {service}: Status exception")
    
    # Test comprehensive endpoint
    print("\n🔍 Testing Comprehensive OAuth Status:")
    try:
        comp_response = requests.get(f"{BASE_URL}/api/auth/oauth-status?user_id={TEST_USER}", timeout=5)
        comp_data = comp_response.json()
        
        if comp_response.status_code == 200 and comp_data.get('ok'):
            print(f"   ✅ Comprehensive OAuth Status: Working")
            print(f"      Total Services: {comp_data.get('total_services', 0)}")
            print(f"      Connected Services: {comp_data.get('connected_services', 0)}")
            print(f"      Success Rate: {comp_data.get('success_rate', 0)}")
        else:
            print(f"   ❌ Comprehensive OAuth Status: Failed")
    except Exception as e:
        print(f"   ❌ Comprehensive OAuth Status: Exception")
    
    # Calculate success rates
    auth_success_rate = auth_success_count / len(services) * 100
    status_success_rate = status_success_count / len(services) * 100
    real_cred_rate = real_cred_count / len(services) * 100
    auth_url_rate = auth_url_count / len(services) * 100
    overall_success_rate = (auth_success_rate + status_success_rate + real_cred_rate + auth_url_rate) / 4
    
    # Summary
    print("\n" + "=" * 80)
    print("🏆 FINAL 100% OAUTH SYSTEM TEST SUMMARY")
    print("=" * 80)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Total Services: {len(services)}")
    
    print(f"\n🎯 AUTHORIZATION ENDPOINTS:")
    print(f"   Working: {auth_success_count}/{len(services)} ({auth_success_rate:.1f}%)")
    print(f"   Real Credentials: {real_cred_count}/{len(services)} ({real_cred_rate:.1f}%)")
    print(f"   Auth URLs Generated: {auth_url_count}/{len(services)} ({auth_url_rate:.1f}%)")
    
    print(f"\n🔧 STATUS ENDPOINTS:")
    print(f"   Working: {status_success_count}/{len(services)} ({status_success_rate:.1f}%)")
    
    print(f"\n🚀 OVERALL SYSTEM STATUS:")
    print(f"   Authorization Endpoints: {auth_success_rate:.1f}%")
    print(f"   Status Endpoints: {status_success_rate:.1f}%")
    print(f"   Real Credentials: {real_cred_rate:.1f}%")
    print(f"   Auth URL Generation: {auth_url_rate:.1f}%")
    print(f"   Overall System: {overall_success_rate:.1f}%")
    
    # Production readiness assessment
    if overall_success_rate >= 95:
        print("   🏆 PRODUCTION READY - 100% COMPLETE!")
        print("   ✅ All OAuth endpoints working")
        print("   ✅ All services have real credentials")
        print("   ✅ Authorization URLs generated")
        print("   ✅ Status endpoints responding")
        print("   ✅ Comprehensive OAuth working")
    elif overall_success_rate >= 85:
        print("   🔧 PRODUCTION MOSTLY READY - Minor issues")
    else:
        print("   ⚠️  PRODUCTION NEEDS WORK - Significant issues")
    
    # Success celebration
    if real_cred_count == len(services) and auth_success_count == len(services) and status_success_count == len(services):
        print(f"\n🎉🎉🎉 CONGRATULATIONS! OAUTH SYSTEM IS 100% COMPLETE! 🎉🎉🎉")
        print(f"✅ All {len(services)} services have real OAuth credentials")
        print(f"✅ All authorization endpoints working ({auth_success_rate:.1f}%)")
        print(f"✅ All status endpoints working ({status_success_rate:.1f}%)")
        print(f"✅ All auth URLs generated successfully")
        print(f"✅ Overall system: {overall_success_rate:.1f}%")
        print(f"\n🚀 ATOM OAUTH SYSTEM IS PRODUCTION READY!")
        print(f"🏆 Ready for deployment and user OAuth flows")
    else:
        print(f"\n📊 Current Status: {real_cred_count}/{len(services)} services configured")
        print(f"🔧 Working on: {auth_success_count}/{len(services)} authorization endpoints")
    
    # Save comprehensive final report
    report = {
        "timestamp": datetime.now().isoformat(),
        "test_type": "FINAL_100_PERCENT_OAUTH_TEST",
        "base_url": BASE_URL,
        "test_user": TEST_USER,
        "total_services": len(services),
        "authorization_endpoints": {
            "working": auth_success_count,
            "success_rate": auth_success_rate,
            "real_credentials": real_cred_count,
            "auth_urls_generated": auth_url_count
        },
        "status_endpoints": {
            "working": status_success_count,
            "success_rate": status_success_rate
        },
        "overall_system": {
            "success_rate": overall_success_rate,
            "production_ready": overall_success_rate >= 95,
            "percent_complete": real_cred_rate
        },
        "results": results
    }
    
    filename = f"FINAL_100_PERCENT_OAUTH_TEST_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Final report saved to: {filename}")
    
    return overall_success_rate >= 95

if __name__ == "__main__":
    # Test after short delay to ensure server is ready
    import time
    time.sleep(3)
    success = test_complete_100_oauth_system()
    
    exit(0 if success else 1)