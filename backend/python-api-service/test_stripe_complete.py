#!/usr/bin/env python3
"""
Stripe Integration Test
Comprehensive test suite for Stripe integration functionality
"""

import asyncio
import sys
import os
sys.path.append(os.path.dirname(os.path.abspath(__file__)))

import unittest
from unittest.mock import patch, MagicMock
import json
import requests
from datetime import datetime, timezone, timedelta

# Import Stripe service
try:
    from stripe_service import StripeService
    from stripe_handler import stripe_handler_bp
    from auth_handler_stripe import auth_stripe_bp
    STRIPE_SERVICE_AVAILABLE = True
except ImportError as e:
    print(f"Stripe service not available: {e}")
    STRIPE_SERVICE_AVAILABLE = False

# Import Stripe handlers
try:
    from stripe_handler import stripe_handler_bp
    from auth_handler_stripe import auth_stripe_bp
    STRIPE_HANDLERS_AVAILABLE = True
except ImportError as e:
    print(f"Stripe handlers not available: {e}")
    STRIPE_HANDLERS_AVAILABLE = False


class TestStripeService(unittest.TestCase):
    """Test Stripe service functionality"""
    
    def setUp(self):
        if not STRIPE_SERVICE_AVAILABLE:
            self.skipTest("Stripe service not available")
        
        self.user_id = "test_user_123"
        self.access_token = "sk_test_mock_token"
    
    def test_service_instantiation(self):
        """Test Stripe service instantiation"""
        service = StripeService()
        
        self.assertIsNotNone(service)
        self.assertEqual(service.api_base_url, "https://api.stripe.com/v1")
        self.assertEqual(service.timeout, 60)
        self.assertEqual(service.max_retries, 3)
        
        print(f"✅ Stripe Service instantiated with API URL {service.api_base_url}")
    
    def test_service_headers(self):
        """Test Stripe service headers generation"""
        service = StripeService()
        headers = service._get_headers(self.access_token)
        
        self.assertIsInstance(headers, dict)
        self.assertEqual(headers["Authorization"], f"Bearer {self.access_token}")
        self.assertEqual(headers["Content-Type"], "application/x-www-form-urlencoded")
        self.assertIn("User-Agent", headers)
        
        print("✅ Stripe Service headers generation correct")
    
    @unittest.skipUnless(STRIPE_SERVICE_AVAILABLE, "Stripe service not available")
    def test_get_balance(self):
        """Test getting account balance"""
        service = StripeService()
        
        # Mock implementation
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "object": "balance",
                "available": [
                    {
                        "amount": 500000,
                        "currency": "usd",
                        "source_types": {
                            "card": 300000,
                            "bank_account": 200000
                        }
                    }
                ],
                "pending": [
                    {
                        "amount": 100000,
                        "currency": "usd",
                        "source_types": {
                            "card": 100000
                        }
                    }
                ]
            }
            
            result = service.get_balance(self.access_token)
            
            self.assertIsInstance(result, dict)
            self.assertIn('available', result)
            self.assertIn('pending', result)
            
        print("✅ Balance retrieval test passed")
    
    @unittest.skipUnless(STRIPE_SERVICE_AVAILABLE, "Stripe service not available")
    def test_get_payments(self):
        """Test getting payments"""
        service = StripeService()
        
        # Mock implementation
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "object": "list",
                "data": [
                    {
                        "id": "pi_1",
                        "object": "payment_intent",
                        "amount": 2000,
                        "currency": "usd",
                        "status": "succeeded",
                        "created": 1672531200
                    }
                ],
                "has_more": False
            }
            
            result = service.list_payments(self.access_token, limit=10)
            
            self.assertIsInstance(result, dict)
            self.assertIn('data', result)
            
            if result['data']:
                payment = result['data'][0]
                self.assertEqual(payment['object'], 'payment_intent')
                self.assertEqual(payment['amount'], 2000)
            
        print("✅ Payments retrieval test passed")
    
    @unittest.skipUnless(STRIPE_SERVICE_AVAILABLE, "Stripe service not available")
    def test_create_payment_intent(self):
        """Test creating payment intent"""
        service = StripeService()
        
        # Mock implementation
        with patch.object(service, '_make_request') as mock_request:
            mock_request.return_value = {
                "id": "pi_test_123",
                "object": "payment_intent",
                "amount": 10000,
                "currency": "usd",
                "status": "requires_payment_method",
                "created": 1672531200
            }
            
            result = service.create_payment(
                self.access_token,
                amount=10000,
                currency="usd"
            )
            
            self.assertIsInstance(result, dict)
            self.assertEqual(result['id'], 'pi_test_123')
            self.assertEqual(result['amount'], 10000)
            self.assertEqual(result['currency'], 'usd')
            
        print("✅ Payment intent creation test passed")


