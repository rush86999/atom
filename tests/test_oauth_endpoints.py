#!/usr/bin/env python3
"""
Comprehensive OAuth Endpoint Test Script for ATOM Platform
Tests all OAuth authorization endpoints and provides detailed status report
"""

import requests
import json
import sys
from datetime import datetime
from typing import Dict, List, Any


class OAuthEndpointTester:
    """Test all OAuth authorization endpoints in the ATOM Platform"""

    def __init__(
        self,
        base_url: str = "http://localhost:5058",
        test_user_id: str = "test_user_oauth",
    ):
        self.base_url = base_url.rstrip("/")
        self.test_user_id = test_user_id
        self.results = []
        self.summary = {
            "timestamp": datetime.now().isoformat(),
            "base_url": base_url,
            "test_user_id": test_user_id,
            "overall_success": False,
            "success_rate": 0.0,
            "authorization_endpoints_working": 0,
            "status_endpoints_working": 0,
            "total_services_tested": 0,
        }

    def test_authorization_endpoint(
        self, service_name: str, endpoint_path: str
    ) -> Dict[str, Any]:
        """Test a single OAuth authorization endpoint"""
        url = f"{self.base_url}{endpoint_path}?user_id={self.test_user_id}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                # Check if response is JSON or HTML redirect
                content_type = response.headers.get("content-type", "")
                if "application/json" in content_type:
                    try:
                        data = response.json()
                    except json.JSONDecodeError:
                        return {
                            "service": service_name,
                            "test": "authorization",
                            "success": False,
                            "status_code": 200,
                            "message": f"❌ {service_name.title()} OAuth Integration: Authorization endpoint returned 200 but response is not valid JSON",
                        }
                else:
                    # Handle HTML redirect response (which is valid for OAuth)
                    return {
                        "service": service_name,
                        "test": "authorization",
                        "success": True,
                        "status_code": 200,
                        "message": f"✅ {service_name.title()} OAuth Integration: Authorization endpoint working (HTML redirect response)",
                        "response_type": "html_redirect",
                    }

                # Check if we got a proper auth URL
                if "auth_url" in data and data["auth_url"]:
                    # Check for placeholder credentials
                    auth_url = data["auth_url"]
                    if "your-" in auth_url or "placeholder" in auth_url.lower():
                        return {
                            "service": service_name,
                            "test": "authorization",
                            "success": False,
                            "status_code": 200,
                            "message": f"⚠️ {service_name.title()} OAuth Integration: Authorization endpoint working but using placeholder credentials",
                            "auth_url": auth_url,
                            "csrf_token": data.get("csrf_token"),
                            "user_id": data.get("user_id"),
                        }
                    else:
                        return {
                            "service": service_name,
                            "test": "authorization",
                            "success": True,
                            "status_code": 200,
                            "message": f"✅ {service_name.title()} OAuth Integration: Authorization endpoint working with real credentials",
                            "auth_url": auth_url,
                            "csrf_token": data.get("csrf_token"),
                            "user_id": data.get("user_id"),
                        }
                else:
                    return {
                        "service": service_name,
                        "test": "authorization",
                        "success": False,
                        "status_code": 200,
                        "message": f"❌ {service_name.title()} OAuth Integration: Authorization endpoint returned 200 but no auth_url in response",
                        "response_data": data,
                    }

            elif response.status_code == 404:
                return {
                    "service": service_name,
                    "test": "authorization",
                    "success": False,
                    "status_code": 404,
                    "message": f"❌ {service_name.title()} OAuth Integration: Endpoint not found (404)",
                }

            elif response.status_code == 500:
                return {
                    "service": service_name,
                    "test": "authorization",
                    "success": False,
                    "status_code": 500,
                    "message": f"❌ {service_name.title()} OAuth Integration: Unexpected status code 500",
                }

            else:
                return {
                    "service": service_name,
                    "test": "authorization",
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"❌ {service_name.title()} OAuth Integration: Unexpected status code {response.status_code}",
                }

        except requests.exceptions.ConnectionError:
            return {
                "service": service_name,
                "test": "authorization",
                "success": False,
                "status_code": None,
                "message": f"❌ {service_name.title()} OAuth Integration: Connection refused - backend may not be running",
            }

        except requests.exceptions.Timeout:
            return {
                "service": service_name,
                "test": "authorization",
                "success": False,
                "status_code": None,
                "message": f"❌ {service_name.title()} OAuth Integration: Request timeout",
            }

        except Exception as e:
            return {
                "service": service_name,
                "test": "authorization",
                "success": False,
                "status_code": None,
                "message": f"❌ {service_name.title()} OAuth Integration: Unexpected error: {str(e)}",
            }

    def test_status_endpoint(
        self, service_name: str, endpoint_path: str
    ) -> Dict[str, Any]:
        """Test a single OAuth status endpoint"""
        url = f"{self.base_url}{endpoint_path}?user_id={self.test_user_id}"

        try:
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                return {
                    "service": service_name,
                    "test": "status",
                    "success": True,
                    "status_code": 200,
                    "message": f"✅ {service_name.title()} OAuth Integration: Status endpoint working",
                }

            elif response.status_code == 404:
                return {
                    "service": service_name,
                    "test": "status",
                    "success": False,
                    "status_code": 404,
                    "message": f"❌ {service_name.title()} OAuth Integration: Status endpoint not found (404)",
                }

            elif response.status_code == 500:
                return {
                    "service": service_name,
                    "test": "status",
                    "success": False,
                    "status_code": 500,
                    "message": f"❌ {service_name.title()} OAuth Integration: Status endpoint returned 500",
                }

            else:
                return {
                    "service": service_name,
                    "test": "status",
                    "success": False,
                    "status_code": response.status_code,
                    "message": f"❌ {service_name.title()} OAuth Integration: Status endpoint returned {response.status_code}",
                }

        except Exception as e:
            return {
                "service": service_name,
                "test": "status",
                "success": False,
                "status_code": None,
                "message": f"❌ {service_name.title()} OAuth Integration: Status endpoint error: {str(e)}",
            }

    def run_comprehensive_test(self):
        """Run comprehensive test of all OAuth endpoints"""
        print(f"\n🔍 Testing OAuth Endpoints at {self.base_url}")
        print("=" * 60)

        # Define all OAuth services to test
        oauth_services = [
            {
                "name": "gmail",
                "auth_endpoint": "/api/auth/gmail/authorize",
                "status_endpoint": "/api/auth/gmail/status",
            },
            {
                "name": "outlook",
                "auth_endpoint": "/api/auth/outlook/authorize",
                "status_endpoint": "/api/auth/outlook/status",
            },
            {
                "name": "slack",
                "auth_endpoint": "/api/auth/slack/authorize",
                "status_endpoint": "/api/auth/slack/status",
            },
            {
                "name": "teams",
                "auth_endpoint": "/api/auth/teams/authorize",
                "status_endpoint": "/api/auth/teams/status",
            },
            {
                "name": "trello",
                "auth_endpoint": "/api/auth/trello/authorize",
                "status_endpoint": "/api/auth/trello/status",
            },
            {
                "name": "asana",
                "auth_endpoint": "/api/auth/asana/authorize",
                "status_endpoint": "/api/auth/asana/status",
            },
            {
                "name": "notion",
                "auth_endpoint": "/api/auth/notion/authorize",
                "status_endpoint": "/api/auth/notion/status",
            },
            {
                "name": "github",
                "auth_endpoint": "/api/auth/github/authorize",
                "status_endpoint": "/api/auth/github/status",
            },
            {
                "name": "dropbox",
                "auth_endpoint": "/api/auth/dropbox/authorize",
                "status_endpoint": "/api/auth/dropbox/status",
            },
            {
                "name": "gdrive",
                "auth_endpoint": "/api/auth/gdrive/authorize",
                "status_endpoint": "/api/auth/gdrive/status",
            },
        ]

        # Test authorization endpoints
        print("\n📋 Testing Authorization Endpoints:")
        print("-" * 40)

        for service in oauth_services:
            print(f"Testing {service['name']}...", end=" ")
            result = self.test_authorization_endpoint(
                service["name"], service["auth_endpoint"]
            )
            self.results.append(result)

            if result["success"]:
                print("✅")
            else:
                print("❌")

        # Test status endpoints
        print("\n📊 Testing Status Endpoints:")
        print("-" * 40)

        for service in oauth_services:
            print(f"Testing {service['name']} status...", end=" ")
            result = self.test_status_endpoint(
                service["name"], service["status_endpoint"]
            )
            self.results.append(result)

            if result["success"]:
                print("✅")
            else:
                print("❌")

        # Calculate summary statistics
        total_tests = len(self.results)
        successful_tests = sum(1 for r in self.results if r["success"])
        auth_successful = sum(
            1 for r in self.results if r["test"] == "authorization" and r["success"]
        )
        status_successful = sum(
            1 for r in self.results if r["test"] == "status" and r["success"]
        )

        self.summary.update(
            {
                "overall_success": successful_tests
                > (total_tests * 0.5),  # More than 50% success
                "success_rate": round((successful_tests / total_tests) * 100, 1)
                if total_tests > 0
                else 0,
                "authorization_endpoints_working": auth_successful,
                "status_endpoints_working": status_successful,
                "total_services_tested": len(oauth_services),
            }
        )

    def print_detailed_report(self):
        """Print detailed test report"""
        print(f"\n📊 COMPREHENSIVE OAUTH TEST REPORT")
        print("=" * 60)
        print(f"Timestamp: {self.summary['timestamp']}")
        print(f"Base URL: {self.summary['base_url']}")
        print(f"Test User: {self.summary['test_user_id']}")
        print(
            f"Overall Success: {'✅ YES' if self.summary['overall_success'] else '❌ NO'}"
        )
        print(f"Success Rate: {self.summary['success_rate']}%")
        print(
            f"Authorization Endpoints Working: {self.summary['authorization_endpoints_working']}/{self.summary['total_services_tested']}"
        )
        print(
            f"Status Endpoints Working: {self.summary['status_endpoints_working']}/{self.summary['total_services_tested']}"
        )

        # Group results by service
        service_results = {}
        for result in self.results:
            service = result["service"]
            if service not in service_results:
                service_results[service] = {"authorization": None, "status": None}

            if result["test"] == "authorization":
                service_results[service]["authorization"] = result
            else:
                service_results[service]["status"] = result

        # Print service-by-service results
        print(f"\n🔍 SERVICE-BY-SERVICE RESULTS:")
        print("-" * 60)

        for service_name, results in service_results.items():
            auth_result = results["authorization"]
            status_result = results["status"]

            print(f"\n{service_name.upper()}:")
            print(f"  Authorization: {auth_result['message']}")
            print(f"  Status: {status_result['message']}")

    def print_credential_analysis(self):
        """Analyze and report on credential configuration"""
        print(f"\n🔐 CREDENTIAL CONFIGURATION ANALYSIS:")
        print("-" * 60)

        auth_results = [
            r
            for r in self.results
            if r["test"] == "authorization" and r["status_code"] == 200
        ]

        services_with_real_creds = []
        services_with_placeholder_creds = []

        for result in auth_results:
            if "placeholder" in result.get(
                "message", ""
            ).lower() or "your-" in result.get("auth_url", ""):
                services_with_placeholder_creds.append(result["service"])
            else:
                services_with_real_creds.append(result["service"])

        print(f"✅ Services with REAL credentials: {len(services_with_real_creds)}")
        for service in services_with_real_creds:
            print(f"   - {service}")

        print(
            f"⚠️  Services with PLACEHOLDER credentials: {len(services_with_placeholder_creds)}"
        )
        for service in services_with_placeholder_creds:
            print(f"   - {service}")

        print(
            f"❌ Services with NO authorization endpoint: {self.summary['total_services_tested'] - len(auth_results)}"
        )

    def save_report(self, filename: str = None):
        """Save test results to JSON file"""
        if filename is None:
            timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
            filename = f"oauth_test_report_{timestamp}.json"

        report = {
            "timestamp": self.summary["timestamp"],
            "base_url": self.summary["base_url"],
            "test_user_id": self.summary["test_user_id"],
            "summary": self.summary,
            "detailed_results": self.results,
        }

        with open(filename, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n💾 Report saved to: {filename}")
        return filename

    def print_recommendations(self):
        """Print recommendations for fixing issues"""
        print(f"\n🎯 RECOMMENDATIONS:")
        print("-" * 60)

        # Analyze issues
        auth_failures = [
            r for r in self.results if r["test"] == "authorization" and not r["success"]
        ]
        status_failures = [
            r for r in self.results if r["test"] == "status" and not r["success"]
        ]

        if auth_failures:
            print(f"\n🔧 Fix Authorization Endpoints ({len(auth_failures)} issues):")
            for failure in auth_failures:
                print(f"   - {failure['service']}: {failure['message']}")

        if status_failures:
            print(f"\n🔧 Fix Status Endpoints ({len(status_failures)} issues):")
            for failure in status_failures:
                print(f"   - {failure['service']}: {failure['message']}")

        # Check for placeholder credentials
        placeholder_services = []
        for result in self.results:
            if result["test"] == "authorization" and result["status_code"] == 200:
                if "placeholder" in result.get(
                    "message", ""
                ).lower() or "your-" in result.get("auth_url", ""):
                    placeholder_services.append(result["service"])

        if placeholder_services:
            print(
                f"\n🔑 Configure Real Credentials ({len(placeholder_services)} services):"
            )
            for service in placeholder_services:
                print(
                    f"   - {service}: Update OAuth configuration with real client ID/secret"
                )


def main():
    """Main function to run the OAuth endpoint tests"""
    # Parse command line arguments
    base_url = "http://localhost:5058"
    test_user_id = "test_user_oauth"

    if len(sys.argv) > 1:
        base_url = sys.argv[1]

    if len(sys.argv) > 2:
        test_user_id = sys.argv[2]

    # Create tester and run tests
    tester = OAuthEndpointTester(base_url, test_user_id)

    try:
        tester.run_comprehensive_test()
        tester.print_detailed_report()
        tester.print_credential_analysis()
        tester.print_recommendations()

        # Save report
        report_file = tester.save_report()

        # Exit with appropriate code
        if tester.summary["overall_success"]:
            print(
                f"\n🎉 OAuth system is OPERATIONAL with {tester.summary['success_rate']}% success rate!"
            )
            sys.exit(0)
        else:
            print(
                f"\n⚠️  OAuth system needs ATTENTION - {tester.summary['success_rate']}% success rate"
            )
            sys.exit(1)

    except KeyboardInterrupt:
        print("\n\n❌ Testing interrupted by user")
        sys.exit(1)
    except Exception as e:
        print(f"\n❌ Unexpected error during testing: {e}")
        sys.exit(1)


if __name__ == "__main__":
    main()
