#!/usr/bin/env python3
"""
Comprehensive OAuth Validation Script for Atom AI Assistant

This script validates the current OAuth authentication system status,
tests all OAuth endpoints, and provides detailed reporting on the
production readiness of the OAuth implementation.

Usage:
    python test_oauth_validation.py
"""

import json
import time
import requests
from typing import Dict, List, Any
from datetime import datetime


class OAuthValidator:
    """Comprehensive OAuth validation and testing class"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.test_user = "test_user_oauth"
        self.results = {}
        self.timestamp = datetime.now().isoformat()

        # Services with expected status
        self.services = [
            "gmail",
            "outlook",
            "slack",
            "teams",
            "trello",
            "asana",
            "notion",
            "github",
            "dropbox",
            "gdrive",
        ]

        # Services that should have real credentials configured
        self.expected_real_credentials = [
            "gmail",
            "slack",
            "trello",
            "asana",
            "notion",
            "dropbox",
            "gdrive",
        ]

        # Services that need credentials
        self.expected_needs_credentials = ["outlook", "teams", "github"]

    def test_health_endpoint(self) -> Dict[str, Any]:
        """Test the health endpoint"""
        try:
            response = requests.get(f"{self.base_url}/healthz", timeout=10)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "error": str(e),
            }

    def test_service_status_endpoint(self) -> Dict[str, Any]:
        """Test the service status endpoint"""
        try:
            response = requests.get(f"{self.base_url}/api/services/status", timeout=10)
            return {
                "success": response.status_code == 200,
                "status_code": response.status_code,
                "response": response.json() if response.status_code == 200 else None,
                "error": None,
            }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "error": str(e),
            }

    def test_oauth_status_endpoints(self) -> Dict[str, Any]:
        """Test all OAuth status endpoints"""
        results = {}
        success_count = 0

        for service in self.services:
            try:
                url = f"{self.base_url}/api/auth/{service}/status?user_id={self.test_user}"
                response = requests.get(url, timeout=10)

                if response.status_code == 200:
                    data = response.json()
                    results[service] = {
                        "success": True,
                        "status_code": response.status_code,
                        "status": data.get("status", "unknown"),
                        "credentials": data.get("credentials", "unknown"),
                        "message": data.get("message", ""),
                        "response": data,
                    }
                    success_count += 1
                else:
                    results[service] = {
                        "success": False,
                        "status_code": response.status_code,
                        "status": "error",
                        "credentials": "unknown",
                        "message": f"HTTP {response.status_code}",
                        "response": None,
                    }

            except Exception as e:
                results[service] = {
                    "success": False,
                    "status_code": None,
                    "status": "error",
                    "credentials": "unknown",
                    "message": str(e),
                    "response": None,
                }

        return {
            "success_rate": f"{success_count}/{len(self.services)} ({success_count / len(self.services) * 100:.1f}%)",
            "success_count": success_count,
            "total_services": len(self.services),
            "results": results,
        }

    def test_comprehensive_oauth_status(self) -> Dict[str, Any]:
        """Test the comprehensive OAuth status endpoint"""
        try:
            url = f"{self.base_url}/api/auth/oauth-status?user_id={self.test_user}"
            response = requests.get(url, timeout=10)

            if response.status_code == 200:
                data = response.json()
                return {
                    "success": True,
                    "status_code": response.status_code,
                    "response": data,
                    "error": None,
                }
            else:
                return {
                    "success": False,
                    "status_code": response.status_code,
                    "response": None,
                    "error": f"HTTP {response.status_code}",
                }
        except Exception as e:
            return {
                "success": False,
                "status_code": None,
                "response": None,
                "error": str(e),
            }

    def test_oauth_authorization_endpoints(self) -> Dict[str, Any]:
        """Test OAuth authorization endpoints (should return 404 for status-only server)"""
        results = {}
        not_found_count = 0

        for service in self.services:
            try:
                url = f"{self.base_url}/api/auth/{service}/authorize?user_id={self.test_user}"
                response = requests.get(url, timeout=10)

                results[service] = {
                    "status_code": response.status_code,
                    "expected_404": response.status_code == 404,
                    "message": "Status-only server (expected 404)"
                    if response.status_code == 404
                    else f"Unexpected: {response.status_code}",
                }

                if response.status_code == 404:
                    not_found_count += 1

            except Exception as e:
                results[service] = {
                    "status_code": None,
                    "expected_404": False,
                    "message": str(e),
                }

        return {
            "not_found_count": not_found_count,
            "total_services": len(self.services),
            "results": results,
        }

    def analyze_oauth_status(self, status_results: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze OAuth status results"""
        if not status_results.get("success"):
            return {"error": "No status data available"}

        data = status_results["response"]
        if not data:
            return {"error": "No response data"}

        connected_services = []
        needs_credentials_services = []
        unknown_services = []

        for service, result in data.get("results", {}).items():
            status = result.get("status", "unknown")
            credentials = result.get("credentials", "unknown")

            if status == "connected" and credentials == "real_configured":
                connected_services.append(service)
            elif status == "needs_credentials" or credentials == "placeholder":
                needs_credentials_services.append(service)
            else:
                unknown_services.append(service)

        return {
            "connected_services": connected_services,
            "needs_credentials_services": needs_credentials_services,
            "unknown_services": unknown_services,
            "connected_count": len(connected_services),
            "needs_credentials_count": len(needs_credentials_services),
            "unknown_count": len(unknown_services),
            "success_rate": f"{len(connected_services)}/{len(self.services)} ({len(connected_services) / len(self.services) * 100:.1f}%)",
        }

    def validate_production_readiness(self) -> Dict[str, Any]:
        """Validate production readiness based on OAuth status"""
        analysis = self.analyze_oauth_status(
            self.results.get("comprehensive_status", {})
        )

        readiness_checks = {
            "health_endpoint_operational": self.results.get("health", {}).get(
                "success", False
            ),
            "service_status_operational": self.results.get("service_status", {}).get(
                "success", False
            ),
            "oauth_status_endpoints_operational": self.results.get(
                "oauth_status", {}
            ).get("success_count", 0)
            == len(self.services),
            "comprehensive_status_operational": self.results.get(
                "comprehensive_status", {}
            ).get("success", False),
            "expected_services_connected": analysis.get("connected_count", 0)
            >= len(self.expected_real_credentials),
            "authorization_endpoints_properly_disabled": self.results.get(
                "authorization_endpoints", {}
            ).get("not_found_count", 0)
            == len(self.services),
        }

        all_checks_passed = all(readiness_checks.values())

        return {
            "production_ready": all_checks_passed,
            "readiness_checks": readiness_checks,
            "analysis": analysis,
            "summary": "✅ PRODUCTION READY"
            if all_checks_passed
            else "❌ NOT PRODUCTION READY",
        }

    def run_comprehensive_validation(self) -> Dict[str, Any]:
        """Run comprehensive OAuth validation"""
        print("🔍 Starting Comprehensive OAuth Validation...")
        print("=" * 60)

        # Test health endpoint
        print("📊 Testing health endpoint...")
        self.results["health"] = self.test_health_endpoint()

        # Test service status endpoint
        print("📊 Testing service status endpoint...")
        self.results["service_status"] = self.test_service_status_endpoint()

        # Test individual OAuth status endpoints
        print("📊 Testing individual OAuth status endpoints...")
        self.results["oauth_status"] = self.test_oauth_status_endpoints()

        # Test comprehensive OAuth status
        print("📊 Testing comprehensive OAuth status...")
        self.results["comprehensive_status"] = self.test_comprehensive_oauth_status()

        # Test authorization endpoints (should be 404)
        print("📊 Testing OAuth authorization endpoints...")
        self.results["authorization_endpoints"] = (
            self.test_oauth_authorization_endpoints()
        )

        # Analyze results
        print("📊 Analyzing OAuth status...")
        self.results["analysis"] = self.analyze_oauth_status(
            self.results["comprehensive_status"]
        )

        # Validate production readiness
        print("📊 Validating production readiness...")
        self.results["production_readiness"] = self.validate_production_readiness()

        return self.results

    def generate_report(self) -> Dict[str, Any]:
        """Generate comprehensive validation report"""
        report = {
            "timestamp": self.timestamp,
            "base_url": self.base_url,
            "test_user": self.test_user,
            "validation_results": self.results,
            "summary": {
                "total_tests": 5,
                "successful_tests": sum(
                    [
                        1 if self.results.get("health", {}).get("success") else 0,
                        1
                        if self.results.get("service_status", {}).get("success")
                        else 0,
                        1
                        if self.results.get("comprehensive_status", {}).get("success")
                        else 0,
                        1
                        if self.results.get("oauth_status", {}).get("success_count", 0)
                        == len(self.services)
                        else 0,
                        1
                        if self.results.get("authorization_endpoints", {}).get(
                            "not_found_count", 0
                        )
                        == len(self.services)
                        else 0,
                    ]
                ),
                "production_ready": self.results.get("production_readiness", {}).get(
                    "production_ready", False
                ),
            },
        }

        return report

    def print_detailed_report(self):
        """Print detailed validation report to console"""
        print("\n" + "=" * 60)
        print("📋 COMPREHENSIVE OAUTH VALIDATION REPORT")
        print("=" * 60)

        # Health endpoint
        health = self.results.get("health", {})
        print(f"\n🔧 Health Endpoint: {'✅' if health.get('success') else '❌'}")
        if health.get("success"):
            print(f"   Status: {health.get('response', {}).get('status', 'unknown')}")
            print(
                f"   Message: {health.get('response', {}).get('message', 'No message')}"
            )
        else:
            print(f"   Error: {health.get('error', 'Unknown error')}")

        # Service status
        service_status = self.results.get("service_status", {})
        print(
            f"\n🔧 Service Status Endpoint: {'✅' if service_status.get('success') else '❌'}"
        )
        if service_status.get("success"):
            data = service_status.get("response", {})
            print(
                f"   Active Services: {data.get('active_services', 0)}/{data.get('total_services', 0)}"
            )
        else:
            print(f"   Error: {service_status.get('error', 'Unknown error')}")

        # OAuth status endpoints
        oauth_status = self.results.get("oauth_status", {})
        print(f"\n🔐 OAuth Status Endpoints: {oauth_status.get('success_rate', '0%')}")
        for service, result in oauth_status.get("results", {}).items():
            status_icon = "✅" if result.get("success") else "❌"
            status = result.get("status", "unknown")
            credentials = result.get("credentials", "unknown")
            print(f"   {status_icon} {service.upper()}: {status} ({credentials})")

        # Comprehensive OAuth status
        comp_status = self.results.get("comprehensive_status", {})
        print(
            f"\n📊 Comprehensive OAuth Status: {'✅' if comp_status.get('success') else '❌'}"
        )
        if comp_status.get("success"):
            data = comp_status.get("response", {})
            print(
                f"   Connected Services: {data.get('connected_services', 0)}/{data.get('total_services', 0)}"
            )
            print(f"   Success Rate: {data.get('success_rate', '0%')}")

        # Authorization endpoints
        auth_endpoints = self.results.get("authorization_endpoints", {})
        print(f"\n🔑 OAuth Authorization Endpoints:")
        print(
            f"   Status: {'✅ Properly disabled (404)' if auth_endpoints.get('not_found_count', 0) == len(self.services) else '❌ Unexpected behavior'}"
        )
        print(
            f"   404 Responses: {auth_endpoints.get('not_found_count', 0)}/{auth_endpoints.get('total_services', 0)}"
        )

        # Production readiness
        readiness = self.results.get("production_readiness", {})
        print(f"\n🚀 PRODUCTION READINESS: {readiness.get('summary', 'UNKNOWN')}")
        for check, passed in readiness.get("readiness_checks", {}).items():
            icon = "✅" if passed else "❌"
            check_name = check.replace("_", " ").title()
            print(f"   {icon} {check_name}")

        # Analysis
        analysis = self.results.get("analysis", {})
        print(f"\n📈 OAUTH SYSTEM ANALYSIS:")
        print(
            f"   Connected Services: {analysis.get('connected_count', 0)}/{len(self.services)}"
        )
        print(
            f"   Needs Credentials: {analysis.get('needs_credentials_count', 0)}/{len(self.services)}"
        )
        print(
            f"   Unknown Status: {analysis.get('unknown_count', 0)}/{len(self.services)}"
        )
        print(f"   Success Rate: {analysis.get('success_rate', '0%')}")

        print(f"\n⏰ Validation completed at: {self.timestamp}")
        print("=" * 60)


def main():
    """Main function to run OAuth validation"""
    validator = OAuthValidator()

    try:
        # Run comprehensive validation
        results = validator.run_comprehensive_validation()

        # Generate and print report
        validator.print_detailed_report()

        # Save detailed report to file
        report = validator.generate_report()
        report_filename = (
            f"oauth_validation_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}.json"
        )
        with open(report_filename, "w") as f:
            json.dump(report, f, indent=2)

        print(f"\n💾 Detailed report saved to: {report_filename}")

        # Exit with appropriate code
        if validator.results.get("production_readiness", {}).get(
            "production_ready", False
        ):
            print("\n🎉 OAUTH SYSTEM IS PRODUCTION READY!")
            exit(0)
        else:
            print("\n⚠️  OAUTH SYSTEM NEEDS ATTENTION BEFORE PRODUCTION DEPLOYMENT")
            exit(1)

    except Exception as e:
        print(f"\n❌ Validation failed with error: {e}")
        exit(1)


if __name__ == "__main__":
    main()
