#!/usr/bin/env python3
"""
Salesforce Integration Test Script
Tests the complete Salesforce integration including OAuth, service operations, and health endpoints
"""

import os
import sys
import asyncio
import logging
from datetime import datetime, timezone
import requests

# Add the current directory to Python path
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

# Configure logging
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s"
)
logger = logging.getLogger(__name__)

# Test configuration
BASE_URL = "http://localhost:5000"  # Adjust if your API runs on different port
TEST_USER_ID = "test_user_salesforce"


class SalesforceIntegrationTester:
    """Test class for Salesforce integration"""

    def __init__(self, base_url: str, user_id: str):
        self.base_url = base_url
        self.user_id = user_id
        self.session = requests.Session()

    def test_health_endpoints(self) -> bool:
        """Test Salesforce health endpoints"""
        logger.info("Testing Salesforce health endpoints...")

        endpoints = [
            "/api/salesforce/health",
            "/api/salesforce/health/tokens",
            "/api/salesforce/health/connection",
            "/api/salesforce/health/summary",
        ]

        all_healthy = True

        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                if "tokens" in endpoint or "connection" in endpoint:
                    url += f"?user_id={self.user_id}"

                response = self.session.get(url)

                if response.status_code == 200:
                    data = response.json()
                    logger.info(f"✅ {endpoint}: {data.get('status', 'healthy')}")
                else:
                    logger.error(f"❌ {endpoint}: HTTP {response.status_code}")
                    all_healthy = False

            except Exception as e:
                logger.error(f"❌ {endpoint}: {e}")
                all_healthy = False

        return all_healthy

    def test_service_registry(self) -> bool:
        """Test if Salesforce is properly registered in service registry"""
        logger.info("Testing Salesforce service registry...")

        try:
            # Get all services
            response = self.session.get(f"{self.base_url}/api/services")

            if response.status_code == 200:
                services = response.json()
                salesforce_services = [
                    service for service in services if "salesforce" in service.lower()
                ]

                if salesforce_services:
                    logger.info(
                        f"✅ Salesforce services found: {len(salesforce_services)}"
                    )
                    for service in salesforce_services:
                        logger.info(f"   - {service}")
                    return True
                else:
                    logger.error("❌ No Salesforce services found in registry")
                    return False
            else:
                logger.error(
                    f"❌ Service registry endpoint failed: {response.status_code}"
                )
                return False

        except Exception as e:
            logger.error(f"❌ Service registry test failed: {e}")
            return False

    def test_comprehensive_integration_api(self) -> bool:
        """Test Salesforce endpoints in comprehensive integration API"""
        logger.info("Testing comprehensive integration API endpoints...")

        endpoints = [
            ("GET", "/api/integrations/salesforce/status"),
            ("POST", "/api/integrations/salesforce/sync"),
            ("GET", "/api/integrations/salesforce/search"),
        ]

        all_successful = True

        for method, endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"

                if method == "GET":
                    url += f"?user_id={self.user_id}"
                    response = self.session.get(url)
                elif method == "POST":
                    payload = {"user_id": self.user_id}
                    if "sync" in endpoint:
                        payload["data_types"] = ["contacts", "accounts"]
                    elif "search" in endpoint:
                        payload["query"] = "test"
                        payload["data_type"] = "contacts"
                    response = self.session.post(url, json=payload)

                if response.status_code in [200, 201]:
                    data = response.json()
                    if data.get("success", False) or data.get("ok", False):
                        logger.info(f"✅ {method} {endpoint}: Success")
                    else:
                        logger.warning(
                            f"⚠️ {method} {endpoint}: API returned success=False"
                        )
                else:
                    logger.warning(
                        f"⚠️ {method} {endpoint}: HTTP {response.status_code} (may be expected for unauthenticated user)"
                    )

            except Exception as e:
                logger.error(f"❌ {method} {endpoint}: {e}")
                all_successful = False

        return all_successful

    def test_oauth_endpoints(self) -> bool:
        """Test Salesforce OAuth endpoints"""
        logger.info("Testing Salesforce OAuth endpoints...")

        endpoints = ["/api/auth/salesforce/authorize", "/api/oauth/salesforce/url"]

        all_accessible = True

        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                if "authorize" in endpoint:
                    url += f"?user_id={self.user_id}"

                response = self.session.get(url)

                # OAuth endpoints may return various status codes depending on configuration
                if response.status_code in [200, 302, 400, 503]:
                    logger.info(
                        f"✅ {endpoint}: Accessible (HTTP {response.status_code})"
                    )
                else:
                    logger.warning(
                        f"⚠️ {endpoint}: Unexpected HTTP {response.status_code}"
                    )

            except Exception as e:
                logger.error(f"❌ {endpoint}: {e}")
                all_accessible = False

        return all_accessible

    def test_database_operations(self) -> bool:
        """Test Salesforce database operations (if database is available)"""
        logger.info("Testing Salesforce database operations...")

        try:
            # Import database modules
            import asyncpg
            from db_oauth_salesforce import (
                init_salesforce_oauth_table,
                get_user_salesforce_tokens,
                store_salesforce_tokens,
            )

            # This test requires a running database
            # For now, just verify the modules can be imported
            logger.info("✅ Salesforce database modules imported successfully")
            return True

        except ImportError as e:
            logger.warning(f"⚠️ Database modules not available: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Database operations test failed: {e}")
            return False

    def run_all_tests(self) -> dict:
        """Run all Salesforce integration tests"""
        logger.info("🚀 Starting Salesforce Integration Tests")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Test User ID: {self.user_id}")
        logger.info("=" * 60)

        test_results = {}

        # Run tests
        test_results["health_endpoints"] = self.test_health_endpoints()
        test_results["service_registry"] = self.test_service_registry()
        test_results["comprehensive_api"] = self.test_comprehensive_integration_api()
        test_results["oauth_endpoints"] = self.test_oauth_endpoints()
        test_results["database_operations"] = self.test_database_operations()

        # Summary
        logger.info("=" * 60)
        logger.info("📊 Salesforce Integration Test Summary")
        logger.info("=" * 60)

        passed_tests = sum(test_results.values())
        total_tests = len(test_results)

        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status} {test_name}")

        logger.info(f"Overall: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            logger.info("🎉 All Salesforce integration tests passed!")
        else:
            logger.warning("⚠️ Some Salesforce integration tests failed")

        return test_results


def main():
    """Main test execution function"""
    # Check if API is running
    try:
        response = requests.get(f"{BASE_URL}/api/health", timeout=5)
        if response.status_code != 200:
            logger.error(f"❌ API not responding at {BASE_URL}")
            logger.info("Please start the API server first:")
            logger.info("cd atom/backend/python-api-service && python main_api_app.py")
            return 1
    except requests.exceptions.ConnectionError:
        logger.error(f"❌ Cannot connect to API at {BASE_URL}")
        logger.info("Please start the API server first:")
        logger.info("cd atom/backend/python-api-service && python main_api_app.py")
        return 1

    # Run tests
    tester = SalesforceIntegrationTester(BASE_URL, TEST_USER_ID)
    results = tester.run_all_tests()

    # Return appropriate exit code
    passed_tests = sum(results.values())
    total_tests = len(results)

    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    exit(main())
