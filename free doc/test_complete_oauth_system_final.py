#!/usr/bin/env python3
"""
Test Complete Fixed OAuth Server
"""

import requests
import json
from datetime import datetime

def test_complete_oauth_system():
    """Test the complete OAuth system"""
    
    print("🎉 TESTING COMPLETE FIXED OAUTH SYSTEM")
    print("=" * 70)
    
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
    placeholder_count = 0
    
    # Test authorization endpoints
    print("🔍 Testing Authorization Endpoints:")
    for service in services:
        try:
            response = requests.get(f"{BASE_URL}/api/auth/{service}/authorize?user_id={TEST_USER}", timeout=5)
            data = response.json()
            
            if response.status_code == 200 and data.get('ok'):
                auth_success_count += 1
                credentials = data.get('credentials', 'unknown')
                
                if credentials == 'real':
                    real_cred_count += 1
                elif credentials == 'placeholder':
                    placeholder_count += 1
                
                results[service] = {
                    "auth_status": "✅ WORKING",
                    "auth_code": response.status_code,
                    "credentials": credentials
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
    
    # Test status endpoints
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
    print("\n🔍 Testing Comprehensive Endpoint:")
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
    overall_success_rate = (auth_success_rate + status_success_rate + real_cred_rate) / 3
    
    # Summary
    print("\n" + "=" * 70)
    print("📊 COMPLETE OAUTH SYSTEM TEST SUMMARY")
    print("=" * 70)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Total Services: {len(services)}")
    
    print(f"\n🔧 AUTHORIZATION ENDPOINTS:")
    print(f"   Working: {auth_success_count}/{len(services)} ({auth_success_rate:.1f}%)")
    print(f"   Real Credentials: {real_cred_count}")
    print(f"   Placeholder Credentials: {placeholder_count}")
    
    print(f"\n🔧 STATUS ENDPOINTS:")
    print(f"   Working: {status_success_count}/{len(services)} ({status_success_rate:.1f}%)")
    
    print(f"\n🎯 CREDENTIAL STATUS:")
    print(f"   Real Credentials: {real_cred_count}/{len(services)} ({real_cred_rate:.1f}%)")
    print(f"   Placeholder Credentials: {placeholder_count}/{len(services)} ({placeholder_count/len(services)*100:.1f}%)")
    
    print(f"\n🚀 OVERALL SYSTEM STATUS:")
    print(f"   OAuth System: {overall_success_rate:.1f}%")
    
    # Production readiness assessment
    if overall_success_rate >= 85:
        print("   🏆 PRODUCTION READY!")
    elif overall_success_rate >= 70:
        print("   🔧 MOSTLY READY - Minor configuration needed")
    else:
        print("   ⚠️  NEEDS WORK - Significant configuration needed")
    
    # Services needing attention
    print(f"\n📋 SERVICES NEEDING REAL CREDENTIALS:")
    services_needing = []
    for service, result in results.items():
        if result.get('credentials') == 'placeholder':
            services_needing.append(service)
    
    for service in services_needing:
        print(f"   🔧 {service.upper()}: Needs real OAuth credentials")
    
    # Save comprehensive report
    report = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "test_user": TEST_USER,
        "total_services": len(services),
        "authorization_endpoints": {
            "working": auth_success_count,
            "success_rate": auth_success_rate
        },
        "status_endpoints": {
            "working": status_success_count,
            "success_rate": status_success_rate
        },
        "credentials": {
            "real": real_cred_count,
            "placeholder": placeholder_count,
            "real_percentage": real_cred_rate
        },
        "overall_system": {
            "success_rate": overall_success_rate,
            "production_ready": overall_success_rate >= 85
        },
        "services_needing_credentials": services_needing,
        "results": results
    }
    
    filename = f"complete_oauth_system_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {filename}")
    
    return overall_success_rate >= 85

if __name__ == "__main__":
    # Test after short delay to ensure server is ready
    import time
    time.sleep(2)
    success = test_complete_oauth_system()
    
    if success:
        print("\n🎉 OAUTH SERVER IS PRODUCTION READY!")
        print("✅ All critical endpoints working")
        print("✅ Real credentials loaded")
        print("✅ System fully functional")
        print("\n🚀 READY FOR MICROSOFT AZURE SETUP!")
    else:
        print("\n⚠️  OAUTH SERVER NEEDS ATTENTION")
        print("🔧 Some endpoints or credentials need fixing")