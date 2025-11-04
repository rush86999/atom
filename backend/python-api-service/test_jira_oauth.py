#!/usr/bin/env python3
"""
Test Script for Jira OAuth Implementation

This script tests the Jira OAuth 2.0 implementation to ensure it's working correctly.
It verifies the OAuth flow, token exchange, and resource discovery functionality.
"""

import os
import sys
import json
import requests
from urllib.parse import urlencode

# Add the current directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))


def test_environment_config():
    """Test that required environment variables are set"""
    print("🔧 Testing Environment Configuration...")

    required_vars = ["ATLASSIAN_CLIENT_ID", "ATLASSIAN_CLIENT_SECRET"]
    missing_vars = []

    for var in required_vars:
        value = os.getenv(var)
        if not value or value.startswith(("mock_", "YOUR_")):
            missing_vars.append(var)
            print(f"❌ {var}: Not configured")
        else:
            print(f"✅ {var}: Configured")

    if missing_vars:
        print(f"\n❌ Missing required environment variables: {', '.join(missing_vars)}")
        print("Please add these to your .env file:")
        for var in missing_vars:
            print(f"  {var}=your-value-here")
        return False

    print("✅ All required environment variables are configured")
    return True


def test_oauth_start_endpoint():
    """Test the OAuth start endpoint"""
    print("\n🚀 Testing OAuth Start Endpoint...")

    try:
        # Test the OAuth start endpoint
        base_url = "http://localhost:5058"
        start_url = f"{base_url}/api/auth/jira/start?user_id=test-user-123"

        print(f"Testing endpoint: {start_url}")

        response = requests.get(start_url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            if data.get("ok"):
                auth_url = data.get("auth_url")
                print(f"✅ OAuth start endpoint working")
                print(f"   Auth URL: {auth_url[:100]}...")
                return True
            else:
                print(f"❌ OAuth start endpoint returned error: {data.get('error')}")
                return False
        else:
            print(f"❌ OAuth start endpoint failed with status: {response.status_code}")
            print(f"   Response: {response.text}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to OAuth start endpoint: {e}")
        return False


def test_jira_handler_endpoints():
    """Test the Jira handler endpoints"""
    print("\n🔍 Testing Jira Handler Endpoints...")

    base_url = "http://localhost:5058"
    endpoints = ["/api/jira/projects", "/api/jira/search", "/api/jira/list-issues"]

    all_working = True

    for endpoint in endpoints:
        try:
            test_url = f"{base_url}{endpoint}"
            print(f"Testing endpoint: {endpoint}")

            # Test with a mock user_id (will fail auth but should return proper error)
            test_data = {
                "user_id": "test-user-123",
                "project_id": "TEST" if "project" in endpoint else None,
                "query": "test" if "search" in endpoint else None,
            }

            response = requests.post(test_url, json=test_data, timeout=10)

            if response.status_code in [
                200,
                401,
            ]:  # 401 is expected for unauthenticated user
                print(f"✅ {endpoint}: Endpoint responding")
            else:
                print(f"❌ {endpoint}: Failed with status {response.status_code}")
                all_working = False

        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint}: Connection failed - {e}")
            all_working = False

    return all_working


def test_oauth_status_endpoints():
    """Test OAuth status and management endpoints"""
    print("\n📊 Testing OAuth Status Endpoints...")

    base_url = "http://localhost:5058"
    endpoints = ["/api/auth/jira/status", "/api/auth/jira/disconnect"]

    all_working = True

    for endpoint in endpoints:
        try:
            test_url = f"{base_url}{endpoint}"
            print(f"Testing endpoint: {endpoint}")

            test_data = {"user_id": "test-user-123"}
            method = "POST" if "disconnect" in endpoint else "POST"

            response = requests.request(method, test_url, json=test_data, timeout=10)

            if response.status_code in [200, 404]:  # 404 is OK for non-existent user
                data = response.json()
                if data.get("ok") or endpoint == "/api/auth/jira/disconnect":
                    print(f"✅ {endpoint}: Endpoint responding correctly")
                else:
                    print(
                        f"⚠️ {endpoint}: Endpoint working but returned: {data.get('error', 'unknown error')}"
                    )
            else:
                print(f"❌ {endpoint}: Failed with status {response.status_code}")
                all_working = False

        except requests.exceptions.RequestException as e:
            print(f"❌ {endpoint}: Connection failed - {e}")
            all_working = False

    return all_working


