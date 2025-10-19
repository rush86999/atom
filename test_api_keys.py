import os
import sys
import requests
import json
from typing import Dict, Any


def test_api_key_validation():
    """Test API key validation endpoint"""

    # Test server URL
    base_url = "http://localhost:5058"

    # Test with mock API keys first
    test_headers = {
        "X-OpenAI-API-Key": "sk-test-mock-openai-key-123",
        "X-Google-Client-ID": "test-google-client-id-456",
        "X-Google-Client-Secret": "test-google-secret-789",
        "Content-Type": "application/json",
    }

    print("🧪 Testing API Key Validation Endpoint")
    print("=" * 50)

    try:
        # Test health endpoint first
        print("1. Testing health endpoint...")
        health_response = requests.get(f"{base_url}/healthz", timeout=10)
        print(f"   Status: {health_response.status_code}")
        if health_response.status_code == 200:
            health_data = health_response.json()
            print(f"   Response: {json.dumps(health_data, indent=2)}")
        else:
            print(f"   ❌ Health check failed: {health_response.text}")
            return False

        # Test workflow agent API (actual endpoint)
        print("\n2. Testing workflow agent API...")
        workflow_response = requests.post(
            f"{base_url}/api/workflow-agent/analyze",
            json={"user_input": "test workflow", "user_id": "test_user"},
            timeout=10,
        )

        print(f"   Status: {workflow_response.status_code}")

        if workflow_response.status_code == 200:
            workflow_data = workflow_response.json()
            print("   ✅ Workflow agent API is working!")
            print(f"   Response: {workflow_data.get('message', 'No message')}")
            return True
        else:
            print(f"   ❌ Workflow API failed: {workflow_response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print("   ❌ Could not connect to server. Is the backend running?")
        print("   💡 Start the backend with: python main_api_app.py")
        return False
    except requests.exceptions.Timeout:
        print("   ❌ Request timed out. Server may be unresponsive.")
        return False
    except Exception as e:
        print(f"   ❌ Unexpected error: {e}")
        return False


def test_with_real_keys():
    """Test with real API keys from environment"""

    print("\n" + "=" * 50)
    print("🔑 Testing with Real API Keys (if available)")
    print("=" * 50)

    # Check for real API keys in environment
    real_headers = {}
    keys_available = False

    if os.getenv("OPENAI_API_KEY"):
        real_headers["X-OpenAI-API-Key"] = os.getenv("OPENAI_API_KEY")
        keys_available = True
        print("   ✅ OpenAI API key found in environment")

    if os.getenv("GOOGLE_CLIENT_ID"):
        real_headers["X-Google-Client-ID"] = os.getenv("GOOGLE_CLIENT_ID")
        keys_available = True
        print("   ✅ Google Client ID found in environment")

    if os.getenv("GOOGLE_CLIENT_SECRET"):
        real_headers["X-Google-Client-Secret"] = os.getenv("GOOGLE_CLIENT_SECRET")
        keys_available = True
        print("   ✅ Google Client Secret found in environment")

    if not keys_available:
        print("   ℹ️  No real API keys found in environment variables")
        print("   💡 For production usage, set service credentials:")
        print("      export OPENAI_API_KEY=your-key-here")
        print("      export GOOGLE_CLIENT_ID=your-client-id")
        print("      export GOOGLE_CLIENT_SECRET=your-client-secret")
        print("   ℹ️  Note: Current implementation uses mock data for testing")
        return

    real_headers["Content-Type"] = "application/json"

    try:
        response = requests.post(
            "http://localhost:5058/api/integrations/validate",
            headers=real_headers,
            timeout=15,
        )

        print(f"   Status: {response.status_code}")
        if response.status_code == 200:
            data = response.json()
            print(f"   Response: {json.dumps(data, indent=2)}")

            # Check individual key validations
            if data.get("success") and "validation_results" in data:
                results = data["validation_results"]
                for key_name, validation in results.items():
                    status = "✅" if validation.get("valid") else "❌"
                    print(f"   {status} {key_name}: {validation.get('message')}")
        else:
            print(f"   ❌ Real key validation failed: {response.text}")

    except Exception as e:
        print(f"   ❌ Error testing real keys: {e}")


if __name__ == "__main__":
    print("🚀 ATOM API Key Testing Script")
    print("This script tests the API key validation functionality.")
    print()

    # Test with mock keys first
    success = test_api_key_validation()

    # Test with real keys if available
    test_with_real_keys()

    print("\n" + "=" * 50)
    if success:
        print("🎉 Basic API key validation test completed successfully!")
        print("Next steps:")
        print("1. Obtain real API keys from service providers")
        print("2. Set them as environment variables")
        print("3. Run this script again to test real integrations")
    else:
        print("❌ Testing failed. Please check:")
        print("   - Is the backend server running?")
        print("   - Are there any error messages in the server logs?")
        print("   - Check firewall/network connectivity")

    print("\nTo start the backend server:")
    print("cd backend/python-api-service")
    print("source venv311/bin/activate")
    print("python main_api_app.py")
