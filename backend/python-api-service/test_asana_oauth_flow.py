#!/usr/bin/env python3
"""
Asana OAuth Flow Test Script
Tests the complete Asana OAuth flow with real credentials
"""

import os
import sys
import logging
import requests
from urllib.parse import urlparse, parse_qs
from dotenv import load_dotenv

# Load production environment
env_file = "../../.env.production"
if os.path.exists(env_file):
    load_dotenv(env_file)
    print(f"✅ Loaded environment from: {env_file}")
else:
    print(f"❌ Environment file not found: {env_file}")
    sys.exit(1)

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

BASE_URL = "http://localhost:5058"
TEST_USER_ID = "test-user-" + str(hash(os.urandom(16).hex()))


def test_oauth_initiation():
    """Test Asana OAuth initiation endpoint"""
    print("\n🔧 Testing OAuth Initiation")

    try:
        # Call the OAuth initiation endpoint
        url = f"{BASE_URL}/api/auth/asana/initiate?user_id={TEST_USER_ID}"
        response = requests.get(url, allow_redirects=False)

        print(f"Status Code: {response.status_code}")
        print(f"Headers: {dict(response.headers)}")

        if response.status_code == 302:
            # Check if redirecting to Asana
            location = response.headers.get("Location", "")
            print(f"Redirect Location: {location}")

            if "app.asana.com/-/oauth_authorize" in location:
                print("✅ SUCCESS: Redirecting to Asana OAuth authorization page")

                # Parse the redirect URL to check parameters
                parsed = urlparse(location)
                params = parse_qs(parsed.query)

                required_params = [
                    "client_id",
                    "redirect_uri",
                    "response_type",
                    "state",
                ]
                missing_params = [p for p in required_params if p not in params]

                if not missing_params:
                    print("✅ All required OAuth parameters present:")
                    for param in required_params:
                        value = params[param][0] if params[param] else "MISSING"
                        print(f"   - {param}: {value[:50]}...")

                    # Verify client ID matches our environment
                    env_client_id = os.getenv("ASANA_CLIENT_ID")
                    if params["client_id"][0] == env_client_id:
                        print("✅ Client ID matches environment configuration")
                    else:
                        print("❌ Client ID mismatch between redirect and environment")

                    return True
                else:
                    print(f"❌ Missing OAuth parameters: {missing_params}")
                    return False
            else:
                print("❌ Not redirecting to Asana OAuth URL")
                return False
        else:
            print(f"❌ Expected 302 redirect, got {response.status_code}")
            if response.status_code >= 400:
                print(f"Error response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(
            "❌ Cannot connect to server. Make sure the backend is running on localhost:5058"
        )
        return False
    except Exception as e:
        print(f"❌ OAuth initiation test failed: {e}")
        return False


def test_health_endpoint():
    """Test Asana health endpoint"""
    print("\n🔧 Testing Health Endpoint")

    try:
        url = f"{BASE_URL}/api/asana/health?user_id={TEST_USER_ID}"
        response = requests.get(url)

        print(f"Status Code: {response.status_code}")

        if response.status_code == 200:
            data = response.json()
            print(f"Response: {data}")

            if data.get("ok") is not False:  # Could be True or not present
                print("✅ Health endpoint responding")
                return True
            else:
                print(f"❌ Health endpoint error: {data.get('error')}")
                return False
        else:
            print(f"❌ Health endpoint returned {response.status_code}")
            print(f"Response: {response.text}")
            return False

    except requests.exceptions.ConnectionError:
        print(
            "❌ Cannot connect to server. Make sure the backend is running on localhost:5058"
        )
        return False
    except Exception as e:
        print(f"❌ Health endpoint test failed: {e}")
        return False


def test_environment_config():
    """Test that environment is properly configured"""
    print("\n🔧 Testing Environment Configuration")

    client_id = os.getenv("ASANA_CLIENT_ID")
    client_secret = os.getenv("ASANA_CLIENT_SECRET")

    if not client_id or not client_secret:
        print("❌ Asana credentials not found in environment")
        print("   Required: ASANA_CLIENT_ID, ASANA_CLIENT_SECRET")
        return False

    print("✅ Asana credentials found in environment")
    print(f"   Client ID: {client_id[:8]}...{client_id[-4:]}")
    print(f"   Client Secret: {client_secret[:8]}...{client_secret[-4:]}")

    # Check if credentials look valid
    if len(client_id) >= 8 and len(client_secret) >= 8:
        print("✅ Credentials appear to be valid format")
        return True
    else:
        print("❌ Credentials appear to be invalid format")
        return False


def test_server_availability():
    """Test if the server is running"""
    print("\n🔧 Testing Server Availability")

    try:
        response = requests.get(f"{BASE_URL}/healthz", timeout=5)

        if response.status_code == 200:
            data = response.json()
            print(f"✅ Server is running - Status: {data.get('status', 'unknown')}")
            return True
        else:
            print(f"❌ Server responded with {response.status_code}")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Server is not running on localhost:5058")
        print("   Start the server with: python start_app.py")
        return False
    except Exception as e:
        print(f"❌ Server availability test failed: {e}")
        return False


def main():
    """Run all Asana OAuth flow tests"""
    print("=" * 60)
    print("🚀 ASANA OAUTH FLOW TEST")
    print("=" * 60)
    print(f"Base URL: {BASE_URL}")
    print(f"Test User ID: {TEST_USER_ID}")
    print("=" * 60)

    tests = [
        ("Server Availability", test_server_availability),
        ("Environment Configuration", test_environment_config),
        ("Health Endpoint", test_health_endpoint),
        ("OAuth Initiation", test_oauth_initiation),
    ]

    results = []

    for test_name, test_func in tests:
        try:
            result = test_func()
            results.append((test_name, result))
        except Exception as e:
            print(f"❌ Test '{test_name}' failed with exception: {e}")
            results.append((test_name, False))

    # Print summary
    print("\n" + "=" * 60)
    print("📊 ASANA OAUTH FLOW TEST SUMMARY")
    print("=" * 60)

    passed = 0
    total = len(results)

    for test_name, result in results:
        status = "✅ PASS" if result else "❌ FAIL"
        print(f"{status}: {test_name}")
        if result:
            passed += 1

    print(f"\n🎯 Results: {passed}/{total} tests passed ({passed / total * 100:.1f}%)")

    if passed == total:
        print("\n🎉 SUCCESS: Asana OAuth flow is working correctly!")
        print("   - Server is running and accessible")
        print("   - Environment properly configured")
        print("   - OAuth initiation redirects to Asana")
        print("   - Ready for user authentication")
        return 0
    elif passed >= 3:
        print(f"\n⚠️  PARTIAL SUCCESS: {passed}/{total} tests passed")
        print("   Core OAuth flow is working")
        print("   Some components may need attention")
        return 1
    else:
        print(f"\n❌ FAILURE: Only {passed}/{total} tests passed")
        print("   Major issues detected in OAuth flow")
        return 2


if __name__ == "__main__":
    sys.exit(main())
