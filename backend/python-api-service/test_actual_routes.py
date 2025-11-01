#!/usr/bin/env python3
"""
Test actual routes in the running Flask app
"""
import requests
import json

def test_routes():
    base_url = "http://localhost:5058"
    
    print("Testing Actual Routes...")
    print("="*50)
    
    # Test various endpoints to see what's available
    endpoints = [
        "/",
        "/healthz",
        "/api/services",
        "/services/api/services",  # Try different combinations
        "/api/dashboard",
        "/api/calendar/events",
        "/api/tasks",
        "/api/messages",
        "/api/workflow-automation/generate",
        "/api/user-api-keys",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"{endpoint}: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        print(f"  Success: {data.get('success', 'N/A')}")
                        if 'services' in data:
                            print(f"  Services: {len(data.get('services', []))}")
                except:
                    pass
        except Exception as e:
            print(f"{endpoint}: Error - {e}")
    
    # Test POST endpoints
    print("\nTesting POST endpoints:")
    post_endpoints = [
        ("/api/workflow-automation/generate", {"user_input": "test", "user_id": "test_user"}),
        ("/api/services/register-workflow", {"service_id": "asana", "workflow_config": {}}),
    ]
    
    for endpoint, data in post_endpoints:
        try:
            response = requests.post(f"{base_url}{endpoint}", json=data)
            print(f"POST {endpoint}: {response.status_code}")
            if response.status_code == 200:
                try:
                    data = response.json()
                    if isinstance(data, dict):
                        print(f"  Success: {data.get('success', 'N/A')}")
                except:
                    pass
        except Exception as e:
            print(f"POST {endpoint}: Error - {e}")

if __name__ == "__main__":
    test_routes()