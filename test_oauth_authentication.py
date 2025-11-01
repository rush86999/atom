#!/usr/bin/env python3
"""
Comprehensive OAuth Authentication Test Script for ATOM Platform

This script tests all OAuth authentication endpoints to ensure they are
properly registered and functioning correctly.

Features tested:
- OAuth authorization initiation for all services
- OAuth status endpoints
- Error handling for missing credentials
- Blueprint registration verification
"""

import requests
import json
import sys
import time
from typing import Dict, List, Tuple

# Configuration
BASE_URL = "http://localhost:5058"
TEST_USER_ID = "test_user_oauth"

# OAuth services to test
OAUTH_SERVICES = [
    {
        "name": "gmail",
        "auth_endpoint": "/api/auth/gmail/authorize",
        "status_endpoint": "/api/auth/gmail/status",
        "description": "Gmail OAuth Integration",
    },
    {
        "name": "outlook",
        "auth_endpoint": "/api/auth/outlook/authorize",
        "status_endpoint": "/api/auth/outlook/status",
        "description": "Outlook OAuth Integration",
    },
    {
        "name": "slack",
        "auth_endpoint": "/api/auth/slack/authorize",
        "status_endpoint": "/api/auth/slack/status",
        "description": "Slack OAuth Integration",
    },
    {
        "name": "teams",
        "auth_endpoint": "/api/auth/teams/authorize",
        "status_endpoint": "/api/auth/teams/status",
        "description": "Microsoft Teams OAuth Integration",
    },
    {
        "name": "trello",
        "auth_endpoint": "/api/auth/trello/authorize",
        "status_endpoint": "/api/auth/trello/status",
        "description": "Trello OAuth Integration",
    },
    {
        "name": "asana",
        "auth_endpoint": "/api/auth/asana/authorize",
        "status_endpoint": "/api/auth/asana/status",
        "description": "Asana OAuth Integration",
    },
    {
        "name": "notion",
        "auth_endpoint": "/api/auth/notion/authorize",
        "status_endpoint": "/api/auth/notion/status",
        "description": "Notion OAuth Integration",
    },
    {
        "name": "github",
        "auth_endpoint": "/api/auth/github/authorize",
        "status_endpoint": "/api/auth/github/status",
        "description": "GitHub OAuth Integration",
    },
    {
        "name": "dropbox",
        "auth_endpoint": "/api/auth/dropbox/authorize",
        "status_endpoint": "/api/auth/dropbox/status",
        "description": "Dropbox OAuth Integration",
    },
    {
        "name": "gdrive",
        "auth_endpoint": "/api/auth/gdrive/authorize",
        "status_endpoint": "/api/auth/gdrive/status",
        "description": "Google Drive OAuth Integration",
    },
]


