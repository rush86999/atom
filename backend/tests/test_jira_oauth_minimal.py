#!/usr/bin/env python3
"""
Minimal Jira OAuth Test Script
Tests Jira OAuth configuration and connectivity without requiring backend
"""

import os
import sys
import asyncio
import httpx
import json
from urllib.parse import urlencode
from dotenv import load_dotenv

# Load environment variables
load_dotenv()


class JiraOAuthMinimalTest:
    def __init__(self):
        self.client_id = os.getenv("JIRA_CLIENT_ID")
        self.client_secret = os.getenv("JIRA_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "JIRA_REDIRECT_URI", "http://localhost:8000/api/auth/jira/callback"
        )
        self.atlassian_auth_url = "https://auth.atlassian.com"
        self.atlassian_api_url = "https://api.atlassian.com"

    def print_header(self, message):
        """Print formatted header"""
        print(f"\n{'=' * 60}")
        print(f"🧪 {message}")
        print(f"{'=' * 60}")

    def print_success(self, message):
        """Print success message"""
        print(f"✅ {message}")

    def print_warning(self, message):
        """Print warning message"""
        print(f"⚠️  {message}")

    def print_error(self, message):
        """Print error message"""
        print(f"❌ {message}")

    def test_configuration(self):
        """Test Jira OAuth configuration"""
        self.print_header("Testing Jira OAuth Configuration")

        config_ok = True

        # Check required environment variables
        if not self.client_id:
            self.print_error("JIRA_CLIENT_ID not found in environment")
            config_ok = False
        else:
            self.print_success(f"JIRA_CLIENT_ID: {self.client_id[:10]}...")

        if not self.client_secret:
            self.print_error("JIRA_CLIENT_SECRET not found in environment")
            config_ok = False
        else:
            self.print_success(f"JIRA_CLIENT_SECRET: {self.client_secret[:10]}...")

        self.print_success(f"JIRA_REDIRECT_URI: {self.redirect_uri}")

        if config_ok:
            self.print_success("Configuration validation passed")
        else:
            self.print_error("Configuration validation failed")

        return config_ok

    async def test_atlassian_connectivity(self):
        """Test connectivity to Atlassian endpoints"""
        self.print_header("Testing Atlassian Connectivity")

        endpoints = [
            ("Atlassian Auth", "https://auth.atlassian.com"),
            ("Atlassian API", "https://api.atlassian.com"),
            ("Token Endpoint", "https://auth.atlassian.com/oauth/token"),
        ]

        results = {}

        async with httpx.AsyncClient() as client:
            for name, url in endpoints:
                try:
                    response = await client.get(url, timeout=10.0)
                    if response.status_code in [200, 301, 302, 401]:
                        self.print_success(
                            f"{name} - Reachable (Status: {response.status_code})"
                        )
                        results[name] = "REACHABLE"
                    else:
                        self.print_warning(f"{name} - Status {response.status_code}")
                        results[name] = f"STATUS_{response.status_code}"
                except Exception as e:
                    self.print_error(f"{name} - Connection failed: {e}")
                    results[name] = "UNREACHABLE"

        return results

    async def test_oauth_authorization_flow(self):
        """Test OAuth authorization URL generation"""
        self.print_header("Testing OAuth Authorization Flow")

        try:
            # Generate authorization URL with required scopes
            auth_params = {
                "audience": "api.atlassian.com",
                "client_id": self.client_id,
                "scope": "read:jira-work read:issue-details:jira read:comments:jira read:attachments:jira",
                "redirect_uri": self.redirect_uri,
                "response_type": "code",
                "state": "test_state_minimal_123",
                "prompt": "consent",
            }

            auth_url = f"{self.atlassian_auth_url}/authorize?{urlencode(auth_params)}"

            self.print_success("Authorization URL generated successfully")
            self.print_success(f"URL Length: {len(auth_url)} characters")
            self.print_success(f"Scopes: {auth_params['scope']}")

            # Test if the authorization URL is accessible
            async with httpx.AsyncClient() as client:
                try:
                    response = await client.get(
                        auth_url, follow_redirects=False, timeout=10.0
                    )
                    if response.status_code in [200, 302]:
                        self.print_success("Authorization endpoint is reachable")
                    else:
                        self.print_warning(
                            f"Authorization endpoint status: {response.status_code}"
                        )
                except Exception as e:
                    self.print_warning(f"Authorization endpoint test: {e}")

            # Print the authorization URL for manual testing
            print(f"\n🔗 Authorization URL for manual testing:")
            print(f"{auth_url}")
            print(f"\n📝 To test manually:")
            print(f"1. Copy the URL above")
            print(f"2. Open in browser")
            print(f"3. Complete OAuth flow")
            print(f"4. Note the authorization code from redirect URL")

            return auth_url

        except Exception as e:
            self.print_error(f"Failed to generate authorization URL: {e}")
            return None

    async def test_token_endpoint(self):
        """Test token endpoint functionality"""
        self.print_header("Testing Token Endpoint")

        token_url = f"{self.atlassian_auth_url}/oauth/token"

        try:
            async with httpx.AsyncClient() as client:
                # Test with invalid code to verify endpoint is working
                test_data = {
                    "grant_type": "authorization_code",
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": "invalid_test_code_minimal_456",
                    "redirect_uri": self.redirect_uri,
                }

                response = await client.post(token_url, data=test_data, timeout=10.0)

                if response.status_code == 400:
                    self.print_success("Token endpoint is responding correctly")
                    self.print_success("(Expected 400 for invalid authorization code)")

                    # Try to parse error response
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            self.print_success(f"Error type: {error_data['error']}")
                    except:
                        pass

                elif response.status_code == 401:
                    self.print_warning(
                        "Token endpoint returned 401 - check client credentials"
                    )
                else:
                    self.print_warning(
                        f"Token endpoint returned status: {response.status_code}"
                    )

                return response.status_code

        except Exception as e:
            self.print_error(f"Token endpoint test failed: {e}")
            return None

    async def test_accessible_resources(self):
        """Test accessible resources endpoint (requires valid token)"""
        self.print_header("Testing Accessible Resources Endpoint")

        resources_url = f"{self.atlassian_api_url}/oauth/token/accessible-resources"

        # This test requires a valid access token, so we'll just test connectivity
        try:
            async with httpx.AsyncClient() as client:
                # Test without token (should return 401)
                response = await client.get(resources_url, timeout=10.0)

                if response.status_code == 401:
                    self.print_success(
                        "Accessible resources endpoint requires authentication"
                    )
                    self.print_success("(Expected 401 without access token)")
                else:
                    self.print_warning(
                        f"Accessible resources endpoint status: {response.status_code}"
                    )

        except Exception as e:
            self.print_error(f"Accessible resources test failed: {e}")

    def test_code_structure(self):
        """Test if Jira integration code structure exists"""
        self.print_header("Testing Code Structure")

        files_to_check = [
            "backend/python-api-service/jira_handler.py",
            "backend/python-api-service/jira_service_real.py",
            "backend/python-api-service/db_oauth_jira.py",
            "backend/jira_oauth_api.py",
            "src/ui-shared/integrations/jira/components/JiraManager.tsx",
            "frontend-nextjs/pages/oauth/jira/callback.tsx",
        ]

        results = {}

        for file_path in files_to_check:
            if os.path.exists(file_path):
                self.print_success(f"{file_path} - Exists")
                results[file_path] = "EXISTS"

                # Check file size
                file_size = os.path.getsize(file_path)
                if file_size > 100:  # Reasonable minimum size
                    self.print_success(f"  Size: {file_size} bytes")
                else:
                    self.print_warning(f"  Size: {file_size} bytes (may be empty)")
            else:
                self.print_error(f"{file_path} - Missing")
                results[file_path] = "MISSING"

        return results

    async def run_comprehensive_test(self):
        """Run all minimal tests"""
        self.print_header("JIRA OAUTH MINIMAL TEST SUITE")
        print("Testing Jira OAuth configuration without backend dependency...")

        # Run all test suites
        test_results = {}

        # Test configuration first
        config_ok = self.test_configuration()
        if not config_ok:
            self.print_error("Configuration failed - stopping tests")
            return test_results

        # Run connectivity tests
        test_results["connectivity"] = await self.test_atlassian_connectivity()
        test_results["authorization_flow"] = await self.test_oauth_authorization_flow()
        test_results["token_endpoint"] = await self.test_token_endpoint()
        test_results["resources_endpoint"] = await self.test_accessible_resources()
        test_results["code_structure"] = self.test_code_structure()

        # Print summary
        self.print_header("MINIMAL TEST SUMMARY")

        total_checks = 0
        passed_checks = 0

        for category, results in test_results.items():
            if category == "authorization_flow":
                # Special handling for auth URL
                if results:
                    passed_checks += 1
                total_checks += 1
                continue

            if isinstance(results, dict):
                for test, result in results.items():
                    total_checks += 1
                    if result in ["REACHABLE", "EXISTS", 400, 401]:
                        passed_checks += 1

        print(f"\n🎯 Test Results: {passed_checks}/{total_checks} checks passed")

        if passed_checks == total_checks:
            self.print_success(
                "All minimal tests passed! Jira OAuth is configured correctly."
            )
            print(f"\n🚀 Next Steps:")
            print(f"1. Start the backend: ./start-backend.sh")
            print(f"2. Test the complete OAuth flow")
            print(f"3. Verify Jira integration in the frontend")
        else:
            self.print_warning(f"{total_checks - passed_checks} checks need attention")
            print(f"\n🔧 Recommended Actions:")
            print(f"1. Check Atlassian Developer Console configuration")
            print(f"2. Verify redirect URI matches your backend URL")
            print(f"3. Ensure required scopes are enabled")

        return test_results


async def main():
    """Main test function"""
    tester = JiraOAuthMinimalTest()
    await tester.run_comprehensive_test()


if __name__ == "__main__":
    # Run async tests
    asyncio.run(main())