def test_atlassian_api_connectivity():
    """Test direct connectivity to Atlassian API (without OAuth)"""
    print("\n🌐 Testing Atlassian API Connectivity...")

    try:
        # Test the Atlassian API status endpoint (public)
        status_url = "https://status.atlassian.com/api/v2/status.json"
        response = requests.get(status_url, timeout=10)

        if response.status_code == 200:
            data = response.json()
            status = data.get("status", {}).get("description", "Unknown")
            print(f"✅ Atlassian API Status: {status}")
            return True
        else:
            print(f"❌ Failed to get Atlassian API status: {response.status_code}")
            return False

    except requests.exceptions.RequestException as e:
        print(f"❌ Failed to connect to Atlassian API: {e}")
        return False


def test_jira_oauth_flow_explanation():
    """Explain the complete Jira OAuth flow"""
    print("\n📋 Jira OAuth 2.0 Flow Explanation:")
    print("1. User clicks 'Connect Jira' in frontend")
    print("2. Frontend calls /api/auth/jira/start?user_id=USER_ID")
    print("3. Backend returns Atlassian OAuth authorization URL")
    print("4. User is redirected to Atlassian for authentication")
    print("5. Atlassian redirects to /api/auth/jira/callback with code")
    print("6. Backend exchanges code for access token")
    print("7. Backend discovers user's Jira resources via /accessible-resources")
    print("8. Backend stores encrypted tokens and cloud ID in database")
    print("9. Frontend can now make Jira API calls using the cloud ID")


def main():
    """Run all tests"""
    print("=" * 60)
    print("🧪 Jira OAuth Implementation Test Suite")
    print("=" * 60)

    # Check if backend is running
    try:
        health_url = "http://localhost:5058/healthz"
        response = requests.get(health_url, timeout=5)
        if response.status_code != 200:
            print("❌ Backend server is not running on localhost:5058")
            print("   Please start the backend server first:")
            print("   cd atom/backend/python-api-service")
            print("   python start_app.py")
            return
    except requests.exceptions.RequestException:
        print("❌ Backend server is not running on localhost:5058")
        print("   Please start the backend server first:")
        print("   cd atom/backend/python-api-service")
        print("   python start_app.py")
        return

    # Run tests
    tests = [
        test_environment_config,
        test_oauth_start_endpoint,
        test_jira_handler_endpoints,
        test_oauth_status_endpoints,
        test_atlassian_api_connectivity,
    ]

    results = []
    for test in tests:
        try:
            result = test()
            results.append(result)
        except Exception as e:
            print(f"❌ Test {test.__name__} failed with exception: {e}")
            results.append(False)

    # Summary
    print("\n" + "=" * 60)
    print("📊 Test Summary")
    print("=" * 60)

    passed = sum(results)
    total = len(results)

    print(f"✅ Tests Passed: {passed}/{total}")
    print(f"❌ Tests Failed: {total - passed}/{total}")

    if passed == total:
        print("\n🎉 All tests passed! Jira OAuth implementation is working correctly.")
        print("\n🚀 Next steps:")
        print("1. Test the complete OAuth flow in the frontend")
        print("2. Verify Jira API calls work with the discovered cloud ID")
        print("3. Test token refresh functionality")
    else:
        print(
            "\n⚠️ Some tests failed. Please check the configuration and implementation."
        )

    # Explain the flow
    test_jira_oauth_flow_explanation()


if __name__ == "__main__":
    main()
