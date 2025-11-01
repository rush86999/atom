#!/usr/bin/env python3
"""
Test the new health endpoints
"""
import requests
import json

def test_health_endpoints():
    base_url = "http://localhost:5058"
    
    print("Testing Health Endpoints...")
    print("="*50)
    
    # Test all health endpoints
    health_endpoints = [
        "/api/gmail/health",
        "/api/outlook/health",
        "/api/slack/health",
        "/api/teams/health",
        "/api/github/health",
        "/api/gdrive/health",
        "/api/dropbox/health",
        "/api/trello/health",
        "/api/asana/health",
        "/api/notion/health"
    ]
    
    working_endpoints = []
    failed_endpoints = []
    
    for endpoint in health_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            status_icon = "✅" if response.status_code == 200 else "❌"
            print(f"{status_icon} {endpoint}: {response.status_code}")
            
            if response.status_code == 200:
                data = response.json()
                working_endpoints.append({
                    "endpoint": endpoint,
                    "service": data.get("service", "unknown"),
                    "status": data.get("status", "unknown")
                })
            else:
                failed_endpoints.append(endpoint)
                
        except Exception as e:
            print(f"❌ {endpoint}: Error - {e}")
            failed_endpoints.append(endpoint)
    
    # Summary
    print(f"\n" + "="*50)
    print("SUMMARY")
    print("="*50)
    print(f"\nWorking health endpoints: {len(working_endpoints)}/{len(health_endpoints)}")
    print(f"Failed health endpoints: {len(failed_endpoints)}/{len(health_endpoints)}")
    
    if working_endpoints:
        print(f"\nWorking endpoints:")
        for endpoint_info in working_endpoints:
            print(f"  ✅ {endpoint_info['endpoint']} - {endpoint_info['service']} ({endpoint_info['status']})")
    
    if failed_endpoints:
        print(f"\nFailed endpoints:")
        for endpoint in failed_endpoints:
            print(f"  ❌ {endpoint}")
    
    # Test service registry integration
    print(f"\n" + "="*50)
    print("SERVICE REGISTRY INTEGRATION")
    print("="*50)
    
    try:
        response = requests.get(f"{base_url}/api/services/health")
        if response.status_code == 200:
            data = response.json()
            print(f"✅ Service registry health: {response.status_code}")
            print(f"   Overall health: {data.get('overall_health', 'unknown')}")
            print(f"   Health percentage: {data.get('health_percentage', 0)}%")
            print(f"   Healthy services: {data.get('healthy_services', 0)}/{data.get('total_services', 0)}")
        else:
            print(f"❌ Service registry health: {response.status_code}")
    except Exception as e:
        print(f"❌ Service registry health: Error - {e}")

if __name__ == "__main__":
    test_health_endpoints()