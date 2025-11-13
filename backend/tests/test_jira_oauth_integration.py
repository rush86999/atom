#!/usr/bin/env python3
"""
Jira OAuth Integration Test Script
Tests the complete Jira OAuth flow and API integration
"""

import os
import sys
import asyncio
import httpx
import json
from urllib.parse import urlencode, urlparse, parse_qs
from dotenv import load_dotenv

# Add backend to path for imports
sys.path.append(
    os.path.join(os.path.dirname(__file__), "backend", "python-api-service")
)

# Load environment variables
load_dotenv()


class JiraOAuthIntegrationTest:
    def __init__(self):
        self.base_url = "http://localhost:5059"  # Default backend port
        self.client_id = os.getenv("JIRA_CLIENT_ID")
        self.client_secret = os.getenv("JIRA_CLIENT_SECRET")
        self.redirect_uri = os.getenv(
            "JIRA_REDIRECT_URI", "http://localhost:5059/api/auth/jira/callback"
        )

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

    async def test_backend_health(self):
        """Test if backend is running"""
        self.print_header("Testing Backend Health")

        try:
            async with httpx.AsyncClient() as client:
                response = await client.get(f"{self.base_url}/health", timeout=10.0)

                if response.status_code == 200:
                    self.print_success("Backend is running and healthy")
                    return True
                else:
                    self.print_error(f"Backend returned status {response.status_code}")
                    return False

        except httpx.ConnectError:
            self.print_error("Backend is not running")
            self.print_warning("Start the backend with: ./start-backend.sh")
            return False
        except Exception as e:
            self.print_error(f"Backend health check failed: {e}")
            return False

    async def test_jira_oauth_endpoints(self):
        """Test Jira OAuth endpoints"""
        self.print_header("Testing Jira OAuth Endpoints")

        endpoints = {
            "/api/auth/jira/start": "GET",
            "/api/auth/jira/status": "POST",
            "/api/auth/jira/disconnect": "POST",
        }

        results = {}

        async with httpx.AsyncClient() as client:
            for endpoint, method in endpoints.items():
                try:
                    url = f"{self.base_url}{endpoint}"

                    if method == "GET":
                        # Test start endpoint with user_id parameter
                        response = await client.get(
                            f"{url}?user_id=test_user_123", timeout=10.0
                        )
                    else:
                        # Test POST endpoints with user_id in body
                        response = await client.post(
                            url, json={"user_id": "test_user_123"}, timeout=10.0
                        )

                    if response.status_code in [200, 400, 401]:
                        self.print_success(
                            f"{endpoint} - Responding (Status: {response.status_code})"
                        )
                        results[endpoint] = "SUCCESS"
                    else:
                        self.print_warning(
                            f"{endpoint} - Unexpected status: {response.status_code}"
                        )
                        results[endpoint] = "WARNING"

                    # Print response details for debugging
                    if response.status_code != 200:
                        try:
                            error_data = response.json()
                            self.print_warning(
                                f"  Response: {json.dumps(error_data, indent=2)}"
                            )
                        except:
                            self.print_warning(f"  Response: {response.text[:200]}")

                except Exception as e:
                    self.print_error(f"{endpoint} - Failed: {e}")
                    results[endpoint] = "FAILED"

        return results

    async def test_jira_api_endpoints(self):
        """Test Jira API endpoints"""
        self.print_header("Testing Jira API Endpoints")

        endpoints = {
            "/api/jira/projects": {"user_id": "test_user_123"},
            "/api/jira/search": {
                "user_id": "test_user_123",
                "project_id": "TEST",
                "query": "test",
            },
            "/api/jira/list-issues": {"user_id": "test_user_123", "project_id": "TEST"},
        }

        results = {}

        async with httpx.AsyncClient() as client:
            for endpoint, data in endpoints.items():
                try:
                    url = f"{self.base_url}{endpoint}"
                    response = await client.post(url, json=data, timeout=10.0)

                    if response.status_code == 401:
                        self.print_success(
                            f"{endpoint} - Properly requires authentication"
                        )
                        results[endpoint] = "AUTH_REQUIRED"
                    elif response.status_code == 400:
                        self.print_warning(
                            f"{endpoint} - Validation error (may need real project ID)"
                        )
                        results[endpoint] = "VALIDATION_ERROR"
                    elif response.status_code == 200:
                        self.print_success(f"{endpoint} - Working")
                        results[endpoint] = "SUCCESS"
                    else:
                        self.print_warning(
                            f"{endpoint} - Status: {response.status_code}"
                        )
                        results[endpoint] = "UNEXPECTED_STATUS"

                    # Print response details
                    try:
                        response_data = response.json()
                        if "error" in response_data:
                            self.print_warning(f"  Error: {response_data['error']}")
                    except:
                        pass

                except Exception as e:
                    self.print_error(f"{endpoint} - Failed: {e}")
                    results[endpoint] = "FAILED"

        return results

    async def test_oauth_flow_simulation(self):
        """Simulate OAuth flow steps"""
        self.print_header("Simulating OAuth Flow")

        steps = [
            ("Configuration Check", self._check_configuration),
            ("Authorization URL Generation", self._generate_auth_url),
            ("Token Exchange Simulation", self._simulate_token_exchange),
        ]

        results = {}

        for step_name, step_func in steps:
            try:
                result = await step_func()
                self.print_success(f"{step_name} - {result}")
                results[step_name] = "SUCCESS"
            except Exception as e:
                self.print_error(f"{step_name} - Failed: {e}")
                results[step_name] = "FAILED"

        return results

    async def _check_configuration(self):
        """Check OAuth configuration"""
        if not self.client_id:
            raise ValueError("JIRA_CLIENT_ID not configured")
        if not self.client_secret:
            raise ValueError("JIRA_CLIENT_SECRET not configured")
        return "Configuration valid"

    async def _generate_auth_url(self):
        """Generate OAuth authorization URL"""
        auth_params = {
            "audience": "api.atlassian.com",
            "client_id": self.client_id,
            "scope": "read:jira-work read:issue-details:jira read:comments:jira read:attachments:jira",
            "redirect_uri": self.redirect_uri,
            "response_type": "code",
            "state": "test_state_12345",
            "prompt": "consent",
        }

        auth_url = f"https://auth.atlassian.com/authorize?{urlencode(auth_params)}"
        return f"URL generated ({len(auth_url)} chars)"

    async def _simulate_token_exchange(self):
        """Simulate token exchange with invalid code"""
        token_url = "https://auth.atlassian.com/oauth/token"

        async with httpx.AsyncClient() as client:
            data = {
                "grant_type": "authorization_code",
                "client_id": self.client_id,
                "client_secret": self.client_secret,
                "code": "invalid_test_code_123",
                "redirect_uri": self.redirect_uri,
            }

            response = await client.post(token_url, data=data, timeout=10.0)

            if response.status_code == 400:
                return "Token endpoint responding correctly"
            else:
                raise ValueError(
                    f"Unexpected token endpoint response: {response.status_code}"
                )

    async def test_frontend_integration(self):
        """Test frontend integration points"""
        self.print_header("Testing Frontend Integration")

        # Check if frontend files exist
        frontend_files = [
            "src/ui-shared/integrations/jira/components/JiraManager.tsx",
            "frontend-nextjs/pages/oauth/jira/callback.tsx",
            "src/skills/jiraSkills.ts",
        ]

        results = {}

        for file_path in frontend_files:
            if os.path.exists(file_path):
                self.print_success(f"{file_path} - Exists")
                results[file_path] = "EXISTS"
            else:
                self.print_error(f"{file_path} - Missing")
                results[file_path] = "MISSING"

        return results

    async def run_comprehensive_test(self):
        """Run all integration tests"""
        self.print_header("JIRA OAUTH INTEGRATION TEST SUITE")
        print("Testing complete Jira OAuth integration...")

        # Run all test suites
        test_results = {}

        # Test backend health
        backend_healthy = await self.test_backend_health()
        if not backend_healthy:
            self.print_error("Backend not available - stopping tests")
            return test_results

        # Run other tests
        test_results["oauth_endpoints"] = await self.test_jira_oauth_endpoints()
        test_results["api_endpoints"] = await self.test_jira_api_endpoints()
        test_results["oauth_flow"] = await self.test_oauth_flow_simulation()
        test_results["frontend"] = await self.test_frontend_integration()

        # Print summary
        self.print_header("TEST SUMMARY")

        total_tests = 0
        passed_tests = 0
        failed_tests = 0

        for category, results in test_results.items():
            print(f"\n📊 {category.upper()}:")
            for test, result in results.items():
                status_icon = (
                    "✅" if result in ["SUCCESS", "EXISTS", "AUTH_REQUIRED"] else "❌"
                )
                print(f"  {status_icon} {test}: {result}")
                total_tests += 1
                if result in ["SUCCESS", "EXISTS", "AUTH_REQUIRED"]:
                    passed_tests += 1
                else:
                    failed_tests += 1

        print(f"\n🎯 Overall Results: {passed_tests}/{total_tests} tests passed")

        if failed_tests == 0:
            self.print_success("All integration tests passed! Jira OAuth is ready.")
        else:
            self.print_warning(f"{failed_tests} tests need attention")

        return test_results


async def main():
    """Main test function"""
    tester = JiraOAuthIntegrationTest()
    await tester.run_comprehensive_test()


if __name__ == "__main__":
    # Run async tests
    asyncio.run(main())