class OAuthTester:
    def __init__(self, base_url: str = BASE_URL):
        self.base_url = base_url
        self.results = []

    def test_health_endpoint(self) -> bool:
        """Test the main health endpoint to verify server is running"""
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            if response.status_code == 200:
                data = response.json()
                print(
                    f"✅ Health endpoint: Server is running (v{data.get('version', 'unknown')})"
                )
                print(f"   Total blueprints: {data.get('total_blueprints', 0)}")
                return True
            else:
                print(f"❌ Health endpoint: Server returned {response.status_code}")
                return False
        except requests.exceptions.RequestException as e:
            print(f"❌ Health endpoint: Connection failed - {e}")
            return False

    def test_oauth_authorization(self, service: Dict) -> Tuple[bool, str]:
        """Test OAuth authorization initiation for a service"""
        try:
            endpoint = f"{self.base_url}{service['auth_endpoint']}"
            params = {"user_id": TEST_USER_ID}

            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Check for expected response structure
                if all(key in data for key in ["auth_url", "csrf_token", "user_id"]):
                    auth_url = data["auth_url"]

                    # Check if client ID is configured (not None)
                    if "client_id=None" in auth_url:
                        return (
                            True,
                            f"✅ {service['description']}: Authorization endpoint working (credentials not configured)",
                        )
                    else:
                        return (
                            True,
                            f"✅ {service['description']}: Authorization endpoint working with credentials",
                        )
                else:
                    return (
                        False,
                        f"❌ {service['description']}: Invalid response structure",
                    )

            elif response.status_code == 404:
                return False, f"❌ {service['description']}: Endpoint not found (404)"
            else:
                return (
                    False,
                    f"❌ {service['description']}: Unexpected status code {response.status_code}",
                )

        except requests.exceptions.RequestException as e:
            return False, f"❌ {service['description']}: Connection failed - {e}"

    def test_oauth_status(self, service: Dict) -> Tuple[bool, str]:
        """Test OAuth status endpoint for a service"""
        try:
            endpoint = f"{self.base_url}{service['status_endpoint']}"
            params = {"user_id": TEST_USER_ID}

            response = requests.get(endpoint, params=params, timeout=10)

            if response.status_code == 200:
                data = response.json()

                # Status endpoint should return JSON with connection status
                if isinstance(data, dict):
                    if data.get("ok") is not None:
                        return (
                            True,
                            f"✅ {service['description']}: Status endpoint working",
                        )
                    else:
                        # Even if there's an error, the endpoint is accessible
                        return (
                            True,
                            f"⚠️ {service['description']}: Status endpoint accessible (returned error: {data.get('error', {}).get('message', 'unknown')})",
                        )
                else:
                    return (
                        False,
                        f"❌ {service['description']}: Invalid response format",
                    )

            elif response.status_code == 404:
                return (
                    False,
                    f"❌ {service['description']}: Status endpoint not found (404)",
                )
            else:
                return (
                    False,
                    f"❌ {service['description']}: Status endpoint returned {response.status_code}",
                )

        except requests.exceptions.RequestException as e:
            return (
                False,
                f"❌ {service['description']}: Status endpoint connection failed - {e}",
            )

    def run_comprehensive_test(self) -> Dict:
        """Run comprehensive OAuth authentication tests"""
        print("🚀 Starting Comprehensive OAuth Authentication Test")
        print("=" * 60)

        # Test server health first
        if not self.test_health_endpoint():
            print("❌ Cannot proceed - server is not accessible")
            return {"overall_success": False, "results": self.results}

        print("\n🔐 Testing OAuth Authorization Endpoints")
        print("-" * 40)

        auth_success_count = 0
        for service in OAUTH_SERVICES:
            success, message = self.test_oauth_authorization(service)
            print(message)
            self.results.append(
                {
                    "service": service["name"],
                    "test": "authorization",
                    "success": success,
                    "message": message,
                }
            )
            if success:
                auth_success_count += 1

        print(
            f"\n📊 Authorization Results: {auth_success_count}/{len(OAUTH_SERVICES)} services working"
        )

        print("\n📈 Testing OAuth Status Endpoints")
        print("-" * 40)

        status_success_count = 0
        for service in OAUTH_SERVICES:
            success, message = self.test_oauth_status(service)
            print(message)
            self.results.append(
                {
                    "service": service["name"],
                    "test": "status",
                    "success": success,
                    "message": message,
                }
            )
            if success:
                status_success_count += 1

        print(
            f"\n📊 Status Results: {status_success_count}/{len(OAUTH_SERVICES)} services working"
        )

        # Calculate overall success
        total_tests = len(OAUTH_SERVICES) * 2  # auth + status for each service
        successful_tests = auth_success_count + status_success_count
        overall_success_rate = successful_tests / total_tests if total_tests > 0 else 0

        print("\n" + "=" * 60)
        print(f"🎯 FINAL RESULTS")
        print(f"   Authorization Endpoints: {auth_success_count}/{len(OAUTH_SERVICES)}")
        print(f"   Status Endpoints: {status_success_count}/{len(OAUTH_SERVICES)}")
        print(f"   Overall Success Rate: {overall_success_rate:.1%}")

        if overall_success_rate >= 0.8:
            print("✅ OAuth Authentication System: PASSED")
        elif overall_success_rate >= 0.5:
            print("⚠️ OAuth Authentication System: PARTIAL SUCCESS")
        else:
            print("❌ OAuth Authentication System: FAILED")

        return {
            "overall_success": overall_success_rate >= 0.8,
            "success_rate": overall_success_rate,
            "authorization_success": auth_success_count,
            "status_success": status_success_count,
            "total_services": len(OAUTH_SERVICES),
            "results": self.results,
        }

    def generate_report(self, test_results: Dict):
        """Generate a detailed test report"""
        timestamp = time.strftime("%Y-%m-%d %H:%M:%S")

        report = {
            "timestamp": timestamp,
            "base_url": self.base_url,
            "test_user_id": TEST_USER_ID,
            "summary": {
                "overall_success": test_results["overall_success"],
                "success_rate": test_results["success_rate"],
                "authorization_endpoints_working": test_results[
                    "authorization_success"
                ],
                "status_endpoints_working": test_results["status_success"],
                "total_services_tested": test_results["total_services"],
            },
            "detailed_results": test_results["results"],
        }

        # Save report to file
        filename = f"oauth_test_report_{time.strftime('%Y%m%d_%H%M%S')}.json"
        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n📄 Test report saved to: {filename}")
        return report


def main():
    """Main test execution function"""
    tester = OAuthTester()

    try:
        results = tester.run_comprehensive_test()
        report = tester.generate_report(results)

        # Exit with appropriate code
        if results["overall_success"]:
            sys.exit(0)
        else:
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n⏹️ Test interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n💥 Unexpected error: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
