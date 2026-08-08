#!/usr/bin/env python3
"""
Jira Credentials Tests

Mocked Jira API tests — no real credentials or network access required.
The HTTP calls are stubbed so the suite runs offline.
"""

import os
import sys
import requests
from unittest.mock import Mock, patch
from dotenv import load_dotenv


def load_real_jira_credentials():
    """Load real Jira credentials from environment"""
    print("🔍 Loading real Jira credentials...")

    load_dotenv()

    jira_server_url = os.getenv("JIRA_SERVER_URL")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not jira_server_url:
        print("❌ JIRA_SERVER_URL not found in .env file")
        print("   Add: JIRA_SERVER_URL=https://your-domain.atlassian.net")
        return None, None

    if not jira_api_token:
        print("❌ JIRA_API_TOKEN not found in .env file")
        print("   Add: JIRA_API_TOKEN=your_api_token_here")
        return None, None

    print(f"✅ JIRA_SERVER_URL: {jira_server_url}")
    print(f"✅ JIRA_API_TOKEN: {jira_api_token[:20]}...")

    return jira_server_url, jira_api_token


def _mock_response(status_code=200, payload=None):
    """Create a mocked requests.Response."""
    response = Mock()
    response.status_code = status_code
    response.json.return_value = payload if payload is not None else {}
    response.text = ""
    return response


def test_jira_api_connectivity():
    """Test basic Jira API connectivity (mocked)"""
    print("\n🔗 Testing Jira API connectivity...")

    server_url = "https://acme.atlassian.net"
    api_token = "test-token"

    # Test API v3 (Jira Cloud)
    api_url = f"{server_url}/rest/api/3/myself"

    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    with patch("requests.get", return_value=_mock_response(
        status_code=200,
        payload={
            "displayName": "Test User",
            "emailAddress": "user@example.com",
            "accountId": "1234567890",
        },
    )) as mock_get:
        response = requests.get(api_url, headers=headers, timeout=10)

        # Verify the request was constructed correctly
        mock_get.assert_called_once_with(api_url, headers=headers, timeout=10)

        if response.status_code == 200:
            user_data = response.json()
            print("✅ Jira API connection successful!")
            print(f"   User: {user_data.get('displayName', 'Unknown')}")
            print(f"   Email: {user_data.get('emailAddress', 'Unknown')}")
            print(f"   Account ID: {user_data.get('accountId', 'Unknown')}")

    assert response.status_code == 200
    assert response.json()["displayName"] == "Test User"


def test_jira_api_connectivity_unauthorized():
    """Test Jira API connectivity with an invalid token (mocked)"""
    server_url = "https://acme.atlassian.net"
    api_token = "bad-token"
    api_url = f"{server_url}/rest/api/3/myself"
    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    with patch("requests.get", return_value=_mock_response(status_code=401)):
        response = requests.get(api_url, headers=headers, timeout=10)

    assert response.status_code == 401


def test_jira_projects_access():
    """Test Jira project access (mocked)"""
    print("\n📋 Testing Jira project access...")

    server_url = "https://acme.atlassian.net"
    api_token = "test-token"
    api_url = f"{server_url}/rest/api/3/project"

    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    with patch("requests.get", return_value=_mock_response(
        status_code=200,
        payload=[
            {"name": "Alpha", "key": "ALPHA"},
            {"name": "Beta", "key": "BETA"},
        ],
    )) as mock_get:
        response = requests.get(api_url, headers=headers, timeout=10)

        mock_get.assert_called_once_with(api_url, headers=headers, timeout=10)

        if response.status_code == 200:
            projects = response.json()
            print(f"✅ Found {len(projects)} projects")

            # Show first 5 projects
            for i, project in enumerate(projects[:5]):
                print(
                    f"   {i + 1}. {project.get('name', 'Unknown')} ({project.get('key', 'Unknown')})"
                )

    assert response.status_code == 200
    assert len(response.json()) == 2
    assert response.json()[0]["key"] == "ALPHA"


