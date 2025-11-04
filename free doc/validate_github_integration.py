#!/usr/bin/env python3
"""
GitHub Integration Validation Script
Validates GitHub OAuth setup and tests connectivity
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


class GitHubIntegrationValidator:
    """Validates GitHub integration setup and functionality"""

    def __init__(self):
        self.base_url = "http://localhost:5059"  # Default backend port
        self.client_id = os.getenv("GITHUB_CLIENT_ID")
        self.client_secret = os.getenv("GITHUB_CLIENT_SECRET")
        self.access_token = os.getenv("GITHUB_ACCESS_TOKEN")
        self.redirect_uri = os.getenv(
            "GITHUB_REDIRECT_URI", "http://localhost:3000/oauth/github/callback"
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

    def test_configuration(self):
        """Test GitHub OAuth configuration"""
        self.print_header("Testing GitHub OAuth Configuration")

        config_ok = True

        # Check required environment variables
        if not self.client_id:
            self.print_error("GITHUB_CLIENT_ID not found in environment")
            config_ok = False
        else:
            self.print_success(f"GITHUB_CLIENT_ID: {self.client_id[:10]}...")

        if not self.client_secret:
            self.print_error("GITHUB_CLIENT_SECRET not found in environment")
            config_ok = False
        else:
            self.print_success(f"GITHUB_CLIENT_SECRET: {self.client_secret[:10]}...")

        if not self.access_token:
            self.print_warning("GITHUB_ACCESS_TOKEN not found (OAuth will be required)")
        else:
            self.print_success(f"GITHUB_ACCESS_TOKEN: {self.access_token[:10]}...")

        self.print_success(f"GITHUB_REDIRECT_URI: {self.redirect_uri}")

        if config_ok:
            self.print_success("Configuration validation passed")
        else:
            self.print_error("Configuration validation failed")

        return config_ok

    async def test_backend_health(self):
        """Test if backend is running and GitHub endpoints are available"""
        self.print_header("Testing Backend GitHub Endpoints")

        endpoints = [
            "/api/auth/github/health",
            "/api/auth/github/start",
            "/api/auth/github/status",
        ]

        results = {}

        async with httpx.AsyncClient() as client:
            for endpoint in endpoints:
                try:
                    url = f"{self.base_url}{endpoint}"

                    if endpoint == "/api/auth/github/start":
                        # Test start endpoint with user_id parameter
                        response = await client.get(
                            f"{url}?user_id=test_user_123", timeout=10.0
                        )
                    elif endpoint == "/api/auth/github/status":
                        # Test status endpoint with POST
                        response = await client.post(
                            url, json={"user_id": "test_user_123"}, timeout=10.0
                        )
                    else:
                        # Test health endpoint
                        response = await client.get(url, timeout=10.0)

                    if response.status_code in [200, 400, 401]:
                        self.print_success(
                            f"{endpoint} - Responding (Status: {response.status_code})"
                        )
                        results[endpoint] = "SUCCESS"

                        # Print response details for debugging
                        try:
                            response_data = response.json()
                            if "status" in response_data:
                                self.print_success(
                                    f"  Status: {response_data['status']}"
                                )
                        except:
                            pass

                    else:
                        self.print_warning(
                            f"{endpoint} - Unexpected status: {response.status_code}"
                        )
                        results[endpoint] = "WARNING"

                except httpx.ConnectError:
                    self.print_error(f"{endpoint} - Backend not running")
                    results[endpoint] = "BACKEND_DOWN"
                except Exception as e:
                    self.print_error(f"{endpoint} - Failed: {e}")
                    results[endpoint] = "FAILED"

        return results

    async def test_github_oauth_flow(self):
        """Test GitHub OAuth authorization flow"""
        self.print_header("Testing GitHub OAuth Authorization Flow")

        try:
            # Generate authorization URL with required scopes
            auth_params = {
                "client_id": self.client_id,
                "redirect_uri": self.redirect_uri,
                "scope": "repo,user,read:org,read:project",
                "state": "test_state_github_123",
                "allow_signup": "false",
            }

            auth_url = f"https://github.com/oauth/authorize?{urlencode(auth_params)}"

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
                        self.print_success("GitHub authorization endpoint is reachable")
                    else:
                        self.print_warning(
                            f"GitHub authorization endpoint status: {response.status_code}"
                        )
                except Exception as e:
                    self.print_warning(f"GitHub authorization endpoint test: {e}")

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

    async def test_github_token_endpoint(self):
        """Test GitHub token endpoint functionality"""
        self.print_header("Testing GitHub Token Endpoint")

        token_url = "https://github.com/oauth/access_token"

        try:
            async with httpx.AsyncClient() as client:
                # Test with invalid code to verify endpoint is working
                test_data = {
                    "client_id": self.client_id,
                    "client_secret": self.client_secret,
                    "code": "invalid_test_code_github_456",
                    "redirect_uri": self.redirect_uri,
                }

                headers = {
                    "Accept": "application/json",
                    "Content-Type": "application/json",
                }

                response = await client.post(
                    token_url, json=test_data, headers=headers, timeout=10.0
                )

                if response.status_code == 200:
                    # GitHub returns 200 even for invalid codes, but with error in response
                    try:
                        error_data = response.json()
                        if "error" in error_data:
                            self.print_success("Token endpoint is responding correctly")
                            self.print_success(
                                "(Expected error for invalid authorization code)"
                            )
                            self.print_success(f"Error type: {error_data['error']}")
                    except:
                        self.print_warning(
                            "Token endpoint returned unexpected response"
                        )
                else:
                    self.print_warning(
                        f"Token endpoint returned status: {response.status_code}"
                    )

                return response.status_code

        except Exception as e:
            self.print_error(f"Token endpoint test failed: {e}")
            return None

    async def test_github_api_connectivity(self):
        """Test GitHub API connectivity with access token"""
        self.print_header("Testing GitHub API Connectivity")

        if not self.access_token:
            self.print_warning(
                "No access token available - skipping API connectivity test"
            )
            return "NO_TOKEN"

        api_endpoints = [
            ("User Info", "https://api.github.com/user"),
            ("User Repos", "https://api.github.com/user/repos"),
            ("Rate Limit", "https://api.github.com/rate_limit"),
        ]

        results = {}

        headers = {
            "Authorization": f"Bearer {self.access_token}",
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "ATOM-Integration-Test/1.0",
        }

        async with httpx.AsyncClient() as client:
            for name, endpoint in api_endpoints:
                try:
                    response = await client.get(endpoint, headers=headers, timeout=10.0)

                    if response.status_code == 200:
                        self.print_success(f"{name} - Connected")
                        results[name] = "CONNECTED"

                        # Print rate limit info if available
                        if name == "Rate Limit":
                            try:
                                rate_data = response.json()
                                remaining = rate_data["resources"]["core"]["remaining"]
                                self.print_success(
                                    f"  Rate limit remaining: {remaining}"
                                )
                            except:
                                pass

                    elif response.status_code == 401:
                        self.print_error(f"{name} - Unauthorized (invalid token)")
                        results[name] = "UNAUTHORIZED"
                    else:
                        self.print_warning(f"{name} - Status: {response.status_code}")
                        results[name] = f"STATUS_{response.status_code}"

                except Exception as e:
                    self.print_error(f"{name} - Connection failed: {e}")
                    results[name] = "FAILED"

        return results

    def test_code_structure(self):
        """Test if GitHub integration code structure exists"""
        self.print_header("Testing Code Structure")

        files_to_check = [
            "backend/github_oauth_api.py",
            "backend/python-api-service/github_handler.py",
            "backend/python-api-service/github_service.py",
            "backend/python-api-service/db_oauth_github.py",
        ]

        results = {}

        for file_path in files_to_check:
            if os.path.exists(file_path):
                self.print_success(f"{file_path} - Exists")

                # Check file size
                file_size = os.path.getsize(file_path)
                if file_size > 100:  # Reasonable minimum size
                    self.print_success(f"  Size: {file_size} bytes")
                else:
                    self.print_warning(f"  Size: {file_size} bytes (may be empty)")

                results[file_path] = "EXISTS"
            else:
                self.print_error(f"{file_path} - Missing")
                results[file_path] = "MISSING"

        return results

    async def run_comprehensive_validation(self):
        """Run all validation tests"""
        self.print_header("GITHUB INTEGRATION VALIDATION SUITE")
        print("Testing complete GitHub integration setup...")

        # Run all test suites
        test_results = {}

        # Test configuration first
        config_ok = self.test_configuration()
        if not config_ok:
            self.print_error("Configuration failed - stopping tests")
            return test_results

        # Run connectivity tests
        test_results["backend_endpoints"] = await self.test_backend_health()
        test_results["oauth_flow"] = await self.test_github_oauth_flow()
        test_results["token_endpoint"] = await self.test_github_token_endpoint()
        test_results["api_connectivity"] = await self.test_github_api_connectivity()
        test_results["code_structure"] = self.test_code_structure()

        # Print summary
        self.print_header("VALIDATION SUMMARY")

        total_checks = 0
        passed_checks = 0

        for category, results in test_results.items():
            if category == "oauth_flow":
                # Special handling for auth URL
                if results:
                    passed_checks += 1
                total_checks += 1
                continue

            if isinstance(results, dict):
                for test, result in results.items():
                    total_checks += 1
                    if result in ["SUCCESS", "EXISTS", "CONNECTED", 200]:
                        passed_checks += 1

        print(f"\n🎯 Test Results: {passed_checks}/{total_checks} checks passed")

        if passed_checks == total_checks:
            self.print_success("🎉 All tests passed! GitHub integration is ready.")
            print(f"\n🚀 Next Steps:")
            print(f"1. Test the complete OAuth flow manually")
            print(f"2. Verify GitHub operations in the frontend")
            print(f"3. Deploy to production")
        elif passed_checks >= total_checks * 0.7:
            self.print_success(
                "✅ Most tests passed! GitHub integration is functional."
            )
            print(f"\n🔧 Minor improvements needed:")
            print(f"1. Check any failed endpoints")
            print(f"2. Verify OAuth configuration")
        else:
            self.print_warning(
                f"⚠️  {total_checks - passed_checks} checks need attention"
            )
            print(f"\n🔧 Recommended Actions:")
            print(f"1. Fix backend connectivity issues")
            print(f"2. Verify GitHub OAuth app configuration")
            print(f"3. Check environment variables")

        return test_results


async def main():
    """Main validation function"""
    validator = GitHubIntegrationValidator()
    results = await validator.run_comprehensive_validation()

    # Save detailed report
    report_file = "github_integration_validation_report.json"
    with open(report_file, "w") as f:
        json.dump(results, f, indent=2)
    print(f"\n📄 Detailed report saved to: {report_file}")


if __name__ == "__main__":
    # Run async tests
    asyncio.run(main())
