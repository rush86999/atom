"""
Test script for API key handling in Atom Python API

This script tests the API key extraction and validation functionality
to ensure that API keys are properly handled from frontend requests.
"""

import requests
import json
import sys

def test_api_key_extraction():
    """Test API key extraction from headers and request body"""

    # Test server URL
    base_url = "http://localhost:5058"

    print("🧪 Testing API key extraction...")

    # Test 1: API keys in headers
    headers = {
        "X-OpenAI-API-Key": "sk-test-openai-key-1234567890",
        "X-Google-Client-ID": "google-client-id-1234567890",
        "X-Notion-API-Token": "notion-token-1234567890",
        "Content-Type": "application/json"
    }

    try:
        response = requests.get(f"{base_url}/api/integrations/validate", headers=headers)
        if response.status_code == 200:
            data = response.json()
            print("✅ API key extraction from headers: SUCCESS")
            print(f"   Validation results: {json.dumps(data['validation_results'], indent=2)}")
        else:
            print(f"❌ API key extraction from headers: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ API key extraction from headers: ERROR - {e}")

    # Test 2: API keys in request body
    payload = {
        "api_keys": {
            "openai_api_key": "sk-test-openai-body-key-1234567890",
            "trello_api_key": "trello-key-1234567890",
            "trello_api_secret": "trello-secret-1234567890"
        }
    }

    try:
        response = requests.post(
            f"{base_url}/api/integrations/validate",
            headers={"Content-Type": "application/json"},
            json=payload
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ API key extraction from body: SUCCESS")
            print(f"   Validation results: {json.dumps(data['validation_results'], indent=2)}")
        else:
            print(f"❌ API key extraction from body: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ API key extraction from body: ERROR - {e}")

    # Test 3: Dashboard with API keys
    try:
        response = requests.get(
            f"{base_url}/api/dashboard?user_id=test_user",
            headers=headers
        )
        if response.status_code == 200:
            data = response.json()
            print("✅ Dashboard with API keys: SUCCESS")
            print(f"   Calendar events: {len(data.get('calendar', []))}")
            print(f"   Tasks: {len(data.get('tasks', []))}")
            print(f"   Messages: {len(data.get('messages', []))}")
        else:
            print(f"❌ Dashboard with API keys: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Dashboard with API keys: ERROR - {e}")

def test_integration_status():
    """Test integration status endpoint"""

    base_url = "http://localhost:5058"

    print("\n🧪 Testing integration status...")

    try:
        response = requests.get(f"{base_url}/api/integrations/status")
        if response.status_code == 200:
            data = response.json()
            print("✅ Integration status: SUCCESS")
            for service, status in data.items():
                print(f"   {service}: {status['status']}")
        else:
            print(f"❌ Integration status: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Integration status: ERROR - {e}")

def test_health_check():
    """Test health check endpoint"""

    base_url = "http://localhost:5058"

    print("\n🧪 Testing health check...")

    try:
        response = requests.get(f"{base_url}/healthz")
        if response.status_code == 200:
            data = response.json()
            print("✅ Health check: SUCCESS")
            print(f"   Status: {data['status']}")
            print(f"   Database: {data['database']}")
            print(f"   Real services: {data['real_services']}")
        else:
            print(f"❌ Health check: FAILED (Status: {response.status_code})")
            print(f"   Response: {response.text}")
    except requests.exceptions.RequestException as e:
        print(f"❌ Health check: ERROR - {e}")

if __name__ == "__main__":
    print("🚀 Starting API key handling tests...")
    print("=" * 50)

    # Check if server is running
    try:
        response = requests.get("http://localhost:5058/healthz", timeout=2)
        if response.status_code != 200:
            print("❌ Python API server is not running on port 5058")
            print("   Please start the server first: python minimal_app.py")
            sys.exit(1)
    except requests.exceptions.RequestException:
        print("❌ Python API server is not running on port 5058")
        print("   Please start the server first: python minimal_app.py")
        sys.exit(1)

    # Run tests
    test_health_check()
    test_integration_status()
    test_api_key_extraction()

    print("\n" + "=" * 50)
    print("🎉 All tests completed!")