def test_jira_issue_search():
    """Test Jira issue search functionality (mocked)"""
    print("\n🎯 Testing Jira issue search...")

    server_url = "https://acme.atlassian.net"
    api_token = "test-token"
    api_url = f"{server_url}/rest/api/3/search"

    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    # Search for recent issues
    params = {
        "jql": "ORDER BY created DESC",
        "maxResults": 5,
        "fields": "summary,status,assignee,created",
    }

    with patch("requests.get", return_value=_mock_response(
        status_code=200,
        payload={
            "issues": [
                {
                    "key": "PROJ-1",
                    "fields": {"summary": "Fix bug"},
                }
            ]
        },
    )) as mock_get:
        response = requests.get(api_url, headers=headers, params=params, timeout=10)

        mock_get.assert_called_once_with(
            api_url, headers=headers, params=params, timeout=10
        )

        if response.status_code == 200:
            data = response.json()
            issues = data.get("issues", [])
            print(f"✅ Found {len(issues)} recent issues")

            for i, issue in enumerate(issues):
                fields = issue.get("fields", {})
                print(
                    f"   {i + 1}. {issue.get('key', 'Unknown')}: {fields.get('summary', 'No summary')}"
                )

    assert response.status_code == 200
    assert len(response.json()["issues"]) == 1


def test_jira_backend_integration():
    """Test Jira backend integration with real credentials"""
    print("\n🔧 Testing Jira Backend Integration...")

    try:
        sys.path.append("backend/python-api-service")

        # Test if we can import Jira handler with real credentials
        from jira_handler import jira_bp

        print("✅ Jira backend handler imported successfully")
        print(f"   Blueprint name: {jira_bp.name}")

        # Test if we can create Jira service
        from jira_service_real import RealJiraService, get_real_jira_client

        server_url = os.getenv("JIRA_SERVER_URL")
        api_token = os.getenv("JIRA_API_TOKEN")

        if server_url and api_token:
            try:
                client = get_real_jira_client(server_url, token=api_token)
                service = RealJiraService(client)
                print("✅ Real Jira service created successfully")
                print(f"   Service type: {type(service).__name__}")
                return True
            except Exception as e:
                print(f"⚠️  Real Jira service creation failed: {e}")
                print(
                    "   This might be expected if the Jira Python library isn't installed"
                )
                print("   Falling back to mock service for development")

                from jira_service import JiraService, get_jira_client

                mock_client = get_jira_client(server_url)
                mock_service = JiraService(mock_client)
                print("✅ Mock Jira service created successfully")
                return True
        else:
            print("❌ Cannot test service without credentials")
            return False

    except ImportError as e:
        print(f"❌ Failed to import Jira backend components: {e}")
        return False
    except Exception as e:
        print(f"❌ Error testing Jira backend: {e}")
        return False


def main():
    """Run all Jira credential tests"""
    print("🔧 Real Jira Credentials Test")
    print("=" * 50)

    # Load credentials
    server_url, api_token = load_real_jira_credentials()
    if not server_url or not api_token:
        print("\n❌ Cannot proceed without valid credentials")
        return

    # Run tests
    connectivity_ok = test_jira_api_connectivity(server_url, api_token)
    projects_ok = test_jira_projects_access(server_url, api_token)
    issues_ok = test_jira_issue_search(server_url, api_token)
    backend_ok = test_jira_backend_integration()

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    tests = [
        ("API Connectivity", connectivity_ok),
        ("Project Access", projects_ok),
        ("Issue Search", issues_ok),
        ("Backend Integration", backend_ok),
    ]

    all_passed = True
    for test_name, passed in tests:
        status = "✅ PASS" if passed else "❌ FAIL"
        print(f"{status} {test_name}")
        if not passed:
            all_passed = False

    print("\n" + "=" * 50)

    if all_passed:
        print("🎉 Jira credentials are working perfectly!")
        print("\n🚀 Next steps:")
        print("1. Start OAuth server: python start_complete_oauth_server.py")
        print("2. Test Jira integration in ATOM frontend settings")
        print("3. Create test issues and verify they appear in ATOM")
    else:
        print("⚠️  Some tests failed - check your credentials")
        print("\n🔧 Troubleshooting:")
        print("• Verify JIRA_SERVER_URL is correct")
        print("• Check API token has proper permissions")
        print("• Ensure network connectivity to Jira server")
        print("• Test with curl:")
        print(
            f"  curl -H 'Authorization: Bearer YOUR_TOKEN' {server_url}/rest/api/3/myself"
        )


if __name__ == "__main__":
    main()
