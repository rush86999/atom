#!/usr/bin/env python3
"""
Test OAuth Status with Direct Import
"""

import requests
import json
from datetime import datetime

# Test OAuth status endpoints directly
BASE_URL = "http://localhost:5058"
TEST_USER = "test_user"
TIMEOUT = 10

def test_oauth_status():
    """Test OAuth status endpoints"""
    
    services = [
        'gmail', 'outlook', 'slack', 'teams', 'trello', 
        'asana', 'notion', 'github', 'dropbox', 'gdrive'
    ]
    
    print(f"🔍 Testing OAuth Status Endpoints at {BASE_URL}")
    print("=" * 60)
    
    results = {}
    success_count = 0
    
    for service in services:
        try:
            endpoint = f"{BASE_URL}/api/auth/{service}/status"
            params = {"user_id": TEST_USER}
            
            response = requests.get(endpoint, params=params, timeout=TIMEOUT)
            
            if response.status_code == 200:
                status = "✅ WORKING"
                success_count += 1
                data = response.json()
                details = f"Status: {data.get('status', 'unknown')}, Credentials: {data.get('credentials', 'unknown')}"
            else:
                status = f"❌ ERROR ({response.status_code})"
                details = response.text[:100] if response.text else "No content"
            
            results[service] = {
                "status": status,
                "status_code": response.status_code,
                "details": details,
                "endpoint": endpoint
            }
            
            print(f"Testing {service}... {status}")
            
        except Exception as e:
            results[service] = {
                "status": "❌ EXCEPTION",
                "error": str(e),
                "endpoint": f"{BASE_URL}/api/auth/{service}/status"
            }
            print(f"Testing {service}... ❌ EXCEPTION: {e}")
    
    # Test comprehensive endpoint
    print("\n" + "=" * 60)
    print("🔍 Testing Comprehensive OAuth Status Endpoint")
    try:
        comp_endpoint = f"{BASE_URL}/api/auth/oauth-status"
        comp_response = requests.get(comp_endpoint, params={"user_id": TEST_USER}, timeout=TIMEOUT)
        
        if comp_response.status_code == 200:
            comp_data = comp_response.json()
            print("✅ Comprehensive OAuth Status working")
            print(f"   Total Services: {comp_data.get('total_services', 0)}")
            print(f"   Connected Services: {comp_data.get('connected_services', 0)}")
            print(f"   Success Rate: {comp_data.get('success_rate', 0)}")
            print(f"   Services Needing Credentials: {comp_data.get('services_needing_credentials', 0)}")
        else:
            print(f"❌ Comprehensive endpoint failed: {comp_response.status_code}")
    except Exception as e:
        print(f"❌ Comprehensive endpoint exception: {e}")
    
    # Summary
    print("\n" + "=" * 60)
    print("📊 OAUTH STATUS ENDPOINT TEST SUMMARY")
    print("=" * 60)
    print(f"Timestamp: {datetime.now().isoformat()}")
    print(f"Total Services: {len(services)}")
    print(f"Working: {success_count}")
    print(f"Success Rate: {success_count/len(services)*100:.1f}%")
    
    if success_count == len(services):
        print("🎉 ALL OAUTH STATUS ENDPOINTS WORKING!")
    else:
        print(f"⚠️  {len(services) - success_count} endpoints need attention")
    
    # Analysis
    print("\n🔍 CREDENTIAL STATUS ANALYSIS:")
    connected_services = []
    placeholder_services = []
    
    for service, result in results.items():
        if result.get("status") == "✅ WORKING":
            if "real" in result.get("details", ""):
                connected_services.append(service)
            elif "placeholder" in result.get("details", ""):
                placeholder_services.append(service)
    
    print(f"   ✅ Real Credentials Configured: {len(connected_services)}")
    for service in connected_services:
        print(f"      - {service}")
    
    print(f"   🔧 Placeholder Credentials: {len(placeholder_services)}")
    for service in placeholder_services:
        print(f"      - {service}")
    
    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "test_user": TEST_USER,
        "total_services": len(services),
        "success_count": success_count,
        "success_rate": success_count/len(services)*100,
        "connected_services": connected_services,
        "placeholder_services": placeholder_services,
        "results": results
    }
    
    filename = f"oauth_status_final_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {filename}")
    
    return success_count == len(services)

if __name__ == "__main__":
    # Test after short delay to ensure server is ready
    import time
    time.sleep(2)
    test_oauth_status()