#!/usr/bin/env python3
"""
Test the running Flask app to see what routes are actually available
"""
import requests
import json

def test_running_app():
    base_url = "http://localhost:5058"
    
    print("Testing Running Flask App Routes...")
    print("="*50)
    
    # Test health endpoint
    print("\n1. Health endpoint:")
    try:
        response = requests.get(f"{base_url}/healthz")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Database: {data.get('database', 'unknown')}")
            print(f"   Minimal: {data.get('minimal', 'unknown')}")
            if 'blueprints' in data:
                print(f"   Blueprints: {data['blueprints']}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test service registry endpoints with different variations
    print("\n2. Service Registry Endpoints:")
    endpoints = [
        "/api/services",
        "/services/api/services",
        "/services",
        "/api/service_registry/services",
    ]
    
    for endpoint in endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"   {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")
    
    # Test other known working endpoints
    print("\n3. Known Working Endpoints:")
    working_endpoints = [
        "/api/calendar/events",
        "/api/tasks",
        "/api/messages",
        "/api/workflow-automation/generate",
    ]
    
    for endpoint in working_endpoints:
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"   {endpoint}: {response.status_code}")
        except Exception as e:
            print(f"   {endpoint}: Error - {e}")

if __name__ == "__main__":
    test_running_app()