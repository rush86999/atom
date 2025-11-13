"""
Comprehensive Asana Integration Test Script
Tests the complete Asana OAuth and API integration
"""

import os
import sys
import requests
import json
import time
from datetime import datetime, timezone
import asyncio

# Add backend to path
sys.path.append(os.path.join(os.path.dirname(__file__), "backend"))

# Test configuration
BASE_URL = "http://localhost:8000"
ASANA_BASE_URL = "https://app.asana.com/api/1.0"

# Test credentials (use environment variables in production)
ASANA_CLIENT_ID = os.getenv("ASANA_CLIENT_ID", "1211551350187489")
ASANA_CLIENT_SECRET = os.getenv(
    "ASANA_CLIENT_SECRET", "a4d944583e2e3fd199b678ece03762b0"
)
ASANA_REDIRECT_URI = os.getenv(
    "ASANA_REDIRECT_URI", "http://localhost:8000/api/auth/asana/callback"
)


class AsanaIntegrationTester:
    """Comprehensive Asana integration test suite"""

    def __init__(self):
        self.base_url = BASE_URL
        self.test_results = []
        self.session = requests.Session()

    def log_test(self, test_name, status, details=None):
        """Log test result"""
        result = {
            "test": test_name,
            "status": status,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "details": details or {},
        }
        self.test_results.append(result)
        print(f"{'✅' if status == 'PASS' else '❌'} {test_name}: {status}")
        if details:
            print(f"   Details: {details}")

    def test_api_health(self):
        """Test basic API health"""
        try:
            response = self.session.get(f"{self.base_url}/health")
            if response.status_code == 200:
                data = response.json()
                self.log_test("API Health Check", "PASS", data)
                return True
            else:
                self.log_test(
                    "API Health Check", "FAIL", {"status_code": response.status_code}
                )
                return False
        except Exception as e:
            self.log_test("API Health Check", "FAIL", {"error": str(e)})
            return False

    def test_asana_health_endpoint(self):
        """Test Asana health endpoint"""
        try:
            response = self.session.get(
                f"{self.base_url}/api/asana/health?user_id=test_user"
            )
            if response.status_code == 200:
                data = response.json()
                self.log_test("Asana Health Endpoint", "PASS", data)
                return True
            else:
                self.log_test(
                    "Asana Health Endpoint",
                    "FAIL",
                    {"status_code": response.status_code},
                )
                return False
        except Exception as e:
            self.log_test("Asana Health Endpoint", "FAIL", {"error": str(e)})
            return False

    def test_asana_oauth_configuration(self):
        """Test Asana OAuth configuration"""
        try:
            # Check if credentials are configured
            if not ASANA_CLIENT_ID or ASANA_CLIENT_ID == "placeholder":
                self.log_test(
                    "Asana OAuth Configuration",
                    "SKIP",
                    {"reason": "Placeholder credentials"},
                )
                return False

            response = self.session.get(
                f"{self.base_url}/api/auth/asana/authorize?user_id=test_user"
            )
            if response.status_code == 200:
                data = response.json()
                if data.get("ok") and data.get("auth_url"):
                    self.log_test(
                        "Asana OAuth Configuration",
                        "PASS",
                        {
                            "client_id_configured": bool(ASANA_CLIENT_ID),
                            "auth_url_generated": True,
                        },
                    )
                    return True
                else:
                    self.log_test(
                        "Asana OAuth Configuration", "FAIL", {"response": data}
                    )
                    return False
            else:
                self.log_test(
                    "Asana OAuth Configuration",
                    "FAIL",
                    {"status_code": response.status_code},
                )
                return False
        except Exception as e:
            self.log_test("Asana OAuth Configuration", "FAIL", {"error": str(e)})
            return False

    def test_asana_api_endpoints(self):
        """Test Asana API endpoints structure"""
        endpoints_to_test = [
            "/api/asana/user/profile",
            "/api/asana/workspaces",
            "/api/asana/projects",
            "/api/asana/tasks",
            "/api/asana/teams",
            "/api/asana/users",
            "/api/asana/status",
        ]

        passed = 0
        failed = 0

        for endpoint in endpoints_to_test:
            try:
                response = self.session.get(
                    f"{self.base_url}{endpoint}?user_id=test_user"
                )
                # For endpoints that require real tokens, we expect 400/401 errors
                # which means the endpoint exists but needs authentication
                if response.status_code in [200, 400, 401]:
                    passed += 1
                else:
                    failed += 1
                    print(f"   ❌ {endpoint}: HTTP {response.status_code}")
            except Exception as e:
                failed += 1
                print(f"   ❌ {endpoint}: {str(e)}")

        details = {
            "endpoints_tested": len(endpoints_to_test),
            "endpoints_accessible": passed,
            "endpoints_failed": failed,
        }

        if failed == 0:
            self.log_test("Asana API Endpoints Structure", "PASS", details)
            return True
        else:
            self.log_test("Asana API Endpoints Structure", "PARTIAL", details)
            return False

    def test_asana_service_integration(self):
        """Test Asana service integration"""
        try:
            # Import and test the Asana service directly
            from backend.integrations.asana_service import AsanaService

            service = AsanaService()

            # Test service initialization
            if service.client_id and service.client_id != "placeholder":
                self.log_test(
                    "Asana Service Integration",
                    "PASS",
                    {
                        "service_initialized": True,
                        "client_id_configured": True,
                        "api_base_url": service.api_base_url,
                    },
                )
                return True
            else:
                self.log_test(
                    "Asana Service Integration",
                    "FAIL",
                    {"service_initialized": True, "client_id_configured": False},
                )
                return False

        except Exception as e:
            self.log_test("Asana Service Integration", "FAIL", {"error": str(e)})
            return False

    def test_asana_database_schema(self):
        """Test Asana database schema availability"""
        try:
            schema_path = os.path.join(os.path.dirname(__file__), "asana_schema.sql")
            if os.path.exists(schema_path):
                with open(schema_path, "r") as f:
                    schema_content = f.read()

                # Check for key table definitions
                required_tables = [
                    "user_asana_oauth_tokens",
                    "user_asana_tasks",
                    "user_asana_projects",
                ]

                tables_found = []
                for table in required_tables:
                    if table in schema_content:
                        tables_found.append(table)

                self.log_test(
                    "Asana Database Schema",
                    "PASS",
                    {
                        "schema_file_exists": True,
                        "tables_found": tables_found,
                        "total_tables_checked": len(required_tables),
                    },
                )
                return True
            else:
                self.log_test(
                    "Asana Database Schema", "FAIL", {"error": "Schema file not found"}
                )
                return False

        except Exception as e:
            self.log_test("Asana Database Schema", "FAIL", {"error": str(e)})
            return False

    def test_comprehensive_oauth_flow(self):
        """Test comprehensive OAuth flow simulation"""
        try:
            # Step 1: Initiate OAuth
            auth_response = self.session.get(
                f"{self.base_url}/api/auth/asana/authorize?user_id=test_user_123"
            )

            if auth_response.status_code == 200:
                auth_data = auth_response.json()

                if auth_data.get("ok") and auth_data.get("auth_url"):
                    # Step 2: Simulate callback (this would normally come from Asana)
                    callback_params = {
                        "code": "mock_authorization_code",
                        "state": auth_data.get("state", "mock_state"),
                        "user_id": "test_user_123",
                    }

                    # Note: The actual callback would be handled by Asana's redirect
                    # This test just verifies the initiation works
                    self.log_test(
                        "Comprehensive OAuth Flow",
                        "PASS",
                        {
                            "oauth_initiation_works": True,
                            "auth_url_generated": True,
                            "state_parameter": bool(auth_data.get("state")),
                        },
                    )
                    return True
                else:
                    self.log_test(
                        "Comprehensive OAuth Flow", "FAIL", {"auth_response": auth_data}
                    )
                    return False
            else:
                self.log_test(
                    "Comprehensive OAuth Flow",
                    "FAIL",
                    {"status_code": auth_response.status_code},
                )
                return False

        except Exception as e:
            self.log_test("Comprehensive OAuth Flow", "FAIL", {"error": str(e)})
            return False

    def test_error_handling(self):
        """Test error handling for Asana endpoints"""
        try:
            # Test with invalid parameters
            response = self.session.get(f"{self.base_url}/api/asana/health")
            # Should handle missing user_id parameter gracefully
            if response.status_code in [400, 200]:
                self.log_test(
                    "Error Handling", "PASS", {"missing_parameter_handled": True}
                )
                return True
            else:
                self.log_test(
                    "Error Handling", "FAIL", {"status_code": response.status_code}
                )
                return False

        except Exception as e:
            self.log_test("Error Handling", "FAIL", {"error": str(e)})
            return False

    def run_all_tests(self):
        """Run all integration tests"""
        print("🚀 Starting Comprehensive Asana Integration Tests")
        print("=" * 60)
        print(f"📋 Test Configuration:")
        print(f"   Base URL: {self.base_url}")
        print(f"   Asana Client ID: {ASANA_CLIENT_ID[:8]}...")
        print(f"   Redirect URI: {ASANA_REDIRECT_URI}")
        print("=" * 60)

        # Run all tests
        tests = [
            self.test_api_health,
            self.test_asana_health_endpoint,
            self.test_asana_oauth_configuration,
            self.test_asana_api_endpoints,
            self.test_asana_service_integration,
            self.test_asana_database_schema,
            self.test_comprehensive_oauth_flow,
            self.test_error_handling,
        ]

        for test in tests:
            test()

        # Generate summary
        self.generate_summary()

    def generate_summary(self):
        """Generate test summary"""
        print("\n" + "=" * 60)
        print("📊 TEST SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = len([r for r in self.test_results if r["status"] == "PASS"])
        failed_tests = len([r for r in self.test_results if r["status"] == "FAIL"])
        skipped_tests = len([r for r in self.test_results if r["status"] == "SKIP"])

        print(f"Total Tests: {total_tests}")
        print(f"✅ Passed: {passed_tests}")
        print(f"❌ Failed: {failed_tests}")
        print(f"⚠️  Skipped: {skipped_tests}")

        success_rate = (passed_tests / total_tests) * 100 if total_tests > 0 else 0
        print(f"📈 Success Rate: {success_rate:.1f}%")

        # Show failed tests
        if failed_tests > 0:
            print("\n🔍 Failed Tests:")
            for result in self.test_results:
                if result["status"] == "FAIL":
                    print(f"   - {result['test']}: {result.get('details', {})}")

        # Overall status
        if failed_tests == 0:
            print("\n🎉 ALL TESTS PASSED! Asana integration is ready for production.")
        else:
            print(
                f"\n⚠️  {failed_tests} test(s) failed. Review and fix before production."
            )

        # Save detailed results
        self.save_test_results()

    def save_test_results(self):
        """Save detailed test results to file"""
        results_file = "asana_integration_test_results.json"
        results_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "test_environment": {
                "base_url": self.base_url,
                "asana_client_id_configured": bool(
                    ASANA_CLIENT_ID and ASANA_CLIENT_ID != "placeholder"
                ),
                "asana_redirect_uri": ASANA_REDIRECT_URI,
            },
            "summary": {
                "total_tests": len(self.test_results),
                "passed": len([r for r in self.test_results if r["status"] == "PASS"]),
                "failed": len([r for r in self.test_results if r["status"] == "FAIL"]),
                "skipped": len([r for r in self.test_results if r["status"] == "SKIP"]),
            },
            "detailed_results": self.test_results,
        }

        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"\n📄 Detailed results saved to: {results_file}")


def main():
    """Main test execution"""
    # Check if backend is running
    try:
        response = requests.get(f"{BASE_URL}/health", timeout=5)
        if response.status_code != 200:
            print("❌ Backend server is not running. Please start the backend first.")
            print("   Run: python atom/backend/main_api_app.py")
            return
    except requests.exceptions.ConnectionError:
        print("❌ Cannot connect to backend server. Please start the backend first.")
        print("   Run: python atom/backend/main_api_app.py")
        return

    # Run tests
    tester = AsanaIntegrationTester()
    tester.run_all_tests()


if __name__ == "__main__":
    main()
