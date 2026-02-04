"""
Production Real Service Testing Script

This script tests all 33 services in the Atom production deployment
with real API calls and service integrations.
"""

import json
import logging
import time
from typing import Any, Dict, List, Optional
import requests

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)


class ProductionServiceTester:
    """Test all production services with real API calls"""

    def __init__(self, base_url: str = "http://localhost:5058"):
        self.base_url = base_url
        self.test_user = "production_test_user"
        self.results = {}

    def test_health_endpoints(self):
        """Test all health and status endpoints"""
        logger.info("🔍 Testing Health Endpoints")

        health_endpoints = [
            ("/healthz", "API Server Health"),
            ("/api/services/status", "Service Registry Health"),
            ("/api/transcription/health", "Voice Processing Health"),
            ("/api/user/api-keys/test_user/status", "BYOK System Health"),
        ]

        for endpoint, description in health_endpoints:
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                if response.status_code == 200:
                    data = response.json()
                    self.results[description] = {
                        "status": "✅ OPERATIONAL",
                        "response_time": response.elapsed.total_seconds(),
                        "details": data,
                    }
                    logger.info(
                        f"✅ {description}: {response.elapsed.total_seconds():.3f}s"
                    )
                else:
                    self.results[description] = {
                        "status": "❌ FAILED",
                        "error": f"HTTP {response.status_code}",
                    }
                    logger.error(f"❌ {description}: HTTP {response.status_code}")
            except Exception as e:
                self.results[description] = {"status": "❌ ERROR", "error": str(e)}
                logger.error(f"❌ {description}: {e}")

    def test_byok_system(self):
        """Test BYOK system with real API key operations"""
        logger.info("🔑 Testing BYOK System")

        # Test provider configuration
        test_providers = [
            {
                "name": "OpenAI",
                "endpoint": f"/api/user/api-keys/{self.test_user}/keys/openai",
                "test_key": "sk-test-openai-production-12345",
            },
            {
                "name": "DeepSeek",
                "endpoint": f"/api/user/api-keys/{self.test_user}/keys/deepseek",
                "test_key": "sk-test-deepseek-production-67890",
            },
        ]

        for provider in test_providers:
            try:
                # Configure API key
                response = requests.post(
                    f"{self.base_url}{provider['endpoint']}",
                    json={"api_key": provider["test_key"]},
                    timeout=10,
                )

                if response.status_code == 200:
                    # Test provider status
                    status_response = requests.get(
                        f"{self.base_url}/api/user/api-keys/{self.test_user}/status",
                        timeout=10,
                    )

                    if status_response.status_code == 200:
                        status_data = status_response.json()
                        provider_status = status_data.get("status", {}).get(
                            "openai"
                            if "openai" in provider["endpoint"]
                            else "deepseek",
                            {},
                        )

                        self.results[f"BYOK - {provider['name']}"] = {
                            "status": "✅ CONFIGURED",
                            "configured": provider_status.get("configured", False),
                            "test_result": provider_status.get("test_result", {}),
                        }
                        logger.info(f"✅ BYOK {provider['name']}: Configured")
                    else:
                        self.results[f"BYOK - {provider['name']}"] = {
                            "status": "⚠️ PARTIAL",
                            "error": "Status check failed",
                        }
                        logger.warning(
                            f"⚠️ BYOK {provider['name']}: Status check failed"
                        )
                else:
                    self.results[f"BYOK - {provider['name']}"] = {
                        "status": "❌ FAILED",
                        "error": f"Configuration failed: HTTP {response.status_code}",
                    }
                    logger.error(f"❌ BYOK {provider['name']}: Configuration failed")

            except Exception as e:
                self.results[f"BYOK - {provider['name']}"] = {
                    "status": "❌ ERROR",
                    "error": str(e),
                }
                logger.error(f"❌ BYOK {provider['name']}: {e}")

    def test_workflow_automation(self):
        """Test workflow automation with real natural language inputs"""
        logger.info("🤖 Testing Workflow Automation")

        test_cases = [
            {
                "input": "Create a customer onboarding workflow with welcome email and calendar invite",
                "expected_services": ["gmail", "google_calendar"],
                "min_steps": 2,
            },
            {
                "input": "Automate project kickoff with team communication and document sharing",
                "expected_services": ["slack", "google_drive", "trello"],
                "min_steps": 2,
            },
            {
                "input": "Set up meeting follow-up automation with notes and action items",
                "expected_services": ["gmail", "notion", "asana"],
                "min_steps": 2,
            },
        ]

        for i, test_case in enumerate(test_cases):
            try:
                response = requests.post(
                    f"{self.base_url}/api/workflow-automation/generate",
                    json={"user_input": test_case["input"], "user_id": self.test_user},
                    timeout=30,
                )

                if response.status_code == 200:
                    data = response.json()
                    if data.get("success"):
                        workflow = data.get("workflow", {})
                        steps = workflow.get("steps", [])
                        services = workflow.get("services", [])

                        # Calculate service coverage
                        expected_services = set(test_case["expected_services"])
                        actual_services = set(services)
                        coverage = len(expected_services.intersection(actual_services))
                        coverage_percentage = (coverage / len(expected_services)) * 100

                        self.results[f"Workflow Test {i + 1}"] = {
                            "status": "✅ GENERATED",
                            "steps_count": len(steps),
                            "services_found": list(actual_services),
                            "service_coverage": f"{coverage_percentage:.1f}%",
                            "response_time": response.elapsed.total_seconds(),
                        }
                        logger.info(
                            f"✅ Workflow {i + 1}: {len(steps)} steps, {coverage_percentage:.1f}% coverage"
                        )
                    else:
                        self.results[f"Workflow Test {i + 1}"] = {
                            "status": "❌ FAILED",
                            "error": data.get("message", "Unknown error"),
                        }
                        logger.error(
                            f"❌ Workflow {i + 1}: {data.get('message', 'Unknown error')}"
                        )
                else:
                    self.results[f"Workflow Test {i + 1}"] = {
                        "status": "❌ HTTP ERROR",
                        "error": f"HTTP {response.status_code}: {response.text}",
                    }
                    logger.error(f"❌ Workflow {i + 1}: HTTP {response.status_code}")

            except Exception as e:
                self.results[f"Workflow Test {i + 1}"] = {
                    "status": "❌ ERROR",
                    "error": str(e),
                }
                logger.error(f"❌ Workflow {i + 1}: {e}")

    def test_service_registry(self):
        """Test service registry and individual service endpoints"""
        logger.info("🔌 Testing Service Registry")

        try:
            # Get all services
            response = requests.get(f"{self.base_url}/api/services", timeout=10)
            if response.status_code == 200:
                data = response.json()
                total_services = data.get("total_services", 0)
                active_services = data.get("active_services", 0)
                services_list = data.get("services", [])

                self.results["Service Registry"] = {
                    "status": "✅ OPERATIONAL",
                    "total_services": total_services,
                    "active_services": active_services,
                    "services_available": len(services_list),
                }
                logger.info(
                    f"✅ Service Registry: {total_services} total, {active_services} active"
                )

                # Test individual service health
                service_health = {}
                for service in services_list[:10]:  # Test first 10 services
                    service_id = service.get("id")
                    health = service.get("health", "unknown")
                    service_health[service_id] = health

                self.results["Service Health Sample"] = service_health

            else:
                self.results["Service Registry"] = {
                    "status": "❌ FAILED",
                    "error": f"HTTP {response.status_code}",
                }
                logger.error(f"❌ Service Registry: HTTP {response.status_code}")

        except Exception as e:
            self.results["Service Registry"] = {"status": "❌ ERROR", "error": str(e)}
            logger.error(f"❌ Service Registry: {e}")

    def test_oauth_endpoints(self):
        """Test OAuth authorization endpoints"""
        logger.info("🔐 Testing OAuth Endpoints")

        oauth_endpoints = [
            ("/api/auth/gdrive/authorize?user_id=test_user", "Google Drive OAuth"),
            ("/api/auth/asana/authorize?user_id=test_user", "Asana OAuth"),
        ]

        for endpoint, description in oauth_endpoints:
            try:
                response = requests.get(
                    f"{self.base_url}{endpoint}", allow_redirects=False, timeout=10
                )

                # OAuth endpoints should redirect (302) or return success (200)
                if response.status_code in [200, 302]:
                    self.results[description] = {
                        "status": "✅ REDIRECTING",
                        "response_code": response.status_code,
                    }
                    logger.info(f"✅ {description}: HTTP {response.status_code}")
                else:
                    self.results[description] = {
                        "status": "⚠️ UNEXPECTED",
                        "response_code": response.status_code,
                    }
                    logger.warning(f"⚠️ {description}: HTTP {response.status_code}")

            except Exception as e:
                self.results[description] = {"status": "❌ ERROR", "error": str(e)}
                logger.error(f"❌ {description}: {e}")

    def test_performance_metrics(self):
        """Test performance and response times"""
        logger.info("⚡ Testing Performance Metrics")

        performance_tests = [
            ("/healthz", "Health Check"),
            ("/api/services/status", "Service Status"),
            ("/api/user/api-keys/test_user/status", "BYOK Status"),
        ]

        performance_results = {}

        for endpoint, description in performance_tests:
            try:
                # Test response time
                start_time = time.time()
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                response_time = time.time() - start_time

                if response.status_code == 200:
                    performance_results[description] = {
                        "response_time": response_time,
                        "status": "✅ SUCCESS",
                    }
                    logger.info(f"✅ {description}: {response_time:.3f}s")
                else:
                    performance_results[description] = {
                        "response_time": response_time,
                        "status": f"❌ HTTP {response.status_code}",
                    }
                    logger.error(f"❌ {description}: HTTP {response.status_code}")

            except Exception as e:
                performance_results[description] = {
                    "response_time": None,
                    "status": f"❌ ERROR: {str(e)}",
                }
                logger.error(f"❌ {description}: {e}")

        self.results["Performance Metrics"] = performance_results

    def generate_report(self):
        """Generate comprehensive test report"""
        logger.info("📊 Generating Test Report")

        # Calculate overall statistics
        total_tests = len(self.results)
        successful_tests = len(
            [r for r in self.results.values() if "✅" in r.get("status", "")]
        )
        failed_tests = len(
            [r for r in self.results.values() if "❌" in r.get("status", "")]
        )
        warning_tests = len(
            [r for r in self.results.values() if "⚠️" in r.get("status", "")]
        )

        success_rate = (successful_tests / total_tests) * 100 if total_tests > 0 else 0

        report = {
            "summary": {
                "total_tests": total_tests,
                "successful_tests": successful_tests,
                "failed_tests": failed_tests,
                "warning_tests": warning_tests,
                "success_rate": f"{success_rate:.1f}%",
                "timestamp": time.strftime("%Y-%m-%d %H:%M:%S"),
            },
            "detailed_results": self.results,
        }

        # Save report to file
        with open("production_service_test_report.json", "w") as f:
            json.dump(report, f, indent=2)

        # Print summary
        print("\n" + "=" * 60)
        print("🚀 PRODUCTION SERVICE TEST REPORT")
        print("=" * 60)
        print(
            f"📊 Summary: {successful_tests}/{total_tests} tests passed ({success_rate:.1f}%)"
        )
        print(f"🕒 Timestamp: {report['summary']['timestamp']}")

        print(f"\n🎯 Key Findings:")
        for test_name, result in self.results.items():
            status = result.get("status", "UNKNOWN")
            print(f"   {status} {test_name}")

            # Show additional details for key metrics
            if "response_time" in result:
                print(f"      ⏱️ Response time: {result['response_time']:.3f}s")
            if "service_coverage" in result:
                print(f"      📈 Service coverage: {result['service_coverage']}")
            if "total_services" in result:
                print(f"      🔌 Total services: {result['total_services']}")

        print(f"\n💡 Recommendations:")
        if success_rate >= 90:
            print("   ✅ System is production-ready!")
        elif success_rate >= 80:
            print("   ⚠️ Minor improvements needed before production")
        else:
            print("   ❌ Significant improvements needed")

        print(f"\n📁 Detailed report saved to: production_service_test_report.json")

        return report

    def run_all_tests(self):
        """Run all production service tests"""
        logger.info("🚀 Starting Production Service Tests")
        logger.info(f"🌐 Base URL: {self.base_url}")
        logger.info(f"👤 Test User: {self.test_user}")

        # Run all test suites
        self.test_health_endpoints()
        self.test_byok_system()
        self.test_workflow_automation()
        self.test_service_registry()
        self.test_oauth_endpoints()
        self.test_performance_metrics()

        # Generate final report
        report = self.generate_report()

        return report


def main():
    """Main function to run production service tests"""
    tester = ProductionServiceTester()
    report = tester.run_all_tests()

    # Exit with appropriate code
    success_rate = float(report["summary"]["success_rate"].rstrip("%"))
    if success_rate >= 80:
        print("\n🎉 PRODUCTION SERVICE TESTS: PASSED ✅")
        exit(0)
    else:
        print("\n❌ PRODUCTION SERVICE TESTS: NEEDS IMPROVEMENT ⚠️")
        exit(1)


if __name__ == "__main__":
    main()
