"""
Stripe Integration Test Script
Enhanced testing for Stripe payment processing with mock data and comprehensive error handling
"""

import asyncio
import json
import sys
import os
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
from unittest.mock import Mock, patch, AsyncMock

# Add backend directory to path for imports
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

try:
    from stripe_routes import router as stripe_router

    # Import Stripe services directly from files
    sys.path.append(os.path.join(os.path.dirname(__file__), "..", "python-api-service"))
    from stripe_service import stripe_service, StripeService

    STRIPE_AVAILABLE = True
except ImportError as e:
    print(f"❌ Stripe integration not available: {e}")
    STRIPE_AVAILABLE = False


class MockStripeService:
    """Mock Stripe service for testing without real API calls"""

    def __init__(self):
        self.api_base_url = "https://api.stripe.com/v1"
        self.mock_customers = self._create_mock_customers()
        self.mock_payments = self._create_mock_payments()
        self.mock_subscriptions = self._create_mock_subscriptions()
        self.mock_products = self._create_mock_products()

    def _create_mock_customers(self):
        """Create mock customer data"""
        return {
            "data": [
                {
                    "id": "cus_test123",
                    "object": "customer",
                    "email": "customer1@example.com",
                    "name": "John Doe",
                    "description": "Premium customer",
                    "created": 1609459200,
                    "metadata": {"plan": "premium"},
                },
                {
                    "id": "cus_test456",
                    "object": "customer",
                    "email": "customer2@example.com",
                    "name": "Jane Smith",
                    "description": "Basic customer",
                    "created": 1609545600,
                    "metadata": {"plan": "basic"},
                },
            ],
            "has_more": False,
            "url": "/v1/customers",
        }

    def _create_mock_payments(self):
        """Create mock payment data"""
        return {
            "data": [
                {
                    "id": "ch_test123",
                    "object": "charge",
                    "amount": 2000,
                    "currency": "usd",
                    "customer": "cus_test123",
                    "description": "Monthly subscription",
                    "status": "succeeded",
                    "created": 1609459200,
                    "metadata": {"invoice_id": "inv_123"},
                },
                {
                    "id": "ch_test456",
                    "object": "charge",
                    "amount": 1500,
                    "currency": "usd",
                    "customer": "cus_test456",
                    "description": "One-time payment",
                    "status": "succeeded",
                    "created": 1609545600,
                    "metadata": {"invoice_id": "inv_456"},
                },
            ],
            "has_more": False,
            "url": "/v1/charges",
        }

    def _create_mock_subscriptions(self):
        """Create mock subscription data"""
        return {
            "data": [
                {
                    "id": "sub_test123",
                    "object": "subscription",
                    "customer": "cus_test123",
                    "status": "active",
                    "current_period_start": 1609459200,
                    "current_period_end": 1612137600,
                    "items": {
                        "data": [
                            {
                                "id": "si_test123",
                                "price": {
                                    "id": "price_test123",
                                    "product": "prod_test123",
                                },
                            }
                        ]
                    },
                    "metadata": {"plan": "premium"},
                }
            ],
            "has_more": False,
            "url": "/v1/subscriptions",
        }

    def _create_mock_products(self):
        """Create mock product data"""
        return {
            "data": [
                {
                    "id": "prod_test123",
                    "object": "product",
                    "name": "Premium Plan",
                    "description": "Premium subscription plan",
                    "active": True,
                    "metadata": {"features": "all"},
                },
                {
                    "id": "prod_test456",
                    "object": "product",
                    "name": "Basic Plan",
                    "description": "Basic subscription plan",
                    "active": True,
                    "metadata": {"features": "limited"},
                },
            ],
            "has_more": False,
            "url": "/v1/products",
        }

    def list_payments(
        self,
        access_token: str,
        limit: int = 30,
        customer: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """Mock list payments method"""
        if not access_token:
            raise Exception("Authentication required")

        payments = self.mock_payments.copy()
        if customer:
            payments["data"] = [
                p for p in payments["data"] if p.get("customer") == customer
            ]
        if status:
            payments["data"] = [
                p for p in payments["data"] if p.get("status") == status
            ]

        payments["data"] = payments["data"][:limit]
        return payments

    def get_payment(self, access_token: str, payment_id: str):
        """Mock get payment method"""
        if not access_token:
            raise Exception("Authentication required")

        payment = next(
            (p for p in self.mock_payments["data"] if p["id"] == payment_id), None
        )
        if not payment:
            raise Exception(f"Payment {payment_id} not found")
        return payment

    def create_payment(
        self,
        access_token: str,
        amount: int,
        currency: str = "usd",
        customer: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Mock create payment method"""
        if not access_token:
            raise Exception("Authentication required")

        new_payment = {
            "id": f"ch_new_{int(datetime.now().timestamp())}",
            "object": "charge",
            "amount": amount,
            "currency": currency,
            "customer": customer,
            "description": description,
            "status": "succeeded",
            "created": int(datetime.now().timestamp()),
            "metadata": metadata or {},
        }
        self.mock_payments["data"].insert(0, new_payment)
        return new_payment

    def list_customers(
        self, access_token: str, limit: int = 30, email: Optional[str] = None
    ):
        """Mock list customers method"""
        if not access_token:
            raise Exception("Authentication required")

        customers = self.mock_customers.copy()
        if email:
            customers["data"] = [
                c for c in customers["data"] if c.get("email") == email
            ]

        customers["data"] = customers["data"][:limit]
        return customers

    def get_customer(self, access_token: str, customer_id: str):
        """Mock get customer method"""
        if not access_token:
            raise Exception("Authentication required")

        customer = next(
            (c for c in self.mock_customers["data"] if c["id"] == customer_id), None
        )
        if not customer:
            raise Exception(f"Customer {customer_id} not found")
        return customer

    def create_customer(
        self,
        access_token: str,
        email: str,
        name: Optional[str] = None,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Mock create customer method"""
        if not access_token:
            raise Exception("Authentication required")

        new_customer = {
            "id": f"cus_new_{int(datetime.now().timestamp())}",
            "object": "customer",
            "email": email,
            "name": name,
            "description": description,
            "created": int(datetime.now().timestamp()),
            "metadata": metadata or {},
        }
        self.mock_customers["data"].insert(0, new_customer)
        return new_customer

    def list_subscriptions(
        self,
        access_token: str,
        limit: int = 30,
        customer: Optional[str] = None,
        status: Optional[str] = None,
    ):
        """Mock list subscriptions method"""
        if not access_token:
            raise Exception("Authentication required")

        subscriptions = self.mock_subscriptions.copy()
        if customer:
            subscriptions["data"] = [
                s for s in subscriptions["data"] if s.get("customer") == customer
            ]
        if status:
            subscriptions["data"] = [
                s for s in subscriptions["data"] if s.get("status") == status
            ]

        subscriptions["data"] = subscriptions["data"][:limit]
        return subscriptions

    def get_subscription(self, access_token: str, subscription_id: str):
        """Mock get subscription method"""
        if not access_token:
            raise Exception("Authentication required")

        subscription = next(
            (s for s in self.mock_subscriptions["data"] if s["id"] == subscription_id),
            None,
        )
        if not subscription:
            raise Exception(f"Subscription {subscription_id} not found")
        return subscription

    def create_subscription(
        self,
        access_token: str,
        customer: str,
        items: List[Dict],
        metadata: Optional[Dict] = None,
    ):
        """Mock create subscription method"""
        if not access_token:
            raise Exception("Authentication required")

        new_subscription = {
            "id": f"sub_new_{int(datetime.now().timestamp())}",
            "object": "subscription",
            "customer": customer,
            "status": "active",
            "current_period_start": int(datetime.now().timestamp()),
            "current_period_end": int(
                (datetime.now() + timedelta(days=30)).timestamp()
            ),
            "items": {
                "data": [
                    {
                        "id": f"si_new_{int(datetime.now().timestamp())}",
                        "price": {
                            "id": items[0].get("price", "price_default"),
                            "product": "prod_default",
                        },
                    }
                ]
            },
            "metadata": metadata or {},
        }
        self.mock_subscriptions["data"].insert(0, new_subscription)
        return new_subscription

    def cancel_subscription(self, access_token: str, subscription_id: str):
        """Mock cancel subscription method"""
        if not access_token:
            raise Exception("Authentication required")

        subscription = next(
            (s for s in self.mock_subscriptions["data"] if s["id"] == subscription_id),
            None,
        )
        if not subscription:
            raise Exception(f"Subscription {subscription_id} not found")

        subscription["status"] = "canceled"
        subscription["canceled_at"] = int(datetime.now().timestamp())
        return subscription

    def list_products(self, access_token: str, limit: int = 30, active: bool = True):
        """Mock list products method"""
        if not access_token:
            raise Exception("Authentication required")

        products = self.mock_products.copy()
        if active:
            products["data"] = [
                p for p in products["data"] if p.get("active") == active
            ]

        products["data"] = products["data"][:limit]
        return products

    def get_product(self, access_token: str, product_id: str):
        """Mock get product method"""
        if not access_token:
            raise Exception("Authentication required")

        product = next(
            (p for p in self.mock_products["data"] if p["id"] == product_id), None
        )
        if not product:
            raise Exception(f"Product {product_id} not found")
        return product

    def create_product(
        self,
        access_token: str,
        name: str,
        description: Optional[str] = None,
        metadata: Optional[Dict] = None,
    ):
        """Mock create product method"""
        if not access_token:
            raise Exception("Authentication required")

        new_product = {
            "id": f"prod_new_{int(datetime.now().timestamp())}",
            "object": "product",
            "name": name,
            "description": description,
            "active": True,
            "created": int(datetime.now().timestamp()),
            "metadata": metadata or {},
        }
        self.mock_products["data"].insert(0, new_product)
        return new_product

    def get_balance(self, access_token: str):
        """Mock get balance method"""
        if not access_token:
            raise Exception("Authentication required")

        return {
            "object": "balance",
            "available": [{"amount": 100000, "currency": "usd"}],
            "pending": [{"amount": 5000, "currency": "usd"}],
        }

    def get_account(self, access_token: str):
        """Mock get account method"""
        if not access_token:
            raise Exception("Authentication required")

        return {
            "id": "acct_test123",
            "object": "account",
            "business_type": "company",
            "country": "US",
            "default_currency": "usd",
            "details_submitted": True,
            "email": "business@example.com",
            "type": "standard",
        }

    def health_check(self, access_token: str):
        """Mock health check method"""
        return {
            "status": "healthy",
            "timestamp": datetime.utcnow().isoformat(),
            "response_time": "fast",
            "api_version": "2023-10-16",
        }


class StripeIntegrationTest:
    """Enhanced test class for Stripe integration functionality with mock data"""

    def __init__(self):
        self.test_results = []
        self.access_token = "mock_access_token_12345"
        self.mock_service = MockStripeService()

    def log_test(self, test_name: str, success: bool, details: str = ""):
        """Log test result"""
        status = "✅ PASS" if success else "❌ FAIL"
        result = {
            "test": test_name,
            "status": status,
            "details": details,
            "timestamp": datetime.now().isoformat(),
        }
        self.test_results.append(result)
        print(f"{status} {test_name}")
        if details:
            print(f"   Details: {details}")

    async def test_health_check(self):
        """Test Stripe health check endpoint"""
        try:
            result = self.mock_service.health_check(self.access_token)
            success = result.get("status") == "healthy"
            self.log_test("Health Check", success, f"Status: {result.get('status')}")
            return success
        except Exception as e:
            self.log_test("Health Check", False, f"Error: {str(e)}")
            return False

    async def test_list_payments(self):
        """Test listing Stripe payments with mock data"""
        try:
            result = self.mock_service.list_payments(self.access_token, limit=5)
            success = isinstance(result, dict) and "data" in result
            payment_count = len(result.get("data", []))
            self.log_test(
                "List Payments",
                success,
                f"Retrieved {payment_count} payments with mock data",
            )
            return success
        except Exception as e:
            self.log_test("List Payments", False, f"Error: {str(e)}")
            return False

    async def test_get_payment(self):
        """Test getting specific payment with mock data"""
        try:
            payment_id = "ch_test123"
            result = self.mock_service.get_payment(self.access_token, payment_id)
            success = isinstance(result, dict) and result.get("id") == payment_id
            self.log_test(
                "Get Payment",
                success,
                f"Retrieved payment: {result.get('description', 'N/A')}",
            )
            return success
        except Exception as e:
            self.log_test("Get Payment", False, f"Error: {str(e)}")
            return False

    async def test_create_payment(self):
        """Test creating a new payment with mock data"""
        try:
            result = self.mock_service.create_payment(
                self.access_token,
                amount=2500,
                currency="usd",
                customer="cus_test123",
                description="Test payment creation",
            )
            success = isinstance(result, dict) and result.get("amount") == 2500
            self.log_test(
                "Create Payment",
                success,
                f"Created payment: ${result.get('amount', 0) / 100:.2f} {result.get('currency')}",
            )
            return success
        except Exception as e:
            self.log_test("Create Payment", False, f"Error: {str(e)}")
            return False

    async def test_list_customers(self):
        """Test listing Stripe customers with mock data"""
        try:
            result = self.mock_service.list_customers(self.access_token, limit=5)
            success = isinstance(result, dict) and "data" in result
            customer_count = len(result.get("data", []))
            self.log_test(
                "List Customers",
                success,
                f"Retrieved {customer_count} customers with mock data",
            )
            return success
        except Exception as e:
            self.log_test("List Customers", False, f"Error: {str(e)}")
            return False

    async def test_get_customer(self):
        """Test getting specific customer with mock data"""
        try:
            customer_id = "cus_test123"
            result = self.mock_service.get_customer(self.access_token, customer_id)
            success = isinstance(result, dict) and result.get("id") == customer_id
            self.log_test(
                "Get Customer",
                success,
                f"Retrieved customer: {result.get('name', 'N/A')}",
            )
            return success
        except Exception as e:
            self.log_test("Get Customer", False, f"Error: {str(e)}")
            return False

    async def test_create_customer(self):
        """Test creating a new customer with mock data"""
        try:
            result = self.mock_service.create_customer(
                self.access_token,
                email="newcustomer@example.com",
                name="New Customer",
                description="Test customer creation",
            )
            success = (
                isinstance(result, dict)
                and result.get("email") == "newcustomer@example.com"
            )
            self.log_test(
                "Create Customer",
                success,
                f"Created customer: {result.get('name')} ({result.get('email')})",
            )
            return success
        except Exception as e:
            self.log_test("Create Customer", False, f"Error: {str(e)}")
            return False

    async def test_list_subscriptions(self):
        """Test listing Stripe subscriptions with mock data"""
        try:
            result = self.mock_service.list_subscriptions(self.access_token, limit=5)
            success = isinstance(result, dict) and "data" in result
            subscription_count = len(result.get("data", []))
            self.log_test(
                "List Subscriptions",
                success,
                f"Retrieved {subscription_count} subscriptions with mock data",
            )
            return success
        except Exception as e:
            self.log_test("List Subscriptions", False, f"Error: {str(e)}")
            return False

    async def test_get_subscription(self):
        """Test getting specific subscription with mock data"""
        try:
            subscription_id = "sub_test123"
            result = self.mock_service.get_subscription(
                self.access_token, subscription_id
            )
            success = isinstance(result, dict) and result.get("id") == subscription_id
            self.log_test(
                "Get Subscription",
                success,
                f"Retrieved subscription: {result.get('status', 'N/A')}",
            )
            return success
        except Exception as e:
            self.log_test("Get Subscription", False, f"Error: {str(e)}")
            return False

    async def test_create_subscription(self):
        """Test creating a new subscription with mock data"""
        try:
            result = self.mock_service.create_subscription(
                self.access_token,
                customer="cus_test123",
                items=[{"price": "price_test123", "quantity": 1}],
                metadata={"plan": "premium"},
            )
            success = isinstance(result, dict) and result.get("status") == "active"
            self.log_test(
                "Create Subscription",
                success,
                f"Created subscription: {result.get('status')} status",
            )
            return success
        except Exception as e:
            self.log_test("Create Subscription", False, f"Error: {str(e)}")
            return False

    async def test_cancel_subscription(self):
        """Test canceling a subscription with mock data"""
        try:
            subscription_id = "sub_test123"
            result = self.mock_service.cancel_subscription(
                self.access_token, subscription_id
            )
            success = isinstance(result, dict) and result.get("status") == "canceled"
            self.log_test(
                "Cancel Subscription",
                success,
                f"Cancelled subscription: {result.get('status')} status",
            )
            return success
        except Exception as e:
            self.log_test("Cancel Subscription", False, f"Error: {str(e)}")
            return False

    async def test_list_products(self):
        """Test listing Stripe products with mock data"""
        try:
            result = self.mock_service.list_products(self.access_token, limit=5)
            success = isinstance(result, dict) and "data" in result
            product_count = len(result.get("data", []))
            self.log_test(
                "List Products",
                success,
                f"Retrieved {product_count} products with mock data",
            )
            return success
        except Exception as e:
            self.log_test("List Products", False, f"Error: {str(e)}")
            return False

    async def test_get_product(self):
        """Test getting specific product with mock data"""
        try:
            product_id = "prod_test123"
            result = self.mock_service.get_product(self.access_token, product_id)
            success = isinstance(result, dict) and result.get("id") == product_id
            self.log_test(
                "Get Product",
                success,
                f"Retrieved product: {result.get('name', 'N/A')}",
            )
            return success
        except Exception as e:
            self.log_test("Get Product", False, f"Error: {str(e)}")
            return False

    async def test_create_product(self):
        """Test creating a new product with mock data"""
        try:
            result = self.mock_service.create_product(
                self.access_token,
                name="Enterprise Plan",
                description="Enterprise subscription plan",
                metadata={"features": "enterprise"},
            )
            success = (
                isinstance(result, dict) and result.get("name") == "Enterprise Plan"
            )
            self.log_test(
                "Create Product",
                success,
                f"Created product: {result.get('name')}",
            )
            return success
        except Exception as e:
            self.log_test("Create Product", False, f"Error: {str(e)}")
            return False

    async def test_get_balance(self):
        """Test getting account balance with mock data"""
        try:
            result = self.mock_service.get_balance(self.access_token)
            success = isinstance(result, dict) and "available" in result
            available_balance = result.get("available", [{}])[0].get("amount", 0)
            self.log_test(
                "Get Balance",
                success,
                f"Available balance: ${available_balance / 100:.2f}",
            )
            return success
        except Exception as e:
            self.log_test("Get Balance", False, f"Error: {str(e)}")
            return False

    async def test_get_account(self):
        """Test getting account information with mock data"""
        try:
            result = self.mock_service.get_account(self.access_token)
            success = isinstance(result, dict) and result.get("id") == "acct_test123"
            self.log_test(
                "Get Account",
                success,
                f"Account type: {result.get('type', 'N/A')}",
            )
            return success
        except Exception as e:
            self.log_test("Get Account", False, f"Error: {str(e)}")
            return False

    async def test_error_handling(self):
        """Test error handling with invalid access token"""
        try:
            # Test with invalid token
            self.mock_service.get_customer("", "cus_test123")
            self.log_test(
                "Error Handling", False, "Should have raised authentication error"
            )
            return False
        except Exception as e:
            success = "Authentication required" in str(e)
            self.log_test(
                "Error Handling",
                success,
                f"Properly handled authentication error: {str(e)}",
            )
            return success

    async def test_filtering_functionality(self):
        """Test filtering functionality with mock data"""
        try:
            # Test customer filtering by email
            result = self.mock_service.list_customers(
                self.access_token, email="customer1@example.com"
            )
            success = len(result.get("data", [])) == 1
            self.log_test(
                "Filtering Functionality",
                success,
                f"Filtered customers by email: {len(result.get('data', []))} found",
            )
            return success
        except Exception as e:
            self.log_test("Filtering Functionality", False, f"Error: {str(e)}")
            return False

    async def test_stripe_service_methods(self):
        """Test direct Stripe service methods"""
        try:
            # Test service initialization and basic methods
            service_available = stripe_service is not None
            api_base_url = stripe_service.api_base_url if stripe_service else None

            overall_success = (
                service_available and api_base_url == "https://api.stripe.com/v1"
            )
            self.log_test(
                "Stripe Service Methods",
                overall_success,
                f"Service available: {service_available}, API URL: {api_base_url}",
            )
            return overall_success
        except Exception as e:
            self.log_test("Stripe Service Methods", False, f"Error: {str(e)}")
            return False

    async def run_all_tests(self):
        """Run all Stripe integration tests"""
        print("🧪 Starting Enhanced Stripe Integration Tests...")
        print("=" * 50)

        if not STRIPE_AVAILABLE:
            print("❌ Stripe integration is not available")
            return False

        # Run all test methods
        test_methods = [
            self.test_health_check,
            self.test_list_payments,
            self.test_get_payment,
            self.test_create_payment,
            self.test_list_customers,
            self.test_get_customer,
            self.test_create_customer,
            self.test_list_subscriptions,
            self.test_get_subscription,
            self.test_create_subscription,
            self.test_cancel_subscription,
            self.test_list_products,
            self.test_get_product,
            self.test_create_product,
            self.test_get_balance,
            self.test_get_account,
            self.test_error_handling,
            self.test_filtering_functionality,
            self.test_stripe_service_methods,
        ]

        for test_method in test_methods:
            await test_method()

        # Generate summary
        print("\n" + "=" * 50)
        print("📊 Test Summary")
        print("=" * 50)

        passed = sum(1 for result in self.test_results if "✅" in result["status"])
        total = len(self.test_results)

        print(f"Tests Passed: {passed}/{total}")
        print(f"Success Rate: {(passed / total) * 100:.1f}%")

        # Save detailed results
        self.save_test_results()

        return passed == total

    def save_test_results(self):
        """Save test results to JSON file"""
        results_file = "stripe_integration_test_results.json"
        results_data = {
            "test_run": {
                "timestamp": datetime.now().isoformat(),
                "total_tests": len(self.test_results),
                "passed_tests": sum(
                    1 for r in self.test_results if "✅" in r["status"]
                ),
                "failed_tests": sum(
                    1 for r in self.test_results if "❌" in r["status"]
                ),
            },
            "results": self.test_results,
        }

        with open(results_file, "w") as f:
            json.dump(results_data, f, indent=2)

        print(f"📄 Detailed results saved to: {results_file}")


async def main():
    """Main test execution function"""
    tester = StripeIntegrationTest()
    success = await tester.run_all_tests()

    if success:
        print("\n🎉 All Stripe integration tests passed!")
        return 0
    else:
        print("\n⚠️ Some Stripe integration tests failed. Check the results above.")
        return 1


if __name__ == "__main__":
    exit_code = asyncio.run(main())
    sys.exit(exit_code)
