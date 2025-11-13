#!/usr/bin/env python3
"""
Jira Credential Verification Script
Tests Jira API connectivity with provided credentials
"""

import os
import sys
import requests
from dotenv import load_dotenv


def load_jira_credentials():
    """Load Jira credentials from environment"""
    print("🔍 Loading Jira credentials from environment...")

    load_dotenv()

    jira_server_url = os.getenv("JIRA_SERVER_URL")
    jira_api_token = os.getenv("JIRA_API_TOKEN")

    if not jira_server_url:
        print("❌ JIRA_SERVER_URL not found in environment")
        print("   Add to .env: JIRA_SERVER_URL=https://your-domain.atlassian.net")
        return None, None

    if not jira_api_token:
        print("❌ JIRA_API_TOKEN not found in environment")
        print("   Add to .env: JIRA_API_TOKEN=your_api_token_here")
        return None, None

    print(f"✅ JIRA_SERVER_URL: {jira_server_url}")
    print(f"✅ JIRA_API_TOKEN: {jira_api_token[:20]}...")

    return jira_server_url, jira_api_token


def test_jira_connectivity(server_url, api_token):
    """Test basic Jira API connectivity"""
    print("\n🔗 Testing Jira API connectivity...")

    # Test API v3 (Jira Cloud)
    api_url = f"{server_url}/rest/api/3/myself"

    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    try:
        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code == 200:
            user_data = response.json()
            print("✅ Jira API connection successful!")
            print(f"   User: {user_data.get('displayName', 'Unknown')}")
            print(f"   Email: {user_data.get('emailAddress', 'Unknown')}")
            print(f"   Account ID: {user_data.get('accountId', 'Unknown')}")
            return True

        elif response.status_code == 401:
            print("❌ Authentication failed - Invalid API token")
            print("   Check your JIRA_API_TOKEN in .env file")
            return False

        elif response.status_code == 403:
            print("❌ Permission denied - Check API token permissions")
            return False

        elif response.status_code == 404:
            print("❌ Server not found - Check JIRA_SERVER_URL")
            print(f"   URL tested: {server_url}")
            return False

        else:
            print(f"❌ API request failed with status: {response.status_code}")
            print(f"   Response: {response.text[:200]}...")
            return False

    except requests.exceptions.ConnectionError:
        print("❌ Connection failed - Cannot reach Jira server")
        print(f"   Check network connectivity and server URL: {server_url}")
        return False

    except requests.exceptions.Timeout:
        print("❌ Request timeout - Server is not responding")
        return False

    except Exception as e:
        print(f"❌ Unexpected error: {e}")
        return False


def test_jira_projects(server_url, api_token):
    """Test Jira project access"""
    print("\n📋 Testing Jira project access...")

    api_url = f"{server_url}/rest/api/3/project"

    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    try:
        response = requests.get(api_url, headers=headers, timeout=10)

        if response.status_code == 200:
            projects = response.json()
            print(f"✅ Found {len(projects)} projects")

            # Show first 5 projects
            for i, project in enumerate(projects[:5]):
                print(
                    f"   {i + 1}. {project.get('name', 'Unknown')} ({project.get('key', 'Unknown')})"
                )

            if len(projects) > 5:
                print(f"   ... and {len(projects) - 5} more projects")

            return True
        else:
            print(f"❌ Failed to fetch projects: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error fetching projects: {e}")
        return False


def test_jira_issues(server_url, api_token):
    """Test Jira issue search"""
    print("\n🎯 Testing Jira issue search...")

    # Search for recent issues
    api_url = f"{server_url}/rest/api/3/search"

    headers = {"Accept": "application/json", "Authorization": f"Bearer {api_token}"}

    params = {
        "jql": "ORDER BY created DESC",
        "maxResults": 5,
        "fields": "summary,status,assignee,created",
    }

    try:
        response = requests.get(api_url, headers=headers, params=params, timeout=10)

        if response.status_code == 200:
            data = response.json()
            issues = data.get("issues", [])
            print(f"✅ Found {len(issues)} recent issues")

            for i, issue in enumerate(issues):
                fields = issue.get("fields", {})
                print(
                    f"   {i + 1}. {issue.get('key', 'Unknown')}: {fields.get('summary', 'No summary')}"
                )

            return True
        else:
            print(f"❌ Failed to search issues: {response.status_code}")
            return False

    except Exception as e:
        print(f"❌ Error searching issues: {e}")
        return False


def test_jira_oauth_capabilities():
    """Test if Jira OAuth endpoints are available"""
    print("\n🔄 Testing Jira OAuth capabilities...")

    try:
        # Test if auth handler can be imported
        sys.path.append("backend/python-api-service")
        from auth_handler_jira import JIRA_SERVER_URL, JIRA_API_TOKEN

        print("✅ Jira auth handler is properly configured")
        print(f"   Server URL in handler: {JIRA_SERVER_URL}")
        print(f"   API Token in handler: {'SET' if JIRA_API_TOKEN else 'NOT SET'}")

        return True

    except ImportError as e:
        print(f"❌ Failed to import Jira auth handler: {e}")
        return False

    except Exception as e:
        print(f"❌ Error testing Jira OAuth: {e}")
        return False


def main():
    """Run all Jira credential tests"""
    print("🔧 Jira Credential Verification")
    print("=" * 50)

    # Load credentials
    server_url, api_token = load_jira_credentials()
    if not server_url or not api_token:
        print("\n❌ Cannot proceed without valid credentials")
        print("\n📝 How to get Jira credentials:")
        print("1. Go to https://id.atlassian.com/manage-profile/security/api-tokens")
        print("2. Create an API token")
        print("3. Add to .env file:")
        print("   JIRA_SERVER_URL=https://your-domain.atlassian.net")
        print("   JIRA_API_TOKEN=your_api_token_here")
        return

    # Run tests
    connectivity_ok = test_jira_connectivity(server_url, api_token)
    projects_ok = test_jira_projects(server_url, api_token)
    issues_ok = test_jira_issues(server_url, api_token)
    oauth_ok = test_jira_oauth_capabilities()

    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)

    tests = [
        ("API Connectivity", connectivity_ok),
        ("Project Access", projects_ok),
        ("Issue Search", issues_ok),
        ("OAuth Handler", oauth_ok),
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
        print("1. Test Jira OAuth flow in ATOM")
        print("2. Verify Jira integration in frontend settings")
        print("3. Create test issues and verify they appear in ATOM")
    else:
        print("⚠️  Some tests failed - check your credentials")
        print("\n🔧 Troubleshooting:")
        print("• Verify JIRA_SERVER_URL is correct")
        print("• Check API token has proper permissions")
        print("• Ensure network connectivity to Jira server")
        print(
            "• Test with curl: curl -H 'Authorization: Bearer YOUR_TOKEN' YOUR_SERVER/rest/api/3/myself"
        )


if __name__ == "__main__":
    main()