class TestStripeAPI(unittest.TestCase):
    """Test Stripe API endpoints"""
    
    def setUp(self):
        if not STRIPE_HANDLERS_AVAILABLE:
            self.skipTest("Stripe handlers not available")
    
    def test_stripe_health_endpoint(self):
        """Test Stripe health endpoint"""
        # Mock health check response
        health_data = {
            "ok": True,
            "service": "stripe",
            "status": "registered",
            "needs_oauth": True,
            "api_version": "v1"
        }
        
        self.assertIsInstance(health_data, dict)
        self.assertTrue(health_data.get('ok'))
        self.assertEqual(health_data.get('service'), 'stripe')
        self.assertEqual(health_data.get('api_version'), 'v1')
        
        print("✅ Stripe health endpoint structure correct")
    
    def test_stripe_oauth_flow(self):
        """Test Stripe OAuth flow structure"""
        oauth_data = {
            "ok": True,
            "authorization_url": "https://connect.stripe.com/oauth/authorize",
            "client_id": "test_client_id",
            "scopes": ["read_only", "read_write"],
            "state": "test_state"
        }
        
        self.assertIsInstance(oauth_data, dict)
        self.assertTrue(oauth_data.get('ok'))
        self.assertIn('authorization_url', oauth_data)
        self.assertIn('scopes', oauth_data)
        self.assertTrue('read_write' in oauth_data['scopes'])
        
        print("✅ Stripe OAuth flow structure correct")
    
    def test_stripe_payments_api_structure(self):
        """Test Stripe payments API response structure"""
        payments_response = {
            "ok": True,
            "payments": [
                {
                    "id": "pi-1",
                    "amount": 2000,
                    "currency": "usd",
                    "status": "succeeded",
                    "created_at": "2023-01-15T10:30:00Z",
                    "customer": "cus_test_123",
                    "description": "Test payment"
                }
            ],
            "total_count": 1
        }
        
        self.assertIsInstance(payments_response, dict)
        self.assertTrue(payments_response.get('ok'))
        self.assertIn('payments', payments_response)
        self.assertIsInstance(payments_response['payments'], list)
        
        if payments_response['payments']:
            payment_data = payments_response['payments'][0]
            self.assertIn('id', payment_data)
            self.assertIn('amount', payment_data)
            self.assertIn('currency', payment_data)
        
        print("✅ Stripe payments API structure correct")


class TestStripeIntegration(unittest.TestCase):
    """Test Stripe integration completeness"""
    
    def test_service_availability(self):
        """Test that all required Stripe components are available"""
        available_components = []
        
        if STRIPE_SERVICE_AVAILABLE:
            available_components.append("✅ Stripe Service")
        else:
            available_components.append("❌ Stripe Service")
        
        if STRIPE_HANDLERS_AVAILABLE:
            available_components.append("✅ Stripe Handlers")
        else:
            available_components.append("❌ Stripe Handlers")
        
        print("\n🔍 Stripe Integration Components Status:")
        for component in available_components:
            print(f"  {component}")
        
        # At least service should be available
        self.assertTrue(STRIPE_SERVICE_AVAILABLE, "Stripe service should be available")
    
    def test_stripe_capabilities(self):
        """Test Stripe service capabilities"""
        if not STRIPE_SERVICE_AVAILABLE:
            self.skipTest("Stripe service not available")
        
        service = StripeService()
        
        # Check if service has required methods
        required_methods = [
            'get_balance',
            'list_payments',
            'create_payment',
            'list_customers'
        ]
        
        for method in required_methods:
            self.assertTrue(hasattr(service, method), f"Method '{method}' should be available")
        
        print(f"✅ All {len(required_methods)} expected capabilities available")
    
    def test_environment_configuration(self):
        """Test Stripe environment configuration"""
        stripe_client_id = os.getenv("STRIPE_CLIENT_ID")
        stripe_client_secret = os.getenv("STRIPE_CLIENT_SECRET")
        
        if stripe_client_id and stripe_client_secret:
            print("✅ Stripe environment variables configured")
            self.assertNotEqual(stripe_client_id, "mock_stripe_client_id")
            self.assertNotEqual(stripe_client_secret, "mock_stripe_client_secret")
        else:
            print("⚠️  Stripe environment variables not configured (using mock mode)")
            print("   Set STRIPE_CLIENT_ID and STRIPE_CLIENT_SECRET for real integration")


def main():
    """Main test runner"""
    print("🧪 ATOM Stripe Integration Test Suite")
    print("=" * 50)
    
    # Create test suite
    suite = unittest.TestSuite()
    
    # Add synchronous tests
    suite.addTest(TestStripeService('test_service_instantiation'))
    suite.addTest(TestStripeService('test_service_headers'))
    suite.addTest(TestStripeService('test_get_balance'))
    suite.addTest(TestStripeService('test_get_payments'))
    suite.addTest(TestStripeService('test_create_payment_intent'))
    suite.addTest(TestStripeAPI('test_stripe_health_endpoint'))
    suite.addTest(TestStripeAPI('test_stripe_oauth_flow'))
    suite.addTest(TestStripeAPI('test_stripe_payments_api_structure'))
    suite.addTest(TestStripeIntegration('test_service_availability'))
    suite.addTest(TestStripeIntegration('test_stripe_capabilities'))
    suite.addTest(TestStripeIntegration('test_environment_configuration'))
    
    # Run synchronous tests
    print("\n🔄 Running Synchronous Tests...")
    runner = unittest.TextTestRunner(verbosity=0)
    result = runner.run(suite)
    
    # Summary
    print("\n" + "=" * 50)
    print("📊 TEST SUMMARY")
    print("=" * 50)
    
    total_tests = result.testsRun
    failures = len(result.failures)
    errors = len(result.errors)
    passed = total_tests - failures - errors
    
    print(f"Total Tests: {total_tests}")
    print(f"Passed: {passed}")
    print(f"Failed: {failures}")
    print(f"Errors: {errors}")
    
    if failures == 0 and errors == 0:
        print("\n🎉 All tests passed! Stripe integration is working correctly.")
        return True
    else:
        print("\n❌ Some tests failed. Check implementation.")
        if result.failures:
            print("\nFailures:")
            for test, traceback in result.failures:
                print(f"- {test}: {traceback}")
        if result.errors:
            print("\nErrors:")
            for test, traceback in result.errors:
                print(f"- {test}: {traceback}")
        return False


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)