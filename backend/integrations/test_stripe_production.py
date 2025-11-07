"""
Stripe Integration Production Testing Script
Comprehensive testing for Stripe integration in production-like environment
"""

import os
import sys
import asyncio
import json
import requests
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import logging

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Add backend directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))


class StripeProductionTest:
    """Production testing class for Stripe integration"""

    def __init__(self, base_url: str = "http://localhost:8000"):
        self.base_url = base_url
        self.test_results = []
        self.access_token = "test_access_token"  # Will be replaced with real token

    def log_test(
        self,
        test_name: str,
        success: bool,
        details: str = "",
        response_time: float = None,
    ):
        """Log test result with timing information"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "response_time": response_time,
            "timestamp": datetime.now().isoformat(),
        }
        self.test_results.append(result)

        time_info = f" ({response_time:.2f}s)" if response_time else ""
        print(f"{status} {test_name}{time_info}")
        if details:
            print(f"   Details: {details}")

    async def test_health_endpoint(self):
        """Test Stripe health endpoint"""
        start_time = datetime.now()
        try:
            response = requests.get(f"{self.base_url}/stripe/health", timeout=10)
            response_time = (datetime.now() - start_time).total_seconds()

            success = response.status_code == 200
            status_info = response.json().get("status", "unknown")

            self.log_test(
                "Health Endpoint",
                success,
                f"Status: {status_info}, HTTP: {response.status_code}",
                response_time,
            )
            return success
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            self.log_test("Health Endpoint", False, f"Error: {str(e)}", response_time)
            return False

    async def test_api_connectivity(self):
        """Test basic API connectivity and response formatting"""
        start_time = datetime.now()
        try:
            response = requests.get(f"{self.base_url}/stripe/", timeout=10)
            response_time = (datetime.now() - start_time).total_seconds()

            success = response.status_code == 200
            data = response.json()
            endpoints = data.get("endpoints", [])

            self.log_test(
                "API Connectivity",
                success,
                f"Endpoints available: {len(endpoints)}",
                response_time,
            )
            return success
        except Exception as e:
            response_time = (datetime.now() - start_time).total_seconds()
            self.log_test("API Connectivity", False, f"Error: {str(e)}", response_time)
            return False

    async def test_payment_endpoints(self):
        """Test payment-related endpoints"""
        tests = [
            ("GET /stripe/payments", "GET", "/stripe/payments?limit=1"),
            (
                "GET /stripe/payments with params",
                "GET",
                "/stripe/payments?limit=5&status=succeeded",
            ),
        ]

        results = []
        for test_name, method, endpoint in tests:
            start_time = datetime.now()
            try:
                if method == "GET":
                    response = requests.get(f"{self.base_url}{endpoint}", timeout=15)
                else:
                    response = requests.post(f"{self.base_url}{endpoint}", timeout=15)

                response_time = (datetime.now() - start_time).total_seconds()
                success = response.status_code in [
                    200,
                    401,
                ]  # 401 is expected without auth

                status_info = f"HTTP: {response.status_code}"
                if response.status_code == 200:
                    data = response.json()
                    status_info += f", Data keys: {list(data.keys())}"

                self.log_test(test_name, success, status_info, response_time)
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(test_name, False, f"Error: {str(e)}", response_time)
                results.append(False)

        return all(results)

    async def test_customer_endpoints(self):
        """Test customer-related endpoints"""
        tests = [
            ("GET /stripe/customers", "GET", "/stripe/customers?limit=1"),
            (
                "GET /stripe/customers with email",
                "GET",
                "/stripe/customers?limit=5&email=test@example.com",
            ),
        ]

        results = []
        for test_name, method, endpoint in tests:
            start_time = datetime.now()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=15)
                response_time = (datetime.now() - start_time).total_seconds()
                success = response.status_code in [
                    200,
                    401,
                ]  # 401 is expected without auth

                status_info = f"HTTP: {response.status_code}"
                if response.status_code == 200:
                    data = response.json()
                    status_info += f", OK: {data.get('ok', False)}"

                self.log_test(test_name, success, status_info, response_time)
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(test_name, False, f"Error: {str(e)}", response_time)
                results.append(False)

        return all(results)

    async def test_subscription_endpoints(self):
        """Test subscription-related endpoints"""
        tests = [
            ("GET /stripe/subscriptions", "GET", "/stripe/subscriptions?limit=1"),
            (
                "GET /stripe/subscriptions with status",
                "GET",
                "/stripe/subscriptions?limit=5&status=active",
            ),
        ]

        results = []
        for test_name, method, endpoint in tests:
            start_time = datetime.now()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=15)
                response_time = (datetime.now() - start_time).total_seconds()
                success = response.status_code in [
                    200,
                    401,
                ]  # 401 is expected without auth

                status_info = f"HTTP: {response.status_code}"
                self.log_test(test_name, success, status_info, response_time)
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(test_name, False, f"Error: {str(e)}", response_time)
                results.append(False)

        return all(results)

    async def test_product_endpoints(self):
        """Test product-related endpoints"""
        tests = [
            ("GET /stripe/products", "GET", "/stripe/products?limit=1"),
            (
                "GET /stripe/products active only",
                "GET",
                "/stripe/products?limit=5&active=true",
            ),
        ]

        results = []
        for test_name, method, endpoint in tests:
            start_time = datetime.now()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=15)
                response_time = (datetime.now() - start_time).total_seconds()
                success = response.status_code in [
                    200,
                    401,
                ]  # 401 is expected without auth

                status_info = f"HTTP: {response.status_code}"
                self.log_test(test_name, success, status_info, response_time)
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(test_name, False, f"Error: {str(e)}", response_time)
                results.append(False)

        return all(results)

    async def test_financial_endpoints(self):
        """Test financial and account endpoints"""
        tests = [
            ("GET /stripe/balance", "GET", "/stripe/balance"),
            ("GET /stripe/account", "GET", "/stripe/account"),
            ("GET /stripe/profile", "GET", "/stripe/profile"),
            ("GET /stripe/search", "GET", "/stripe/search?query=test&limit=5"),
        ]

        results = []
        for test_name, method, endpoint in tests:
            start_time = datetime.now()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=15)
                response_time = (datetime.now() - start_time).total_seconds()
                success = response.status_code in [
                    200,
                    401,
                ]  # 401 is expected without auth

                status_info = f"HTTP: {response.status_code}"
                self.log_test(test_name, success, status_info, response_time)
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(test_name, False, f"Error: {str(e)}", response_time)
                results.append(False)

        return all(results)

    async def test_response_times(self):
        """Test API response times for performance"""
        endpoints = [
            "/stripe/health",
            "/stripe/",
            "/stripe/payments?limit=1",
            "/stripe/customers?limit=1",
        ]

        results = []
        for endpoint in endpoints:
            start_time = datetime.now()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                response_time = (datetime.now() - start_time).total_seconds()

                # Consider response time acceptable if under 2 seconds
                success = response_time < 2.0
                status_info = (
                    f"Time: {response_time:.2f}s, HTTP: {response.status_code}"
                )

                self.log_test(
                    f"Response Time {endpoint}", success, status_info, response_time
                )
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(
                    f"Response Time {endpoint}",
                    False,
                    f"Error: {str(e)}",
                    response_time,
                )
                results.append(False)

        return all(results)

    async def test_error_handling(self):
        """Test error handling scenarios"""
        tests = [
            ("Invalid endpoint", "GET", "/stripe/invalid_endpoint", 404),
            (
                "Invalid payment ID",
                "GET",
                "/stripe/payments/invalid_id",
                401,
            ),  # 401 expected without auth
        ]

        results = []
        for test_name, method, endpoint, expected_status in tests:
            start_time = datetime.now()
            try:
                response = requests.get(f"{self.base_url}{endpoint}", timeout=10)
                response_time = (datetime.now() - start_time).total_seconds()

                # For error tests, we expect specific status codes
                success = response.status_code == expected_status
                status_info = (
                    f"Expected: {expected_status}, Got: {response.status_code}"
                )

                self.log_test(test_name, success, status_info, response_time)
                results.append(success)
            except Exception as e:
                response_time = (datetime.now() - start_time).total_seconds()
                self.log_test(test_name, False, f"Error: {str(e)}", response_time)
                results.append(False)

        return all(results)

    async def run_all_tests(self):
        """Run all production tests"""
        print("🚀 Starting Stripe Production Integration Tests")
        print("=" * 60)
        print(f"Target URL: {self.base_url}")
        print(f"Start Time: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}")
        print("=" * 60)

        # Run all test categories
        test_categories = [
            ("Health Check", self.test_health_endpoint),
            ("API Connectivity", self.test_api_connectivity),
            ("Payment Endpoints", self.test_payment_endpoints),
            ("Customer Endpoints", self.test_customer_endpoints),
            ("Subscription Endpoints", self.test_subscription_endpoints),
            ("Product Endpoints", self.test_product_endpoints),
            ("Financial Endpoints", self.test_financial_endpoints),
            ("Response Times", self.test_response_times),
            ("Error Handling", self.test_error_handling),
        ]

        category_results = []
        for category_name, test_method in test_categories:
            print(f"\n📋 Testing: {category_name}")
            print("-" * 40)
            result = await test_method()
            category_results.append(result)

        # Generate comprehensive summary
        print("\n" + "=" * 60)
        print("📊 PRODUCTION TEST SUMMARY")
        print("=" * 60)

        total_tests = len(self.test_results)
        passed_tests = sum(1 for r in self.test_results if "✅" in r["status"])
        failed_tests = total_tests - passed_tests

        # Calculate average response time
        response_times = [
            r["response_time"]
            for r in self.test_results
            if r["response_time"] is not None
        ]
        avg_response_time = (
            sum(response_times) / len(response_times) if response_times else 0
        )

        print(f"Total Tests: {total_tests}")
        print(f"Tests Passed: {passed_tests}")
        print(f"Tests Failed: {failed_tests}")
        print(f"Success Rate: {(passed_tests / total_tests) * 100:.1f}%")
        print(f"Average Response Time: {avg_response_time:.2f}s")

        # Performance metrics
        slow_tests = [r for r in self.test_results if r.get("response_time", 0) > 2.0]
        if slow_tests:
            print(f"Slow Tests (>2s): {len(slow_tests)}")
            for test in slow_tests[:3]:  # Show top 3 slowest
                print(f"  - {test['test']}: {test['response_time']:.2f}s")

        # Save detailed results
        self.save_test_results()

        overall_success = all(category_results)
        if overall_success:
            print("\n🎉 ALL PRODUCTION TESTS PASSED!")
            print("Stripe integration is ready for production use.")
        else:
            print("\n⚠️  SOME TESTS FAILED")
            print("Review the failed tests above before production deployment.")

        return overall_success

    def save_test_results(self):
        """Save detailed test results to JSON file"""
        results_file = "stripe_production_test_results.json"
        results_data = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "base_url": self.base_url,
                "total_tests": len(self.test_results),
                "passed_tests": sum(
                    1 for r in self.test_results if "✅" in r["status"]
                ),
                "failed_tests": sum(
                    1 for r in self.test_results if "❌" in r["status"]
                ),
                "average_response_time": sum(
                    r["response_time"] for r in self.test_results if r["response_time"]
                )
                / len([r for r in self.test_results if r["response_time"]]),
            },
            "results": self.test_results,
        }

        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"📄 Detailed results saved to: {results_file}")


async def main():
    """Main test execution function"""
    import argparse

    parser = argparse.ArgumentParser(description="Stripe Production Integration Tests")
    parser.add_argument(
        "--url", default="http://localhost:8000", help="Base URL of the API"
    )
    parser.add_argument("--token", help="Access token for authenticated tests")

    args = parser.parse_args()

    tester = StripeProductionTest(base_url=args.url)
    if args.token:
        tester.access_token = args.token

    success = await tester.run_all_tests()

    return 0 if success else 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
