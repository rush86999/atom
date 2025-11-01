#!/usr/bin/env python3
"""
Test to check what routes are actually registered in the running Flask app
"""
import requests
import json

def test_running_routes():
    base_url = "http://localhost:5058"
    
    print("Testing Running Flask App Routes...")
    print("="*50)
    
    # Try to create a debug endpoint to list all routes
    print("\n1. Testing debug endpoints:")
    debug_endpoints = [
        "/api/routes",
        "/routes",
        "/debug/routes",
        "/api/debug/routes",
    ]
    
    for endpoint in debug_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"   {endpoint}: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                if 'routes' in data:
                    print(f"     Found {len(data['routes'])} routes")
                    # Show service-related routes
                    service_routes = [r for r in data['routes'] if 'service' in r.get('endpoint', '').lower() or 'service' in r.get('path', '').lower()]
                    for route in service_routes[:10]:  # Show first 10
                        print(f"       {route['endpoint']}: {route['path']}")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")
    
    # Test service registry endpoints with different variations
    print("\n2. Testing service registry endpoints:")
    service_endpoints = [
        "/api/services",
        "/services",
        "/service_registry/api/services",
        "/api/service_registry/services",
    ]
    
    for endpoint in service_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"   {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")
    
    # Test other known endpoints to see what's working
    print("\n3. Testing other endpoints:")
    other_endpoints = [
        "/api/calendar/events",
        "/api/tasks",
        "/api/messages",
        "/api/workflow-automation/generate",
        "/api/user-api-keys",
        "/api/dashboard",
    ]
    
    for endpoint in other_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"   {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")

if __name__ == "__main__":
    test_running_routes()