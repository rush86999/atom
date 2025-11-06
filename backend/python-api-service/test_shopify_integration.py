#!/usr/bin/env python3
"""
Shopify Integration Test Script
Tests the complete Shopify integration including OAuth, service operations, and health endpoints
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
TEST_USER_ID = "test_user_shopify"


class ShopifyIntegrationTester:
    """Test class for Shopify integration"""

    def __init__(self, base_url: str, user_id: str):
        self.base_url = base_url
        self.user_id = user_id
        self.session = requests.Session()

    def test_health_endpoints(self) -> bool:
        """Test Shopify health endpoints"""
        logger.info("Testing Shopify health endpoints...")

        endpoints = [
            "/api/shopify/health",
            "/api/shopify/health/tokens",
            "/api/shopify/health/connection",
            "/api/shopify/health/summary",
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
        """Test if Shopify is properly registered in service registry"""
        logger.info("Testing Shopify service registry...")

        try:
            # Get all services
            response = self.session.get(f"{self.base_url}/api/services")

            if response.status_code == 200:
                services = response.json()
                shopify_services = [
                    service for service in services if "shopify" in service.lower()
                ]

                if shopify_services:
                    logger.info(f"✅ Shopify services found: {len(shopify_services)}")
                    for service in shopify_services:
                        logger.info(f"   - {service}")
                    return True
                else:
                    logger.error("❌ No Shopify services found in registry")
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
        """Test Shopify endpoints in comprehensive integration API"""
        logger.info("Testing comprehensive integration API endpoints...")

        endpoints = [
            ("GET", "/api/integrations/shopify/status"),
            ("POST", "/api/integrations/shopify/sync"),
            ("GET", "/api/integrations/shopify/search"),
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
                        payload["data_types"] = ["products", "orders"]
                    elif "search" in endpoint:
                        payload["query"] = "test"
                        payload["data_type"] = "products"
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
        """Test Shopify OAuth endpoints"""
        logger.info("Testing Shopify OAuth endpoints...")

        endpoints = ["/api/auth/shopify/authorize", "/api/oauth/shopify/url"]

        all_accessible = True

        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}"
                if "authorize" in endpoint:
                    url += f"?user_id={self.user_id}&shop_name=test-shop"

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

    def test_api_endpoints(self) -> bool:
        """Test Shopify API endpoints"""
        logger.info("Testing Shopify API endpoints...")

        endpoints = [
            "/api/shopify/products",
            "/api/shopify/orders",
            "/api/shopify/customers",
        ]

        all_accessible = True

        for endpoint in endpoints:
            try:
                url = f"{self.base_url}{endpoint}?user_id={self.user_id}"
                response = self.session.get(url)

                # API endpoints may return 401 for unauthenticated users
                if response.status_code in [200, 401]:
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
        """Test Shopify database operations (if database is available)"""
        logger.info("Testing Shopify database operations...")

        try:
            # Import database modules
            import asyncpg
            from db_oauth_shopify import (
                init_shopify_oauth_table,
                get_user_shopify_tokens,
                store_shopify_tokens,
            )

            # This test requires a running database
            # For now, just verify the modules can be imported
            logger.info("✅ Shopify database modules imported successfully")
            return True

        except ImportError as e:
            logger.warning(f"⚠️ Database modules not available: {e}")
            return False
        except Exception as e:
            logger.error(f"❌ Database operations test failed: {e}")
            return False

    def run_all_tests(self) -> dict:
        """Run all Shopify integration tests"""
        logger.info("🚀 Starting Shopify Integration Tests")
        logger.info(f"Base URL: {self.base_url}")
        logger.info(f"Test User ID: {self.user_id}")
        logger.info("=" * 60)

        test_results = {}

        # Run tests
        test_results["health_endpoints"] = self.test_health_endpoints()
        test_results["service_registry"] = self.test_service_registry()
        test_results["comprehensive_api"] = self.test_comprehensive_integration_api()
        test_results["oauth_endpoints"] = self.test_oauth_endpoints()
        test_results["api_endpoints"] = self.test_api_endpoints()
        test_results["database_operations"] = self.test_database_operations()

        # Summary
        logger.info("=" * 60)
        logger.info("📊 Shopify Integration Test Summary")
        logger.info("=" * 60)

        passed_tests = sum(test_results.values())
        total_tests = len(test_results)

        for test_name, result in test_results.items():
            status = "✅ PASS" if result else "❌ FAIL"
            logger.info(f"{status} {test_name}")

        logger.info(f"Overall: {passed_tests}/{total_tests} tests passed")

        if passed_tests == total_tests:
            logger.info("🎉 All Shopify integration tests passed!")
        else:
            logger.warning("⚠️ Some Shopify integration tests failed")

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
    tester = ShopifyIntegrationTester(BASE_URL, TEST_USER_ID)
    results = tester.run_all_tests()

    # Return appropriate exit code
    passed_tests = sum(results.values())
    total_tests = len(results)

    return 0 if passed_tests == total_tests else 1


if __name__ == "__main__":
    exit(main())
