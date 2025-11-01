#!/usr/bin/env python3
"""
Test script to check service registry functionality
"""
import sys
import os
import requests
import json

# Add the current directory to the Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

def test_service_registry():
    """Test service registry endpoints"""
    base_url = "http://localhost:5058"
    
    print("Testing Service Registry Endpoints...")
    print("=" * 50)
    
    # Test health endpoint
    print("\n1. Testing health endpoint:")
    try:
        response = requests.get(f"{base_url}/healthz")
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            health_data = response.json()
            print(f"   Database: {health_data.get('database', 'unknown')}")
            print(f"   Minimal: {health_data.get('minimal', 'unknown')}")
    except Exception as e:
        print(f"   Error: {e}")
    
    # Test service registry endpoints
    endpoints = [
        "/api/services",
        "/api/services/health", 
        "/api/services/status",
        "/api/services/workflow-capabilities",
        "/api/services/chat-commands"
    ]
    
    for endpoint in endpoints:
        print(f"\n2. Testing {endpoint}:")
        try:
            response = requests.get(f"{base_url}{endpoint}")
            print(f"   Status: {response.status_code}")
            if response.status_code == 200:
                data = response.json()
                print(f"   Success: {data.get('success', 'unknown')}")
                if 'total_services' in data:
                    print(f"   Total Services: {data['total_services']}")
                if 'active_services' in data:
                    print(f"   Active Services: {data['active_services']}")
            elif response.status_code == 404:
                print("   Endpoint not found")
        except Exception as e:
            print(f"   Error: {e}")
    
    # Test workflow automation endpoint
    print("\n3. Testing workflow automation:")
    try:
        response = requests.post(
            f"{base_url}/api/workflow-automation/generate",
            json={
                "user_input": "Schedule meeting and create tasks",
                "user_id": "test_user"
            }
        )
        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Success: {data.get('success', 'unknown')}")
            print(f"   Workflow ID: {data.get('workflow_id', 'unknown')}")
    except Exception as e:
        print(f"   Error: {e}")

if __name__ == "__main__":
    test_service_registry()