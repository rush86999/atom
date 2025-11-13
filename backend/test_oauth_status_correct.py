#!/usr/bin/env python3
"""
Test OAuth Status Endpoints with Correct URLs
"""

import requests
import json
from datetime import datetime

# Configuration
BASE_URL = "http://localhost:5058"
TEST_USER = "test_user"
TIMEOUT = 10

def test_oauth_status_endpoints():
    """Test OAuth status endpoints with correct URLs"""
    
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
            # Correct endpoint URL
            endpoint = f"{BASE_URL}/api/auth/{service}/status"
            params = {"user_id": TEST_USER}
            
            response = requests.get(endpoint, params=params, timeout=TIMEOUT)
            
            if response.status_code == 200:
                status = "✅ WORKING"
                success_count += 1
                details = response.json() if response.content else "No content"
            else:
                status = f"❌ ERROR ({response.status_code})"
                details = response.text[:200] if response.text else "No content"
            
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
    
    # Save results
    report = {
        "timestamp": datetime.now().isoformat(),
        "base_url": BASE_URL,
        "test_user": TEST_USER,
        "total_services": len(services),
        "success_count": success_count,
        "success_rate": success_count/len(services)*100,
        "results": results
    }
    
    filename = f"oauth_status_test_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
    with open(filename, 'w') as f:
        json.dump(report, f, indent=2)
    
    print(f"\n📄 Detailed report saved to: {filename}")
    
    return success_count == len(services)

if __name__ == "__main__":
    test_oauth_status_endpoints()